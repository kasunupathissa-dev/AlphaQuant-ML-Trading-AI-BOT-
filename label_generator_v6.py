import pandas as pd
import numpy as np
from sqlalchemy import text
import config

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

def calculate_shotgun_labels(df, atr_tp_mult=1.5, atr_sl_mult=1.0, time_limit_hours=24):
    """
    Calculates a binary label based on the outcome of the primary_signal:
    - 1: SUCCESS (Price hits TP before SL in the direction of primary_signal)
    - 0: FAILURE (Price hits SL first, or times out/reaches time limit)
    - -1: IGNORE (No primary signal was generated for this candle)
    """
    labels = pd.Series(np.nan, index=df.index, dtype=float)
    atr_series = calculate_atr(df, config.ATR_PERIOD)
    
    df_dt_index = df.set_index(pd.to_datetime(df['timestamp'], unit='ms'))

    for i in range(len(df)):
        primary_sig = df['primary_signal'].iloc[i]
        
        # If no primary signal was generated, this row is ignored
        if primary_sig == -1 or pd.isna(primary_sig):
            continue
            
        entry_price = df['close'].iloc[i]
        current_atr = atr_series.iloc[i]
        entry_time = df_dt_index.index[i]

        if pd.isna(current_atr) or current_atr <= 0:
            continue

        # Set TP/SL barriers based on primary signal direction
        if primary_sig == 1: # LONG
            upper_barrier = entry_price + (current_atr * atr_tp_mult)
            lower_barrier = entry_price - (current_atr * atr_sl_mult)
        elif primary_sig == 0: # SHORT
            upper_barrier = entry_price + (current_atr * atr_sl_mult)
            lower_barrier = entry_price - (current_atr * atr_tp_mult)
        else:
            continue

        end_time = entry_time + pd.Timedelta(hours=time_limit_hours)
        if df_dt_index.index[-1] < end_time:
            continue # not enough future data for a full horizon -- exclude, don't fabricate
            
        future_window = df_dt_index.loc[entry_time:end_time].iloc[1:]
        if future_window.empty:
            continue

        first_touch_upper = future_window[future_window['high'] >= upper_barrier].index.min()
        first_touch_lower = future_window[future_window['low'] <= lower_barrier].index.min()

        raw_label = 0 # Default to failure (times out or hits opposite)
        
        if primary_sig == 1: # LONG
            if pd.notna(first_touch_upper) and pd.notna(first_touch_lower):
                raw_label = 1 if first_touch_upper < first_touch_lower else 0
            elif pd.notna(first_touch_upper):
                raw_label = 1
            elif pd.notna(first_touch_lower):
                raw_label = 0
        elif primary_sig == 0: # SHORT
            if pd.notna(first_touch_lower) and pd.notna(first_touch_upper):
                raw_label = 1 if first_touch_lower < first_touch_upper else 0
            elif pd.notna(first_touch_lower):
                raw_label = 1
            elif pd.notna(first_touch_upper):
                raw_label = 0

        # Cost penalty check: ensure gross return clears 20 bps cost
        cost_pct = 0.0020
        if raw_label == 1:
            if primary_sig == 1:
                gross_return = (upper_barrier - entry_price) / entry_price
            else:
                gross_return = (entry_price - lower_barrier) / entry_price
                
            labels.iloc[i] = 1 if gross_return > cost_pct else 0
        else:
            labels.iloc[i] = 0
                 
    return labels

def generate_and_store_labels():
    print("==================================================")
    print(f"  ALPHAQUANT: SYMMETRICAL META-LABELING ({config.TIMEFRAME}) ")
    print("==================================================")

    engine = get_db_engine()
    if engine is None: return

    table_name_market = f"market_data_{config.TIMEFRAME}"
    table_name_features = f"feature_store_{config.TIMEFRAME}"

    with engine.connect() as connection:
        assets = pd.read_sql_query(f"SELECT DISTINCT asset FROM {table_name_market}", connection)['asset'].tolist()

        for asset in assets:
            print(f"\n[PROCESS] Generating Symmetrical Labels for {asset} ({config.TIMEFRAME})...")
            
            # Join with feature_store to retrieve primary_signal
            query = f"""
            SELECT m.timestamp, m.open, m.high, m.low, m.close, f.primary_signal
            FROM {table_name_market} m
            JOIN {table_name_features} f ON m.timestamp = f.timestamp AND m.asset = f.asset
            WHERE m.asset = '{asset}'
            ORDER BY m.timestamp ASC
            """
            df = pd.read_sql(query, connection)
            if len(df) < 100:
                print("  [SKIP] Not enough candles to label.")
                continue
            
            shotgun_labels = calculate_shotgun_labels(
                df, 
                atr_tp_mult=config.ATR_TAKE_PROFIT_MULTIPLIER, 
                atr_sl_mult=config.ATR_STOP_LOSS_MULTIPLIER,
                time_limit_hours=config.BARRIER_TIME_LIMIT_HOURS
            )
            df['target_label'] = shotgun_labels
            
            print("  --- Label Distribution ---")
            label_counts = shotgun_labels.value_counts(dropna=False).sort_index()
            print(f"    Class 0 (FAILURE): {label_counts.get(0.0, 0)}")
            print(f"    Class 1 (SUCCESS): {label_counts.get(1.0, 0)}")
            print(f"    Ignored/Unresolved: {label_counts.get(np.nan, 0)}")
            print("  --------------------------")

            labeled_df = df.dropna(subset=['target_label']).copy()
            if labeled_df.empty: continue

            temp_table_name = "temp_labels_update"
            update_df = labeled_df[['timestamp', 'target_label']]
            update_df.to_sql(temp_table_name, connection, if_exists='replace', index=False)

            update_sql = f"""
            UPDATE {table_name_features} fs JOIN {temp_table_name} temp ON fs.timestamp = temp.timestamp
            SET fs.target_label = temp.target_label
            WHERE fs.asset = '{asset}';
            """
            connection.execute(text(update_sql))
            connection.execute(text(f"DROP TABLE {temp_table_name}"))
            connection.commit()
            
            print(f"  [SUCCESS] Assigned outcomes to database table {table_name_features}.")

    print("\n==================================================")
    print(f"[SYSTEM] Symmetrical Meta-Labeling Complete ({config.TIMEFRAME}).")
    print("==================================================")

if __name__ == "__main__":
    generate_and_store_labels()
