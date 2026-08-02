import pandas as pd
import numpy as np
import xgboost as xgb
from sklearn.model_selection import train_test_split, cross_val_predict
from sklearn.calibration import calibration_curve
from sklearn.metrics import classification_report
from sklearn.base import BaseEstimator, ClassifierMixin, clone
from sklearn.isotonic import IsotonicRegression
import joblib
import os
import json
import config

# 🟢 V7.2 Upgrade for V8 Shotgun Pipeline (Cleanup)
from database_config import get_db_engine

class ManualCalibratedClassifier(BaseEstimator, ClassifierMixin):
    def __init__(self, estimator, cv=3):
        self.estimator = estimator
        self.cv = cv
        
    def fit(self, X, y, sample_weight=None):
        self.classes_ = np.unique(y)
        n_classes = len(self.classes_)
        
        fit_params = {}
        if sample_weight is not None:
            fit_params['sample_weight'] = sample_weight
            
        this_estimator = clone(self.estimator)
        oof_probs = cross_val_predict(
            this_estimator, X, y, cv=self.cv,
            method='predict_proba', params=fit_params
        )
        
        self.estimator_ = clone(self.estimator)
        if sample_weight is not None:
            self.estimator_.fit(X, y, sample_weight=sample_weight)
        else:
            self.estimator_.fit(X, y)
            
        self.calibrators_ = []
        for i, c in enumerate(self.classes_):
            y_bin = (y == c).astype(int)
            calibrator = IsotonicRegression(out_of_bounds='clip')
            calibrator.fit(oof_probs[:, i], y_bin)
            self.calibrators_.append(calibrator)
            
        return self
        
    def predict_proba(self, X):
        raw_probs = self.estimator_.predict_proba(X)
        calibrated_probs = np.zeros_like(raw_probs)
        
        for i, calibrator in enumerate(self.calibrators_):
            calibrated_probs[:, i] = calibrator.predict(raw_probs[:, i])
            
        row_sums = calibrated_probs.sum(axis=1, keepdims=True)
        row_sums[row_sums == 0] = 1.0
        calibrated_probs = calibrated_probs / row_sums
        return calibrated_probs
        
    def predict(self, X):
        probs = self.predict_proba(X)
        return self.classes_[np.argmax(probs, axis=1)]

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
        
        # Only select rows with binary meta-labels (0 = failure, 1 = success)
        df = df[df['target_label'].isin([0, 1])].copy()
        df['target_label'] = df['target_label'].astype(int)
        
        if len(df) < 50 or df['target_label'].nunique() < 2:
            print(f"  [SKIP] Insufficient or non-diverse triggered signals data for {asset} (Rows: {len(df)}). Skipping.")
            continue

        # Expanded Technical Indicator Pool (DTIP) + Chop Index
        features = [
            'dist_ema_50', 'dist_ema_200', 'atr_pct', 'volume_zscore', 'adx_14', 'bb_width',
            'funding_rate_zscore', 'oi_zscore', 'rsi_14', 'macd_hist', 'supertrend_direction', 'chop_index'
        ]
        X = df[features]
        y = df['target_label']

        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42, stratify=y)

        class_weights = y_train.value_counts(normalize=True)
        weights = y_train.apply(lambda x: 1 / class_weights[x])
        
        print(f"  [DEBUG] Weight range: min={weights.min():.2f}, max={weights.max():.2f}")
        print(f"  [DEBUG] Class distribution in y_train: {y_train.value_counts().to_dict()}")

        objective = 'binary:logistic'
        eval_metric = 'logloss'

        base_model = xgb.XGBClassifier(
            objective=objective,
            n_estimators=500,
            learning_rate=0.05,
            max_depth=4,
            subsample=0.8,
            colsample_bytree=0.8,
            eval_metric=eval_metric,
            random_state=42
        )

        # Wrap in calibration model (Isotonic Regression)
        model = ManualCalibratedClassifier(estimator=base_model, cv=3)
        model.fit(X_train, y_train, sample_weight=weights)

        # Predict probabilities
        y_prob = model.predict_proba(X_test)
        y_pred = model.predict(X_test)

        # Calculate Brier Score
        brier = multiclass_brier_score(y_test.values, y_prob)
        print(f"  [CALIBRATION] Binary Brier Score: {brier:.4f}")

        # Calibration Curves (Reliability Check)
        try:
            # SUCCESS (Class 1) calibration curve
            true_l, pred_l = calibration_curve(y_test == 1, y_prob[:, 1], n_bins=5)
            print("  [CALIBRATION] SUCCESS class reliability (Predicted vs True):")
            for p_pred, p_true in zip(pred_l, true_l):
                print(f"    - Pred Prob: {p_pred:.2f} ==> True Freq: {p_true:.2f}")
        except Exception as ce:
            print(f"  [WARNING] Could not compute complete reliability curve bins: {ce}")

        print("\n--- Model Performance on Test Set ---")
        print(classification_report(y_test, y_pred, labels=[0, 1], target_names=['FAILURE', 'SUCCESS'], zero_division=0))
        
        brain = {
            'model': model,
            'features': features
        }

        safe_filename = asset.replace("/", "_") + "_brain.pkl"
        joblib.dump(brain, safe_filename)
        print(f"\n  [SUCCESS] Saved Shotgun Calibrated Brain to {safe_filename}")

        # Weekly Calibration Drift Tracking
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
            'success_reliability': []
        }
        
        try:
            true_l, pred_l = calibration_curve(y_test == 1, y_prob[:, 1], n_bins=5)
            for p_pred, p_true in zip(pred_l, true_l):
                metadata_entry['success_reliability'].append({'pred': float(p_pred), 'true': float(p_true)})
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
