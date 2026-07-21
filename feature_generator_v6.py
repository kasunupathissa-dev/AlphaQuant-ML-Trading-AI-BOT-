import pandas as pd
from sqlalchemy import text
import ccxt

# 🟢 V6.5 Upgrade: Use the centralized database and feature library
from database_config import get_db_engine
from feature_library import calculate_features_and_signals, calculate_zscore

class V6_5_FeatureStore:
    def __init__(self):
        print("==================================================")
        print("  ALPHAQUANT V6.5: REFACTORED FEATURE ENGINE    ")
        print("==================================================")
        self.exchange = ccxt.binance({'enableRateLimit': True, 'options': {'defaultType': 'future'}})

    def get_sentiment_features(self, asset, start_time):
        try:
            funding_history = self.exchange.fetch_funding_rate_history(asset, since=start_time, limit=1000)
            oi_history = self.exchange.fetch_open_interest_history(asset, '1h', since=start_time, limit=1000)
            
            funding_df = pd.DataFrame(funding_history)[['timestamp', 'fundingRate']]
            oi_df = pd.DataFrame(oi_history)[['timestamp', 'openInterestAmount']]

            funding_df['timestamp'] = pd.to_datetime(funding_df['timestamp'], unit='ms')
            oi_df['timestamp'] = pd.to_datetime(oi_df['timestamp'], unit='ms')

            funding_df = funding_df.set_index('timestamp').resample('1H').last()
            oi_df = oi_df.set_index('timestamp').resample('1H').last()

            funding_df['funding_rate_zscore'] = calculate_zscore(funding_df['fundingRate'])
            oi_df['oi_zscore'] = calculate_zscore(oi_df['openInterestAmount'])
            
            return funding_df[['funding_rate_zscore']], oi_df[['oi_zscore']]
        except Exception:
            return pd.DataFrame(columns=['funding_rate_zscore']), pd.DataFrame(columns=['oi_zscore'])

    def run(self):
        engine = get_db_engine()
        if engine is None: return

        with engine.connect() as connection:
            assets = pd.read_sql_query("SELECT DISTINCT asset FROM market_data_1h", connection)['asset'].tolist()

            connection.execute(text("DROP TABLE IF EXISTS feature_store"))
            connection.execute(text('''
            CREATE TABLE feature_store (
                id INT AUTO_INCREMENT PRIMARY KEY, asset VARCHAR(20) NOT NULL, timestamp BIGINT NOT NULL,
                dist_ema_50 DOUBLE, dist_ema_200 DOUBLE, atr_pct DOUBLE, volume_zscore DOUBLE, adx_14 DOUBLE, bb_width DOUBLE,
                funding_rate_zscore DOUBLE, oi_zscore DOUBLE,
                primary_trend_long INT, primary_trend_short INT,
                primary_breakout_long INT, primary_breakout_short INT,
                primary_reversion_long INT, primary_reversion_short INT,
                target_label_long INT, target_label_short INT,
                UNIQUE INDEX idx_asset_timestamp (asset, timestamp)
            )'''))
            connection.commit()

            for asset in assets:
                print(f"[PROCESS] Generating V6.5 Features for {asset}...")
                df = pd.read_sql(f"SELECT * FROM market_data_1h WHERE asset = '{asset}' ORDER BY timestamp ASC", connection)
                if len(df) < 250: continue

                # 🟢 V6.5 Refactor: Call the shared library function
                feature_df = calculate_features_and_signals(df)
                
                start_timestamp = df['timestamp'].min()
                funding_df, oi_df = self.get_sentiment_features(asset, start_timestamp)
                
                feature_df['datetime'] = pd.to_datetime(feature_df['timestamp'], unit='ms')
                feature_df = feature_df.set_index('datetime')
                
                final_df = feature_df.join(funding_df).join(oi_df)
                
                final_df['funding_rate_zscore'] = final_df['funding_rate_zscore'].fillna(0)
                final_df['oi_zscore'] = final_df['oi_zscore'].fillna(0)
                final_df.dropna(inplace=True)
                
                columns_to_insert = [
                    'asset', 'timestamp', 'dist_ema_50', 'dist_ema_200', 'atr_pct', 'volume_zscore', 'adx_14', 'bb_width',
                    'funding_rate_zscore', 'oi_zscore',
                    'primary_trend_long', 'primary_trend_short',
                    'primary_breakout_long', 'primary_breakout_short',
                    'primary_reversion_long', 'primary_reversion_short'
                ]
                insert_df = final_df.reset_index()[columns_to_insert]

                insert_df.to_sql('feature_store', connection, if_exists='append', index=False)
                print(f"  [SUCCESS] Populated database with {len(insert_df)} hardened feature vectors.")
            
            connection.commit()

        print("\n==================================================")
        print("[SYSTEM] V6.5 Feature Generation Complete.")
        print("==================================================")

if __name__ == "__main__":
    generator = V6_5_FeatureStore()
    generator.run()