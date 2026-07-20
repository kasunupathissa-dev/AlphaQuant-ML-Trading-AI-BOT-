import sqlite3
import pandas as pd
import numpy as np

DB_NAME = "alphaquant_ml_v4.db"

def calculate_triple_barrier_labels(df, atr_tp_mult=1.5, atr_sl_mult=1.0, time_limit=24):
    """
    🟢 V4.2: Triple Barrier Labeling (Volatility Adjusted)
    Uses dynamic ATR bands instead of fixed percentages.
    If High and Low both breach within the same candle, assumes SL hit first (Pessimistic Execution).
    """
    labels = pd.Series(index=df.index, dtype=float)
    
    # Need ATR to calculate barriers
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
            
        # 1. Dynamic Barriers based on volatility
        tp_target = entry_price + (current_atr * atr_tp_mult)
        sl_target = entry_price - (current_atr * atr_sl_mult)
        
        # 2. Time Barrier
        end_idx = min(i + time_limit + 1, len(df))
        future_window = df.iloc[i+1 : end_idx]
        
        if future_window.empty:
            continue 
            
        hit_status = np.nan
        
        for _, row in future_window.iterrows():
            hit_tp = row['high'] >= tp_target
            hit_sl = row['low'] <= sl_target
            
            # Pessimistic execution: If both happen in the same 1H candle, assume Stop Loss hit first.
            if hit_sl:
                hit_status = 0.0
                break
            elif hit_tp:
                hit_status = 1.0
                break
                
        # If the loop finishes and hit_status is still NaN, it means the Time Barrier expired.
        # We classify time expirations as a Loss (0.0) because the momentum failed to materialize.
        if pd.isna(hit_status):
            hit_status = 0.0
            
        labels.iloc[i] = hit_status

    return labels

def generate_and_store_labels():
    print("==================================================")
    print("  ALPHAQUANT V4.2: TRIPLE BARRIER LABELING        ")
    print("==================================================")

    conn = sqlite3.connect(DB_NAME)
    assets_df = pd.read_sql_query("SELECT DISTINCT asset FROM market_data_1h", conn)
    assets = assets_df['asset'].tolist()

    for asset in assets:
        print(f"[PROCESS] Generating Volatility-Adjusted Labels for {asset}...")
        
        query = f"SELECT timestamp, open, high, low, close FROM market_data_1h WHERE asset = '{asset}' ORDER BY timestamp ASC"
        df = pd.read_sql_query(query, conn)
        
        df['target_label'] = calculate_triple_barrier_labels(df)
        
        labeled_df = df.dropna(subset=['target_label']).copy()
        
        if labeled_df.empty: continue

        update_data = list(zip(labeled_df['target_label'].astype(int), labeled_df['timestamp'], [asset]*len(labeled_df)))
        
        cursor = conn.cursor()
        cursor.executemany('''
            UPDATE feature_store 
            SET target_label = ?
            WHERE timestamp = ? AND asset = ?
        ''', update_data)
        
        conn.commit()
        print(f"  [SUCCESS] Assigned {len(labeled_df)} Triple Barrier outcomes.")

    conn.close()
    print("==================================================")
    print("[SYSTEM] Labeling Complete. Ready for Calibrated ML Training.")
    print("==================================================")

if __name__ == "__main__":
    generate_and_store_labels()