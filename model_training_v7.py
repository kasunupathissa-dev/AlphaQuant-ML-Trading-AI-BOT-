import pandas as pd
import numpy as np
import xgboost as xgb
from sklearn.model_selection import train_test_split
from sklearn.calibration import CalibratedClassifierCV, calibration_curve
from sklearn.metrics import classification_report
import joblib
import os
import json
import config

# 🟢 V7.2 Upgrade for V8 Shotgun Pipeline (Cleanup)
from database_config import get_db_engine

def multiclass_brier_score(y_true, y_prob):
    """
    Computes the multiclass Brier Score (MSE of predicted probabilities vs one-hot true targets).
    """
    num_classes = y_prob.shape[1]
    y_true_one_hot = np.eye(num_classes)[y_true]
    return np.mean(np.sum((y_prob - y_true_one_hot) ** 2, axis=1))

def train_shotgun_models():
    print("==================================================")
    print(f"  ALPHAQUANT: SHOTGUN CALIBRATED TRAINING ({config.TIMEFRAME}) ")
    print("==================================================")

    engine = get_db_engine()
    if engine is None: return
    table_name = f"feature_store_{config.TIMEFRAME}"

    for asset in config.TARGET_ASSETS:
        print(f"\n{'='*15} Training Shotgun Model for {asset} {'='*15}")
        
        query = f"SELECT * FROM {table_name} WHERE asset = '{asset}'"
        try:
            df = pd.read_sql(query, engine)
        except Exception as e:
            print(f"  [ERROR] DB Read failed: {e}")
            continue
        
        df.dropna(subset=['target_label'], inplace=True)
        df = df[df['target_label'] != 2].copy()
        df['target_label'] = df['target_label'].astype(int)
        
        if len(df) < 100 or df['target_label'].nunique() < 2:
            print(f"  [SKIP] Insufficient or non-diverse data for {asset}. Skipping.")
            continue

        features = ['dist_ema_50', 'dist_ema_200', 'atr_pct', 'volume_zscore', 'adx_14', 'bb_width', 'funding_rate_zscore', 'oi_zscore']
        X = df[features]
        y = df['target_label']

        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42, stratify=y)

        class_weights = y_train.value_counts(normalize=True)
        weights = y_train.apply(lambda x: 1 / class_weights[x])

        base_model = xgb.XGBClassifier(
            objective='binary:logistic',
            n_estimators=500,
            learning_rate=0.05,
            max_depth=4,
            subsample=0.8,
            colsample_bytree=0.8,
            eval_metric='logloss'
        )

        # Wrap in calibration model (Isotonic Regression)
        model = CalibratedClassifierCV(estimator=base_model, method='isotonic', cv=3)
        model.fit(X_train, y_train, sample_weight=weights)

        # Predict probabilities
        y_prob = model.predict_proba(X_test)
        y_pred = model.predict(X_test)

        # Calculate Brier Score
        brier = multiclass_brier_score(y_test.values, y_prob)
        print(f"  [CALIBRATION] Multiclass Brier Score: {brier:.4f}")

        # Calibration Curves (Reliability Check)
        try:
            # LONG Class calibration
            true_l, pred_l = calibration_curve(y_test == 1, y_prob[:, 1], n_bins=5)
            print("  [CALIBRATION] LONG class reliability (Predicted vs True):")
            for p_pred, p_true in zip(pred_l, true_l):
                print(f"    - Pred Prob: {p_pred:.2f} ==> True Freq: {p_true:.2f}")
                
            # SHORT Class calibration
            true_s, pred_s = calibration_curve(y_test == 0, y_prob[:, 0], n_bins=5)
            print("  [CALIBRATION] SHORT class reliability (Predicted vs True):")
            for p_pred, p_true in zip(pred_s, true_s):
                print(f"    - Pred Prob: {p_pred:.2f} ==> True Freq: {p_true:.2f}")
        except Exception as ce:
            print(f"  [WARNING] Could not compute complete reliability curve bins: {ce}")

        print("\n--- Model Performance on Test Set ---")
        print(classification_report(y_test, y_pred, labels=[0, 1], target_names=['SHORT', 'LONG'], zero_division=0))
        
        brain = {
            'model': model,
            'features': features
        }

        safe_filename = asset.replace("/", "_") + "_brain.pkl"
        joblib.dump(brain, safe_filename)
        print(f"\n  [SUCCESS] Saved Shotgun Calibrated Brain to {safe_filename}")

        # 🟢 V8.4 Upgrade: Weekly Calibration Drift Tracking
        metadata_file = "model_metadata.json"
        metadata = {}
        if os.path.exists(metadata_file):
            try:
                with open(metadata_file, "r") as f:
                    metadata = json.load(f)
            except Exception:
                pass
                
        metadata_entry = {
            'last_trained': str(pd.Timestamp.now()),
            'brier_score': float(brier),
            'long_reliability': [],
            'short_reliability': []
        }
        
        try:
            true_l, pred_l = calibration_curve(y_test == 1, y_prob[:, 1], n_bins=5)
            for p_pred, p_true in zip(pred_l, true_l):
                metadata_entry['long_reliability'].append({'pred': float(p_pred), 'true': float(p_true)})
                
            true_s, pred_s = calibration_curve(y_test == 0, y_prob[:, 0], n_bins=5)
            for p_pred, p_true in zip(pred_s, true_s):
                metadata_entry['short_reliability'].append({'pred': float(p_pred), 'true': float(p_true)})
        except Exception:
            pass
            
        metadata[asset] = metadata_entry
        try:
            with open(metadata_file, "w") as f:
                json.dump(metadata, f, indent=4)
            print(f"  [METADATA] Updated weekly calibration metadata in {metadata_file}")
        except Exception as me_err:
            print(f"  [WARNING] Failed to write calibration metadata: {me_err}")

    print("\n==================================================")
    print(f" Shotgun Model Training Complete ({config.TIMEFRAME}).")
    print("==================================================")

if __name__ == "__main__":
    train_shotgun_models()