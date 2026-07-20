import sqlite3
import pandas as pd
import pandas_ta as ta
import numpy as np

DB_NAME = "alphaquant_ml_v4.db"

def calculate_features(df):
    """
    Transforms raw OHLCV data into Machine Learning features.
    No strings/text allowed. Everything must be continuous or categorical numbers.
    """
    # Create a copy to avoid SettingWithCopy warnings
    features = df.copy()

    # 1. Technical Distance Features
    # Instead of "Bullish", we measure exactly how far price is from the EMA.
    # Positive = Above EMA. Negative = Below EMA.
    features['ema_50'] = ta.ema(features['close'], length=50)
    features['ema_200'] = ta.ema(features['close'], length=200)
    
    # Distance to EMAs (Percentage)
    features['dist_ema_50'] = (features['close'] - features['ema_50']) / features['ema_50']
    features['dist_ema_200'] = (features['close'] - features['ema_200']) / features['ema_200']

    # VWAP Approximation
    features['typ_price'] = (features['high'] + features['low'] + features['close']) / 3
    features['vwap'] = (features['typ_price'] * features['volume']).cumsum() / features['volume'].cumsum()
    features['dist_vwap'] = (features['close'] - features['vwap']) / features['vwap']

    # 2. Volatility Features
    features['atr'] = ta.atr(features['high'], features['low'], features['close'], length=14)
    features['atr_pct'] = features['atr'] / features['close']

    # 3. RSI Momentum
    features['rsi_14'] = ta.rsi(features['close'], length=14)
    # Normalize RSI from 0-100 to -1 to +1 range for ML
    features['rsi_norm'] = (features['rsi_14'] - 50) / 50

    # 4. Volume Features
    # Ratio of current volume to 20-period moving average of volume
    features['vol_sma'] = features['volume'].rolling(20).mean()
    features['vol_surge_ratio'] = features['volume'] / features['vol_sma']

    # 5. Smart Money Concept (SMC): Basic FVG Proximity Math
    # We look at the candle 2 periods ago to see if a gap was created.
    features['fvg_bull_gap'] = features['low'].shift(0) - features['high'].shift(2)
    features['fvg_bear_gap'] = features['low'].shift(2) - features['high'].shift(0)
    
    # If gap is > 0, there is a gap. We normalize it by ATR to measure its significance.
    features['fvg_bull_intensity'] = np.where(features['fvg_bull_gap'] > 0, features['fvg_bull_gap'] / features['atr'], 0)
    features['fvg_bear_intensity'] = np.where(features['fvg_bear_gap'] > 0, features['fvg_bear_gap'] / features['atr'], 0)

    # Drop the temporary calculation columns, keeping only the final ML features
    cols_to_drop = ['ema_50', 'ema_200', 'typ_price', 'vwap', 'atr', 'rsi_14', 'vol_sma', 'fvg_bull_gap', 'fvg_bear_gap']
    features.drop(columns=cols_to_drop, inplace=True)

    # Drop any rows with NaN (caused by the initial rolling windows like EMA-200)
    features.dropna(inplace=True)

    return features

def generate_and_store_features():
    print("==================================================")
    print("  ALPHAQUANT V4.0: STAGE 2 - FEATURE GENERATOR    ")
    print("==================================================")

    conn = sqlite3.connect(DB_NAME)
    
    # Get list of all assets currently in the raw database
    assets_df = pd.read_sql_query("SELECT DISTINCT asset FROM market_data_1h", conn)
    assets = assets_df['asset'].tolist()

    if not assets:
        print("[ERROR] No data found in 'market_data_1h'. Run data_ingestion.py first.")
        return

    for asset in assets:
        print(f"[PROCESS] Generating features for {asset}...")
        
        # Load the raw OHLCV data for this asset
        query = f"SELECT timestamp, open, high, low, close, volume FROM market_data_1h WHERE asset = '{asset}' ORDER BY timestamp ASC"
        df = pd.read_sql_query(query, conn)
        
        if len(df) < 250:
            print(f"  [SKIP] Not enough data for {asset} (Needs at least 200 rows for EMA).")
            continue

        # Run the massive mathematical transformation
        feature_df = calculate_features(df)
        
        # Add the asset column back
        feature_df['asset'] = asset
        
        # We only want to insert the calculated features into the feature_store table.
        # Ensure columns match the SQL schema defined in Stage 1.
        insert_df = feature_df[['asset', 'timestamp', 'dist_ema_50', 'dist_ema_200', 'dist_vwap', 'atr_pct']]
        
        # Use pandas to_sql to insert. We use a temp table to handle upserts (updates).
        insert_df.to_sql('temp_features', conn, if_exists='replace', index=False)
        
        cursor = conn.cursor()
        cursor.execute('''
            INSERT OR REPLACE INTO feature_store 
            (asset, timestamp, dist_ema_50, dist_ema_200, dist_vwap, atr_pct)
            SELECT asset, timestamp, dist_ema_50, dist_ema_200, dist_vwap, atr_pct
            FROM temp_features
        ''')
        conn.commit()
        
        print(f"  [SUCCESS] Calculated and saved {len(insert_df)} feature vectors for {asset}.")

    conn.close()
    print("==================================================")
    print("[SYSTEM] Feature Generation Complete.")
    print("==================================================")

if __name__ == "__main__":
    generate_and_store_features()