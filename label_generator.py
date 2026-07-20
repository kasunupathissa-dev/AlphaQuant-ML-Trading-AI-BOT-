import sqlite3
import pandas as pd
import numpy as np

DB_NAME = "alphaquant_ml_v4.db"

def calculate_ml_labels(df, tp_pct=0.02, sl_pct=0.01):
    """
    Looks into the future to see if a trade would have won or lost.
    tp_pct: 2% Take Profit target
    sl_pct: 1% Stop Loss target
    
    Returns 1 if TP hits first, 0 if SL hits first, NaN if unresolved.
    """
    labels = pd.Series(index=df.index, dtype=float)
    
    for i in range(len(df)):
        entry_price = df['close'].iloc[i]
        
        # Calculate absolute price targets for a LONG trade
        tp_target = entry_price * (1 + tp_pct)
        sl_target = entry_price * (1 - sl_pct)
        
        # Look at the next 24 hours of price action
        future_window = df.iloc[i+1 : i+25]
        
        if future_window.empty:
            continue # End of dataset, cannot know the future
            
        # Find exactly when TP and SL are hit
        tp_hit = future_window[future_window['high'] >= tp_target]
        sl_hit = future_window[future_window['low'] <= sl_target]
        
        tp_index = tp_hit.index[0] if not tp_hit.empty else float('inf')
        sl_index = sl_hit.index[0] if not sl_hit.empty else float('inf')
        
        if tp_index < sl_index:
            labels.iloc[i] = 1 # WIN
        elif sl_index < tp_index:
            labels.iloc[i] = 0 # LOSS
        # If neither hit within 24 hours, it remains NaN (we will ignore these in training)

    return labels

def generate_and_store_labels():
    print("==================================================")
    print("  ALPHAQUANT V4.0: STAGE 3 - LABEL GENERATOR      ")
    print("==================================================")

    conn = sqlite3.connect(DB_NAME)
    
    assets_df = pd.read_sql_query("SELECT DISTINCT asset FROM market_data_1h", conn)
    assets = assets_df['asset'].tolist()

    for asset in assets:
        print(f"[PROCESS] Looking into the future to generate labels for {asset}...")
        
        query = f"SELECT timestamp, open, high, low, close FROM market_data_1h WHERE asset = '{asset}' ORDER BY timestamp ASC"
        df = pd.read_sql_query(query, conn)
        
        # Calculate what happens to a theoretical LONG trade taken at every single hour
        df['target_label'] = calculate_ml_labels(df)
        
        # Filter out NaN rows (where neither TP nor SL was hit in the 24h window)
        labeled_df = df.dropna(subset=['target_label']).copy()
        
        if labeled_df.empty:
            continue

        # Prepare for bulk update into the feature_store
        # We only want to update the target_label column where asset and timestamp match
        update_data = list(zip(labeled_df['target_label'].astype(int), labeled_df['timestamp'], [asset]*len(labeled_df)))
        
        cursor = conn.cursor()
        # SQL UPDATE statement to add the labels to our existing feature rows
        cursor.executemany('''
            UPDATE feature_store 
            SET target_label = ?
            WHERE timestamp = ? AND asset = ?
        ''', update_data)
        
        conn.commit()
        print(f"  [SUCCESS] Assigned {len(labeled_df)} future outcomes for {asset}.")

    conn.close()
    print("==================================================")
    print("[SYSTEM] Future Labeling Complete. Data is ready for ML Training.")
    print("==================================================")

if __name__ == "__main__":
    generate_and_store_labels()