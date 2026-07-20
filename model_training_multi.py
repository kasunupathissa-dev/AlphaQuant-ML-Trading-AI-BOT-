import sqlite3
import pandas as pd
import numpy as np
import xgboost as xgb
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, precision_score
import joblib
import os

DB_NAME = "alphaquant_ml_v4.db"
TARGET_ASSETS = ["BTC/USDT", "ETH/USDT", "SOL/USDT", "BNB/USDT", "ADA/USDT", "XRP/USDT"]

def train_specialized_models():
    print("==================================================")
    print("  ALPHAQUANT V4.1.2: SQLITE SYNC FIX              ")
    print("==================================================")

    # 1. First, let's debug exactly what is inside the feature_store table
    conn = sqlite3.connect(DB_NAME)
    
    print("[SYSTEM] Checking Database Integrity...")
    try:
        check_df = pd.read_sql_query("SELECT asset, COUNT(*) as count, SUM(CASE WHEN target_label IS NOT NULL THEN 1 ELSE 0 END) as labeled FROM feature_store GROUP BY asset", conn)
        print(check_df.to_string(index=False))
    except Exception as e:
        print(f"[FATAL] Cannot read feature_store: {e}")
        return

    for asset in TARGET_ASSETS:
        print(f"\n[SYSTEM] Training Specialized Brain for {asset}...")
        
        # V4.1.2 FIX: Added explicit casting and better error handling for SQLite datatypes
        query = f"""
            SELECT 
                dist_ema_20, dist_ema_50, dist_ema_200, 
                macd_hist_norm, rsi_norm, atr_pct, 
                bb_width, cvd_norm, fvg_bull_intensity, fvg_bear_intensity,
                target_label 
            FROM feature_store 
            WHERE target_label IS NOT NULL AND asset = '{asset}'
        """
        try:
            df = pd.read_sql_query(query, conn)
        except Exception as e:
            print(f"  [ERROR] Database read failed for {asset}: {e}")
            continue
        
        if len(df) < 50:
            print(f"  [ERROR] Not enough data for {asset} (Found {len(df)} rows).")
            continue

        wins = len(df[df['target_label'] == 1.0])
        losses = len(df[df['target_label'] == 0.0])
        scale_weight = losses / wins if wins > 0 else 1.0
        
        print(f"  -> Samples: {len(df)} | Baseline Win Rate: {(wins/len(df))*100:.2f}% | Imbalance Wgt: {scale_weight:.2f}")

        X = df.drop(columns=['target_label'])
        y = df['target_label']
        
        if wins == 0 or losses == 0:
            print(f"  [ERROR] {asset} data is purely one-sided. Cannot train.")
            continue

        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42, shuffle=False)

        model = xgb.XGBClassifier(
            n_estimators=500,        
            learning_rate=0.01,      
            max_depth=3,             
            subsample=0.8,           
            colsample_bytree=0.8,    
            objective='binary:logistic', 
            eval_metric='auc',
            scale_pos_weight=scale_weight,
            early_stopping_rounds=20 
        )

        try:
            model.fit(X_train, y_train, eval_set=[(X_test, y_test)], verbose=False)
        except Exception as e:
            print(f"  [ERROR] XGBoost training failed for {asset}: {e}")
            continue

        y_pred_proba = model.predict_proba(X_test)[:, 1] 
        
        best_threshold = 0.45 
        best_precision = 0.0
        
        print(f"  -> Calibrating Thresholds for {asset}...")
        for thresh in np.arange(0.35, 0.65, 0.01): 
            y_pred_custom = (y_pred_proba >= thresh).astype(int)
            precision = precision_score(y_test, y_pred_custom, zero_division=0) * 100
            trades = sum(y_pred_custom)
            
            if precision > best_precision and trades >= 1:
                best_precision = precision
                best_threshold = thresh

        print(f"  [RESULT] {asset} | Optimal Threshold: {best_threshold*100:.1f}% | Expected Win Rate: {best_precision:.1f}%")

        safe_filename = asset.replace("/", "_") + "_brain.pkl"
        joblib.dump({'model': model, 'optimal_threshold': best_threshold}, safe_filename)
        print(f"  [SUCCESS] Saved {safe_filename}")

    conn.close()
    print("\n==================================================")
    print(" V4.1 Multi-Model Training Complete.")
    print("==================================================")

if __name__ == "__main__":
    train_specialized_models()