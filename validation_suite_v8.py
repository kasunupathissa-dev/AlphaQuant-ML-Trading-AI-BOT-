import pandas as pd
import numpy as np
import joblib
from sklearn.model_selection import TimeSeriesSplit
from sklearn.calibration import CalibratedClassifierCV
from sklearn.metrics import classification_report
from sklearn.base import BaseEstimator, ClassifierMixin, clone
from sklearn.model_selection import cross_val_predict
from sklearn.isotonic import IsotonicRegression
import xgboost as xgb
import warnings
import config

# 🟢 V8.1 Upgrade for V8 Shotgun Pipeline (Robustness Fix)
from database_config import get_db_engine

warnings.filterwarnings("ignore", category=UserWarning)

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

class QuantValidationSuiteV8:
    def __init__(self):
        print("==================================================")
        print(f"  ALPHAQUANT: WALK-FORWARD VALIDATION ({config.TIMEFRAME}) ")
        print("==================================================")
        self.engine = get_db_engine()
        self.table_name = f"feature_store_{config.TIMEFRAME}"

    def run_all_checks(self):
        if self.engine is None: return

        for asset in config.TARGET_ASSETS:
            print(f"\n{'='*20} VALIDATING: {asset} {'='*20}")
            
            safe_filename = asset.replace("/", "_") + "_brain.pkl"
            try:
                brain_data = joblib.load(safe_filename)
            except FileNotFoundError:
                print(f"[INFO] Brain file '{safe_filename}' not found. Skipping validation.")
                continue

            if 'model' not in brain_data or 'features' not in brain_data:
                print(f"[WARNING] Incompatible brain format in '{safe_filename}'. Skipping validation.")
                continue

            self.walk_forward_validation(brain_data, asset)

    def walk_forward_validation(self, brain_data, asset):
        print(f"\n[CHECK 1/1] Walk-Forward Validation for Calibrated Model on {asset}...")
        
        query = f"SELECT * FROM {self.table_name} WHERE asset = '{asset}'"
        df = pd.read_sql(query, self.engine)
        
        # Load only triggered binary signals rows
        df = df[df['target_label'].isin([0, 1])].copy()
        df['target_label'] = df['target_label'].astype(int)

        # Meta-labeling datasets are smaller since they only look at triggers. Adjust sample count checks.
        min_samples = 200 if config.TIMEFRAME == "15m" else 50
        if len(df) < min_samples: 
            print(f"  -> Not enough triggered sample data for robust walk-forward analysis. Have {len(df)}, need {min_samples}.")
            print("-" * 50)
            return

        features = brain_data['features']

        # ===================================================================
        # 🛡️ PIPELINE GUARDRAILS (Suggestion 5) — Fail Fast on Silent Bugs
        # ===================================================================
        # Guard 1: ADX non-negative check (catches DM sign inversion regression)
        if 'adx_14' in df.columns:
            neg_adx = (df['adx_14'] < 0).sum()
            assert neg_adx == 0, f"[GUARDRAIL FAIL] CRITICAL: {neg_adx} negative ADX values detected for {asset}! Check minus_dm sign in feature_library.py."

        # Guard 2: Label starvation check (catches NaN sentinel regression)
        if 'target_label' in df.columns:
            total_rows_raw = len(pd.read_sql(f"SELECT * FROM {self.table_name} WHERE asset = '{asset}'", self.engine))
            triggered_rows = len(df)
            nan_pct = 1.0 - (triggered_rows / max(total_rows_raw, 1))
            assert nan_pct < 0.97, f"[GUARDRAIL FAIL] CRITICAL: {nan_pct:.1%} of labels are NaN/ignored for {asset}! Possible label starvation — check label_generator NaN sentinel."

        # Guard 3: Infinite value check (catches divide-by-zero regressions)
        inf_mask = df[features].isin([np.inf, -np.inf]).any(axis=1)
        inf_count = inf_mask.sum()
        assert inf_count == 0, f"[GUARDRAIL FAIL] CRITICAL: {inf_count} rows with Inf values in features for {asset}! Check feature_library.py."

        # Guard 4: Feature schema alignment (catches brain/feature-store version mismatch)
        missing_features = set(features) - set(df.columns)
        assert len(missing_features) == 0, f"[GUARDRAIL FAIL] CRITICAL: Brain feature mismatch for {asset}! Missing columns: {missing_features}. Re-run pipeline."

        print(f"  [✅ GUARDRAILS PASSED] ADX, Labels, Inf Values, Schema — all clean for {asset}.")
        # ===================================================================

        X = df[features]
        y = df['target_label']

        tscv = TimeSeriesSplit(n_splits=5)
        all_reports = []
        all_briers = []

        for i, (train_index, test_index) in enumerate(tscv.split(X)):
            X_train, X_test = X.iloc[train_index], X.iloc[test_index]
            y_train, y_test = y.iloc[train_index], y.iloc[test_index]

            if len(X_train) < 30 or len(X_test) < 10:
                print(f"  --- Fold {i+1}/5: Skipping due to insufficient fold samples ---")
                continue
            
            # Re-train calibrated model on the training fold
            base_model = xgb.XGBClassifier(
                objective='binary:logistic',
                n_estimators=300,
                learning_rate=0.05,
                max_depth=4,
                subsample=0.8,
                colsample_bytree=0.8,
                eval_metric='logloss'
            )
            model = CalibratedClassifierCV(estimator=base_model, method='isotonic', cv=3)
            
            class_weights = y_train.value_counts(normalize=True)
            weights = y_train.apply(lambda x: 1 / class_weights[x])
            
            model.fit(X_train, y_train, sample_weight=weights)

            y_pred = model.predict(X_test)
            y_prob = model.predict_proba(X_test)
            
            report = classification_report(y_test, y_pred, labels=[0, 1], target_names=['FAILURE', 'SUCCESS'], output_dict=True, zero_division=0)
            all_reports.append(report)
            
            brier = multiclass_brier_score(y_test.values, y_prob)
            all_briers.append(brier)

            print(f"  --- Fold {i+1}/5 ---")
            print(f"    Brier Score: {brier:.4f}")
            print(f"    Precision (SUCCESS): {report['SUCCESS']['precision']:.2f} | Support: {report['SUCCESS']['support']}")
            print(f"    Precision (FAILURE): {report['FAILURE']['precision']:.2f} | Support: {report['FAILURE']['support']}")

        if all_reports:
            avg_success_precision = np.mean([r['SUCCESS']['precision'] for r in all_reports])
            avg_failure_precision = np.mean([r['FAILURE']['precision'] for r in all_reports])
            avg_brier = np.mean(all_briers)
            
            print("\n  -> Average Walk-Forward Results:")
            print(f"     - Avg Binary Brier Score: {avg_brier:.4f}")
            print(f"     - Avg Precision (SUCCESS): {avg_success_precision:.2f}")
            print(f"     - Avg Precision (FAILURE): {avg_failure_precision:.2f}")
        else:
            print("  -> Could not complete any walk-forward splits.")
        print("-" * 50)

if __name__ == "__main__":
    suite = QuantValidationSuiteV8()
    suite.run_all_checks()
