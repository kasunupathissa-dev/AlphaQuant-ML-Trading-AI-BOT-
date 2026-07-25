import pandas as pd
import numpy as np
from sqlalchemy import text

# 🟢 V6.4 Upgrade for V8 Shotgun Pipeline (Typo Fix)
from database_config import get_db_engine

def calculate_atr(df, period=14):
    """Calculates Average True Range."""
    df_copy = df.copy()
    df_copy['h-l'] = df_copy['high'] - df_copy['low']
    df_copy['h-pc'] = np.abs(df_copy['high'] - df_copy['close'].shift())
    df_copy['l-pc'] = np.abs(df_copy['low'] - df_copy['close'].shift())
    df_copy['tr'] = df_copy[['h-l', 'h-pc', 'l-pc']].max(axis=1)
    return df_copy['tr'].rolling(window=period).mean()

def calculate_shotgun_labels(df, atr_profit_mult=1.5, time_limit_hours=24):
    """
    Calculates a single multi-class label based on the first barrier touched.
    - 1: LONG (Upper barrier hit first)
    - 0: SHORT (Lower barrier hit first)
    - 2: HOLD (Neither barrier hit within the time limit)
    """
    labels = pd.Series(2, index=df.index, dtype=int)
    atr_series = calculate_atr(df, 14)
    
    df_dt_index = df.set_index(pd.to_datetime(df['timestamp'], unit='ms'))

    for i in range(len(df)):
        entry_price = df['close'].iloc[i]
        current_atr = atr_series.iloc[i]
        entry_time = df_dt_index.index[i]

        if pd.isna(current_atr) or current_atr <= 0:
            continue

        upper_barrier = entry_price + (current_atr * atr_profit_mult)
        lower_barrier = entry_price - (current_atr * atr_profit_mult)

        end_time = entry_time + pd.Timedelta(hours=time_limit_hours)
        future_window = df_dt_index.loc[entry_time:end_time].iloc[1:]

        if future_window.empty:
            continue

        first_touch_upper = future_window[future_window['high'] >= upper_barrier].index.min()
        first_touch_lower = future_window[future_window['low'] <= lower_barrier].index.min()

        if pd.notna(first_touch_upper) and pd.notna(first_touch_lower):
            if first_touch_upper < first_touch_lower:
                labels.iloc[i] = 1
            else:
                labels.iloc[i] = 0
        elif pd.notna(first_touch_upper):
            labels.iloc[i] = 1
        elif pd.notna(first_touch_lower):
            labels.iloc[i] = 0
                
    return labels

def generate_and_store_labels():
    print("==================================================")
    print("  ALPHAQUANT V6.4: SYMMETRICAL META-LABELING      ")
    print("==================================================")

    engine = get_db_engine()
    if engine is None: return

    with engine.connect() as connection:
        assets = pd.read_sql_query("SELECT DISTINCT asset FROM market_data_1h", connection)['asset'].tolist()

        for asset in assets:
            print(f"\n[PROCESS] Generating Symmetrical Labels for {asset}...")
            
            query = f"SELECT timestamp, open, high, low, close FROM market_data_1h WHERE asset = '{asset}' ORDER BY timestamp ASC"
            df = pd.read_sql(query, connection)
            
            shotgun_labels = calculate_shotgun_labels(df)
            df['target_label'] = shotgun_labels
            
            print("  --- Label Distribution ---")
            label_counts = shotgun_labels.value_counts().sort_index()
            print(f"    Class 0 (SHORT): {label_counts.get(0, 0)}")
            print(f"    Class 1 (LONG):  {label_counts.get(1, 0)}")
            print(f"    Class 2 (HOLD):  {label_counts.get(2, 0)}")
            print("  --------------------------")

            # 🟢 V6.4 TYPO FIX
            labeled_df = df.dropna(subset=['target_label']).copy()
            if labeled_df.empty: continue

            temp_table_name = "temp_labels_update"
            update_df = labeled_df[['timestamp', 'target_label']]
            update_df.to_sql(temp_table_name, connection, if_exists='replace', index=False)

            update_sql = f"""
            UPDATE feature_store fs JOIN {temp_table_name} temp ON fs.timestamp = temp.timestamp
            SET fs.target_label = temp.target_label
            WHERE fs.asset = '{asset}';
            """
            connection.execute(text(update_sql))
            connection.execute(text(f"DROP TABLE {temp_table_name}"))
            connection.commit()
            
            print(f"  [SUCCESS] Assigned outcomes to feature store.")

    print("\n==================================================")
    print("[SYSTEM] Symmetrical Meta-Labeling Complete.")
    print("==================================================")

if __name__ == "__main__":
    generate_and_store_labels()