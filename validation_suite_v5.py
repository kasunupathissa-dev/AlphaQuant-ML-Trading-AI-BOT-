import pandas as pd
import numpy as np
import joblib
from sklearn.model_selection import train_test_split, TimeSeriesSplit
from sklearn.metrics import precision_score
from statsmodels.stats.proportion import proportion_confint
import warnings

# 🟢 V5.1 Upgrade: Use the centralized database configuration
from database_config import get_db_engine

warnings.filterwarnings("ignore", category=UserWarning)

TARGET_ASSETS = ["BTC/USDT", "ETH/USDT", "SOL/USDT", "BNB/USDT", "ADA/USDT", "XRP/USDT", "LINK/USDT", "AVAX/USDT", "DOGE/USDT", "DOT/USDT"]
LOG_FILE = "trading_log_v5.csv" 

class QuantValidationSuiteV5:
    def __init__(self):
        print("==================================================")
        print("  ALPHAQUANT V5.1: INSTITUTIONAL VALIDATION SUITE ")
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
            self.check_2_live_vs_backtest_gap(asset)
            self.check_3_statistical_significance()
            self.check_4_walk_forward_validation(asset)

    def check_1_calibration_curve(self, brain_data, asset):
        print("\n[CHECK 1/4] Reliability Curve Analysis...")
        
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
            
            X = signal_df.drop(columns=['id', 'asset', 'timestamp', 'target_label_long', 'target_label_short', 'primary_trend_long', 'primary_trend_short', 'primary_breakout_long', 'primary_breakout_short', 'primary_reversion_long', 'primary_reversion_short'])
            y = signal_df[target_col]
            _, X_test, _, y_test = train_test_split(X, y, test_size=0.2, random_state=42, shuffle=False)

            if len(X_test) == 0: continue

            y_pred_proba = model_info['model'].predict_proba(X_test)[:, 1]

            print(f"  {'Prob Bin':<12} | {'Actual Win Rate':<18} | {'Trades':<8}")
            print(f"  {'-'*12} | {'-'*18} | {'-'*8}")

            for i in np.arange(0.5, 0.8, 0.05):
                mask = (y_pred_proba >= i) & (y_pred_proba < i + 0.05)
                if np.sum(mask) > 0:
                    actual_win_rate = y_test[mask].mean() * 100
                    print(f"  {i*100:.0f}% - {i*100+5:.0f}%    | {actual_win_rate:12.1f}%        | {np.sum(mask):<8}")
        print("-" * 50)

    def check_2_live_vs_backtest_gap(self, asset):
        print("\n[CHECK 2/4] Live vs. Backtest Performance Gap...")
        try:
            live_df = pd.read_csv(LOG_FILE)
            asset_live_df = live_df[live_df['Asset'] == asset]
            if not asset_live_df.empty:
                live_wins = len(asset_live_df[asset_live_df['Status'] == 'PROFIT'])
                live_win_rate = (live_wins / len(asset_live_df)) * 100
                print(f"  -> Live Win Rate for {asset}: {live_win_rate:.1f}% ({len(asset_live_df)} trades)")
            else:
                print("  -> No live trades logged for this asset yet.")
        except FileNotFoundError:
            print("  -> Live trade log not found.")
        print("-" * 50)

    def check_3_statistical_significance(self):
        print("\n[CHECK 3/4] Statistical Significance (Wilson Score)...")
        try:
            live_df = pd.read_csv(LOG_FILE)
            if len(live_df) >= 5:
                wins = len(live_df[live_df['Status'] == 'PROFIT'])
                low, high = proportion_confint(wins, len(live_df), method='wilson')
                print(f"  -> Total Live Trades: {len(live_df)}")
                print(f"  -> Observed Win Rate: {(wins/len(live_df))*100:.1f}%")
                print(f"  -> 95% Confidence Interval: True win rate is likely between {low*100:.1f}% and {high*100:.1f}%.")
            else:
                print("  -> Not enough live trades (<5) to calculate significance.")
        except FileNotFoundError:
            print("  -> Live trade log not found.")
        print("-" * 50)

    def check_4_walk_forward_validation(self, asset):
        print("\n[CHECK 4/4] Walk-Forward Validation...")
        
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

                X_train = train.drop(columns=['id', 'asset', 'timestamp', 'target_label_long', 'target_label_short', 'primary_trend_long', 'primary_trend_short', 'primary_breakout_long', 'primary_breakout_short', 'primary_reversion_long', 'primary_reversion_short'])
                y_train = train[target_col]
                X_test = test.drop(columns=['id', 'asset', 'timestamp', 'target_label_long', 'target_label_short', 'primary_trend_long', 'primary_trend_short', 'primary_breakout_long', 'primary_breakout_short', 'primary_reversion_long', 'primary_reversion_short'])
                y_test = test[target_col]
                
                if y_train.nunique() < 2: continue

                model = xgb.XGBClassifier(n_estimators=100, objective='binary:logistic')
                model.fit(X_train, y_train)
                
                y_pred = model.predict(X_test)
                all_precisions.append(precision_score(y_test, y_pred, zero_division=0))

            if all_precisions:
                avg_precision = np.mean(all_precisions) * 100
                verdict = "🟢" if avg_precision >= 50.0 else "🔴"
                results[model_key_template] = f"{verdict} {avg_precision:.1f}%"

        if results:
            print("  -> Average Walk-Forward Win Rates:")
            for model_type, result in results.items():
                print(f"     - {model_type:<18}: {result}")
        else:
            print("  -> Could not complete any walk-forward splits.")
        print("-" * 50)


if __name__ == "__main__":
    suite = QuantValidationSuiteV5()
    suite.run_all_checks()