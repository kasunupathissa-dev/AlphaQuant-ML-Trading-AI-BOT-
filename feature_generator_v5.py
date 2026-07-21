import pandas as pd
import numpy as np
from sqlalchemy import text

# 🟢 V5.1 Upgrade: Use the centralized database configuration
from database_config import get_db_engine

class MultiSignalFeatureStore:
    def __init__(self):
        print("==================================================")
        print("  ALPHAQUANT V5.1: MULTI-SIGNAL FEATURE ENGINE    ")
        print("==================================================")

    def calculate_ema(self, series, span):
        return series.ewm(span=span, adjust=False).mean()

    def calculate_atr(self, df, period=14):
        high_low = df['high'] - df['low']
        high_close = np.abs(df['high'] - df['close'].shift())
        low_close = np.abs(df['low'] - df['close'].shift())
        ranges = pd.concat([high_low, high_close, low_close], axis=1)
        true_range = np.max(ranges, axis=1)
        return true_range.rolling(window=period).mean()

    def calculate_zscore(self, series, period=30):
        mean = series.rolling(window=period).mean()
        std = series.rolling(window=period).std()
        return np.where(std > 1e-8, (series - mean) / std, 0)

    def calculate_bb_width(self, series, period=20):
        sma = series.rolling(window=period).mean()
        std = series.rolling(window=period).std()
        return ((sma + (std * 2)) - (sma - (std * 2))) / sma
        
    def calculate_adx(self, df, period=14):
        plus_dm = df['high'].diff()
        minus_dm = df['low'].diff(-1)
        plus_dm = np.where((plus_dm > minus_dm) & (plus_dm > 0), plus_dm, 0.0)
        minus_dm = np.where((minus_dm > plus_dm) & (minus_dm > 0), minus_dm, 0.0)
        tr = self.calculate_atr(df, 1)
        plus_di = 100 * (pd.Series(plus_dm).ewm(alpha=1/period, adjust=False).mean() / tr.ewm(alpha=1/period, adjust=False).mean())
        minus_di = 100 * (pd.Series(minus_dm).ewm(alpha=1/period, adjust=False).mean() / tr.ewm(alpha=1/period, adjust=False).mean())
        dx = 100 * np.abs(plus_di - minus_di) / (plus_di + minus_di + 1e-8)
        return dx.ewm(alpha=1/period, adjust=False).mean()

    def calculate_features(self, df):
        features = df.copy()

        # --- Base Features ---
        features['ema_50'] = self.calculate_ema(features['close'], 50)
        features['ema_200'] = self.calculate_ema(features['close'], 200)
        features['atr'] = self.calculate_atr(features, 14)
        features['bb_width'] = self.calculate_bb_width(features['close'])
        features['adx_14'] = self.calculate_adx(features, 14)
        features['volume_zscore'] = self.calculate_zscore(features['volume'], 30)
        
        # --- 🟢 V5.1: Primary Signal Generation ---
        
        # 1. Trend Continuation Signal
        features['prev_close'] = features['close'].shift(1)
        features['prev_ema_50'] = features['ema_50'].shift(1)
        features['primary_trend_long'] = np.where((features['prev_close'] <= features['prev_ema_50']) & (features['close'] > features['ema_50']) & (features['ema_50'] > features['ema_200']), 1, 0)
        features['primary_trend_short'] = np.where((features['prev_close'] >= features['prev_ema_50']) & (features['close'] < features['ema_50']) & (features['ema_50'] < features['ema_200']), 1, 0)

        # 2. Volatility Breakout Signal
        # A breakout occurs when BB Width is in the bottom 10th percentile (a squeeze) and price closes outside the bands
        bb_width_squeeze_threshold = features['bb_width'].quantile(0.10)
        is_in_squeeze = features['bb_width'].shift(1) < bb_width_squeeze_threshold
        sma_20 = features['close'].rolling(20).mean()
        std_20 = features['close'].rolling(20).std()
        upper_band = sma_20 + (std_20 * 2)
        lower_band = sma_20 - (std_20 * 2)
        features['primary_breakout_long'] = np.where(is_in_squeeze & (features['close'] > upper_band), 1, 0)
        features['primary_breakout_short'] = np.where(is_in_squeeze & (features['close'] < lower_band), 1, 0)

        # 3. Mean Reversion Signal
        # A reversion occurs when price is more than 3 standard deviations from its 200-period mean
        price_zscore = self.calculate_zscore(features['close'], 200)
        features['primary_reversion_long'] = np.where(price_zscore < -3.0, 1, 0)
        features['primary_reversion_short'] = np.where(price_zscore > 3.0, 1, 0)

        # --- Final Feature Vector ---
        features['dist_ema_50'] = (features['close'] - features['ema_50']) / features['ema_50']
        features['dist_ema_200'] = (features['close'] - features['ema_200']) / features['ema_200']
        features['atr_pct'] = features['atr'] / features['close']
        
        cols_to_drop = ['ema_50', 'ema_200', 'atr', 'prev_close', 'prev_ema_50']
        features.drop(columns=[c for c in cols_to_drop if c in features.columns], inplace=True, errors='ignore')
        features.dropna(inplace=True)
        return features

    def run(self):
        engine = get_db_engine()
        if engine is None: return

        with engine.connect() as connection:
            assets_df = pd.read_sql_query("SELECT DISTINCT asset FROM market_data_1h", connection)
            assets = assets_df['asset'].tolist()

            connection.execute(text("DROP TABLE IF EXISTS feature_store"))
            connection.execute(text('''
            CREATE TABLE feature_store (
                id INT AUTO_INCREMENT PRIMARY KEY,
                asset VARCHAR(20) NOT NULL,
                timestamp BIGINT NOT NULL,
                dist_ema_50 DOUBLE,
                dist_ema_200 DOUBLE,
                atr_pct DOUBLE,
                volume_zscore DOUBLE,
                adx_14 DOUBLE,
                bb_width DOUBLE,
                primary_trend_long INT, primary_trend_short INT,
                primary_breakout_long INT, primary_breakout_short INT,
                primary_reversion_long INT, primary_reversion_short INT,
                target_label_long INT, target_label_short INT,
                UNIQUE INDEX idx_asset_timestamp (asset, timestamp)
            )
            '''))
            connection.commit()

            for asset in assets:
                print(f"[PROCESS] Generating V5.1 Multi-Signal Features for {asset}...")
                query = f"SELECT * FROM market_data_1h WHERE asset = '{asset}' ORDER BY timestamp ASC"
                df = pd.read_sql(query, connection)
                if len(df) < 250: continue

                feature_df = self.calculate_features(df)
                feature_df['asset'] = asset
                
                insert_df = feature_df.drop(columns=['id', 'datetime', 'open', 'high', 'low', 'close', 'volume'])
                insert_df.to_sql('feature_store', connection, if_exists='append', index=False)
                print(f"  [SUCCESS] Populated database with {len(insert_df)} feature vectors.")
            
            connection.commit()

        print("\n==================================================")
        print("[SYSTEM] Multi-Signal Feature Generation Complete.")
        print("==================================================")

if __name__ == "__main__":
    generator = MultiSignalFeatureStore()
    generator.run()