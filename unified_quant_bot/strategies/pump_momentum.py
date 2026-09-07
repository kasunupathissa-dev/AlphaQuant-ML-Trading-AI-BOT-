import pandas as pd
from datetime import datetime, timezone
from typing import Optional
from unified_quant_bot.strategies.base_strategy import BaseStrategy

class VolumePumpMomentumStrategy(BaseStrategy):
    """
    High-Velocity Volume Surge / Pump Momentum Strategy:
    Captures sudden explosive volume spikes (Z >= 3.0) and high-volatility directional expansions.
    """

    def name(self) -> str:
        return "VolumePumpMomentumStrategy"

    def timeframe(self) -> str:
        return "1m"

    def evaluate(self, symbol: str, df: pd.DataFrame, extra_context: dict) -> Optional[dict]:
        pump_info = extra_context.get('pump_info', {})
        if not pump_info.get('pump_detected', False):
            return None

        side = pump_info.get('direction', 'LONG')
        close = float(df['close'].iloc[-1])
        atr = float(df['atr_14'].iloc[-1]) if 'atr_14' in df.columns else (close * 0.015)

        sl_dist = 1.25 * atr
        tp_dist = 2.5 * atr

        sl_price = close - sl_dist if side == "LONG" else close + sl_dist
        tp_price = close + tp_dist if side == "LONG" else close - tp_dist

        sig_id = f"sig_pump_{int(datetime.now(timezone.utc).timestamp())}_{symbol.replace('/', '_')}"

        return {
            "signal_id": sig_id,
            "strategy_name": self.name(),
            "symbol": symbol,
            "side": side,
            "entry_price": close,
            "stop_loss": round(sl_price, 4),
            "take_profit": round(tp_price, 4),
            "risk_reward_ratio": 2.0,
            "confidence": 75.0,
            "market_regime": "VOLATILE",
            "reasons": [
                f"Volume Surge Detected: Z-Score +{pump_info.get('volume_zscore', 3.0)}",
                f"1-Minute Price Surge: {pump_info.get('price_surge_pct', 1.5):+.2f}%"
            ]
        }
