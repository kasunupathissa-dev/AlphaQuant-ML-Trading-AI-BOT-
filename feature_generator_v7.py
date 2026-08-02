import pandas as pd
from sqlalchemy import text
import ccxt
import config

# 🟢 V7.0 Upgrade for V8 Shotgun Pipeline
from database_config import get_db_engine
from feature_library import calculate_features_for_shotgun, calculate_zscore

class V7_FeatureStore:
    def __init__(self):
        print("==================================================")
        print(f"  ALPHAQUANT: SHOTGUN FEATURE ENGINE ({config.TIMEFRAME}) ")
        print("==================================================")
        self.exchange = ccxt.binance({'enableRateLimit': True, 'options': {'defaultType': 'future'}})
        self.table_name_market = f"market_data_{config.TIMEFRAME}"
        self.table_name_features = f"feature_store_{config.TIMEFRAME}"

    def get_sentiment_features(self, asset, start_time):
        try:
            # Binance futures funding rates are updated every 8 hours, resample appropriately
            funding_history = self.exchange.fetch_funding_rate_history(asset, since=start_time, limit=1000)
            
            # Fetch OI for the active timeframe
            oi_tf = '15m' if config.TIMEFRAME == '15m' else '1h'
            oi_history = self.exchange.fetch_open_interest_history(asset, oi_tf, since=start_time, limit=1000)
            
            # Convert funding and Open Interest to DataFrames
            funding_list = []
            for f in funding_history:
                funding_list.append({'timestamp': f['timestamp'], 'fundingRate': f['fundingRate']})
            funding_df = pd.DataFrame(funding_list)
            
            oi_list = []
            for o in oi_history:
                oi_list.append({'timestamp': o['timestamp'], 'openInterestAmount': o['openInterestAmount']})
            oi_df = pd.DataFrame(oi_list)

            funding_df['timestamp'] = pd.to_datetime(funding_df['timestamp'], unit='ms')
            oi_df['timestamp'] = pd.to_datetime(oi_df['timestamp'], unit='ms')

            resample_rule = '15min' if config.TIMEFRAME == '15m' else '1h'
            funding_df = funding_df.set_index('timestamp').resample(resample_rule).last()
            oi_df = oi_df.set_index('timestamp').resample(resample_rule).last()

            # Z-score lookback period: 30 for 1H, 120 for 15M (matches ~30 hours)
            z_period = 120 if config.TIMEFRAME == "15m" else 30
            funding_df['funding_rate_zscore'] = calculate_zscore(funding_df['fundingRate'], z_period)
            oi_df['oi_zscore'] = calculate_zscore(oi_df['openInterestAmount'], z_period)
            
            return funding_df[['funding_rate_zscore']], oi_df[['oi_zscore']]
        except Exception as e:
            print(f"  [WARNING] Sentiment fetch failed for {asset}: {e}")
            return pd.DataFrame(columns=['funding_rate_zscore']), pd.DataFrame(columns=['oi_zscore'])

    def run(self):
        engine = get_db_engine()
        if engine is None: return

        with engine.connect() as connection:
            connection.execute(text(f"DROP TABLE IF EXISTS {self.table_name_features}"))
            connection.execute(text(f'''
            CREATE TABLE {self.table_name_features} (
                id INT AUTO_INCREMENT PRIMARY KEY, asset VARCHAR(20) NOT NULL, timestamp BIGINT NOT NULL,
                dist_ema_50 DOUBLE, dist_ema_200 DOUBLE, atr_pct DOUBLE, volume_zscore DOUBLE, adx_14 DOUBLE, bb_width DOUBLE,
                funding_rate_zscore DOUBLE, oi_zscore DOUBLE,
                rsi_14 DOUBLE, macd_hist DOUBLE, supertrend_direction DOUBLE, primary_signal INT,
                target_label INT,
                UNIQUE INDEX idx_asset_timestamp (asset, timestamp)
            )'''))
            connection.commit()

            assets = pd.read_sql_query(f"SELECT DISTINCT asset FROM {self.table_name_market}", connection)['asset'].tolist()

            for asset in assets:
                print(f"[PROCESS] Generating Shotgun Features for {asset} ({config.TIMEFRAME})...")
                df = pd.read_sql(f"SELECT * FROM {self.table_name_market} WHERE asset = '{asset}' ORDER BY timestamp ASC", connection)
                
                # We need at least double the slow EMA period to stabilize indicators (800 * 2 = 1600 candles on 15m)
                min_len = 1600 if config.TIMEFRAME == "15m" else 250
                if len(df) < min_len:
                    print(f"  [SKIP] Insufficient data ({len(df)} candles). Needs at least {min_len}.")
                    continue

                # Call the shotgun feature function
                feature_df = calculate_features_for_shotgun(df)
                
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
                    'funding_rate_zscore', 'oi_zscore', 'rsi_14', 'macd_hist', 'supertrend_direction', 'primary_signal'
                ]
                insert_df = final_df.reset_index()[columns_to_insert]

                insert_df.to_sql(self.table_name_features, connection, if_exists='append', index=False)
                print(f"  [SUCCESS] Populated database table {self.table_name_features} with {len(insert_df)} feature vectors.")
            
            connection.commit()

        print("\n==================================================")
        print(f"[SYSTEM] Shotgun Feature Generation Complete ({config.TIMEFRAME}).")
        print("==================================================")

if __name__ == "__main__":
    generator = V7_FeatureStore()
    generator.run()
