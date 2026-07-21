import pandas as pd
import numpy as np
import joblib
from sklearn.model_selection import train_test_split, TimeSeriesSplit
from sklearn.metrics import precision_score
from statsmodels.stats.proportion import proportion_confint
import warnings

# 🟢 V5: Use the centralized database configuration
from database_config import get_db_engine

# Ignore convergence warnings from the calibration model
warnings.filterwarnings("ignore", category=UserWarning)

TARGET_ASSETS = ["BTC/USDT", "ETH/USDT", "SOL/USDT", "BNB/USDT", "ADA/USDT", "XRP/USDT", "LINK/USDT", "AVAX/USDT", "DOGE/USDT", "DOT/USDT"]
LOG_FILE = "trading_log_v4_4.csv" # The log file from your live V4.4 engine

class QuantValidationSuite:
    def __init__(self):
        print("==================================================")
        print("  ALPHAQUANT V5: INSTITUTIONAL VALIDATION SUITE   ")
        print("==================================================")
        self.engine = get_db_engine()

    def run_all_checks(self):
        if self.engine is None: return

        for asset in TARGET_ASSETS:
            print(f"\n{'='*20} {asset} {'='*20}")
            
            # Load the trained dual-brain model
            safe_filename = asset.replace("/", "_") + "_brain.pkl"
            try:
                brain_data = joblib.load(safe_filename)
            except FileNotFoundError:
                print(f"[ERROR] Brain file '{safe_filename}' not found. Skipping.")
                continue

            # --- Run Checks ---
            self.check_1_calibration_curve(brain_data, asset)
            self.check_2_live_vs_backtest_gap(asset)
            self.check_3_statistical_significance()
            self.check_4_walk_forward_validation(asset)

    def check_1_calibration_curve(self, brain_data, asset):
        print("\n[CHECK 1/4] Running Reliability Curve Analysis...")
        
        # We only need to check one direction, as the calibration method is the same
        if 'LONG' not in brain_data:
            print("  -> No LONG model found to calibrate.")
            return
            
        model = brain_data['LONG']['model']
        
        # Load the same data used for training
        query = f"""
            SELECT * FROM feature_store 
            WHERE primary_long_signal = 1 AND target_label_long IS NOT NULL AND asset = '{asset}'
        """
        df = pd.read_sql(query, self.engine)
        if len(df) < 20: return

        X = df.drop(columns=['id', 'asset', 'timestamp', 'target_label_long', 'target_label_short', 'primary_long_signal', 'primary_short_signal'])
        y = df['target_label_long']
        _, X_test, _, y_test = train_test_split(X, y, test_size=0.2, random_state=42, shuffle=False)

        if len(X_test) == 0: return

        y_pred_proba = model.predict_proba(X_test)[:, 1]

        print("  -> Model Calibration (Reliability Curve):")
        print(f"  {'Prob Bin':<12} | {'Actual Win Rate':<18} | {'Trades':<8}")
        print(f"  {'-'*12} | {'-'*18} | {'-'*8}")

        for i in np.arange(0.5, 0.8, 0.05):
            lower, upper = i, i + 0.05
            mask = (y_pred_proba >= lower) & (y_pred_proba < upper)
            
            if np.sum(mask) > 0:
                actual_win_rate = y_test[mask].mean() * 100
                print(f"  {lower*100:.0f}% - {upper*100:.0f}%    | {actual_win_rate:12.1f}%        | {np.sum(mask):<8}")
        print("-" * 50)

    def check_2_live_vs_backtest_gap(self, asset):
        print("\n[CHECK 2/4] Analyzing Live vs. Backtest Performance Gap...")
        try:
            live_df = pd.read_csv(LOG_FILE)
            asset_live_df = live_df[live_df['Asset'] == asset]
            if not asset_live_df.empty:
                live_wins = len(asset_live_df[asset_live_df['Status'] == 'PROFIT'])
                live_trades = len(asset_live_df)
                live_win_rate = (live_wins / live_trades) * 100
                print(f"  -> Live Win Rate for {asset}: {live_win_rate:.1f}% ({live_trades} trades)")
                # Note: A full comparison would require re-running the backtest logic here.
                # For now, this provides the raw live number for manual comparison.
            else:
                print("  -> No live trades logged for this asset yet.")
        except FileNotFoundError:
            print("  -> Live trade log not found. Skipping.")
        print("-" * 50)

    def check_3_statistical_significance(self):
        print("\n[CHECK 3/4] Calculating Statistical Significance (Wilson Score)...")
        try:
            live_df = pd.read_csv(LOG_FILE)
            if len(live_df) >= 5:
                wins = len(live_df[live_df['Status'] == 'PROFIT'])
                total_trades = len(live_df)
                
                # Wilson Score Interval for Binomial Proportions
                low, high = proportion_confint(wins, total_trades, method='wilson')
                
                print(f"  -> Total Live Trades: {total_trades}")
                print(f"  -> Observed Win Rate: {(wins/total_trades)*100:.1f}%")
                print(f"  -> 95% Confidence Interval: The true win rate is likely between {low*100:.1f}% and {high*100:.1f}%.")
                if (high - low) > 0.3:
                    print("  -> Verdict: Sample size is too small to trust the observed win rate.")
            else:
                print("  -> Not enough live trades (<5) to calculate significance.")
        except FileNotFoundError:
            print("  -> Live trade log not found. Skipping.")
        print("-" * 50)

    def check_4_walk_forward_validation(self, asset):
        print("\n[CHECK 4/4] Performing Walk-Forward Validation...")
        
        query = f"""
            SELECT * FROM feature_store 
            WHERE (primary_long_signal = 1 OR primary_short_signal = 1) AND target_label_long IS NOT NULL AND asset = '{asset}'
        """
        df = pd.read_sql(query, self.engine)
        if len(df) < 200: # Need enough data for multiple splits
            print("  -> Not enough data for walk-forward analysis.")
            print("-" * 50)
            return

        # Use 5 splits for walk-forward
        tscv = TimeSeriesSplit(n_splits=5)
        all_precisions = []

        for train_index, test_index in tscv.split(df):
            train_df, test_df = df.iloc[train_index], df.iloc[test_index]
            
            # This is a simplified re-training for validation purposes
            # We only validate the LONG model here for brevity
            long_train = train_df[train_df['primary_long_signal'] == 1]
            long_test = test_df[test_df['primary_long_signal'] == 1]

            if len(long_train) < 20 or len(long_test) < 5: continue

            X_train = long_train.drop(columns=['id', 'asset', 'timestamp', 'target_label_long', 'target_label_short', 'primary_long_signal', 'primary_short_signal'])
            y_train = long_train['target_label_long']
            X_test = long_test.drop(columns=['id', 'asset', 'timestamp', 'target_label_long', 'target_label_short', 'primary_long_signal', 'primary_short_signal'])
            y_test = long_test['target_label_long']
            
            if y_train.nunique() < 2: continue # Need both wins and losses to train

            model = xgb.XGBClassifier(n_estimators=100, objective='binary:logistic')
            model.fit(X_train, y_train)
            
            y_pred = model.predict(X_test)
            all_precisions.append(precision_score(y_test, y_pred, zero_division=0))

        if all_precisions:
            avg_precision = np.mean(all_precisions) * 100
            print(f"  -> Average Walk-Forward Win Rate (Precision): {avg_precision:.1f}%")
            if avg_precision < 50.0:
                print("  -> Verdict: 🔴 Model fails to generalize on out-of-sample data.")
            else:
                print("  -> Verdict: 🟢 Model shows robust performance on unseen data.")
        else:
            print("  -> Could not complete any walk-forward splits.")
        print("-" * 50)


if __name__ == "__main__":
    suite = QuantValidationSuite()
    suite.run_all_checks()