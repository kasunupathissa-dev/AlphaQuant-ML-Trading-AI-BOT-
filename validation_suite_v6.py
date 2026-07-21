import pandas as pd
import numpy as np
import joblib
import xgboost as xgb
import lightgbm as lgb
from sklearn.model_selection import train_test_split, TimeSeriesSplit
from sklearn.metrics import precision_score
from statsmodels.stats.proportion import proportion_confint
import warnings

# 🟢 V6.3 Upgrade: Use the centralized database configuration
from database_config import get_db_engine

warnings.filterwarnings("ignore", category=UserWarning)

TARGET_ASSETS = ["BTC/USDT", "ETH/USDT", "SOL/USDT", "BNB/USDT", "ADA/USDT", "XRP/USDT", "LINK/USDT", "AVAX/USDT", "DOGE/USDT", "DOT/USDT"]
LOG_FILE = "trading_log_v5.csv" 

class QuantValidationSuiteV6:
    def __init__(self):
        print("==================================================")
        print("  ALPHAQUANT V6.3: FINAL VALIDATION SUITE       ")
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
                print(f"[ERROR] Brain file '{safe_filename}' not found.")
                continue

            self.check_1_calibration_curve(brain_data, asset)
            self.check_4_walk_forward_validation(asset)

    def check_1_calibration_curve(self, brain_data, asset):
        print("\n[CHECK 1/2] Reliability Curve Analysis...")
        
        query = f"SELECT * FROM feature_store WHERE asset = '{asset}'"
        df = pd.read_sql(query, self.engine)
        if len(df) < 50: return

        for model_key, model_info in brain_data.items():
            signal_type, direction = model_key.split('_')
            primary_col = f"primary_{signal_type.lower()}_{direction.lower()}"
            target_col = f"target_label_{direction.lower()}"

            signal_df = df[df[primary_col] == 1]
            if len(signal_df) < 20: continue

            print(f"\n  -> Calibrating {model_key} Model:")
            
            X = signal_df.drop(columns=[c for c in signal_df.columns if 'primary_' in c or 'target_' in c or c in ['id', 'asset', 'timestamp']])
            y = signal_df[target_col]
            _, X_test, _, y_test = train_test_split(X, y, test_size=0.2, random_state=42, shuffle=False)

            if len(X_test) == 0: continue

            xgb_proba = model_info['xgb_model'].predict_proba(X_test)[:, 1]
            lgb_proba = model_info['lgb_model'].predict_proba(X_test)[:, 1]
            y_pred_proba = (xgb_proba + lgb_proba) / 2.0

            print(f"  {'Prob Bin':<12} | {'Actual Win Rate':<18} | {'Trades':<8}")
            print(f"  {'-'*12} | {'-'*18} | {'-'*8}")

            for i in np.arange(0.5, 0.8, 0.05):
                mask = (y_pred_proba >= i) & (y_pred_proba < i + 0.05)
                if np.sum(mask) > 0:
                    actual_win_rate = y_test[mask].mean() * 100
                    print(f"  {i*100:.0f}% - {i*100+5:.0f}%    | {actual_win_rate:12.1f}%        | {np.sum(mask):<8}")
        print("-" * 50)

    def check_4_walk_forward_validation(self, asset):
        print("\n[CHECK 2/2] Walk-Forward Validation...")
        
        query = f"SELECT * FROM feature_store WHERE asset = '{asset}'"
        df = pd.read_sql(query, self.engine)
        if len(df) < 500: 
            print("  -> Not enough data for robust walk-forward analysis.")
            print("-" * 50)
            return

        tscv = TimeSeriesSplit(n_splits=5)
        results = {}

        for model_key_template in ["TREND_LONG", "TREND_SHORT", "BREAKOUT_LONG", "BREAKOUT_SHORT", "REVERSION_LONG", "REVERSION_SHORT"]:
            signal_type, direction = model_key_template.split('_')
            primary_col = f"primary_{signal_type.lower()}_{direction.lower()}"
            target_col = f"target_label_{direction.lower()}"
            
            signal_df = df[df[primary_col] == 1]
            if len(signal_df) < 50: continue

            all_precisions = []
            for train_index, test_index in tscv.split(signal_df):
                train, test = signal_df.iloc[train_index], signal_df.iloc[test_index]
                
                if len(train) < 20 or len(test) < 5: continue

                X_train = train.drop(columns=[c for c in train.columns if 'primary_' in c or 'target_' in c or c in ['id', 'asset', 'timestamp']])
                y_train = train[target_col]
                X_test = test.drop(columns=[c for c in test.columns if 'primary_' in c or 'target_' in c or c in ['id', 'asset', 'timestamp']])
                y_test = test[target_col]
                
                if y_train.nunique() < 2: continue

                xgb_model = xgb.XGBClassifier(n_estimators=100, objective='binary:logistic')
                lgb_model = lgb.LGBMClassifier(n_estimators=100, objective='binary')
                
                xgb_model.fit(X_train, y_train)
                lgb_model.fit(X_train, y_train)

                y_pred_xgb = xgb_model.predict_proba(X_test)[:, 1]
                y_pred_lgb = lgb_model.predict_proba(X_test)[:, 1]
                y_pred_ensemble = (y_pred_xgb + y_pred_lgb) / 2.0
                
                y_pred = (y_pred_ensemble >= 0.5).astype(int)
                all_precisions.append(precision_score(y_test, y_pred, zero_division=0))

            if all_precisions:
                avg_precision = np.mean(all_precisions) * 100
                # 🟢 V6.3 FIX: Replace emoji with plain text for Windows compatibility
                verdict = "PASS" if avg_precision >= 50.0 else "FAIL"
                results[model_key_template] = f"{verdict} ({avg_precision:.1f}%)"

        if results:
            print("  -> Average Walk-Forward Win Rates:")
            for model_type, result in results.items():
                print(f"     - {model_type:<18}: {result}")
        else:
            print("  -> Could not complete any walk-forward splits.")
        print("-" * 50)

if __name__ == "__main__":
    suite = QuantValidationSuiteV6()
    suite.run_all_checks()