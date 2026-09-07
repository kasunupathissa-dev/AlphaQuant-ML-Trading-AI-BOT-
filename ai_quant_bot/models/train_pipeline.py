import os
import joblib
import numpy as np
import pandas as pd
import xgboost as xgb
from sklearn.calibration import CalibratedClassifierCV
from sklearn.model_selection import TimeSeriesSplit
from sklearn.metrics import log_loss, roc_auc_score

class ModelTrainer:
    """Production ML Pipeline with Purged Splits and Probability Calibration."""

    def __init__(self, model_save_path: str = None):
        if model_save_path is None:
            # Resolve to package directory: ai_quant_bot/models/saved_models/
            current_dir = os.path.dirname(os.path.abspath(__file__))
            self.model_save_path = os.path.join(current_dir, 'saved_models')
        else:
            self.model_save_path = model_save_path
            
        # Ensure path ends with slash or separator
        if not self.model_save_path.endswith(os.path.sep):
            self.model_save_path += os.path.sep
            
        os.makedirs(self.model_save_path, exist_ok=True)

    def train_and_calibrate(self, X: pd.DataFrame, y: pd.Series, symbol: str, direction: str = 'long'):
        """Trains an XGBoost model and fits an Isotonic Calibrator."""
        # Sanity assertion
        assert not X.empty and not y.empty, "Dataframe cannot be empty for training."
        assert y.isna().sum() == 0, "Labels must have zero NaNs before fitting."

        # Define Purged Time Series Split
        tscv = TimeSeriesSplit(n_splits=5, gap=15)

        base_model = xgb.XGBClassifier(
            n_estimators=150,
            max_depth=4,
            learning_rate=0.03,
            subsample=0.8,
            colsample_bytree=0.8,
            random_state=42,
            eval_metric='logloss'
        )

        # Train with Isotonic probability calibration
        calibrated_model = CalibratedClassifierCV(
            estimator=base_model,
            method='isotonic',
            cv=tscv
        )

        calibrated_model.fit(X, y)

        # Quick evaluation
        probs = calibrated_model.predict_proba(X)[:, 1]
        print(f"[{symbol.upper()} - {direction.upper()}] Model Trained.")
        print(f"Mean Predicted Prob: {probs.mean():.4f} | Max: {probs.max():.4f} | AUC: {roc_auc_score(y, probs):.4f}")

        # Save artifact
        clean_sym = symbol.replace('/', '_')
        save_file = f"{self.model_save_path}xgb_{clean_sym}_{direction}.joblib"
        joblib.dump(calibrated_model, save_file)
        print(f"Saved artifact to {save_file}\n")
        return calibrated_model
