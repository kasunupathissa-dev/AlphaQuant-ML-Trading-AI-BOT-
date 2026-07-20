import sqlite3
import pandas as pd
import numpy as np

DB_NAME = "alphaquant_ml_v4.db"

class InstitutionalFeatureStore:
    def __init__(self):
        print("==================================================")
        print("  ALPHAQUANT V4.3: INSTITUTIONAL FEATURE ENGINE   ")
        print("==================================================")

    # --- PURE PANDAS MATH FUNCTIONS (NO EXTERNAL DEPENDENCIES) ---
    def calculate_ema(self, series, span):
        return series.ewm(span=span, adjust=False).mean()

    def calculate_atr(self, df, period=14):
        high_low = df['high'] - df['low']
        high_close = np.abs(df['high'] - df['close'].shift())
        low_close = np.abs(df['low'] - df['close'].shift())
        ranges = pd.concat([high_low, high_close, low_close], axis=1)
        true_range = np.max(ranges, axis=1)
        return true_range.rolling(window=period).mean()

    def calculate_choppiness_index(self, df, period=14):
        """ Proxy for Hurst Exponent. High = Ranging, Low = Trending """
        atr_1 = self.calculate_atr(df, 1)
        atr_sum = atr_1.rolling(window=period).sum()
        high_max = df['high'].rolling(window=period).max()
        low_min = df['low'].rolling(window=period).min()
        range_hl = np.maximum(high_max - low_min, 1e-8)
        return 100 * np.log10(atr_sum / range_hl) / np.log10(period)

    def calculate_zscore(self, series, period=30):
        """ Calculates rolling Z-Score for anomaly/drift detection """
        mean = series.rolling(window=period).mean()
        std = series.rolling(window=period).std()
        return np.where(std > 1e-8, (series - mean) / std, 0.0)

    def calculate_bb_width(self, series, period=20, std_dev=2):
        sma = series.rolling(window=period).mean()
        std = series.rolling(window=period).std()
        return ((sma + (std * std_dev)) - (sma - (std * std_dev))) / sma
        
    def calculate_adx(self, df, period=14):
        """ Average Directional Index: Measures absolute trend strength """
        plus_dm = df['high'].diff()
        minus_dm = df['low'].diff(-1)
        
        plus_dm = np.where((plus_dm > minus_dm) & (plus_dm > 0), plus_dm, 0.0)
        minus_dm = np.where((minus_dm > plus_dm) & (minus_dm > 0), minus_dm, 0.0)
        
        tr = self.calculate_atr(df, 1)
        
        plus_di = 100 * (pd.Series(plus_dm).ewm(alpha=1/period, adjust=False).mean() / tr.ewm(alpha=1/period, adjust=False).mean())
        minus_di = 100 * (pd.Series(minus_dm).ewm(alpha=1/period, adjust=False).mean() / tr.ewm(alpha=1/period, adjust=False).mean())
        
        dx = 100 * np.abs(plus_di - minus_di) / (plus_di + minus_di + 1e-8)
        adx = dx.ewm(alpha=1/period, adjust=False).mean()
        return adx

    def calculate_features(self, df):
        features = df.copy()

        # 1. Trend & Distance Features
        features['ema_20'] = self.calculate_ema(features['close'], 20)
        features['ema_50'] = self.calculate_ema(features['close'], 50)
        features['ema_200'] = self.calculate_ema(features['close'], 200)
        
        features['dist_ema_20'] = (features['close'] - features['ema_20']) / features['ema_20']
        features['dist_ema_50'] = (features['close'] - features['ema_50']) / features['ema_50']
        features['dist_ema_200'] = (features['close'] - features['ema_200']) / features['ema_200']

        # 2. Base Volatility
        features['atr'] = self.calculate_atr(features, 14)
        features['atr_pct'] = features['atr'] / features['close']
        
        # 3. Drift & Anomaly Detection (Layer 3)
        features['volatility_zscore'] = self.calculate_zscore(features['atr_pct'], 30)
        features['volume_zscore'] = self.calculate_zscore(features['volume'], 30)
        
        # 4. Market Regime Classifiers (Layer 2)
        features['chop_index'] = self.calculate_choppiness_index(features, 14)
        features['adx_14'] = self.calculate_adx(features, 14)
        features['bb_width'] = self.calculate_bb_width(features['close'])

        # 5. Institutional Structure (FVGs)
        features['fvg_bull_gap'] = features['low'] - features['high'].shift(2)
        features['fvg_bear_gap'] = features['low'].shift(2) - features['high']
        features['fvg_bull_intensity'] = np.where(features['fvg_bull_gap'] > 0, features['fvg_bull_gap'] / features['atr'], 0)
        features['fvg_bear_intensity'] = np.where(features['fvg_bear_gap'] > 0, features['fvg_bear_gap'] / features['atr'], 0)

        # Cleanup Memory
        cols_to_drop = [
            'ema_20', 'ema_50', 'ema_200', 'atr', 'fvg_bull_gap', 'fvg_bear_gap'
        ]
        features.drop(columns=[c for c in cols_to_drop if c in features.columns], inplace=True, errors='ignore')
        features.dropna(inplace=True)

        return features

    def run(self):
        conn = sqlite3.connect(DB_NAME)
        assets_df = pd.read_sql_query("SELECT DISTINCT asset FROM market_data_1h", conn)
        assets = assets_df['asset'].tolist()

        if not assets:
            print("[ERROR] No data found. Please run data_ingestion.py first.")
            return

        cursor = conn.cursor()
        
        # Wipe old schema to upgrade to V4.3
        cursor.execute("DROP TABLE IF EXISTS feature_store")
        
        cursor.execute('''
        CREATE TABLE feature_store (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            asset TEXT NOT NULL,
            timestamp INTEGER NOT NULL,
            dist_ema_20 REAL,
            dist_ema_50 REAL,
            dist_ema_200 REAL,
            atr_pct REAL,
            volatility_zscore REAL,
            volume_zscore REAL,
            chop_index REAL,
            adx_14 REAL,
            bb_width REAL,
            fvg_bull_intensity REAL,
            fvg_bear_intensity REAL,
            target_label INTEGER,
            UNIQUE(asset, timestamp)
        )
        ''')
        conn.commit()

        for asset in assets:
            print(f"[PROCESS] Calculating V4.3 Regime & Drift Features for {asset}...")
            
            query = f"SELECT timestamp, open, high, low, close, volume FROM market_data_1h WHERE asset = '{asset}' ORDER BY timestamp ASC"
            df = pd.read_sql_query(query, conn)
            
            if len(df) < 250: continue

            feature_df = self.calculate_features(df)
            feature_df['asset'] = asset
            
            ml_columns = [
                'asset', 'timestamp', 'dist_ema_20', 'dist_ema_50', 'dist_ema_200',
                'atr_pct', 'volatility_zscore', 'volume_zscore', 'chop_index', 'adx_14', 
                'bb_width', 'fvg_bull_intensity', 'fvg_bear_intensity'
            ]
            
            insert_df = feature_df[ml_columns]
            insert_df.to_sql('temp_adv_features', conn, if_exists='replace', index=False)
            
            cursor.execute('''
                INSERT INTO feature_store 
                (asset, timestamp, dist_ema_20, dist_ema_50, dist_ema_200, atr_pct, volatility_zscore, volume_zscore, chop_index, adx_14, bb_width, fvg_bull_intensity, fvg_bear_intensity)
                SELECT asset, timestamp, dist_ema_20, dist_ema_50, dist_ema_200, atr_pct, volatility_zscore, volume_zscore, chop_index, adx_14, bb_width, fvg_bull_intensity, fvg_bear_intensity
                FROM temp_adv_features
            ''')
            conn.commit()
            print(f"  [SUCCESS] Database populated with {len(insert_df)} institutional feature vectors.")

        conn.close()
        print("\n==================================================")
        print("[SYSTEM] High-Dimensional Feature Generation Complete.")
        print("==================================================")

if __name__ == "__main__":
    generator = InstitutionalFeatureStore()
    generator.run()