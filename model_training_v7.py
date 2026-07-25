import pandas as pd
import numpy as np
import xgboost as xgb
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report
import joblib
import os

# 🟢 V7.2 Upgrade for V8 Shotgun Pipeline (Cleanup)
from database_config import get_db_engine

TARGET_ASSETS = ["BTC/USDT", "ETH/USDT", "SOL/USDT", "BNB/USDT", "ADA/USDT", "XRP/USDT", "LINK/USDT", "AVAX/USDT", "DOGE/USDT", "DOT/USDT"]

def train_shotgun_models():
    print("==================================================")
    print("  ALPHAQUANT V7.2: SHOTGUN MODEL TRAINING         ")
    print("==================================================")

    engine = get_db_engine()
    if engine is None: return

    for asset in TARGET_ASSETS:
        print(f"\n{'='*15} Training Shotgun Model for {asset} {'='*15}")
        
        query = f"SELECT * FROM feature_store WHERE asset = '{asset}'"
        try:
            df = pd.read_sql(query, engine)
        except Exception as e:
            print(f"  [ERROR] DB Read failed: {e}")
            continue
        
        df.dropna(subset=['target_label'], inplace=True)
        df['target_label'] = df['target_label'].astype(int)
        
        if len(df) < 100 or df['target_label'].nunique() < 3:
            print(f"  [SKIP] Insufficient or non-diverse data. Skipping asset.")
            continue

        features = ['dist_ema_50', 'dist_ema_200', 'atr_pct', 'volume_zscore', 'adx_14', 'bb_width', 'funding_rate_zscore', 'oi_zscore']
        X = df[features]
        y = df['target_label']

        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42, stratify=y)

        class_weights = y_train.value_counts(normalize=True)
        weights = y_train.apply(lambda x: 1 / class_weights[x])

        model = xgb.XGBClassifier(
            objective='multi:softprob',
            num_class=3,
            n_estimators=500,
            learning_rate=0.05,
            max_depth=4,
            subsample=0.8,
            colsample_bytree=0.8,
            eval_metric='mlogloss'
            # 🟢 V7.2 CLEANUP: Removed deprecated 'use_label_encoder'
        )

        model.fit(X_train, y_train, sample_weight=weights, verbose=False)

        print("--- Model Performance on Test Set ---")
        y_pred = model.predict(X_test)
        print(classification_report(y_test, y_pred, target_names=['SHORT', 'LONG', 'HOLD']))
        
        brain = {
            'model': model,
            'features': features
        }

        safe_filename = asset.replace("/", "_") + "_brain.pkl"
        joblib.dump(brain, safe_filename)
        print(f"\n  [SUCCESS] Saved Shotgun Brain to {safe_filename}")

    print("\n==================================================")
    print(" V7.2 Shotgun Model Training Complete.")
    print("==================================================")

if __name__ == "__main__":
    train_shotgun_models()