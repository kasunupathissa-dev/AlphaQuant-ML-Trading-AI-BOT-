from abc import ABC, abstractmethod
from typing import Dict, List, Optional
import pandas as pd
from datetime import datetime, timezone

class BaseStrategy(ABC):
    """Abstract Base Class for all quantitative strategy modules."""

    @abstractmethod
    def name(self) -> str:
        """Strategy unique identifier."""
        pass

    @abstractmethod
    def timeframe(self) -> str:
        """Primary evaluation timeframe (e.g. '15m' or '1m')."""
        pass

    @abstractmethod
    def evaluate(self, symbol: str, df: pd.DataFrame, extra_context: dict) -> Optional[dict]:
        """
        Evaluates market data and returns candidate Signal dict or None:
        {
            "signal_id": str,
            "strategy_name": str,
            "symbol": str,
            "side": "LONG" | "SHORT",
            "entry_price": float,
            "stop_loss": float,
            "take_profit": float,
            "risk_reward_ratio": float,
            "confidence": float,
            "market_regime": str,
            "reasons": List[str]
        }
        """
        pass
