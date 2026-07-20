import ccxt
import sqlite3
import pandas as pd
import time
from datetime import datetime

DB_NAME = "alphaquant_ml_v4.db"

# 🟢 V4.3.2: Expanded to 10 highly liquid institutional assets
TARGET_ASSETS = [
    "BTC/USDT", "ETH/USDT", "SOL/USDT", "BNB/USDT", "ADA/USDT", 
    "XRP/USDT", "LINK/USDT", "AVAX/USDT", "DOGE/USDT", "DOT/USDT"
]

def fetch_and_store_historical_data():
    print("==================================================")
    print("  ALPHAQUANT V4.3.2: HISTORICAL DATA INGESTION    ")
    print("==================================================")
    
    exchange = ccxt.binance({
        'enableRateLimit': True,
        'options': {'defaultType': 'future'}
    })

    conn = sqlite3.connect(DB_NAME)
    LIMIT = 1500 

    for asset in TARGET_ASSETS:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] Fetching {LIMIT} hours of history for {asset}...")
        
        try:
            ohlcv = exchange.fetch_ohlcv(asset, "1h", limit=LIMIT)
            df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            df['asset'] = asset
            df['datetime'] = pd.to_datetime(df['timestamp'], unit='ms').dt.strftime('%Y-%m-%d %H:%M:%S')
            
            df = df[['asset', 'timestamp', 'datetime', 'open', 'high', 'low', 'close', 'volume']]
            
            df.to_sql('temp_market_data', conn, if_exists='replace', index=False)
            
            cursor = conn.cursor()
            # 🟢 V4.3.2: Make sure table exists for new deployments
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS market_data_1h (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                asset TEXT NOT NULL,
                timestamp INTEGER NOT NULL,
                datetime TEXT NOT NULL,
                open REAL,
                high REAL,
                low REAL,
                close REAL,
                volume REAL,
                UNIQUE(asset, timestamp)
            )
            ''')
            
            cursor.execute('''
                INSERT OR IGNORE INTO market_data_1h (asset, timestamp, datetime, open, high, low, close, volume)
                SELECT asset, timestamp, datetime, open, high, low, close, volume FROM temp_market_data
            ''')
            conn.commit()
            
            inserted_rows = cursor.rowcount
            print(f"[SUCCESS] {asset}: Saved {len(df)} candles to database. (New unique rows added: {inserted_rows})")
            
            time.sleep(1)
            
        except Exception as e:
            print(f"[ERROR] Failed to fetch data for {asset}: {e}")

    conn.close()
    print("==================================================")
    print("[SYSTEM] Data Ingestion Cycle Complete.")
    print("==================================================")

if __name__ == "__main__":
    fetch_and_store_historical_data()