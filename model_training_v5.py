import pandas as pd
import numpy as np
import xgboost as xgb
from sklearn.model_selection import train_test_split
from sklearn.calibration import CalibratedClassifierCV
from sklearn.metrics import precision_score
import joblib
import os

# 🟢 V5.1 Upgrade: Use the centralized database configuration
from database_config import get_db_engine

TARGET_ASSETS = ["BTC/USDT", "ETH/USDT", "SOL/USDT", "BNB/USDT", "ADA/USDT", "XRP/USDT", "LINK/USDT", "AVAX/USDT", "DOGE/USDT", "DOT/USDT"]

def train_multi_signal_models():
    print("==================================================")
    print("  ALPHAQUANT V5.1: MULTI-SIGNAL META-TRAINING     ")
    print("==================================================")

    engine = get_db_engine()
    if engine is None: return

    for asset in TARGET_ASSETS:
        print(f"\n{'='*15} Training 6x Meta-Models for {asset} {'='*15}")
        
        query = f"SELECT * FROM feature_store WHERE asset = '{asset}'"
        try:
            df = pd.read_sql(query, engine)
        except Exception as e:
            print(f"  [ERROR] DB Read failed: {e}")
            continue
        
        if len(df) < 50: continue

        asset_brain = {} # This will hold all 6 models for the current asset

        # Define the 3 signal types and their corresponding columns
        signal_types = {
            "TREND": ("primary_trend_long", "primary_trend_short"),
            "BREAKOUT": ("primary_breakout_long", "primary_breakout_short"),
            "REVERSION": ("primary_reversion_long", "primary_reversion_short")
        }

        for signal_name, (long_col, short_col) in signal_types.items():
            print(f"\n--- Training for Signal Type: {signal_name} ---")

            # --- TRAIN LONG MODEL ---
            long_df = df[df[long_col] == 1].copy()
            if len(long_df) > 20:
                wins = len(long_df[long_df['target_label_long'] == 1.0])
                losses = len(long_df) - wins
                scale_weight = (losses / wins) * 1.5 if wins > 0 else 1.0
                
                print(f"  [LONG] Samples: {len(long_df)} | Base Win Rate: {(wins/len(long_df))*100:.1f}%")
                
                if wins > 0 and losses > 0:
                    X = long_df.drop(columns=['id', 'asset', 'timestamp', 'target_label_long', 'target_label_short', 'primary_trend_long', 'primary_trend_short', 'primary_breakout_long', 'primary_breakout_short', 'primary_reversion_long', 'primary_reversion_short'])
                    y = long_df['target_label_long']
                    
                    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42, shuffle=False)
                    
                    base_model = xgb.XGBClassifier(n_estimators=300, learning_rate=0.01, max_depth=3, subsample=0.8, colsample_bytree=0.8, objective='binary:logistic', scale_pos_weight=scale_weight)
                    calibrated_model = CalibratedClassifierCV(estimator=base_model, method='isotonic', cv=3)
                    calibrated_model.fit(X_train, y_train)
                    
                    y_pred_proba = calibrated_model.predict_proba(X_test)[:, 1]
                    
                    best_thresh, best_prec = 0.50, 0.0
                    for thresh in np.arange(0.45, 0.75, 0.01): 
                        y_pred_custom = (y_pred_proba >= thresh).astype(int)
                        prec = precision_score(y_test, y_pred_custom, zero_division=0) * 100
                        if prec >= 50.0 and sum(y_pred_custom) >= 1:
                            if thresh > best_thresh or best_prec == 0.0:
                                best_thresh, best_prec = thresh, prec
                                
                    asset_brain[f"{signal_name}_LONG"] = {'model': calibrated_model, 'threshold': best_thresh}
                    print(f"  -> LONG Model Calibrated. Optimal Threshold: {best_thresh*100:.1f}%")

            # --- TRAIN SHORT MODEL ---
            short_df = df[df[short_col] == 1].copy()
            if len(short_df) > 20:
                wins = len(short_df[short_df['target_label_short'] == 1.0])
                losses = len(short_df) - wins
                scale_weight = (losses / wins) * 1.5 if wins > 0 else 1.0
                
                print(f"  [SHORT] Samples: {len(short_df)} | Base Win Rate: {(wins/len(short_df))*100:.1f}%")
                
                if wins > 0 and losses > 0:
                    X = short_df.drop(columns=['id', 'asset', 'timestamp', 'target_label_long', 'target_label_short', 'primary_trend_long', 'primary_trend_short', 'primary_breakout_long', 'primary_breakout_short', 'primary_reversion_long', 'primary_reversion_short'])
                    y = short_df['target_label_short']
                    
                    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42, shuffle=False)

                    base_model = xgb.XGBClassifier(n_estimators=300, learning_rate=0.01, max_depth=3, subsample=0.8, colsample_bytree=0.8, objective='binary:logistic', scale_pos_weight=scale_weight)
                    calibrated_model = CalibratedClassifierCV(estimator=base_model, method='isotonic', cv=3)
                    calibrated_model.fit(X_train, y_train)
                    
                    y_pred_proba = calibrated_model.predict_proba(X_test)[:, 1]

                    best_thresh, best_prec = 0.50, 0.0
                    for thresh in np.arange(0.45, 0.75, 0.01):
                        y_pred_custom = (y_pred_proba >= thresh).astype(int)
                        prec = precision_score(y_test, y_pred_custom, zero_division=0) * 100
                        if prec >= 50.0 and sum(y_pred_custom) >= 1:
                            if thresh > best_thresh or best_prec == 0.0:
                                best_thresh, best_prec = thresh, prec

                    asset_brain[f"{signal_name}_SHORT"] = {'model': calibrated_model, 'threshold': best_thresh}
                    print(f"  -> SHORT Model Calibrated. Optimal Threshold: {best_thresh*100:.1f}%")

        if asset_brain:
            safe_filename = asset.replace("/", "_") + "_brain.pkl"
            joblib.dump(asset_brain, safe_filename)
            print(f"\n  [SUCCESS] Saved 6x Meta-Models to {safe_filename}")

    print("\n==================================================")
    print(" V5.1 Multi-Signal Training Complete.")
    print("==================================================")

if __name__ == "__main__":
    train_multi_signal_models()