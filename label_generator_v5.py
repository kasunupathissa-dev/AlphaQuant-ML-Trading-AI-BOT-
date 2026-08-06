import pandas as pd
import numpy as np
from sqlalchemy import text

# 🟢 V6.6 Upgrade: Use the centralized database configuration
from database_config import get_db_engine

def calculate_triple_barrier_labels(df, atr_tp_mult=1.5, atr_sl_mult=1.0, time_limit=24):
    """
    Calculates win/loss outcomes for both LONG and SHORT scenarios using a robust
    "default to zero" approach to prevent NaN leakage.
    """
    labels_long = pd.Series(np.nan, index=df.index)
    labels_short = pd.Series(np.nan, index=df.index)
    
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
            
        end_idx = i + time_limit + 1
        if end_idx > len(df):
            continue # not enough future data for a full horizon -- exclude, don't fabricate
            
        future_window = df.iloc[i+1 : end_idx]
        
        if future_window.empty:
            continue 
            
        # --- Evaluate LONG Scenario ---
        long_tp, long_sl = entry_price + (current_atr * atr_tp_mult), entry_price - (current_atr * atr_sl_mult)
        long_resolved = False
        for _, row in future_window.iterrows():
            if row['low'] <= long_sl:
                labels_long.iloc[i] = 0.0 # Loss
                long_resolved = True
                break
            elif row['high'] >= long_tp:
                labels_long.iloc[i] = 1.0 # Win
                long_resolved = True
                break
        if not long_resolved:
            labels_long.iloc[i] = 0.0 # Loss on timeout
            
        # --- Evaluate SHORT Scenario ---
        short_tp, short_sl = entry_price - (current_atr * atr_tp_mult), entry_price + (current_atr * atr_sl_mult)
        short_resolved = False
        for _, row in future_window.iterrows():
            if row['high'] >= short_sl:
                labels_short.iloc[i] = 0.0 # Loss
                short_resolved = True
                break
            elif row['low'] <= short_tp:
                labels_short.iloc[i] = 1.0 # Win
                short_resolved = True
                break
        if not short_resolved:
            labels_short.iloc[i] = 0.0 # Loss on timeout

    # Ensure some labels were successfully resolved
    assert labels_long.notnull().any(), "No valid LONG labels resolved!"
    assert labels_short.notnull().any(), "No valid SHORT labels resolved!"

    return labels_long, labels_short

def generate_and_store_labels():
    print("==================================================")
    print("  ALPHAQUANT V6.6: HARDENED META-LABELING         ")
    print("==================================================")

    engine = get_db_engine()
    if engine is None: return

    with engine.connect() as connection:
        assets = pd.read_sql_query("SELECT DISTINCT asset FROM market_data_1h", connection)['asset'].tolist()

        for asset in assets:
            print(f"[PROCESS] Simulating Future Trajectories for {asset}...")
            
            query = f"SELECT timestamp, open, high, low, close FROM market_data_1h WHERE asset = '{asset}' ORDER BY timestamp ASC"
            df = pd.read_sql(query, connection)
            
            long_labels, short_labels = calculate_triple_barrier_labels(df)
            df['target_label_long'] = long_labels
            df['target_label_short'] = short_labels
            
            labeled_df = df.dropna(subset=['target_label_long', 'target_label_short']).copy()
            if labeled_df.empty: continue

            temp_table_name = "temp_labels_update"
            update_df = labeled_df[['timestamp', 'target_label_long', 'target_label_short']]
            update_df.to_sql(temp_table_name, connection, if_exists='replace', index=False)

            update_sql = f"""
            UPDATE feature_store fs JOIN {temp_table_name} temp ON fs.timestamp = temp.timestamp
            SET fs.target_label_long = temp.target_label_long, fs.target_label_short = temp.target_label_short
            WHERE fs.asset = '{asset}';
            """
            connection.execute(text(update_sql))
            connection.execute(text(f"DROP TABLE {temp_table_name}"))
            connection.commit()
            
            print(f"  [SUCCESS] Assigned Independent Long/Short outcomes to feature store.")

    print("==================================================")
    print("[SYSTEM] Meta-Labeling Complete.")
    print("==================================================")

if __name__ == "__main__":
    generate_and_store_labels()