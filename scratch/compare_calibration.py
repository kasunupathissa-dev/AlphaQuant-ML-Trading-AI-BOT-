import sys
import os
# Add the project root to sys.path to resolve imports
sys.path.append("c:/cry_agent/v_4_AQ_AI")

import pandas as pd
import numpy as np
import joblib
import math
import csv
from sklearn.model_selection import train_test_split
from database_config import get_db_engine
import config

def wilson_confidence_interval(p, n, confidence=0.95):
    """
    Computes the Wilson Score Interval for a binomial proportion.
    """
    if n == 0:
        return 0.0, 0.0
    z = 1.96 # 95% confidence level
    denominator = 1 + z**2 / n
    centre_adjusted_probability = p + z**2 / (2 * n)
    adjusted_variance = math.sqrt((p * (1 - p) + z**2 / (4 * n)) / n)
    
    lower = (centre_adjusted_probability - z * adjusted_variance) / denominator
    upper = (centre_adjusted_probability + z * adjusted_variance) / denominator
    return max(0.0, lower), min(1.0, upper)

def brier_score_binary(y_true, y_prob):
    """
    Computes the Brier Score for binary classification (MSE of predicted prob vs outcome).
    """
    if len(y_true) == 0:
        return 0.0
    return np.mean((y_prob - y_true) ** 2)

def read_live_logs(log_file, target_asset):
    """
    Reads and parses live trade logs for a specific asset from the CSV file.
    """
    live_records = []
    if not os.path.exists(log_file):
        return pd.DataFrame()
        
    try:
        with open(log_file, mode='r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                # Normalize keys to lowercase
                row = {k.lower(): v for k, v in row.items() if k is not None}
                
                # Check asset match
                row_asset = row.get('asset', '')
                if row_asset != target_asset:
                    continue
                    
                status = row.get('status', '').upper()
                if status not in ('WIN', 'LOSS', 'PROFIT'):
                    continue
                    
                # Map true label: 1 for win/profit, 0 for loss
                true_label = 1 if ('WIN' in status or 'PROFIT' in status) else 0
                
                # Get predicted probability (strip % if present)
                prob_str = row.get('win_prob', row.get('ai_prob', '0'))
                prob_str = str(prob_str).replace('%', '').strip()
                try:
                    pred_prob = float(prob_str) / 100.0 if float(prob_str) > 1.0 else float(prob_str)
                except ValueError:
                    continue
                    
                pnl = 0.0
                try:
                    pnl = float(row.get('pnl', 0.0))
                except ValueError:
                    pass
                    
                live_records.append({
                    'true_label': true_label,
                    'pred_prob': pred_prob,
                    'pnl': pnl
                })
        return pd.DataFrame(live_records)
    except Exception as e:
        print(f"[ERROR] Failed to read live logs: {e}")
        return pd.DataFrame()

def compare_calibration():
    print("==================================================")
    print("   ALPHAQUANT: CALIBRATION COMPARISON TERMINAL     ")
    print("==================================================")
    
    report_path = "C:/Users/kasun/.gemini/antigravity-ide/brain/e652e605-7137-4acc-949a-fed0b619d0a2/calibration_comparison.md"
    repo_dir = "c:/cry_agent/v_4_AQ_AI"
    log_file = os.path.join(repo_dir, config.LOG_FILE)
    
    engine = get_db_engine()
    if engine is None:
        print("[ERROR] Database connection failed.")
        return
        
    table_name = f"feature_store_{config.TIMEFRAME}"
    features = ['dist_ema_50', 'dist_ema_200', 'atr_pct', 'volume_zscore', 'adx_14', 'bb_width', 'funding_rate_zscore', 'oi_zscore']
    
    report_content = []
    report_content.append("# AlphaQuant: Backtest vs. Live Calibration Comparison\n")
    report_content.append(f"Generated at: {pd.Timestamp.now()}\n")
    report_content.append("This report compares the out-of-sample backtest calibration curves with real live trade log calibration curves.\n")
    
    bin_edges = [0.50, 0.55, 0.60, 0.65, 0.70, 0.75, 0.80, 1.01]
    bin_labels = ["50%-55%", "55%-60%", "60%-65%", "65%-70%", "70%-75%", "75%-80%", "80%+"]
    
    for asset in config.TARGET_ASSETS:
        safe_filename = os.path.join(repo_dir, asset.replace("/", "_") + "_brain.pkl")
        if not os.path.exists(safe_filename):
            continue
            
        # 1. Load OOS Backtest Data
        query = f"SELECT * FROM {table_name} WHERE asset = '{asset}'"
        try:
            df = pd.read_sql(query, engine)
        except Exception as e:
            continue
            
        df.dropna(subset=['target_label'], inplace=True)
        df = df[df['target_label'] != 2].copy()
        df['target_label'] = df['target_label'].astype(int)
        
        if len(df) < 100:
            continue
            
        X = df[features]
        y = df['target_label']
        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42, stratify=y)
        
        # Load model & predict OOS
        try:
            brain_pack = joblib.load(safe_filename)
            model = brain_pack['model']
        except Exception as e:
            continue
            
        y_prob = model.predict_proba(X_test)
        backtest_probs = y_prob[:, 1]
        
        # 2. Fetch Live Logs
        live_df = read_live_logs(log_file, asset)
        
        # Calculate Brier Scores
        backtest_brier = brier_score_binary(y_test.values, backtest_probs)
        live_brier = brier_score_binary(live_df['true_label'].values, live_df['pred_prob'].values) if not live_df.empty else 0.0
        
        report_content.append(f"## Asset: {asset}")
        report_content.append(f"* **Backtest (OOS) Brier Score:** `{backtest_brier:.4f}` (Sample size: {len(y_test)})")
        report_content.append(f"* **Live Trades Brier Score:** `{live_brier:.4f}` (Sample size: {len(live_df) if not live_df.empty else 0})")
        report_content.append("\n")
        
        report_content.append("| Probability Bin | OOS N | OOS Pred | OOS True (95% CI) | Live N | Live Pred | Live True (95% CI) | Delta / Evaluation |")
        report_content.append("| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |")
        
        for i in range(len(bin_labels)):
            low = bin_edges[i]
            high = bin_edges[i+1]
            
            # OOS statistics
            oos_mask = (backtest_probs >= low) & (backtest_probs < high)
            oos_n = np.sum(oos_mask)
            if oos_n > 0:
                oos_pred = np.mean(backtest_probs[oos_mask])
                oos_true = np.mean(y_test.values[oos_mask] == 1)
                oos_ci_l, oos_ci_h = wilson_confidence_interval(oos_true, oos_n)
                oos_pred_str = f"{oos_pred*100:.1f}%"
                oos_true_str = f"{oos_true*100:.1f}% ({oos_ci_l*100:.0f}%-{oos_ci_h*100:.0f}%)"
            else:
                oos_n = 0
                oos_pred_str = "-"
                oos_true_str = "-"
                
            # Live statistics
            live_n = 0
            live_pred_str = "-"
            live_true_str = "-"
            evaluation = "-"
            
            if not live_df.empty:
                live_mask = (live_df['pred_prob'] >= low) & (live_df['pred_prob'] < high)
                live_n = np.sum(live_mask)
                if live_n > 0:
                    live_pred = np.mean(live_df['pred_prob'][live_mask])
                    live_true = np.mean(live_df['true_label'][live_mask] == 1)
                    live_ci_l, live_ci_h = wilson_confidence_interval(live_true, live_n)
                    live_pred_str = f"{live_pred*100:.1f}%"
                    live_true_str = f"{live_true*100:.1f}% ({live_ci_l*100:.0f}%-{live_ci_h*100:.0f}%)"
                    
                    # Evaluate Gap
                    if oos_n > 0:
                        # Check if live True win rate is outside the backtest Wilson interval, or vice versa
                        if live_true < oos_ci_l:
                            evaluation = "⚠️ Underperforming Live (Overconfident)"
                        elif live_true > oos_ci_h:
                            evaluation = "🔍 Outperforming Live (Underconfident)"
                        else:
                            evaluation = "✅ Match (Stable Calibration)"
                    else:
                        evaluation = "New live bin"
            
            report_content.append(
                f"| {bin_labels[i]} | {oos_n} | {oos_pred_str} | {oos_true_str} | {live_n} | {live_pred_str} | {live_true_str} | {evaluation} |"
            )
        
        report_content.append("\n---\n")
        
    try:
        with open(report_path, "w", encoding="utf-8") as rf:
            rf.write("\n".join(report_content))
        print(f"[SUCCESS] Calibration comparison generated at {report_path}")
    except Exception as e:
        print(f"[ERROR] Failed to write report: {e}")

if __name__ == "__main__":
    compare_calibration()
