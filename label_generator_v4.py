import sqlite3
import pandas as pd
import numpy as np

DB_NAME = "alphaquant_ml_v4.db"

def calculate_meta_labels(df, atr_tp_mult=1.5, atr_sl_mult=1.0, time_limit=24):
    """
    🟢 V4.4: Dual-Direction Triple Barrier Meta-Labeling
    Evaluates both Long and Short scenarios independently for every candle.
    """
    labels_long = pd.Series(index=df.index, dtype=float)
    labels_short = pd.Series(index=df.index, dtype=float)
    
    high_low = df['high'] - df['low']
    high_close = np.abs(df['high'] - df['close'].shift())
    low_close = np.abs(df['low'] - df['close'].shift())
    ranges = pd.concat([high_low, high_close, low_close], axis=1)
    true_range = np.max(ranges, axis=1)
    atr_series = true_range.rolling(14).mean()
    
    for i in range(len(df)):
        entry_price = df['close'].iloc[i]
        current_atr = atr_series.iloc[i]
        
        if pd.isna(current_atr) or current_atr <= 0:
            continue
            
        end_idx = min(i + time_limit + 1, len(df))
        future_window = df.iloc[i+1 : end_idx]
        
        if future_window.empty:
            continue 
            
        # Evaluate LONG Scenario
        long_tp = entry_price + (current_atr * atr_tp_mult)
        long_sl = entry_price - (current_atr * atr_sl_mult)
        long_hit = np.nan
        
        for _, row in future_window.iterrows():
            hit_tp = row['high'] >= long_tp
            hit_sl = row['low'] <= long_sl
            if hit_sl:
                long_hit = 0.0
                break
            elif hit_tp:
                long_hit = 1.0
                break
        if pd.isna(long_hit): long_hit = 0.0
        labels_long.iloc[i] = long_hit

        # Evaluate SHORT Scenario
        short_tp = entry_price - (current_atr * atr_tp_mult)
        short_sl = entry_price + (current_atr * atr_sl_mult)
        short_hit = np.nan
        
        for _, row in future_window.iterrows():
            hit_tp = row['low'] <= short_tp
            hit_sl = row['high'] >= short_sl
            if hit_sl:
                short_hit = 0.0
                break
            elif hit_tp:
                short_hit = 1.0
                break
        if pd.isna(short_hit): short_hit = 0.0
        labels_short.iloc[i] = short_hit

    return labels_long, labels_short

def generate_and_store_labels():
    print("==================================================")
    print("  ALPHAQUANT V4.4: DUAL-DIRECTION META-LABELING   ")
    print("==================================================")

    conn = sqlite3.connect(DB_NAME)
    assets_df = pd.read_sql_query("SELECT DISTINCT asset FROM market_data_1h", conn)
    assets = assets_df['asset'].tolist()

    for asset in assets:
        print(f"[PROCESS] Simulating Future Trajectories for {asset}...")
        
        query = f"SELECT timestamp, open, high, low, close FROM market_data_1h WHERE asset = '{asset}' ORDER BY timestamp ASC"
        df = pd.read_sql_query(query, conn)
        
        long_labels, short_labels = calculate_meta_labels(df)
        df['target_label_long'] = long_labels
        df['target_label_short'] = short_labels
        
        labeled_df = df.dropna(subset=['target_label_long', 'target_label_short']).copy()
        
        if labeled_df.empty: continue

        update_data = list(zip(
            labeled_df['target_label_long'].astype(int), 
            labeled_df['target_label_short'].astype(int), 
            labeled_df['timestamp'], 
            [asset]*len(labeled_df)
        ))
        
        cursor = conn.cursor()
        cursor.executemany('''
            UPDATE feature_store 
            SET target_label_long = ?, target_label_short = ?
            WHERE timestamp = ? AND asset = ?
        ''', update_data)
        
        conn.commit()
        print(f"  [SUCCESS] Assigned Independent Long/Short outcomes.")

    conn.close()
    print("==================================================")
    print("[SYSTEM] Meta-Labeling Complete.")
    print("==================================================")

if __name__ == "__main__":
    generate_and_store_labels()