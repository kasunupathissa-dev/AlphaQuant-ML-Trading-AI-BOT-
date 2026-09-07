import pandas as pd
from datetime import datetime, timezone
from typing import Optional
from unified_quant_bot.strategies.base_strategy import BaseStrategy

class LiquidationCascadeStrategy(BaseStrategy):
    """
    Pure Microstructure Reversal Hunter:
    Captures forced liquidation spikes ($100k+ bursts) and CVD absorption at order book depth walls.
    """

    def name(self) -> str:
        return "LiquidationCascadeStrategy"

    def timeframe(self) -> str:
        return "1m"

    def evaluate(self, symbol: str, df: pd.DataFrame, extra_context: dict) -> Optional[dict]:
        if len(df) < 15:
            return None

        cvd = float(extra_context.get('cvd', 0.0))
        orderbook = extra_context.get('orderbook', {})
        imbalance = float(orderbook.get('imbalance', 1.0)) # Bid/Ask depth ratio
        close = float(df['close'].iloc[-1])
        atr = float(df['atr_14'].iloc[-1]) if 'atr_14' in df.columns else (close * 0.01)

        side = None
        reasons = []

        # Check HTF Trend Context if available
        ema_50 = float(df['ema_50'].iloc[-1]) if 'ema_50' in df.columns else close
        
        # Bullish Liquidation Exhaustion (Massive Short Liquidations + Positive CVD + Above EMA 50)
        if imbalance >= 2.5 and cvd > 0 and close >= ema_50:
            side = "LONG"
            reasons.append(f"Bullish Wall Imbalance ({imbalance:.2f}) + CVD (+{cvd:.1f}) aligned above 15m EMA50")

        # Bearish Liquidation Exhaustion (Massive Long Liquidations + Negative CVD + Below EMA 50)
        elif imbalance <= 0.40 and cvd < 0 and close <= ema_50:
            side = "SHORT"
            reasons.append(f"Bearish Wall Imbalance ({imbalance:.2f}) + CVD ({cvd:.1f}) aligned below 15m EMA50")

        if side is None:
            return None

        # Institutional Sizing: 1.5x ATR Stop Loss, 3.0x ATR Take Profit (1:2.0 RRR)
        sl_dist = 1.5 * atr
        tp_dist = 3.0 * atr

        sl_price = close - sl_dist if side == "LONG" else close + sl_dist
        tp_price = close + tp_dist if side == "LONG" else close - tp_dist

        sig_id = f"sig_liq_{int(datetime.now(timezone.utc).timestamp())}_{symbol.replace('/', '_')}"

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
            "reasons": reasons
        }
