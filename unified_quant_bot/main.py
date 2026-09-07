import asyncio
import os
import sys
import time
import joblib
import pandas as pd
import numpy as np
from datetime import datetime, timezone

# Add repository root to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sklearn.base import BaseEstimator, ClassifierMixin

class ManualCalibratedClassifier(BaseEstimator, ClassifierMixin):
    """Calibrated Classifier wrapper allowing joblib to deserialize and predict probabilities cleanly."""
    def __init__(self, estimator=None, cv=3):
        self.estimator = estimator
        self.cv = cv

    def predict_proba(self, X):
        if hasattr(self, 'calibrators_') and hasattr(self, 'estimator_'):
            raw_probs = self.estimator_.predict_proba(X)
            calibrated_probs = np.zeros_like(raw_probs)
            for i, calibrator in enumerate(self.calibrators_):
                calibrated_probs[:, i] = calibrator.predict(raw_probs[:, i])
            row_sums = calibrated_probs.sum(axis=1, keepdims=True)
            row_sums[row_sums == 0] = 1.0
            return calibrated_probs / row_sums
        elif hasattr(self, 'estimator_'):
            return self.estimator_.predict_proba(X)
        elif hasattr(self, 'estimator') and hasattr(self.estimator, 'predict_proba'):
            return self.estimator.predict_proba(X)
        return np.array([[0.5, 0.5]])

from unified_quant_bot.config.config import (
    ALL_SYMBOLS, TARGET_SYMBOLS, TIMEFRAMES, REPO_ROOT
)
from unified_quant_bot.data.database_schema import init_unified_db, AsyncSessionLocal, SignalRejection
from unified_quant_bot.data.redis_store import RedisStore
from unified_quant_bot.data.macro_sentiment import MacroSentimentEngine
from unified_quant_bot.data.market_collector import UnifiedMarketCollector
from unified_quant_bot.features.feature_engine import FeatureEngine
from unified_quant_bot.features.pump_scanner import PumpScanner
from unified_quant_bot.strategies.shotgun_momentum import ShotgunMomentumStrategy
from unified_quant_bot.strategies.liquidation_hunter import LiquidationCascadeStrategy
from unified_quant_bot.strategies.mean_reversion import StatisticalMeanReversionStrategy
from unified_quant_bot.strategies.pump_momentum import VolumePumpMomentumStrategy
from unified_quant_bot.aggregator.signal_aggregator import SignalAggregator
from unified_quant_bot.execution.risk_engine import RiskEngine
from unified_quant_bot.execution.paper_tracker import PaperTracker
from unified_quant_bot.execution.binance_client import BinanceExecutionClient
from unified_quant_bot.monitoring.telegram_gateway import TelegramGateway

from unified_quant_bot.models.ensemble_brain import MetaLabelingFilter
from unified_quant_bot.monitoring.drift_monitor import ModelDriftMonitor
from unified_quant_bot.data.lead_trader_collector import LeadTraderCollector
from unified_quant_bot.data.hyperliquid_collector import HyperliquidWhaleCollector

# Global runtime objects
redis_store = RedisStore()
macro_engine = MacroSentimentEngine()
collector = UnifiedMarketCollector(redis_store)
lead_trader_collector = LeadTraderCollector(TARGET_SYMBOLS)
hyperliquid_collector = HyperliquidWhaleCollector()
feature_engine = FeatureEngine()
pump_scanner = PumpScanner()
meta_filter = MetaLabelingFilter(min_meta_confidence=65.0)
drift_monitor = ModelDriftMonitor(window_size=50, brier_alert_threshold=0.25)

strategies = [
    ShotgunMomentumStrategy(),           # 15m Trend + Binance Order Flow (CVD & Depth Wall Confluence)
    StatisticalMeanReversionStrategy(),  # 15m Mean Reversion + Binance Wall Absorption
    VolumePumpMomentumStrategy()         # 15m Volume Surge Scanner
]

aggregator = SignalAggregator()
risk_engine = RiskEngine()
paper_tracker = PaperTracker()
binance_client = BinanceExecutionClient()
telegram_gateway = TelegramGateway()

loaded_brains = {}
current_prices = {}

def load_ml_brains():
    """Loads pre-trained ML brain classifiers from repository root."""
    for symbol in TARGET_SYMBOLS:
        fname = f"{symbol.replace('/', '_')}_brain.pkl"
        path = os.path.join(REPO_ROOT, fname)
        if os.path.exists(path):
            try:
                raw_brain = joblib.load(path)
                model = raw_brain['model'] if isinstance(raw_brain, dict) and 'model' in raw_brain else raw_brain
                loaded_brains[symbol] = model
                print(f"[ORCHESTRATOR] Loaded ML brain for {symbol}")
            except Exception as e:
                print(f"[ORCHESTRATOR] Brain load warning for {symbol}: {e}")

last_eval_time = {}

async def handle_candle_closed(symbol: str, timeframe: str, latest_bar: dict):
    """Callback fired on incoming candle streams with CPU-optimized throttling for heavy feature extraction."""
    if symbol not in TARGET_SYMBOLS:
        return

    close_price = latest_bar['close']
    current_prices[symbol] = close_price

    # 1. Evaluate open paper positions for TP/SL resolution (Fast O(1) in-memory check)
    closed_events = paper_tracker.update_positions({symbol: latest_bar})
    for ce in closed_events:
        risk_engine.unregister_position(ce['symbol'])
        is_win = (ce['status'] == "PROFIT")
        risk_engine.record_trade_result(ce['symbol'], is_win)
        try:
            prob_num = float(str(ce.get('win_prob', '65.0')).replace('%', '').strip())
            drift_monitor.record_prediction_outcome(prob_num, is_win)
        except Exception:
            pass
        
        stats = paper_tracker.get_stats()
        # Muted internal bot trade closed alert (routed exclusively to Copy Trader signals)

    # 🟢 High-Efficiency CPU Throttle: Only compute 500-bar Pandas feature vectors and ML inference once every 10s per symbol
    now = time.time()
    if (now - last_eval_time.get(symbol, 0)) < 10.0:
        return
    last_eval_time[symbol] = now

    # 2. Fetch multi-timeframe candles from Redis
    df_1m = await redis_store.get_candles_dataframe(symbol, "1m")
    df_15m = await redis_store.get_candles_dataframe(symbol, "15m")

    if len(df_1m) < 30:
        return

    # Calculate indicators
    df_1m_ind = feature_engine.calculate_indicators(df_1m)
    df_15m_ind = feature_engine.calculate_indicators(df_15m) if len(df_15m) >= 50 else df_1m_ind

    # Microstructure context
    cvd = await redis_store.get_cvd(symbol)
    ob_snapshot = await redis_store.get_orderbook_snapshot(symbol)
    pump_info = pump_scanner.scan(symbol, df_1m)
    ml_brain = loaded_brains.get(symbol)

    expected_n = getattr(ml_brain, 'n_features_in_', None)
    if expected_n is None and hasattr(ml_brain, 'estimator_'):
        expected_n = getattr(ml_brain.estimator_, 'n_features_in_', 12)
    expected_n = expected_n or 12
    feat_vec = feature_engine.extract_12_feature_vector(df_15m_ind, n_features=expected_n)

    atr_14 = float(df_15m_ind['atr_14'].iloc[-1]) if 'atr_14' in df_15m_ind.columns else (close_price * 0.015)
    atr_100 = float(df_15m_ind['atr_14'].rolling(min(100, len(df_15m_ind))).mean().iloc[-1]) if 'atr_14' in df_15m_ind.columns else atr_14
    smart_money = lead_trader_collector.get_symbol_consensus(symbol)

    extra_ctx = {
        "cvd": cvd,
        "orderbook": ob_snapshot,
        "pump_info": pump_info,
        "ml_brain": ml_brain,
        "feature_vector": feat_vec,
        "atr_14": atr_14,
        "atr_100": atr_100,
        "smart_money": smart_money
    }

    # 3. Evaluate multi-strategy candidates
    candidates = []
    for strat in strategies:
        target_df = df_15m_ind if strat.timeframe() == "15m" else df_1m_ind
        sig = strat.evaluate(symbol, target_df, extra_ctx)
        if sig:
            candidates.append(sig)

    if not candidates:
        return

    # 4. Aggregate & Arbitrate Candidates (with dynamic thresholds & drought contingency)
    macro_snap = macro_engine.get_macro_snapshot()
    best_signal = aggregator.aggregate(candidates, macro_snap, extra_ctx)

    # 4.5 Evaluate Secondary Meta-Labeling Quality Filter (Prado Framework)
    meta_audit = meta_filter.evaluate_trade_proposal(
        symbol=symbol,
        direction=best_signal['side'],
        strategy=best_signal['strategy_name'],
        base_confidence=best_signal['confidence'],
        extra_context=extra_ctx
    )
    meta_risk = risk_engine.validate_meta_labeling(meta_audit)
    if not meta_risk['eligible']:
        return

    # 5. Evaluate Deterministic Risk Engine
    balance = await binance_client.get_margin_balance()
    spread_pct = (ob_snapshot.get('spread', 0.0) / close_price) * 100.0 if close_price > 0 else 0.02

    risk_audit = risk_engine.evaluate_order_proposal(
        symbol=symbol,
        direction=best_signal['side'],
        entry=best_signal['entry_price'],
        sl=best_signal['stop_loss'],
        tp=best_signal['take_profit'],
        balance=balance,
        spread_pct=spread_pct
    )

    if risk_audit['eligible']:
        # Auto-Approve Paper Trade
        risk_engine.register_position(symbol)
        paper_tracker.record_entry(
            symbol=symbol,
            direction=best_signal['side'],
            strategy=best_signal['strategy_name'],
            entry=best_signal['entry_price'],
            sl=best_signal['stop_loss'],
            tp=best_signal['take_profit'],
            quantity=risk_audit['quantity'],
            win_prob=best_signal['confidence']
        )
        # Muted internal bot trade execution alert (routed exclusively to Copy Trader signals)
    else:
        # Log to Rejection Audit
        try:
            async with AsyncSessionLocal() as db:
                rej = SignalRejection(
                    symbol=symbol,
                    direction=best_signal['side'],
                    strategy=best_signal['strategy_name'],
                    win_prob=best_signal['confidence'],
                    threshold=65.0,
                    regime=best_signal['market_regime'],
                    rejection_reason=risk_audit.get('reason', 'RISK_REJECTED'),
                    entry_price=best_signal['entry_price'],
                    sl_price=best_signal['stop_loss'],
                    tp_price=best_signal['take_profit']
                )
                db.add(rej)
                await db.commit()
        except Exception:
            pass

async def periodic_intelligence_loop():
    """Background worker updating macro metrics silently in background (periodic Telegram reports disabled per user request)."""
    while True:
        try:
            await macro_engine.update_all_macro_metrics()
        except Exception as e:
            print(f"[BACKGROUND LOOP ERROR]: {e}")
        await asyncio.sleep(1800) # Every 30 minutes

import subprocess

async def scheduled_auto_train_loop():
    """Background auto-trainer worker executing weekly retrain every Sunday at 02:00 UTC and hot-reloading brains."""
    last_trained_week = None
    while True:
        try:
            now = datetime.now(timezone.utc)
            current_week = now.isocalendar()[1]
            if now.weekday() == 6 and now.hour == 2 and last_trained_week != current_week:
                last_trained_week = current_week
                await telegram_gateway.send_message("🤖 *[ALPHAQUANT UNIFIED]*\nStarting automated weekly model retraining cycle...")
                
                pipeline_script = os.path.join(REPO_ROOT, "run_full_pipeline_v8.py")
                if os.path.exists(pipeline_script):
                    start_t = datetime.now(timezone.utc)
                    def run_pipeline():
                        return subprocess.run(
                            [sys.executable, pipeline_script],
                            capture_output=True,
                            text=True,
                            timeout=3600,
                            cwd=REPO_ROOT
                        )
                    res = await asyncio.to_thread(run_pipeline)
                    duration = (datetime.now(timezone.utc) - start_t).total_seconds() / 60.0
                    
                    if res.returncode == 0:
                        load_ml_brains() # Hot-reload updated brain models into RAM!
                        await telegram_gateway.send_message(
                            f"✅ *[ALPHAQUANT UNIFIED]*\n"
                            f"Weekly model retraining cycle completed successfully in *{duration:.1f} minutes*.\n"
                            f"New AI brains are now hot-reloaded and live."
                        )
                    else:
                        await telegram_gateway.send_message(
                            f"❌ *[ALPHAQUANT UNIFIED]*\nRetraining failed:\n```\n{res.stderr[-500:]}\n```"
                        )
        except Exception as e:
            print(f"[AUTO-TRAIN ERROR]: {e}")
        await asyncio.sleep(1800) # Check every 30 minutes

async def main():
    print("==================================================")
    print("   ALPHAQUANT UNIFIED QUANTITATIVE SIGNAL ENGINE  ")
    print("==================================================")

    # 1. Initialize Database Schema
    await init_unified_db()

    # 2. Load ML Brain Models
    load_ml_brains()

    # 3. Initialize Execution Client
    await binance_client.initialize()

    # 4. Pre-warm Redis Ring Buffers
    await collector.prewarm_buffers()

    # 5. Register Candle, Binance Copy Trader & Hyperliquid Whale Callbacks
    collector.register_candle_callback(handle_candle_closed)
    lead_trader_collector.register_position_callback(telegram_gateway.send_copy_trader_signal)
    hyperliquid_collector.register_whale_callback(telegram_gateway.send_hyperliquid_whale_signal)

    # 6. Launch Collector, Binance Lead Traders, Hyperliquid On-Chain Whales, Periodic Intelligence, and Auto-Train Loops
    await asyncio.gather(
        collector.start_all_streams(),
        lead_trader_collector.start_polling_loop(interval_seconds=45),
        hyperliquid_collector.run_loop(poll_interval_seconds=15),
        periodic_intelligence_loop(),
        scheduled_auto_train_loop(),
        return_exceptions=True
    )

if __name__ == "__main__":
    asyncio.run(main())
