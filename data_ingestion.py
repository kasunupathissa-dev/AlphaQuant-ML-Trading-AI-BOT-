import ccxt
import pandas as pd
import time
from datetime import datetime, timedelta, timezone
from sqlalchemy import text

# 🟢 V5.2 Upgrade: Use the centralized database configuration
from database_config import get_db_engine

TARGET_ASSETS = [
    "BTC/USDT", "ETH/USDT", "SOL/USDT", "BNB/USDT", "ADA/USDT", 
    "XRP/USDT", "LINK/USDT", "AVAX/USDT", "DOGE/USDT", "DOT/USDT"
]

def fetch_and_store_historical_data():
    print("==================================================")
    print("  ALPHAQUANT V5.2: ROBUST DATA INGESTION PIPELINE ")
    print("==================================================")
    
    engine = get_db_engine()
    if engine is None: return

    exchange = ccxt.binance({'enableRateLimit': True, 'options': {'defaultType': 'future'}})
    limit = 1000 

    for asset in TARGET_ASSETS:
        since = exchange.parse8601((datetime.now(timezone.utc) - timedelta(days=180)).isoformat())
        print(f"[{datetime.now().strftime('%H:%M:%S')}] Fetching maximum history for {asset}...")
        
        all_ohlcv = []
        try:
            while True:
                ohlcv = exchange.fetch_ohlcv(asset, "1h", since=since, limit=limit)
                if not ohlcv: break
                all_ohlcv.extend(ohlcv)
                since = ohlcv[-1][0] + 1

            if not all_ohlcv:
                print(f"  [INFO] No new data found for {asset}.")
                continue

            df = pd.DataFrame(all_ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            df.drop_duplicates(subset=['timestamp'], inplace=True)
            df['asset'] = asset
            df['datetime'] = pd.to_datetime(df['timestamp'], unit='ms')
            df = df[['asset', 'timestamp', 'datetime', 'open', 'high', 'low', 'close', 'volume']]
            
            with engine.connect() as connection:
                connection.execute(text('''
                CREATE TABLE IF NOT EXISTS market_data_1h (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    asset VARCHAR(20) NOT NULL,
                    timestamp BIGINT NOT NULL,
                    datetime DATETIME NOT NULL,
                    open DOUBLE, high DOUBLE, low DOUBLE, close DOUBLE, volume DOUBLE,
                    UNIQUE INDEX idx_asset_timestamp (asset, timestamp)
                )'''))
                
                df.to_sql('temp_market_data', connection, if_exists='replace', index=False)
                
                upsert_sql = """
                INSERT INTO market_data_1h (asset, timestamp, datetime, open, high, low, close, volume)
                SELECT asset, timestamp, datetime, open, high, low, close, volume FROM temp_market_data
                ON DUPLICATE KEY UPDATE
                    open = VALUES(open), high = VALUES(high), low = VALUES(low), 
                    close = VALUES(close), volume = VALUES(volume);
                """
                result = connection.execute(text(upsert_sql))
                connection.commit()
            
            print(f"[SUCCESS] {asset}: Synced {len(df)} total candles to MySQL.")
            
            # 🟢 V5.2: Post-Ingestion Verification Step
            verify_data_integrity(engine, asset)

            time.sleep(1)
            
        except Exception as e:
            print(f"[ERROR] Failed to sync data for {asset}: {e}")

    print("\n==================================================")
    print("[SYSTEM] V5.2 Data Ingestion Cycle Complete.")
    print("==================================================")

def verify_data_integrity(engine, asset):
    """
    Runs duplicate and gap checks on the ingested data for a specific asset.
    """
    with engine.connect() as connection:
        # 1. Duplicate Check
        dup_query = f"SELECT COUNT(*) FROM (SELECT COUNT(timestamp) as c FROM market_data_1h WHERE asset = '{asset}' GROUP BY timestamp HAVING c > 1) as duplicates;"
        duplicate_count = connection.execute(text(dup_query)).scalar()
        if duplicate_count > 0:
            print(f"  [WARNING] Found {duplicate_count} duplicate timestamps for {asset}.")
        else:
            print(f"  [OK] No duplicate timestamps found for {asset}.")

        # 2. Gap Check
        # Check for missing 1-hour intervals
        df = pd.read_sql(f"SELECT timestamp FROM market_data_1h WHERE asset = '{asset}' ORDER BY timestamp", connection)
        df['timestamp_dt'] = pd.to_datetime(df['timestamp'], unit='ms')
        time_diffs = df['timestamp_dt'].diff().dt.total_seconds().dropna()
        gaps = time_diffs[time_diffs > 3600] # 3600 seconds in an hour
        
        if not gaps.empty:
            print(f"  [WARNING] Found {len(gaps)} gaps in the time series for {asset}. Largest gap: {gaps.max()/3600:.1f} hours.")
        else:
            print(f"  [OK] Time series is continuous for {asset}.")

if __name__ == "__main__":
    fetch_and_store_historical_data()