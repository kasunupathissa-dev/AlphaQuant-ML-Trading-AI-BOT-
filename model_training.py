import sqlite3
import pandas as pd
import numpy as np
import xgboost as xgb
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, precision_score, recall_score
import joblib

DB_NAME = "alphaquant_ml_v4.db"
MODEL_FILENAME = "xgboost_v4_model.pkl"

def train_xgboost_model():
    print("==================================================")
    print("  ALPHAQUANT V4.0.4: THRESHOLD CALIBRATION        ")
    print("==================================================")

    conn = sqlite3.connect(DB_NAME)
    query = """
        SELECT 
            dist_ema_20, dist_ema_50, dist_ema_200, 
            macd_hist_norm, rsi_norm, atr_pct, 
            bb_width, cvd_norm, fvg_bull_intensity, fvg_bear_intensity,
            target_label 
        FROM feature_store 
        WHERE target_label IS NOT NULL
    """
    df = pd.read_sql_query(query, conn)
    conn.close()

    if df.empty: return

    wins = len(df[df['target_label'] == 1.0])
    losses = len(df[df['target_label'] == 0.0])
    scale_weight = losses / wins if wins > 0 else 1.0

    X = df.drop(columns=['target_label'])
    y = df['target_label']
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42, shuffle=False)

    model = xgb.XGBClassifier(
        n_estimators=1000,       
        learning_rate=0.01,      
        max_depth=4,             
        subsample=0.8,           
        colsample_bytree=0.8,    
        objective='binary:logistic', 
        eval_metric='auc',
        scale_pos_weight=scale_weight,
        early_stopping_rounds=50 
    )

    model.fit(X_train, y_train, eval_set=[(X_test, y_test)], verbose=False)

    y_pred_proba = model.predict_proba(X_test)[:, 1] 
    
    # 🟢 V4.0.4: Let's find the sweet spot threshold mathematically
    print("\n[AI INSIGHT] Threshold Calibration Testing...")
    print(f"{'Threshold':<12} | {'Precision (Win Rate)':<25} | {'Trades Taken':<15}")
    print("-" * 55)
    
    best_threshold = 0.50
    
    for thresh in np.arange(0.45, 0.65, 0.01):
        y_pred_custom = (y_pred_proba >= thresh).astype(int)
        precision = precision_score(y_test, y_pred_custom, zero_division=0) * 100
        trades_taken = sum(y_pred_custom)
        print(f"{thresh*100:>5.1f}%       | {precision:>20.2f}%      | {trades_taken:>10}")
        
    print("-" * 55)
    
    # We'll save the model anyway, it works, we just need to know how to interpret it
    joblib.dump(model, MODEL_FILENAME)
    print(f"[SUCCESS] AI Brain saved to disk.")

if __name__ == "__main__":
    train_xgboost_model()