import pandas as pd
import numpy as np
import joblib
from sklearn.model_selection import TimeSeriesSplit
from sklearn.metrics import classification_report
import warnings

# 🟢 V8.1 Upgrade for V8 Shotgun Pipeline (Robustness Fix)
from database_config import get_db_engine

warnings.filterwarnings("ignore", category=UserWarning)

TARGET_ASSETS = ["BTC/USDT", "ETH/USDT", "SOL/USDT", "BNB/USDT", "ADA/USDT", "XRP/USDT", "LINK/USDT", "AVAX/USDT", "DOGE/USDT", "DOT/USDT"]

class QuantValidationSuiteV8:
    def __init__(self):
        print("==================================================")
        print("  ALPHAQUANT V8.1: ROBUST VALIDATION SUITE      ")
        print("==================================================")
        self.engine = get_db_engine()

    def run_all_checks(self):
        if self.engine is None: return

        for asset in TARGET_ASSETS:
            print(f"\n{'='*20} VALIDATING: {asset} {'='*20}")
            
            safe_filename = asset.replace("/", "_") + "_brain.pkl"
            try:
                brain_data = joblib.load(safe_filename)
            except FileNotFoundError:
                print(f"[INFO] Brain file '{safe_filename}' not found (likely skipped during training). Skipping validation.")
                continue

            # 🟢 V8.1 FIX: Check for brain format compatibility before proceeding
            if 'model' not in brain_data or 'features' not in brain_data:
                print(f"[WARNING] Incompatible or old brain format in '{safe_filename}'. This asset was likely not retrained. Skipping validation.")
                continue

            self.walk_forward_validation(brain_data, asset)

    def walk_forward_validation(self, brain_data, asset):
        print("\n[CHECK 1/1] Walk-Forward Validation for Shotgun Model...")
        
        query = f"SELECT * FROM feature_store WHERE asset = '{asset}'"
        df = pd.read_sql(query, self.engine)
        df.dropna(subset=['target_label'], inplace=True)
        df['target_label'] = df['target_label'].astype(int)

        if len(df) < 500: 
            print("  -> Not enough data for robust walk-forward analysis.")
            print("-" * 50)
            return

        features = brain_data['features']
        X = df[features]
        y = df['target_label']

        tscv = TimeSeriesSplit(n_splits=5)
        all_reports = []

        for i, (train_index, test_index) in enumerate(tscv.split(X)):
            print(f"  --- Fold {i+1}/5 ---")
            X_train, X_test = X.iloc[train_index], X.iloc[test_index]
            y_train, y_test = y.iloc[train_index], y.iloc[test_index]

            if len(X_train) < 100 or len(X_test) < 20:
                print("  -> Skipping fold due to insufficient data.")
                continue
            
            # Re-train model on the training fold
            model = brain_data['model']
            model.fit(X_train, y_train)

            y_pred = model.predict(X_test)
            
            report = classification_report(y_test, y_pred, target_names=['SHORT', 'LONG', 'HOLD'], output_dict=True, zero_division=0)
            all_reports.append(report)

            print(f"    Precision (LONG): {report['LONG']['precision']:.2f}")
            print(f"    Precision (SHORT): {report['SHORT']['precision']:.2f}")
            print(f"    Trades (LONG): {report['LONG']['support']}")
            print(f"    Trades (SHORT): {report['SHORT']['support']}")

        if all_reports:
            avg_long_precision = np.mean([r['LONG']['precision'] for r in all_reports])
            avg_short_precision = np.mean([r['SHORT']['precision'] for r in all_reports])
            
            print("\n  -> Average Walk-Forward Results:")
            print(f"     - Avg Precision (LONG): {avg_long_precision:.2f}")
            print(f"     - Avg Precision (SHORT): {avg_short_precision:.2f}")
        else:
            print("  -> Could not complete any walk-forward splits.")
        print("-" * 50)

if __name__ == "__main__":
    suite = QuantValidationSuiteV8()
    suite.run_all_checks()