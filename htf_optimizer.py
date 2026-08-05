import os
import sys
import json
import pandas as pd
import numpy as np
from sqlalchemy import text

# Import project settings
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from database_config import get_db_engine
import config
from feature_library import calculate_features_for_shotgun

def simulate_trade_outcome(df, start_idx, direction, entry_price, atr_val):
    """
    Scans forward in df to determine if TP or SL is hit first.
    Returns 1 for WIN (TP hit), 0 for LOSS (SL hit), or 0.5 for TIME LIMIT.
    """
    tp_mult = getattr(config, 'ATR_TAKE_PROFIT_MULTIPLIER', 1.5)
    sl_mult = getattr(config, 'ATR_STOP_LOSS_MULTIPLIER', 1.0)
    
    if direction == "LONG":
        sl = entry_price - atr_val * sl_mult
        tp = entry_price + atr_val * tp_mult
    else:
        sl = entry_price + atr_val * sl_mult
        tp = entry_price - atr_val * tp_mult

    # Limit search to 96 bars (24 hours on 15m)
    max_lookahead = min(start_idx + 96, len(df))
    
    for i in range(start_idx + 1, max_lookahead):
        row = df.iloc[i]
        high = float(row['high'])
        low = float(row['low'])
        
        if direction == "LONG":
            if low <= sl:
                return 0.0 # Loss
            if high >= tp:
                return 1.0 # Win
        else:
            if high >= sl:
                return 0.0 # Loss
            if low <= tp:
                return 1.0 # Win
                
    # Time limit exit: return based on current close PnL
    final_close = float(df.iloc[max_lookahead-1]['close'])
    if direction == "LONG":
        return 1.0 if final_close > entry_price else 0.0
    else:
        return 1.0 if final_close < entry_price else 0.0

def check_htf_rule(row, direction, rule_name):
    close_val = float(row['close'])
    ema_fast = float(row['ema_50'])
    ema_slow = float(row['ema_200'])
    
    if rule_name == "STRICT":
        if direction == "LONG":
            return close_val > ema_fast and ema_fast > ema_slow
        else:
            return close_val < ema_fast and ema_fast < ema_slow
            
    elif rule_name == "EMA_CROSS":
        if direction == "LONG":
            return ema_fast > ema_slow
        else:
            return ema_fast < ema_slow
            
    elif rule_name == "PRICE_ABOVE":
        if direction == "LONG":
            return close_val > ema_slow
        else:
            return close_val < ema_slow
            
    return False

def run_optimizer():
    engine = get_db_engine()
    if engine is None:
        print("[ERROR] Database engine connection failed.")
        return

    table_market = f"market_data_{config.TIMEFRAME}"
    optimal_htf_rules = {}
    rule_candidates = ["STRICT", "EMA_CROSS", "PRICE_ABOVE"]

    print("\n==================================================")
    print("      ALPHAQUANT: HTF FILTER OPTIMIZATION         ")
    print("==================================================")

    for asset in config.TARGET_ASSETS:
        # Load historical price data (all available up to 180 days)
        query = f"SELECT * FROM {table_market} WHERE asset = '{asset}' ORDER BY timestamp DESC"
        try:
            with engine.connect() as conn:
                df = pd.read_sql(text(query), conn)
        except Exception as e:
            print(f"[ERROR] Failed to read database for {asset}: {e}")
            continue

        if df.empty or len(df) < 500:
            print(f"[SKIP] Insufficient data for {asset} (Rows: {len(df)}).")
            continue

        # Reverse back to ascending order for indicator generation
        df = df.iloc[::-1].reset_index(drop=True)
        df = calculate_features_for_shotgun(df)
        df.dropna(subset=['ema_50', 'ema_200', 'atr'], inplace=True)
        df.reset_index(drop=True, inplace=True)

        for direction in ["LONG", "SHORT"]:
            target_signal = 1 if direction == "LONG" else 0
            setups = df[df['primary_signal'] == target_signal]
            
            if len(setups) < 10:
                print(f"[SKIP] {asset} {direction} has only {len(setups)} setups.")
                optimal_htf_rules[f"{asset}_{direction}"] = "STRICT"
                continue

            best_rule = "STRICT"
            best_ev = -999.0
            best_metrics = {}

            # Grid search over rule candidates
            for rule in rule_candidates:
                trades_pnl = []
                
                for idx, row in setups.iterrows():
                    # Evaluate if candidate rule allows this trade setup
                    if check_htf_rule(row, direction, rule):
                        outcome = simulate_trade_outcome(df, idx, direction, float(row['close']), float(row['atr']))
                        pnl = 1.5 if outcome == 1.0 else -1.0
                        trades_pnl.append(pnl)

                trade_count = len(trades_pnl)
                if trade_count < 10: # Safety trade count threshold
                    continue

                wins = sum(1 for p in trades_pnl if p > 0)
                win_rate = (wins / trade_count) * 100
                total_profit = sum(p for p in trades_pnl if p > 0)
                total_loss = abs(sum(p for p in trades_pnl if p < 0))
                profit_factor = total_profit / total_loss if total_loss > 0 else total_profit
                expected_val = sum(trades_pnl) / trade_count

                if expected_val > best_ev:
                    best_ev = expected_val
                    best_rule = rule
                    best_metrics = {
                        "trades": trade_count,
                        "win_rate": f"{win_rate:.1f}%",
                        "profit_factor": f"{profit_factor:.2f}",
                        "expected_val": f"{expected_val:.2f}"
                    }

            optimal_htf_rules[f"{asset}_{direction}"] = best_rule
            print(f"[OPTIMIZED] {asset} {direction} => Rule: {best_rule} (EV: {best_ev:.2f}, Trades: {best_metrics.get('trades', 0)})")

    # Write output optimal mapping
    output_dir = os.path.dirname(os.path.abspath(__file__))
    output_file = os.path.join(output_dir, "optimal_htf_rules.json")
    with open(output_file, 'w') as f:
        json.dump(optimal_htf_rules, f, indent=4)
    print(f"\n[SUCCESS] Optimal HTF rules written to {output_file}:")
    print(json.dumps(optimal_htf_rules, indent=4))

if __name__ == "__main__":
    run_optimizer()
