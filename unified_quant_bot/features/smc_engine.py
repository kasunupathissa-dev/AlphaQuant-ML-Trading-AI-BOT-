import numpy as np
import pandas as pd
from typing import Dict, Any, List, Optional, Tuple

class SmartMoneyConceptsEngine:
    """
    Institutional Smart Money Concepts (SMC) & Market Structure Engine.
    Computes 5 core structural factors:
      1. Order Block Strength (25% weight)
      2. Fair Value Gap (FVG) Inefficiency (20% weight)
      3. Liquidity Zone Sweeps (20% weight)
      4. Break of Structure (BOS) / Change of Character (CHoCH) (20% weight)
      5. Multi-Timeframe Trend & EMA Alignment (15% weight)
    """

    def __init__(self, swing_lookback: int = 5):
        self.swing_lookback = swing_lookback

    def detect_order_blocks(self, df: pd.DataFrame) -> Dict[str, Any]:
        """
        Detects volume-validated Order Blocks (last opposing candle before a strong impulse).
        """
        if len(df) < 10:
            return {"bullish_ob": False, "bearish_ob": False, "score": 50.0}

        closes = df['close'].values
        opens = df['open'].values
        highs = df['high'].values
        lows = df['low'].values
        volumes = df['volume'].values

        avg_vol = np.mean(volumes[-20:]) if len(volumes) >= 20 else np.mean(volumes)

        # Check last 3 candles for an impulse move
        recent_body = abs(closes[-1] - opens[-1])
        prior_body = abs(closes[-2] - opens[-2])
        is_high_volume = volumes[-1] > (1.2 * avg_vol) or volumes[-2] > (1.2 * avg_vol)

        bullish_ob = False
        bearish_ob = False

        # Bullish OB: Prior candle was bearish (red), current or subsequent is strong bullish with volume
        if closes[-2] < opens[-2] and closes[-1] > opens[-1] and closes[-1] > highs[-2] and is_high_volume:
            bullish_ob = True

        # Bearish OB: Prior candle was bullish (green), current or subsequent is strong bearish with volume
        if closes[-2] > opens[-2] and closes[-1] < opens[-1] and closes[-1] < lows[-2] and is_high_volume:
            bearish_ob = True

        score = 50.0
        if bullish_ob or bearish_ob:
            score = 85.0 if is_high_volume else 70.0

        return {
            "bullish_ob": bullish_ob,
            "bearish_ob": bearish_ob,
            "score": score
        }

    def detect_fair_value_gaps(self, df: pd.DataFrame) -> Dict[str, Any]:
        """
        Detects 3-candle Fair Value Gaps (FVG) / Price Inefficiencies.
        Bullish FVG: Low of candle[i] > High of candle[i-2]
        Bearish FVG: High of candle[i] < Low of candle[i-2]
        """
        if len(df) < 5:
            return {"bullish_fvg": False, "bearish_fvg": False, "fvg_size_pct": 0.0, "score": 50.0}

        highs = df['high'].values
        lows = df['low'].values
        closes = df['close'].values

        # Candle i (latest -1), candle i-1 (-2), candle i-2 (-3)
        bullish_fvg = lows[-1] > highs[-3]
        bearish_fvg = highs[-1] < lows[-3]

        fvg_size_pct = 0.0
        score = 50.0

        if bullish_fvg and closes[-1] > 0:
            fvg_size_pct = ((lows[-1] - highs[-3]) / closes[-1]) * 100.0
            score = min(95.0, 60.0 + (fvg_size_pct * 20.0))
        elif bearish_fvg and closes[-1] > 0:
            fvg_size_pct = ((lows[-3] - highs[-1]) / closes[-1]) * 100.0
            score = min(95.0, 60.0 + (fvg_size_pct * 20.0))

        return {
            "bullish_fvg": bullish_fvg,
            "bearish_fvg": bearish_fvg,
            "fvg_size_pct": round(fvg_size_pct, 4),
            "score": score
        }

    def detect_liquidity_sweeps(self, df: pd.DataFrame) -> Dict[str, Any]:
        """
        Detects stop-hunt Liquidity Sweeps at recent swing highs and swing lows.
        Sweep High: Price pierced swing high but closed back below it (bearish rejection wick).
        Sweep Low: Price pierced swing low but closed back above it (bullish rejection wick).
        """
        if len(df) < 15:
            return {"sweep_high": False, "sweep_low": False, "score": 50.0}

        highs = df['high'].values
        lows = df['low'].values
        closes = df['close'].values

        swing_high = np.max(highs[-15:-2])
        swing_low = np.min(lows[-15:-2])

        curr_high = highs[-1]
        curr_low = lows[-1]
        curr_close = closes[-1]

        sweep_high = (curr_high > swing_high) and (curr_close < swing_high)
        sweep_low = (curr_low < swing_low) and (curr_close > swing_low)

        score = 50.0
        if sweep_low or sweep_high:
            score = 85.0

        return {
            "sweep_high": sweep_high,
            "sweep_low": sweep_low,
            "score": score
        }

    def detect_break_of_structure(self, df: pd.DataFrame) -> Dict[str, Any]:
        """
        Detects Break of Structure (BOS) and Change of Character (CHoCH).
        Bullish BOS: Clean close above recent swing high.
        Bearish BOS: Clean close below recent swing low.
        """
        if len(df) < 20:
            return {"bullish_bos": False, "bearish_bos": False, "score": 50.0}

        highs = df['high'].values
        lows = df['low'].values
        closes = df['close'].values

        recent_high = np.max(highs[-15:-1])
        recent_low = np.min(lows[-15:-1])

        bullish_bos = closes[-1] > recent_high
        bearish_bos = closes[-1] < recent_low

        score = 50.0
        if bullish_bos or bearish_bos:
            score = 80.0

        return {
            "bullish_bos": bullish_bos,
            "bearish_bos": bearish_bos,
            "score": score
        }

    def evaluate_trend_alignment(self, df: pd.DataFrame) -> Dict[str, Any]:
        """
        Evaluates Multi-Timeframe Trend & EMA Stack Alignment (EMA 20, 50, 200).
        """
        if len(df) < 30:
            return {"trend_bias": "NEUTRAL", "score": 50.0}

        close_series = df['close']
        ema_20 = close_series.ewm(span=20, adjust=False).mean().iloc[-1]
        ema_50 = close_series.ewm(span=50, adjust=False).mean().iloc[-1] if len(df) >= 50 else ema_20

        curr_close = close_series.iloc[-1]

        if curr_close > ema_20 > ema_50:
            trend_bias = "BULLISH"
            score = 85.0
        elif curr_close < ema_20 < ema_50:
            trend_bias = "BEARISH"
            score = 85.0
        else:
            trend_bias = "NEUTRAL"
            score = 50.0

        return {
            "trend_bias": trend_bias,
            "score": score
        }

    def compute_smc_composite_score(self, df: pd.DataFrame, target_direction: str) -> Dict[str, Any]:
        """
        Aggregates all 5 SMC components into a unified 0-100 SMC Confluence Score.
        Weights:
          - Order Block: 25%
          - Fair Value Gap: 20%
          - Liquidity Sweep: 20%
          - Break of Structure: 20%
          - Trend Alignment: 15%
        """
        direction = target_direction.upper()

        ob_res = self.detect_order_blocks(df)
        fvg_res = self.detect_fair_value_gaps(df)
        liq_res = self.detect_liquidity_sweeps(df)
        bos_res = self.detect_break_of_structure(df)
        trend_res = self.evaluate_trend_alignment(df)

        # Directional scoring
        ob_score = ob_res['score'] if (direction == "LONG" and ob_res['bullish_ob']) or (direction == "SHORT" and ob_res['bearish_ob']) else 45.0
        fvg_score = fvg_res['score'] if (direction == "LONG" and fvg_res['bullish_fvg']) or (direction == "SHORT" and fvg_res['bearish_fvg']) else 45.0
        liq_score = liq_res['score'] if (direction == "LONG" and liq_res['sweep_low']) or (direction == "SHORT" and liq_res['sweep_high']) else 50.0
        bos_score = bos_res['score'] if (direction == "LONG" and bos_res['bullish_bos']) or (direction == "SHORT" and bos_res['bearish_bos']) else 45.0
        trend_score = trend_res['score'] if (direction == "LONG" and trend_res['trend_bias'] == "BULLISH") or (direction == "SHORT" and trend_res['trend_bias'] == "BEARISH") else 40.0

        composite_score = (
            (ob_score * 0.25) +
            (fvg_score * 0.20) +
            (liq_score * 0.20) +
            (bos_score * 0.20) +
            (trend_score * 0.15)
        )

        return {
            "composite_score": round(composite_score, 2),
            "order_block": ob_res,
            "fair_value_gap": fvg_res,
            "liquidity_sweep": liq_res,
            "break_of_structure": bos_res,
            "trend_alignment": trend_res,
            "direction": direction
        }
