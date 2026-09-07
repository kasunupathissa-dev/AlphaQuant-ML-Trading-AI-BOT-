import numpy as np
from sklearn.calibration import CalibratedClassifierCV

class ProbabilityCalibrator:
    """Handles probability calibration using Platt Scaling / Isotonic regression."""
    
    def __init__(self, method: str = 'sigmoid'):
        # method='sigmoid' implements Platt Scaling
        self.method = method
        self.calibrated_model = None

    def fit_calibration(self, base_estimator, X_val, y_val):
        """Fits calibration wrapper over pre-fitted model."""
        self.calibrated_model = CalibratedClassifierCV(
            estimator=base_estimator,
            method=self.method,
            cv='prefit'
        )
        self.calibrated_model.fit(X_val, y_val)
        print(f"[CALIBRATOR] Platt Scaling probability calibration fitted successfully.")
        return self.calibrated_model

    def predict_calibrated_proba(self, X) -> np.ndarray:
        """Returns calibrated probability for classes."""
        if self.calibrated_model is None:
            raise ValueError("Calibrator has not been fitted yet.")
        return self.calibrated_model.predict_proba(X)

    @staticmethod
    def calculate_percentile_gate(probas: np.ndarray, percentile: float = 80.0) -> float:
        """Computes a dynamic percentile gate threshold based on historical scores."""
        # Assume probas is 1D array of class 1 win probabilities
        if len(probas) == 0:
            return 50.0
        return float(np.percentile(probas, percentile))
