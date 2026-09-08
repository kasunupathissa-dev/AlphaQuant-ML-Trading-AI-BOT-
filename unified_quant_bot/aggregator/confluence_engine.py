import os
import time
import math
from typing import Dict, Any, Optional, Tuple
from unified_quant_bot.features.smc_engine import SmartMoneyConceptsEngine

class TriFactorConfluenceEngine:
    """
    Institutional Tri-Factor Confluence Engine (AlphaQuant V2.0).
    Fuses:
      1. Factor 1: Machine Learning Model Confidence (>= 65.0%)
      2. Factor 2: Smart Money Concepts (SMC) Composite Score (>= 60.0)
      3. Factor 3: External Institutional Bias (Hyperliquid Whale Flow, Binance CVD, Copy Traders)
    
    Provides:
      - Signal Quality Grading (A+, A, B, C, REJECT)
      - Dynamic Position Size Multiplier (1.0, 0.75, 0.50, 0.0)
      - Confluence Decay (Late Entry Protection against exhausted impulses)
    """

    def __init__(
        self,
        min_ml_confidence: float = 65.0,
        min_smc_score: float = 60.0,
        decay_rate_per_bar: float = 0.20
    ):
        self.min_ml_confidence = min_ml_confidence
        self.min_smc_score = min_smc_score
        self.decay_rate_per_bar = decay_rate_per_bar
        self.smc_engine = SmartMoneyConceptsEngine()

    def evaluate_confluence(
        self,
        symbol: str,
        direction: str,
        ml_confidence: float,
        df_candles,
        extra_context: Dict[str, Any],
        bars_since_signal: int = 0
    ) -> Dict[str, Any]:
        """
        Evaluates the trade proposal against the Tri-Factor Institutional Confluence Gate.
        """
        direction = direction.upper()

        # 1. Evaluate Factor 1: Machine Learning Probability Score
        f1_pass = (ml_confidence >= self.min_ml_confidence)
        f1_score = ml_confidence

        # 2. Evaluate Factor 2: Smart Money Concepts (SMC) Structure
        smc_eval = self.smc_engine.compute_smc_composite_score(df_candles, direction)
        smc_raw_score = smc_eval['composite_score']
        f2_pass = (smc_raw_score >= self.min_smc_score)

        # 3. Evaluate Factor 3: External Smart Money & Institutional Flow
        smart_money = extra_context.get('smart_money', {})
        cvd_val = float(extra_context.get('cvd', 0.0) or 0.0)
        whale_flow = extra_context.get('whale_bias', 'NEUTRAL') # Can be passed or inferred

        # Consensus alignment check
        lead_consensus = smart_money.get('dominant_side', 'NEUTRAL') if isinstance(smart_money, dict) else 'NEUTRAL'
        cvd_aligned = (direction == "LONG" and cvd_val >= 0) or (direction == "SHORT" and cvd_val <= 0)
        lead_aligned = (direction == lead_consensus) if lead_consensus in ("LONG", "SHORT") else True

        f3_aligned_factors = 0
        if cvd_aligned:
            f3_aligned_factors += 1
        if lead_aligned:
            f3_aligned_factors += 1
        if whale_flow == direction:
            f3_aligned_factors += 1

        f3_score = 50.0 + (f3_aligned_factors * 16.6)
        f3_pass = (f3_aligned_factors >= 1) # At least 1 external confirmation required

        # 4. Overall Composite Confluence Score
        composite_confluence = (
            (f1_score * 0.40) +
            (smc_raw_score * 0.35) +
            (f3_score * 0.25)
        )

        # 5. Apply Confluence Decay (Late Entry Protection)
        # Effective Confluence = Raw Confluence * (1 - decay_rate ^ bars)
        decay_multiplier = math.pow((1.0 - self.decay_rate_per_bar), max(0, bars_since_signal))
        effective_confluence = round(composite_confluence * decay_multiplier, 2)

        # 6. Signal Quality Grading & Position Sizing
        # Grade A+: All factors exceptional (ML >= 80%, SMC >= 75%, External aligned)
        # Grade A : Confluence >= 70, ML >= 75%
        # Grade B : Confluence >= 60, ML >= 65%
        # Grade C : Confluence >= 55, ML >= 65%
        # Reject  : Below threshold or missing primary factor
        grade = "REJECT"
        size_multiplier = 0.0
        is_approved = False

        if f1_pass and effective_confluence >= 55.0:
            if ml_confidence >= 80.0 and smc_raw_score >= 75.0 and f3_aligned_factors >= 2:
                grade = "A+"
                size_multiplier = 1.00
                is_approved = True
            elif effective_confluence >= 70.0 and ml_confidence >= 75.0:
                grade = "A"
                size_multiplier = 1.00
                is_approved = True
            elif effective_confluence >= 62.0 and ml_confidence >= 65.0:
                grade = "B"
                size_multiplier = 0.75
                is_approved = True
            elif effective_confluence >= 55.0 and ml_confidence >= 65.0:
                grade = "C"
                size_multiplier = 0.50
                is_approved = True

        rejection_reason = None
        if not is_approved:
            if not f1_pass:
                rejection_reason = f"ML_CONFIDENCE_LOW ({ml_confidence:.1f}% < {self.min_ml_confidence}%)"
            elif not f2_pass:
                rejection_reason = f"SMC_STRUCTURE_WEAK (Score {smc_raw_score:.1f} < {self.min_smc_score})"
            elif effective_confluence < 55.0:
                rejection_reason = f"CONFLUENCE_DECAYED_OR_LOW (Effective {effective_confluence:.1f} < 55.0)"
            else:
                rejection_reason = "CONFLUENCE_GATE_REJECTED"

        return {
            "is_approved": is_approved,
            "grade": grade,
            "size_multiplier": size_multiplier,
            "effective_confluence": effective_confluence,
            "raw_confluence": round(composite_confluence, 2),
            "decay_multiplier": round(decay_multiplier, 3),
            "factor_1_ml": {"score": f1_score, "passed": f1_pass},
            "factor_2_smc": smc_eval,
            "factor_3_external": {
                "score": f3_score,
                "passed": f3_pass,
                "cvd_aligned": cvd_aligned,
                "lead_aligned": lead_aligned,
                "whale_flow": whale_flow
            },
            "rejection_reason": rejection_reason
        }
