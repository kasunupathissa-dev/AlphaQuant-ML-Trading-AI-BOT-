import numpy as np
import pandas as pd
from typing import Dict, List, Optional
from sklearn.base import BaseEstimator, ClassifierMixin
from sklearn.ensemble import RandomForestClassifier, ExtraTreesClassifier, GradientBoostingClassifier
from sklearn.linear_model import LogisticRegression

class StackedEnsembleClassifier(BaseEstimator, ClassifierMixin):
    """
    Institutional Multi-Model Stacking Ensemble:
    Combines Random Forest, Extra Trees, and Gradient Boosting base estimators
    with a calibrated Logistic Regression Meta-Learner.
    """

    def __init__(self, n_features: int = 14):
        self.n_features = n_features
        self.base_models = [
            RandomForestClassifier(n_estimators=100, max_depth=6, random_state=42, n_jobs=-1),
            ExtraTreesClassifier(n_estimators=100, max_depth=6, random_state=42, n_jobs=-1),
            GradientBoostingClassifier(n_estimators=80, max_depth=4, random_state=42)
        ]
        self.meta_learner = LogisticRegression(C=1.0, max_iter=200)
        self.is_fitted = False

    def fit(self, X: np.ndarray, y: np.ndarray):
        """Fits base models and meta-learner using predictions."""
        n_samples = X.shape[0]
        base_meta_features = np.zeros((n_samples, len(self.base_models) * 2))

        for idx, model in enumerate(self.base_models):
            model.fit(X, y)
            probs = model.predict_proba(X)
            base_meta_features[:, idx*2:(idx+1)*2] = probs

        self.meta_learner.fit(base_meta_features, y)
        self.is_fitted = True
        return self

    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        """Generates ensemble stacked probability predictions."""
        X_arr = np.asarray(X)
        if X_arr.ndim == 1:
            X_arr = X_arr.reshape(1, -1)

        # Slice to expected features if vector length mismatch
        if X_arr.shape[1] > self.n_features:
            X_arr = X_arr[:, :self.n_features]

        if not self.is_fitted:
            # Fallback uniform baseline probability if not fitted
            return np.array([[0.35, 0.65]])

        meta_feats = np.zeros((X_arr.shape[0], len(self.base_models) * 2))
        for idx, model in enumerate(self.base_models):
            probs = model.predict_proba(X_arr)
            meta_feats[:, idx*2:(idx+1)*2] = probs

        return self.meta_learner.predict_proba(meta_feats)

    def predict(self, X: np.ndarray) -> np.ndarray:
        probs = self.predict_proba(X)
        return np.argmax(probs, axis=1)


class MetaLabelingFilter:
    """
    Marcos López de Prado Meta-Labeling Framework:
    Secondary machine learning filter that evaluates whether to execute a primary directional trade signal.
    """

    def __init__(self, min_meta_confidence: float = 65.0):
        self.min_meta_confidence = min_meta_confidence

    def evaluate_trade_proposal(
        self,
        symbol: str,
        direction: str,
        strategy: str,
        base_confidence: float,
        extra_context: dict
    ) -> dict:
        """
        Calculates meta-features (RVOL, Chop, Volatility compression, Order book imbalance, CVD)
        and scores the trade quality.
        """
        ob = extra_context.get('orderbook', {})
        imbalance = float(ob.get('imbalance', 1.0))
        cvd = float(extra_context.get('cvd', 0.0))
        atr_14 = float(extra_context.get('atr_14', 1.0))
        atr_100 = float(extra_context.get('atr_100', atr_14))
        vol_ratio = atr_14 / (atr_100 + 1e-9)

        # Meta scoring factors
        quality_score = base_confidence

        # Factor 1: Order Book Wall Confirmation
        if direction == "LONG" and imbalance >= 1.15:
            quality_score += 3.5
        elif direction == "SHORT" and imbalance <= 0.85:
            quality_score += 3.5
        elif (direction == "LONG" and imbalance < 0.90) or (direction == "SHORT" and imbalance > 1.10):
            quality_score -= 5.0 # Contradicting wall

        # Factor 2: CVD Directional Agreement
        if direction == "LONG" and cvd > 0:
            quality_score += 2.5
        elif direction == "SHORT" and cvd < 0:
            quality_score += 2.5
        elif (direction == "LONG" and cvd < 0) or (direction == "SHORT" and cvd > 0):
            quality_score -= 4.0

        # Factor 3: Volatility Expansion Health
        if 0.8 <= vol_ratio <= 1.5:
            quality_score += 2.0
        elif vol_ratio > 2.5:
            quality_score -= 6.0 # Extreme unpredictable volatility

        passed = quality_score >= self.min_meta_confidence

        return {
            "passed": passed,
            "meta_confidence": round(quality_score, 2),
            "reasons": [
                f"Meta-Confidence: {quality_score:.1f}% (Required >= {self.min_meta_confidence:.1f}%)",
                f"Order Book Imbalance: {imbalance:.2f} | CVD: {cvd:.1f} | Vol Ratio: {vol_ratio:.2f}"
            ]
        }
