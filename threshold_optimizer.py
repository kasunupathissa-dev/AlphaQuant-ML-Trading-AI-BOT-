import os
import sys
import json
import pandas as pd
import numpy as np
import joblib
from sqlalchemy import text

# Import project settings
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from database_config import get_db_engine
import config
from feature_library import calculate_features_for_shotgun

# Deserialization helper for model brains
from sklearn.base import BaseEstimator, ClassifierMixin, clone
from sklearn.model_selection import cross_val_predict
from sklearn.isotonic import IsotonicRegression

class ManualCalibratedClassifier(BaseEstimator, ClassifierMixin):
    def __init__(self, estimator, cv=3):
        self.estimator = estimator
        self.cv = cv
    def fit(self, X, y, sample_weight=None):
        return self
    def predict_proba(self, X):
        return self.estimator.predict_proba(X)

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

def run_optimizer():
    engine = get_db_engine()
    if engine is None:
        print("[ERROR] Database engine connection failed.")
        return

    table_market = f"market_data_{config.TIMEFRAME}"
    features_list = [
        'dist_ema_50', 'dist_ema_200', 'atr_pct', 'volume_zscore', 'adx_14', 'bb_width',
        'funding_rate_zscore', 'oi_zscore', 'rsi_14', 'macd_hist', 'supertrend_direction', 'chop_index'
    ]

    optimal_overrides = {}
    thresholds = [50.0, 52.0, 54.0, 56.0, 58.0, 60.0, 62.0, 64.0, 66.0, 68.0, 70.0]

    print("\n==================================================")
    print("  ALPHAQUANT: WALKFOWARD THRESHOLD OPTIMIZATION   ")
    print("==================================================")

    for asset in config.TARGET_ASSETS:
        brain_file = "/home/kasun/repository/AlphaQuant-ML-Trading-AI-BOT-/" + asset.replace("/", "_") + "_brain.pkl"
        if not os.path.exists(brain_file):
            print(f"[SKIP] Model file {brain_file} not found.")
            continue

        try:
            brain = joblib.load(brain_file)
            model = brain['model']
        except Exception as e:
            print(f"[ERROR] Failed to load brain for {asset}: {e}")
            continue

        # Load all available historical price data
        query = f"""
        SELECT * FROM {table_market} 
        WHERE asset = '{asset}' 
        ORDER BY timestamp DESC
        """
        try:
            with engine.connect() as conn:
                df = pd.read_sql(text(query), conn)
        except Exception as e:
            print(f"[ERROR] Failed to read database for {asset}: {e}")
            continue

        if df.empty or len(df) < 500:
            print(f"[SKIP] Insufficient data for {asset} (Rows: {len(df)}).")
            continue

        # Reverse back to ascending order for feature engineering
        df = df.iloc[::-1].reset_index(drop=True)
        df = calculate_features_for_shotgun(df)
        df['funding_rate_zscore'] = 0.0
        df['oi_zscore'] = 0.0
        df.dropna(subset=['adx_14', 'chop_index', 'ema_50', 'ema_200'], inplace=True)
        df.reset_index(drop=True, inplace=True)

        for direction in ["LONG", "SHORT"]:
            target_signal = 1 if direction == "LONG" else 0
            setups = df[df['primary_signal'] == target_signal]
            
            if len(setups) < 10:
                print(f"[SKIP] {asset} {direction} has only {len(setups)} setups.")
                optimal_overrides[f"{asset}_{direction}"] = 65.0 if direction == "LONG" else 60.0
                continue

            best_thresh = 65.0 if direction == "LONG" else 60.0
            best_ev = -999.0
            best_metrics = {}

            # Grid search
            for thresh in thresholds:
                trades_pnl = []
                
                for idx, row in setups.iterrows():
                    X_live = pd.DataFrame([row[features_list]], columns=features_list)
                    try:
                        probs = model.predict_proba(X_live)[0]
                        win_prob = probs[1] * 100
                    except:
                        continue
                        
                    if win_prob >= thresh:
                        outcome = simulate_trade_outcome(df, idx, direction, float(row['close']), float(row['atr']))
                        # Outcome: 1 for WIN (TP, yields +1.5x risk), 0 for LOSS (SL, yields -1.0x risk)
                        pnl = 1.5 if outcome == 1.0 else -1.0
                        trades_pnl.append(pnl)

                trade_count = len(trades_pnl)
                if trade_count < 10: # Minimum trades count threshold scaled for longer dataset
                    continue

                wins = sum(1 for p in trades_pnl if p > 0)
                win_rate = (wins / trade_count) * 100
                total_profit = sum(p for p in trades_pnl if p > 0)
                total_loss = abs(sum(p for p in trades_pnl if p < 0))
                
                profit_factor = total_profit / total_loss if total_loss > 0 else total_profit
                expected_val = sum(trades_pnl) / trade_count

                if expected_val > best_ev:
                    best_ev = expected_val
                    best_thresh = thresh
                    best_metrics = {
                        "trades": trade_count,
                        "win_rate": f"{win_rate:.1f}%",
                        "profit_factor": f"{profit_factor:.2f}",
                        "expected_val": f"{expected_val:.2f}"
                    }

            if best_ev > -999.0:
                optimal_overrides[f"{asset}_{direction}"] = best_thresh
                print(f"[OPTIMIZED] {asset} {direction} => Thresh: {best_thresh}% (EV: {best_ev:.2f}, Trades: {best_metrics.get('trades', 0)})")
            else:
                optimal_overrides[f"{asset}_{direction}"] = 65.0 if direction == "LONG" else 60.0

    # Write out optimal configurations
    output_file = "optimal_thresholds.json"
    with open(output_file, 'w') as f:
        json.dump(optimal_overrides, f, indent=4)
    print(f"\n[SUCCESS] Optimal thresholds written to {output_file}:")
    print(json.dumps(optimal_overrides, indent=4))

if __name__ == "__main__":
    run_optimizer()
