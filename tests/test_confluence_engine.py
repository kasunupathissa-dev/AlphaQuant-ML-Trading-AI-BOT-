import unittest
import numpy as np
import pandas as pd
from unified_quant_bot.features.smc_engine import SmartMoneyConceptsEngine
from unified_quant_bot.aggregator.confluence_engine import TriFactorConfluenceEngine

class TestConfluenceEngine(unittest.TestCase):

    def setUp(self):
        # Generate synthetic 15m OHLCV DataFrame
        np.random.seed(42)
        n = 50
        base_price = 100.0
        returns = np.random.normal(0.001, 0.01, n)
        closes = base_price * np.cumprod(1 + returns)
        highs = closes * (1 + np.random.uniform(0.001, 0.005, n))
        lows = closes * (1 - np.random.uniform(0.001, 0.005, n))
        opens = np.roll(closes, 1)
        opens[0] = base_price
        volumes = np.random.uniform(100, 1000, n)

        self.df = pd.DataFrame({
            'open': opens,
            'high': highs,
            'low': lows,
            'close': closes,
            'volume': volumes
        })

        self.smc_engine = SmartMoneyConceptsEngine()
        self.confluence_engine = TriFactorConfluenceEngine(min_ml_confidence=65.0, min_smc_score=55.0)

    def test_smc_order_blocks(self):
        res = self.smc_engine.detect_order_blocks(self.df)
        self.assertIn("bullish_ob", res)
        self.assertIn("bearish_ob", res)
        self.assertIn("score", res)
        self.assertIsInstance(res['score'], float)

    def test_smc_fair_value_gaps(self):
        res = self.smc_engine.detect_fair_value_gaps(self.df)
        self.assertIn("bullish_fvg", res)
        self.assertIn("bearish_fvg", res)
        self.assertIn("score", res)

    def test_smc_liquidity_sweeps(self):
        res = self.smc_engine.detect_liquidity_sweeps(self.df)
        self.assertIn("sweep_high", res)
        self.assertIn("sweep_low", res)

    def test_smc_break_of_structure(self):
        res = self.smc_engine.detect_break_of_structure(self.df)
        self.assertIn("bullish_bos", res)
        self.assertIn("bearish_bos", res)

    def test_smc_composite_score(self):
        res = self.smc_engine.compute_smc_composite_score(self.df, "LONG")
        self.assertIn("composite_score", res)
        self.assertGreaterEqual(res['composite_score'], 0.0)
        self.assertLessEqual(res['composite_score'], 100.0)

    def test_confluence_high_confidence_approval(self):
        extra_ctx = {
            "cvd": 500.0,
            "smart_money": {"dominant_side": "LONG"},
            "whale_bias": "LONG"
        }
        res = self.confluence_engine.evaluate_confluence(
            symbol="BTC/USDT",
            direction="LONG",
            ml_confidence=82.0,
            df_candles=self.df,
            extra_context=extra_ctx,
            bars_since_signal=0
        )
        self.assertTrue(res['is_approved'])
        self.assertIn(res['grade'], ["A+", "A", "B", "C"])
        self.assertGreater(res['size_multiplier'], 0.0)

    def test_confluence_low_ml_rejection(self):
        extra_ctx = {"cvd": -100.0}
        res = self.confluence_engine.evaluate_confluence(
            symbol="BTC/USDT",
            direction="LONG",
            ml_confidence=52.0, # Below 65.0 threshold
            df_candles=self.df,
            extra_context=extra_ctx,
            bars_since_signal=0
        )
        self.assertFalse(res['is_approved'])
        self.assertEqual(res['grade'], "REJECT")
        self.assertIn("ML_CONFIDENCE_LOW", res['rejection_reason'])

    def test_confluence_decay_penalty(self):
        extra_ctx = {"cvd": 500.0, "smart_money": {"dominant_side": "LONG"}}
        # Fresh signal (0 bars)
        fresh_res = self.confluence_engine.evaluate_confluence(
            symbol="BTC/USDT",
            direction="LONG",
            ml_confidence=70.0,
            df_candles=self.df,
            extra_context=extra_ctx,
            bars_since_signal=0
        )
        # Decayed signal (4 bars late)
        decayed_res = self.confluence_engine.evaluate_confluence(
            symbol="BTC/USDT",
            direction="LONG",
            ml_confidence=70.0,
            df_candles=self.df,
            extra_context=extra_ctx,
            bars_since_signal=4
        )
        self.assertLess(decayed_res['effective_confluence'], fresh_res['effective_confluence'])

if __name__ == '__main__':
    unittest.main()
