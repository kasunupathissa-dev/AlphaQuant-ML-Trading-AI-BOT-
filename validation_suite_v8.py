import pandas as pd
import numpy as np
import joblib
from sklearn.model_selection import TimeSeriesSplit
from sklearn.calibration import CalibratedClassifierCV
from sklearn.metrics import classification_report
import xgboost as xgb
import warnings
import config

# 🟢 V8.1 Upgrade for V8 Shotgun Pipeline (Robustness Fix)
from database_config import get_db_engine

warnings.filterwarnings("ignore", category=UserWarning)

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
        df.dropna(subset=['target_label'], inplace=True)
        df = df[df['target_label'] != 2].copy()
        df['target_label'] = df['target_label'].astype(int)

        # Require a solid lookback context (especially on 15M where we have thousands of records)
        min_samples = 2000 if config.TIMEFRAME == "15m" else 500
        if len(df) < min_samples: 
            print(f"  -> Not enough data for robust walk-forward analysis. Have {len(df)}, need {min_samples}.")
            print("-" * 50)
            return

        features = brain_data['features']
        X = df[features]
        y = df['target_label']

        tscv = TimeSeriesSplit(n_splits=5)
        all_reports = []
        all_briers = []

        for i, (train_index, test_index) in enumerate(tscv.split(X)):
            X_train, X_test = X.iloc[train_index], X.iloc[test_index]
            y_train, y_test = y.iloc[train_index], y.iloc[test_index]

            if len(X_train) < 300 or len(X_test) < 50:
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
            
            report = classification_report(y_test, y_pred, labels=[0, 1], target_names=['SHORT', 'LONG'], output_dict=True, zero_division=0)
            all_reports.append(report)
            
            brier = multiclass_brier_score(y_test.values, y_prob)
            all_briers.append(brier)

            print(f"  --- Fold {i+1}/5 ---")
            print(f"    Brier Score: {brier:.4f}")
            print(f"    Precision (LONG): {report['LONG']['precision']:.2f} | Support: {report['LONG']['support']}")
            print(f"    Precision (SHORT): {report['SHORT']['precision']:.2f} | Support: {report['SHORT']['support']}")

        if all_reports:
            avg_long_precision = np.mean([r['LONG']['precision'] for r in all_reports])
            avg_short_precision = np.mean([r['SHORT']['precision'] for r in all_reports])
            avg_brier = np.mean(all_briers)
            
            print("\n  -> Average Walk-Forward Results:")
            print(f"     - Avg Multiclass Brier Score: {avg_brier:.4f}")
            print(f"     - Avg Precision (LONG): {avg_long_precision:.2f}")
            print(f"     - Avg Precision (SHORT): {avg_short_precision:.2f}")
        else:
            print("  -> Could not complete any walk-forward splits.")
        print("-" * 50)

if __name__ == "__main__":
    suite = QuantValidationSuiteV8()
    suite.run_all_checks()