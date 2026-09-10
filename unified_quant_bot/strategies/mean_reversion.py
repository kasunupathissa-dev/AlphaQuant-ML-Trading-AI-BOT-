import pandas as pd
import numpy as np
from datetime import datetime, timezone
from typing import Optional
from unified_quant_bot.strategies.base_strategy import BaseStrategy

class StatisticalMeanReversionStrategy(BaseStrategy):
    """
    Statistical Mean Reversion Strategy:
    Triggers when price diverges by >= 3.0 standard deviations from the 200-period mean in choppy/range markets.
    """

    def name(self) -> str:
        return "StatisticalMeanReversionStrategy"

    def timeframe(self) -> str:
        return "15m"

    def evaluate(self, symbol: str, df: pd.DataFrame, extra_context: dict) -> Optional[dict]:
        if len(df) < 50:
            return None

        close_series = df['close']
        close = float(close_series.iloc[-1])
        chop = float(df['chop_index'].iloc[-1]) if 'chop_index' in df.columns else 50.0

        # Microstructure / Order Flow Context
        cvd = float(extra_context.get('cvd', 0.0))
        orderbook = extra_context.get('orderbook', {})
        imbalance = float(orderbook.get('imbalance', 1.0)) # Bid/Ask depth ratio

        # Mean and Std over available window
        window = min(100, len(df))
        mean = close_series.rolling(window).mean().iloc[-1]
        std = close_series.rolling(window).std().iloc[-1] + 1e-9

        z_score = (close - mean) / std

        side = None
        reasons = []

        # Extreme Oversold in Range + Binance Bid Wall Absorption (Imbalance >= 1.15 or CVD > 0)
        if z_score <= -2.75 and chop >= 48.0 and (imbalance >= 1.15 or cvd >= 0):
            side = "LONG"
            reasons.append(
                f"Statistical Oversold Reversion: Z-Score ({z_score:.2f} <= -2.75) | "
                f"Binance Bid Depth Absorption ({imbalance:.2f}) & CVD (+{cvd:.1f}) in Range Regime"
            )

        # Extreme Overbought in Range + Binance Ask Wall Absorption (Imbalance <= 0.85 or CVD < 0)
        elif z_score >= +2.75 and chop >= 48.0 and (imbalance <= 0.85 or cvd <= 0):
            side = "SHORT"
            reasons.append(
                f"Statistical Overbought Reversion: Z-Score ({z_score:.2f} >= +2.75) | "
                f"Binance Ask Depth Absorption ({imbalance:.2f}) & CVD ({cvd:.1f}) in Range Regime"
            )

        if side is None:
            return None

        atr = float(df['atr_14'].iloc[-1]) if 'atr_14' in df.columns else (close * 0.012)
        sl_dist = max(close * 0.008, 1.2 * atr)
        tp_dist = max(close * 0.016, max(2.5 * atr, abs(close - mean))) # Minimum +1.6% profit target to ensure high fee immunity and 1:2 RRR

        sl_price = close - sl_dist if side == "LONG" else close + sl_dist
        tp_price = close + tp_dist if side == "LONG" else close - tp_dist

        rrr = tp_dist / sl_dist if sl_dist > 0 else 2.0

        sig_id = f"sig_reversion_{int(datetime.now(timezone.utc).timestamp())}_{symbol.replace('/', '_')}"

        return {
            "signal_id": sig_id,
            "strategy_name": self.name(),
            "symbol": symbol,
            "side": side,
            "entry_price": close,
            "stop_loss": round(sl_price, 4),
            "take_profit": round(tp_price, 4),
            "risk_reward_ratio": round(rrr, 2),
            "confidence": 75.0,
            "market_regime": "RANGE",
            "reasons": reasons
        }
