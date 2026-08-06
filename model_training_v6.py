import pandas as pd
import numpy as np
import xgboost as xgb
import lightgbm as lgb
from sklearn.model_selection import train_test_split
from sklearn.calibration import CalibratedClassifierCV
from sklearn.metrics import precision_score
import joblib
import os
import shap
import matplotlib.pyplot as plt

# 🟢 V6.5 Upgrade: Use the centralized database configuration
from database_config import get_db_engine

TARGET_ASSETS = ["BTC/USDT", "ETH/USDT", "SOL/USDT", "BNB/USDT", "ADA/USDT", "XRP/USDT", "LINK/USDT", "AVAX/USDT", "DOGE/USDT", "DOT/USDT"]

def train_ensemble_models():
    print("==================================================")
    print("  ALPHAQUANT V6.5: HARDENED ENSEMBLE TRAINING     ")
    print("==================================================")

    engine = get_db_engine()
    if engine is None: return

    for asset in TARGET_ASSETS:
        print(f"\n{'='*15} Training Ensemble Models for {asset} {'='*15}")
        
        query = f"SELECT * FROM feature_store WHERE asset = '{asset}'"
        try:
            df = pd.read_sql(query, engine)
        except Exception as e:
            print(f"  [ERROR] DB Read failed: {e}")
            continue
        
        if len(df) < 50: continue

        asset_brain = {} 

        signal_types = {
            "TREND": ("primary_trend_long", "primary_trend_short"),
            "BREAKOUT": ("primary_breakout_long", "primary_breakout_short"),
            "REVERSION": ("primary_reversion_long", "primary_reversion_short")
        }

        for signal_name, (long_col, short_col) in signal_types.items():
            print(f"\n--- Training for Signal Type: {signal_name} ---")

            for direction, primary_col, target_col in [("LONG", long_col, "target_label_long"), ("SHORT", short_col, "target_label_short")]:
                signal_df = df[df[primary_col] == 1].copy()
                
                # 🟢 V6.5 FIX: Final paranoid drop of any possible NaNs in the target column
                signal_df.dropna(subset=[target_col], inplace=True)
                signal_df[target_col] = signal_df[target_col].astype(int)

                if len(signal_df) < 20: continue

                wins = len(signal_df[signal_df[target_col] == 1])
                losses = len(signal_df) - wins
                
                print(f"  [{direction}] Samples: {len(signal_df)} | Base Win Rate: {(wins/len(signal_df))*100:.1f}%")
                
                if wins > 0 and losses > 0:
                    X = signal_df.drop(columns=['id', 'asset', 'timestamp', 'target_label_long', 'target_label_short', 'primary_trend_long', 'primary_trend_short', 'primary_breakout_long', 'primary_breakout_short', 'primary_reversion_long', 'primary_reversion_short'])
                    y = signal_df[target_col]
                    
                    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42, shuffle=False)
                    
                    from sklearn.model_selection import TimeSeriesSplit
                    ts_cv = TimeSeriesSplit(n_splits=3)
                    
                    xgb_model = xgb.XGBClassifier(n_estimators=300, learning_rate=0.01, max_depth=3, subsample=0.8, colsample_bytree=0.8, objective='binary:logistic', scale_pos_weight=(losses/wins)*1.5)
                    calibrated_xgb = CalibratedClassifierCV(estimator=xgb_model, method='isotonic', cv=ts_cv)
                    calibrated_xgb.fit(X_train, y_train)
                    
                    lgb_model = lgb.LGBMClassifier(n_estimators=300, learning_rate=0.01, max_depth=3, subsample=0.8, colsample_bytree=0.8, objective='binary', scale_pos_weight=(losses/wins)*1.5)
                    calibrated_lgb = CalibratedClassifierCV(estimator=lgb_model, method='isotonic', cv=ts_cv)
                    calibrated_lgb.fit(X_train, y_train)

                    y_pred_xgb = calibrated_xgb.predict_proba(X_test)[:, 1]
                    y_pred_lgb = calibrated_lgb.predict_proba(X_test)[:, 1]
                    y_pred_ensemble = (y_pred_xgb + y_pred_lgb) / 2.0

                    best_thresh, best_prec = 0.50, 0.0
                    for thresh in np.arange(0.45, 0.75, 0.01): 
                        y_pred_custom = (y_pred_ensemble >= thresh).astype(int)
                        prec = precision_score(y_test, y_pred_custom, zero_division=0) * 100
                        if prec >= 50.0 and sum(y_pred_custom) >= 1:
                            if thresh > best_thresh or best_prec == 0.0:
                                best_thresh, best_prec = thresh, prec
                                
                    asset_brain[f"{signal_name}_{direction}"] = {
                        'xgb_model': calibrated_xgb, 
                        'lgb_model': calibrated_lgb, 
                        'threshold': best_thresh
                    }
                    print(f"  -> {direction} Ensemble Calibrated. Optimal Threshold: {best_thresh*100:.1f}%")

                    if signal_name == "TREND" and direction == "LONG" and hasattr(calibrated_xgb, 'calibrated_classifiers_'):
                        if calibrated_xgb.calibrated_classifiers_:
                            fitted_xgb = calibrated_xgb.calibrated_classifiers_[0].estimator
                            explainer = shap.TreeExplainer(fitted_xgb)
                            shap_values = explainer.shap_values(X_test)
                            
                            safe_asset_name = asset.replace("/", "_")
                            plot_filename = f"{safe_asset_name}_shap_summary.png"

                            shap.summary_plot(shap_values, X_test, plot_type="bar", show=False)
                            plt.title(f"SHAP Feature Importance for {asset} TREND_LONG")
                            plt.savefig(plot_filename)
                            plt.close()
                            print(f"  -> Saved SHAP summary plot to {plot_filename}")

        if asset_brain:
            safe_filename = asset.replace("/", "_") + "_brain.pkl"
            joblib.dump(asset_brain, safe_filename)
            print(f"\n  [SUCCESS] Saved Ensemble Brain to {safe_filename}")

    print("\n==================================================")
    print(" V6.5 Ensemble Model Training Complete.")
    print("==================================================")

if __name__ == "__main__":
    train_ensemble_models()