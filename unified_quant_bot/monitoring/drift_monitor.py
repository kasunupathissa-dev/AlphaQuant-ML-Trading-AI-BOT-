import time
import numpy as np
from typing import Dict, List, Optional
from collections import deque

class ModelDriftMonitor:
    """
    Continuous Machine Learning Drift Monitor:
    Tracks rolling Brier accuracy score, calibration degradation, and prediction confidence drift.
    """

    def __init__(self, window_size: int = 50, brier_alert_threshold: float = 0.25):
        self.window_size = window_size
        self.brier_alert_threshold = brier_alert_threshold
        self.history = deque(maxlen=window_size)
        self.last_alert_time = 0

    def record_prediction_outcome(self, predicted_prob: float, outcome_win: bool):
        """
        Records predicted probability vs actual binary outcome (1 for Win, 0 for Loss)
        to compute rolling Brier Score.
        """
        actual = 1.0 if outcome_win else 0.0
        prob = float(predicted_prob) / 100.0 if predicted_prob > 1.0 else float(predicted_prob)
        brier_loss = (prob - actual) ** 2
        
        self.history.append({
            "timestamp": time.time(),
            "prob": prob,
            "actual": actual,
            "brier_loss": brier_loss
        })

    def get_drift_metrics(self) -> dict:
        """Returns current rolling Brier score and calibration status."""
        if not self.history:
            return {
                "sample_count": 0,
                "brier_score": 0.18,
                "is_drifting": False,
                "status": "INSUFFICIENT_DATA"
            }

        brier_scores = [h["brier_loss"] for h in self.history]
        mean_brier = float(np.mean(brier_scores))
        is_drifting = mean_brier >= self.brier_alert_threshold

        status = "DEGRADED_DRIFT_ALERT" if is_drifting else "CALIBRATED_NOMINAL"

        return {
            "sample_count": len(self.history),
            "brier_score": round(mean_brier, 4),
            "is_drifting": is_drifting,
            "status": status
        }
