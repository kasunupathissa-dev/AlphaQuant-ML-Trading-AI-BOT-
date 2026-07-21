import pandas as pd
import numpy as np
import xgboost as xgb
from sklearn.model_selection import train_test_split
from sklearn.calibration import CalibratedClassifierCV
from sklearn.metrics import precision_score
import joblib
import os

# 🟢 V5 Upgrade: Use the centralized database configuration
from database_config import get_db_engine

TARGET_ASSETS = ["BTC/USDT", "ETH/USDT", "SOL/USDT", "BNB/USDT", "ADA/USDT", "XRP/USDT", "LINK/USDT", "AVAX/USDT", "DOGE/USDT", "DOT/USDT"]

def train_dual_meta_models():
    print("==================================================")
    print("  ALPHAQUANT V5: DUAL-MODEL META-TRAINING         ")
    print("==================================================")

    engine = get_db_engine()
    if engine is None: return

    for asset in TARGET_ASSETS:
        print(f"\n[SYSTEM] Training LONG and SHORT Brains for {asset}...")
        
        query = f"""
            SELECT 
                dist_ema_20, dist_ema_50, dist_ema_200, 
                atr_pct, volatility_zscore, volume_zscore, chop_index, adx_14, bb_width, 
                fvg_bull_intensity, fvg_bear_intensity,
                primary_long_signal, primary_short_signal,
                target_label_long, target_label_short
            FROM feature_store 
            WHERE (target_label_long IS NOT NULL OR target_label_short IS NOT NULL) AND asset = '{asset}'
        """
        try:
            df = pd.read_sql(query, engine)
        except Exception as e:
            print(f"  [ERROR] DB Read failed for {asset}: {e}")
            continue
        
        if len(df) < 50: continue

        asset_brain = {}

        # --- TRAIN LONG MODEL ---
        long_df = df[df['primary_long_signal'] == 1].copy()
        if len(long_df) > 20:
            wins = len(long_df[long_df['target_label_long'] == 1.0])
            losses = len(long_df[long_df['target_label_long'] == 0.0])
            scale_weight = (losses / wins) * 1.5 if wins > 0 else 1.0
            
            print(f"  [LONG] Samples: {len(long_df)} | Base Win Rate: {(wins/len(long_df))*100:.1f}%")
            
            if wins > 0 and losses > 0:
                X = long_df.drop(columns=['target_label_long', 'target_label_short', 'primary_long_signal', 'primary_short_signal'])
                y = long_df['target_label_long']
                
                X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42, shuffle=False)
                
                base_long = xgb.XGBClassifier(n_estimators=300, learning_rate=0.01, max_depth=3, subsample=0.8, colsample_bytree=0.8, objective='binary:logistic', scale_pos_weight=scale_weight)
                calibrated_long = CalibratedClassifierCV(estimator=base_long, method='isotonic', cv=3)
                calibrated_long.fit(X_train, y_train)
                
                y_pred_proba = calibrated_long.predict_proba(X_test)[:, 1]
                
                best_thresh, best_prec, best_trades = 0.50, 0.0, 0
                for thresh in np.arange(0.35, 0.65, 0.01): 
                    y_pred_custom = (y_pred_proba >= thresh).astype(int)
                    prec = precision_score(y_test, y_pred_custom, zero_division=0) * 100
                    trades = sum(y_pred_custom)
                    if prec >= 50.0 and trades >= 1:
                        if thresh > best_thresh or best_prec == 0.0:
                            best_thresh, best_prec, best_trades = thresh, prec, trades
                            
                asset_brain['LONG'] = {'model': calibrated_long, 'threshold': best_thresh}
                print(f"  -> LONG Calibrated. Base Threshold: {best_thresh*100:.1f}%")

        # --- TRAIN SHORT MODEL ---
        short_df = df[df['primary_short_signal'] == 1].copy()
        if len(short_df) > 20:
            wins = len(short_df[short_df['target_label_short'] == 1.0])
            losses = len(short_df[short_df['target_label_short'] == 0.0])
            scale_weight = (losses / wins) * 1.5 if wins > 0 else 1.0
            
            print(f"  [SHORT] Samples: {len(short_df)} | Base Win Rate: {(wins/len(short_df))*100:.1f}%")
            
            if wins > 0 and losses > 0:
                X = short_df.drop(columns=['target_label_long', 'target_label_short', 'primary_long_signal', 'primary_short_signal'])
                y = short_df['target_label_short']
                
                X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42, shuffle=False)
                
                base_short = xgb.XGBClassifier(n_estimators=300, learning_rate=0.01, max_depth=3, subsample=0.8, colsample_bytree=0.8, objective='binary:logistic', scale_pos_weight=scale_weight)
                calibrated_short = CalibratedClassifierCV(estimator=base_short, method='isotonic', cv=3)
                calibrated_short.fit(X_train, y_train)
                
                y_pred_proba = calibrated_short.predict_proba(X_test)[:, 1]
                
                best_thresh, best_prec, best_trades = 0.50, 0.0, 0
                for thresh in np.arange(0.35, 0.65, 0.01): 
                    y_pred_custom = (y_pred_proba >= thresh).astype(int)
                    prec = precision_score(y_test, y_pred_custom, zero_division=0) * 100
                    trades = sum(y_pred_custom)
                    if prec >= 50.0 and trades >= 1:
                        if thresh > best_thresh or best_prec == 0.0:
                            best_thresh, best_prec, best_trades = thresh, prec, trades
                            
                asset_brain['SHORT'] = {'model': calibrated_short, 'threshold': best_thresh}
                print(f"  -> SHORT Calibrated. Base Threshold: {best_thresh*100:.1f}%")

        if asset_brain:
            safe_filename = asset.replace("/", "_") + "_brain.pkl"
            joblib.dump(asset_brain, safe_filename)
            print(f"  [SUCCESS] Saved Dual-Brain for {asset}.")

    print("\n==================================================")
    print(" V5 Meta-Model Training Complete.")
    print("==================================================")

if __name__ == "__main__":
    train_dual_meta_models()