import sqlite3
import pandas as pd
import numpy as np

DB_NAME = "alphaquant_ml_v4.db"

class AdvancedFeatureStore:
    def __init__(self):
        print("==================================================")
        print("  ALPHAQUANT V4.0.2: SQLITE FIX                   ")
        print("==================================================")

    def calculate_ema(self, series, span):
        return series.ewm(span=span, adjust=False).mean()

    def calculate_rsi(self, series, period=14):
        delta = series.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        return rsi

    def calculate_atr(self, df, period=14):
        high_low = df['high'] - df['low']
        high_close = np.abs(df['high'] - df['close'].shift())
        low_close = np.abs(df['low'] - df['close'].shift())
        ranges = pd.concat([high_low, high_close, low_close], axis=1)
        true_range = np.max(ranges, axis=1)
        return true_range.rolling(window=period).mean()

    def calculate_macd(self, series, fast=12, slow=26, signal=9):
        ema_fast = self.calculate_ema(series, fast)
        ema_slow = self.calculate_ema(series, slow)
        macd_line = ema_fast - ema_slow
        signal_line = self.calculate_ema(macd_line, signal)
        macd_hist = macd_line - signal_line
        return macd_hist

    def calculate_bb_width(self, series, period=20, std_dev=2):
        sma = series.rolling(window=period).mean()
        std = series.rolling(window=period).std()
        upper_band = sma + (std * std_dev)
        lower_band = sma - (std * std_dev)
        return (upper_band - lower_band) / sma

    def calculate_features(self, df):
        features = df.copy()

        features['ema_20'] = self.calculate_ema(features['close'], 20)
        features['ema_50'] = self.calculate_ema(features['close'], 50)
        features['ema_200'] = self.calculate_ema(features['close'], 200)
        
        features['dist_ema_20'] = (features['close'] - features['ema_20']) / features['ema_20']
        features['dist_ema_50'] = (features['close'] - features['ema_50']) / features['ema_50']
        features['dist_ema_200'] = (features['close'] - features['ema_200']) / features['ema_200']
        
        macd_hist = self.calculate_macd(features['close'])
        features['macd_hist_norm'] = macd_hist / features['close']
        
        rsi = self.calculate_rsi(features['close'], 14)
        features['rsi_norm'] = (rsi - 50) / 50

        features['atr'] = self.calculate_atr(features, 14)
        features['atr_pct'] = features['atr'] / features['close']
        
        features['bb_width'] = self.calculate_bb_width(features['close'])

        features['candle_range'] = features['high'] - features['low']
        features['buying_pressure_ratio'] = np.where(
            features['candle_range'] > 0, 
            (features['close'] - features['low']) / features['candle_range'], 
            0.5
        )
        features['bull_vol'] = features['volume'] * features['buying_pressure_ratio']
        features['bear_vol'] = features['volume'] * (1 - features['buying_pressure_ratio'])
        
        features['net_delta'] = features['bull_vol'] - features['bear_vol']
        features['cvd_24h'] = features['net_delta'].rolling(24).sum()
        features['vol_24h'] = features['volume'].rolling(24).sum()
        features['cvd_norm'] = np.where(features['vol_24h'] > 0, features['cvd_24h'] / features['vol_24h'], 0)

        features['fvg_bull_gap'] = features['low'] - features['high'].shift(2)
        features['fvg_bear_gap'] = features['low'].shift(2) - features['high']
        
        features['fvg_bull_intensity'] = np.where(features['fvg_bull_gap'] > 0, features['fvg_bull_gap'] / features['atr'], 0)
        features['fvg_bear_intensity'] = np.where(features['fvg_bear_gap'] > 0, features['fvg_bear_gap'] / features['atr'], 0)

        cols_to_drop = [
            'ema_20', 'ema_50', 'ema_200', 'atr', 'candle_range', 
            'buying_pressure_ratio', 'bull_vol', 'bear_vol', 'net_delta', 
            'cvd_24h', 'vol_24h', 'fvg_bull_gap', 'fvg_bear_gap'
        ]
        
        features.drop(columns=[c for c in cols_to_drop if c in features.columns], inplace=True, errors='ignore')
        features.dropna(inplace=True)

        return features

    def run(self):
        conn = sqlite3.connect(DB_NAME)
        
        assets_df = pd.read_sql_query("SELECT DISTINCT asset FROM market_data_1h", conn)
        assets = assets_df['asset'].tolist()

        if not assets:
            print("[ERROR] No data found in database.")
            return

        # 🟢 V4.0.2 FIX: Do not drop the table inside the loop! 
        # Create it once outside the loop.
        cursor = conn.cursor()
        cursor.execute("DROP TABLE IF EXISTS feature_store")
        
        cursor.execute('''
        CREATE TABLE feature_store (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            asset TEXT NOT NULL,
            timestamp INTEGER NOT NULL,
            dist_ema_20 REAL,
            dist_ema_50 REAL,
            dist_ema_200 REAL,
            macd_hist_norm REAL,
            rsi_norm REAL,
            atr_pct REAL,
            bb_width REAL,
            cvd_norm REAL,
            fvg_bull_intensity REAL,
            fvg_bear_intensity REAL,
            target_label INTEGER,
            UNIQUE(asset, timestamp)
        )
        ''')
        conn.commit()

        for asset in assets:
            print(f"\n[PROCESS] Generating Advanced Feature Space for {asset}...")
            
            query = f"SELECT timestamp, open, high, low, close, volume FROM market_data_1h WHERE asset = '{asset}' ORDER BY timestamp ASC"
            df = pd.read_sql_query(query, conn)
            
            if len(df) < 250:
                print(f"  [SKIP] Not enough data for {asset}.")
                continue

            feature_df = self.calculate_features(df)
            feature_df['asset'] = asset
            
            ml_columns = [
                'asset', 'timestamp', 'dist_ema_20', 'dist_ema_50', 'dist_ema_200',
                'macd_hist_norm', 'rsi_norm', 'atr_pct', 'bb_width', 'cvd_norm',
                'fvg_bull_intensity', 'fvg_bear_intensity'
            ]
            
            insert_df = feature_df[ml_columns]
            
            # 🟢 V4.0.2 FIX: Append to the main table, do not overwrite it.
            insert_df.to_sql('temp_adv_features', conn, if_exists='replace', index=False)
            
            cursor.execute('''
                INSERT INTO feature_store 
                (asset, timestamp, dist_ema_20, dist_ema_50, dist_ema_200, macd_hist_norm, rsi_norm, atr_pct, bb_width, cvd_norm, fvg_bull_intensity, fvg_bear_intensity)
                SELECT asset, timestamp, dist_ema_20, dist_ema_50, dist_ema_200, macd_hist_norm, rsi_norm, atr_pct, bb_width, cvd_norm, fvg_bull_intensity, fvg_bear_intensity
                FROM temp_adv_features
            ''')
            conn.commit()
            
            print(f"  [SUCCESS] Injected {len(insert_df)} high-dimensional feature vectors into the AI brain.")

        conn.close()
        print("\n==================================================")
        print("[SYSTEM] Advanced Feature Generation Complete.")
        print("Note: Because the feature schema changed, you must run label_generator.py again before training!")
        print("==================================================")

if __name__ == "__main__":
    generator = AdvancedFeatureStore()
    generator.run()