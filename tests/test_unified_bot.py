import unittest
import numpy as np
import pandas as pd
from unified_quant_bot.features.feature_engine import FeatureEngine
from unified_quant_bot.features.pump_scanner import PumpScanner
from unified_quant_bot.strategies.shotgun_momentum import ShotgunMomentumStrategy
from unified_quant_bot.strategies.liquidation_hunter import LiquidationCascadeStrategy
from unified_quant_bot.strategies.mean_reversion import StatisticalMeanReversionStrategy
from unified_quant_bot.strategies.pump_momentum import VolumePumpMomentumStrategy
from unified_quant_bot.aggregator.signal_aggregator import SignalAggregator
from unified_quant_bot.execution.risk_engine import RiskEngine
from unified_quant_bot.execution.paper_tracker import PaperTracker

class TestUnifiedQuantBot(unittest.TestCase):

    def setUp(self):
        # Create synthetic OHLCV dataframe (100 bars)
        dates = pd.date_range("2026-08-26 00:00:00", periods=100, freq="15min")
        close_prices = 100.0 + np.cumsum(np.random.normal(0.1, 0.5, 100))
        high_prices = close_prices + np.random.uniform(0.1, 0.8, 100)
        low_prices = close_prices - np.random.uniform(0.1, 0.8, 100)
        volumes = np.random.uniform(1000, 5000, 100)

        self.df = pd.DataFrame({
            "timestamp": [int(d.timestamp() * 1000) for d in dates],
            "open": close_prices - 0.05,
            "high": high_prices,
            "low": low_prices,
            "close": close_prices,
            "volume": volumes
        })

    def test_feature_engine(self):
        df_ind = FeatureEngine.calculate_indicators(self.df)
        self.assertIn("ema_9", df_ind.columns)
        self.assertIn("atr_14", df_ind.columns)
        self.assertIn("adx_14", df_ind.columns)
        self.assertIn("chop_index", df_ind.columns)

        feat_vec = FeatureEngine.extract_12_feature_vector(df_ind)
        self.assertEqual(feat_vec.shape, (1, 12))

    def test_pump_scanner(self):
        scanner = PumpScanner()
        # Normal scan
        res_normal = scanner.scan("SOL/USDT", self.df)
        self.assertFalse(res_normal["pump_detected"])

        # Inject extreme volume pump
        df_pump = self.df.copy()
        df_pump.loc[df_pump.index[-1], 'volume'] = 50000.0
        df_pump.loc[df_pump.index[-1], 'close'] = df_pump['close'].iloc[-2] * 1.05

        res_pump = scanner.scan("SOL/USDT", df_pump)
        self.assertTrue(res_pump["pump_detected"])
        self.assertEqual(res_pump["direction"], "LONG")

    def test_signal_aggregator(self):
        aggregator = SignalAggregator()
        c1 = {
            "signal_id": "sig_1",
            "strategy_name": "ShotgunMomentumStrategy",
            "side": "LONG",
            "confidence": 72.0
        }
        c2 = {
            "signal_id": "sig_2",
            "strategy_name": "LiquidationCascadeStrategy",
            "side": "LONG",
            "confidence": 68.0
        }
        best = aggregator.aggregate([c1, c2], {"news_sentiment_score": 0.1})
        self.assertIsNotNone(best)
        self.assertEqual(best["strategy_name"], "ShotgunMomentumStrategy")

    def test_risk_engine(self):
        risk = RiskEngine()
        proposal = risk.evaluate_order_proposal(
            symbol="SOL/USDT",
            direction="LONG",
            entry=100.0,
            sl=98.0,
            tp=103.0,
            balance=1000.0,
            spread_pct=0.02
        )
        self.assertTrue(proposal["eligible"])
        self.assertGreater(proposal["quantity"], 0.0)

if __name__ == "__main__":
    unittest.main()
