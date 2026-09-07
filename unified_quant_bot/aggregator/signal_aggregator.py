import time
from typing import List, Dict, Optional

class SignalAggregator:
    """
    Regime-Driven Signal Aggregator:
    Arbitrates signals across multi-timeframe strategies, resolves conflicts, enforces dynamic threshold calibration,
    handles signal drought contingencies, and incorporates Smart Money / Top Trader Confluence.
    """

    def __init__(self):
        self.strategy_weights = {
            "ShotgunMomentumStrategy": 1.25, # Proven 71.11% Win Rate Core
            "LiquidationCascadeStrategy": 1.15,
            "VolumePumpMomentumStrategy": 1.10,
            "StatisticalMeanReversionStrategy": 1.00
        }
        self.last_signal_time = time.time()
        self.drought_threshold_seconds = 21600 # 6 hours

    def get_dynamic_threshold(self, symbol: str, extra_context: dict) -> float:
        """
        Calculates dynamic threshold per asset (FR-4.6) and applies drought relaxation if elapsed time > 6h (FR-4.7).
        """
        base_threshold = 68.0
        
        # Volatility-adaptive modifier
        atr_14 = float(extra_context.get('atr_14', 1.0))
        atr_100 = float(extra_context.get('atr_100', atr_14))
        vol_ratio = atr_14 / (atr_100 + 1e-9)
        vol_adjustment = 0.15 * (vol_ratio - 1.0)
        
        # Drought relaxation
        elapsed = time.time() - self.last_signal_time
        drought_reduction = 2.0 if elapsed >= self.drought_threshold_seconds else 0.0
        
        final_thresh = base_threshold - (vol_adjustment * 10.0) - drought_reduction
        return max(65.0, min(75.0, round(final_thresh, 2)))

    def aggregate(self, candidates: List[dict], macro_context: dict, extra_context: dict = None) -> Optional[dict]:
        if not candidates:
            return None

        extra_ctx = extra_context or {}
        symbol = candidates[0].get('symbol', 'UNKNOWN')
        dynamic_thresh = self.get_dynamic_threshold(symbol, extra_ctx)

        # Filter out candidates below dynamic threshold
        valid = [c for c in candidates if c and c.get('confidence', 0) >= dynamic_thresh]
        if not valid:
            return None

        # Check for conflicting directions on the same symbol
        longs = [c for c in valid if c['side'] == "LONG"]
        shorts = [c for c in valid if c['side'] == "SHORT"]

        if longs and shorts:
            # Direct directional conflict -> Fail closed and return None (No Trade)
            return None

        # Sort valid candidates by weighted confidence
        scored = []
        for c in valid:
            strat = c.get('strategy_name', '')
            w = self.strategy_weights.get(strat, 1.0)
            score = c.get('confidence', 0.0) * w
            scored.append((score, c))

        scored.sort(key=lambda x: x[0], reverse=True)
        best_signal = scored[0][1]

        # Apply Macro Sentiment Modifier
        news_sentiment = macro_context.get('news_sentiment_score', 0.0)
        if best_signal['side'] == "LONG" and news_sentiment < -0.6:
            # Extreme negative news headline detected -> skip LONG
            return None
        if best_signal['side'] == "SHORT" and news_sentiment > +0.6:
            # Extreme positive news headline detected -> skip SHORT
            return None

        # 🟢 Smart Money & Top Trader Confluence Integration
        smart_money = extra_ctx.get('smart_money', {})
        if smart_money:
            bias = float(smart_money.get('bias', 0.0))
            long_pct = float(smart_money.get('long_pct', 50.0))
            short_pct = float(smart_money.get('short_pct', 50.0))
            
            # 1. Smart Money Confluence Boost (+3.5% confidence)
            if best_signal['side'] == "LONG" and (bias >= 0.15 or long_pct >= 60.0):
                best_signal['confidence'] = min(88.0, round(best_signal['confidence'] + 3.5, 2))
                best_signal['smart_money_confluence'] = "ALIGNED_BULLISH"
            elif best_signal['side'] == "SHORT" and (bias <= -0.15 or short_pct >= 60.0):
                best_signal['confidence'] = min(88.0, round(best_signal['confidence'] + 3.5, 2))
                best_signal['smart_money_confluence'] = "ALIGNED_BEARISH"
            
            # 2. Extreme Smart Money Divergence Filter (Reject if >= 78% Whales oppose)
            if best_signal['side'] == "LONG" and short_pct >= 78.0:
                return None # Whale positioning overwhelmingly short -> veto long
            elif best_signal['side'] == "SHORT" and long_pct >= 78.0:
                return None # Whale positioning overwhelmingly long -> veto short

        # Signal accepted -> reset drought timer
        self.last_signal_time = time.time()
        best_signal['dynamic_threshold_used'] = dynamic_thresh
        return best_signal
