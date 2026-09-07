import asyncio
import os
import sys
import pickle
import yaml
import pandas as pd
import numpy as np
import logging
from logging.handlers import RotatingFileHandler
from datetime import datetime, timezone

# Add parent directory to sys.path for direct module imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ai_quant_bot.config.config import TARGET_SYMBOLS, LOG_MAX_BYTES, LOG_ROTATION_BACKUPS
from ai_quant_bot.data.database import init_db
from ai_quant_bot.data.collector import BinanceFuturesCollector
from ai_quant_bot.features.feature_library import FeatureEngineering
from ai_quant_bot.execution.risk_manager import RiskManagementEngine
from ai_quant_bot.execution.binance_client import BinanceFuturesExecutionClient
from ai_quant_bot.monitoring.rejection_audit import audit_rejection, monitor_rejected_signals, calculate_missed_expected_value, check_calibration_drift
from ai_quant_bot.monitoring.telegram_notifier import TelegramNotifier
from ai_quant_bot.monitoring.watchdog import WebSocketWatchdog
from ai_quant_bot.execution.circuit_breaker import AutomatedCircuitBreaker
from ai_quant_bot.data.maintenance import start_maintenance_schedule_loop
from ai_quant_bot.validation_suite import run_5point_sanity_check
from ai_quant_bot.execution.paper_tracker import PaperTradeTracker

from sklearn.base import BaseEstimator, ClassifierMixin, clone
from sklearn.model_selection import TimeSeriesSplit
from sklearn.isotonic import IsotonicRegression

class ManualCalibratedClassifier(BaseEstimator, ClassifierMixin):
    def __init__(self, estimator, cv=3):
        self.estimator = estimator
        self.cv = cv
        
    def fit(self, X, y, sample_weight=None):
        self.classes_ = np.unique(y)
        n_classes = len(self.classes_)
        
        fit_params = {}
        if sample_weight is not None:
            fit_params['sample_weight'] = sample_weight
            
        ts_cv = TimeSeriesSplit(n_splits=self.cv)
        oof_probs = np.full((len(X), n_classes), np.nan)
        
        for train_idx, test_idx in ts_cv.split(X, y):
            X_tr, X_te = X.iloc[train_idx], X.iloc[test_idx]
            y_tr, y_te = y.iloc[train_idx], y.iloc[test_idx]
            
            fold_fit_params = {}
            if sample_weight is not None:
                fold_fit_params['sample_weight'] = sample_weight.iloc[train_idx]
                
            fold_estimator = clone(self.estimator)
            fold_estimator.fit(X_tr, y_tr, **fold_fit_params)
            oof_probs[test_idx] = fold_estimator.predict_proba(X_te)
            
        self.estimator_ = clone(self.estimator)
        if sample_weight is not None:
            self.estimator_.fit(X, y, sample_weight=sample_weight)
        else:
            self.estimator_.fit(X, y)
            
        valid_mask = ~np.isnan(oof_probs[:, 0])
        self.calibrators_ = []
        for i, c in enumerate(self.classes_):
            y_bin = (y == c).astype(int)
            calibrator = IsotonicRegression(out_of_bounds='clip')
            calibrator.fit(oof_probs[valid_mask, i], y_bin[valid_mask])
            self.calibrators_.append(calibrator)
            
    def predict_proba(self, X):
        raw_probs = self.estimator_.predict_proba(X)
        calibrated_probs = np.zeros_like(raw_probs)
        for i, c in enumerate(self.classes_):
            calibrated_probs[:, i] = self.calibrators_[i].predict(raw_probs[:, i])
            
        sums = calibrated_probs.sum(axis=1, keepdims=True)
        sums[sums == 0] = 1.0
        return calibrated_probs / sums

    def predict(self, X):
        probs = self.predict_proba(X)
        return np.argmax(probs, axis=1)

# Configure Rotating Log Files to protect server disk space
log_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "quant_engine.log")
handler = RotatingFileHandler(log_path, maxBytes=LOG_MAX_BYTES, backupCount=LOG_ROTATION_BACKUPS)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[handler, logging.StreamHandler(sys.stdout)]
)

ASSETS_YAML_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config", "assets.yaml")

# Instantiate Core Engines
risk_engine = RiskManagementEngine(ASSETS_YAML_PATH)
binance_client = BinanceFuturesExecutionClient()
notifier = TelegramNotifier()
circuit_breaker = AutomatedCircuitBreaker(notifier)
watchdog = WebSocketWatchdog(TARGET_SYMBOLS, notifier)
paper_tracker = PaperTradeTracker()

# Global state trackers
loaded_brains = {}
current_prices = {}

def load_ml_brains():
    """Loads serialised ML model artifacts from directory."""
    import joblib
    root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    for symbol in TARGET_SYMBOLS:
        fname = f"{symbol.replace('/', '_')}_brain.pkl"
        path = os.path.join(root_dir, fname)
        if os.path.exists(path):
            try:
                loaded_brains[symbol] = joblib.load(path)
                print(f"[ORCHESTRATOR] Loaded ML brain for {symbol}")
            except Exception as e:
                print(f"[WARNING] Failed to load brain for {symbol}: {e}")

def calculate_choppiness_index(df: pd.DataFrame, period: int = 14) -> float:
    """Calculates Choppiness Index value for market regime classification."""
    high = df['high']
    low = df['low']
    close = df['close']
    
    tr = pd.concat([high - low, (high - close.shift(1)).abs(), (low - close.shift(1)).abs()], axis=1).max(axis=1)
    atr_sum = tr.rolling(window=period).sum()
    
    highest_high = high.rolling(window=period).max()
    lowest_low = low.rolling(window=period).min()
    range_high_low = highest_high - lowest_low
    
    chop = 100.0 * (np.log10(atr_sum / (range_high_low + 1e-9)) / np.log10(period))
    return float(chop.fillna(50.0).values[-1])

async def handle_confirmed_trade(symbol: str, direction: str, entry: float, sl: float, tp: float):
    """Executes order routing after user manual confirmation from Telegram."""
    print(f"[ORCHESTRATOR] Confirmed signal received. Placing trade: {symbol} {direction}...")
    
    # 1. Fetch current margin balance
    balance = await binance_client.get_margin_balance()
    if balance == 0.0:
        balance = 10.0 # safety fallback for demo balance
        
    market_info = binance_client.get_market_info(symbol)
    
    # 2. Evaluate sizing parameters
    # Note: regime check fallback here, default to NORMAL on manual confirmation execution path
    audit = risk_engine.evaluate_order_proposal(
        symbol=symbol,
        direction=direction,
        entry=entry,
        atr=abs(entry - sl), # ATR approximation from SL distance
        balance=balance,
        regime="NORMAL",
        market_info=market_info
    )
    
    if audit['eligible']:
        risk_engine.register_active_trade(symbol)
        res = await binance_client.submit_bracket_trade(
            symbol=symbol,
            direction=direction,
            quantity=audit['quantity'],
            sl=sl,
            tp=tp,
            entry_price=entry
        )
        if res.get('success'):
            print(f"[SUCCESS] Position executed for {symbol} at ${res['filled_price']:.4f}")
        else:
            print(f"[ERROR] Position execution failed for {symbol}: {res.get('error')}")
            risk_engine.unregister_active_trade(symbol)
    else:
        print(f"[REJECTED] Sizing evaluation failed during confirmation execution: {audit.get('reason')}")

async def handle_skipped_trade(symbol: str):
    """Handles skips from Telegram."""
    print(f"[ORCHESTRATOR] User skipped trade proposal for {symbol}.")

async def handle_candle_closed(symbol: str, df_history: pd.DataFrame):
    """Asynchronous pipeline handler executed on each completed 1m candle bar."""
    
    # 1. Defensive Programming: Zero NaN validation checks
    assert not df_history.empty, f"Historical candle DataFrame for {symbol} cannot be empty."
    assert df_history.isna().sum().sum() == 0, f"NaN values detected inside historical bars for {symbol}."
    
    # Track latest price
    last_close = float(df_history['close'].values[-1])
    current_prices[symbol] = last_close
    
    # Check and update active paper positions for TP/SL resolution
    candle_dict = {
        'open': float(df_history['open'].values[-1]),
        'high': float(df_history['high'].values[-1]),
        'low': float(df_history['low'].values[-1]),
        'close': last_close,
        'volume': float(df_history['volume'].values[-1])
    }
    closed_trades = paper_tracker.update_positions({symbol: candle_dict})
    for ct in closed_trades:
        risk_engine.unregister_active_trade(ct['symbol'])
        stats = paper_tracker.get_stats()
        res_emoji = "🟢 🔔" if ct['status'] == "PROFIT" else "🔴 🔔"
        pnl_str = f"+${ct['pnl']:.2f}" if ct['pnl'] >= 0 else f"-${abs(ct['pnl']):.2f}"
        close_msg = (
            f"{res_emoji} *[PAPER BOT] TRADE CLOSED — {ct['status']}*\n\n"
            f"• *Asset*: `{ct['symbol']}` | *Direction*: `{ct['direction']}`\n"
            f"• *Net PnL*: `{pnl_str} USD`\n"
            f"• *Entry*: `${ct['entry']:.4f}` → *Exit*: `${ct['exit_price']:.4f}`\n"
            f"• *TP Target*: `${ct['tp']:.4f}` | *SL Level*: `${ct['sl']:.4f}`\n\n"
            f"📊 *Running Paper Win Rate*: *{stats['win_rate']:.2f}%* ({stats['wins']}W / {stats['losses']}L) | Total P&L: *${stats['total_pnl']:+.2f} USD*"
        )
        await notifier.send_message(close_msg)
    
    # Record WebSocket activity to prevent stale timeout watchdog triggers
    watchdog.record_activity(symbol)
    
    # 2. Compute Features
    features = FeatureEngineering.generate_full_feature_vector(df_history)
    if features.empty:
        return
        
    # Zero NaN validation for features
    assert features.isna().sum().sum() == 0, f"NaN values detected inside computed features for {symbol}."
    
    latest_features = features.iloc[[-1]]
    
    # 3. Market Regime Identification
    last_adx = float(latest_features['adx_14'].values[0])
    last_chop = calculate_choppiness_index(df_history, 14)
    
    regime = "NORMAL"
    if last_chop > 55.0 or last_adx < 20.0:
        regime = "CHOPPY"
    elif last_chop < 45.0 and last_adx > 25.0:
        regime = "TRENDING"

    # 4. ML Win Probability Scoring
    win_prob = 50.0
    brain = loaded_brains.get(symbol)
    if brain:
        try:
            model = brain.get('model')
            model_features = brain.get('features', [])
            
            aligned_vector = pd.DataFrame(0.0, index=[0], columns=model_features)
            for col in model_features:
                if col in latest_features.columns:
                    aligned_vector[col] = latest_features[col].values[0]
                    
            proba = model.predict_proba(aligned_vector)
            win_prob = float(proba[0][1] * 100.0)
        except Exception:
            # Fallback spread proxy
            spread = float(latest_features['ema_spread_fast'].values[0])
            win_prob = 53.5 if spread > 0 else 46.5
    else:
        # Mock probability using momentum spread
        spread = float(latest_features['ema_spread_fast'].values[0])
        win_prob = 54.0 if spread > 0 else 45.0

    # 5. Evaluate setup thresholds & Dynamic filters
    direction = "LONG" if float(latest_features['ema_spread_fast'].values[0]) > 0 else "SHORT"
    
    assets_config = {}
    if os.path.exists(ASSETS_YAML_PATH):
        with open(ASSETS_YAML_PATH, 'r') as f:
            assets_config = yaml.safe_load(f) or {}
            
    symbol_settings = assets_config.get(symbol, {})
    threshold = symbol_settings.get('long_threshold' if direction == 'LONG' else 'short_threshold', 52.0)
    
    # Calculate SL/TP barriers
    atr_val = float(latest_features['atr_14'].values[0])
    sl_dist = 1.0 * atr_val
    tp_dist = 1.5 * atr_val
    
    sl_price = last_close - sl_dist if direction == "LONG" else last_close + sl_dist
    tp_price = last_close + tp_dist if direction == "LONG" else last_close - tp_dist

    # Check consecutive losses and drawdown strategy halt locks
    if circuit_breaker.is_execution_halted():
        await audit_rejection(symbol, direction, win_prob, threshold, regime, "CIRCUIT_BREAKER_HALT", last_close, sl_price, tp_price)
        return

    if win_prob >= threshold:
        # Check spread filter
        try:
            ticker = await binance_client.exchange.fetch_ticker(symbol)
            bid = float(ticker.get('bid', 0.0))
            ask = float(ticker.get('ask', 0.0))
            if not circuit_breaker.check_spread(bid, ask):
                await audit_rejection(symbol, direction, win_prob, threshold, regime, "MAX_SPREAD_EXCEEDED", last_close, sl_price, tp_price)
                return
        except Exception as e_spread:
            print(f"[WARNING] Spread audit skipped due to ticker fetch error: {e_spread}")

        # Enforce dynamic High-Timeframe Trend Veto
        is_vetoed = False
        if regime == "TRENDING":
            ema_slow = float(df_history['close'].ewm(span=50, adjust=False).mean().values[-1])
            if direction == "LONG" and last_close < ema_slow:
                is_vetoed = True
            elif direction == "SHORT" and last_close > ema_slow:
                is_vetoed = True
                
        if is_vetoed:
            await audit_rejection(symbol, direction, win_prob, threshold, regime, "TREND_VETO", last_close, sl_price, tp_price)
            return

        # Fetch margin balance & market specs
        balance = await binance_client.get_margin_balance()
        if balance == 0.0:
            balance = 10.0
            
        market_info = binance_client.get_market_info(symbol)
        
        # Verify Risk Management Rules
        risk_audit = risk_engine.evaluate_order_proposal(
            symbol=symbol,
            direction=direction,
            entry=last_close,
            atr=atr_val,
            balance=balance,
            regime=regime,
            market_info=market_info
        )
        
        if risk_audit['eligible']:
            # Auto-approve & Execute simulated trade bracket
            risk_engine.register_active_trade(symbol)
            paper_tracker.record_entry(
                symbol=symbol,
                direction=direction,
                entry=last_close,
                sl=risk_audit['sl_price'],
                tp=risk_audit['tp_price'],
                quantity=risk_audit['quantity'],
                win_prob=win_prob
            )
            await binance_client.submit_bracket_trade(
                symbol=symbol,
                direction=direction,
                quantity=risk_audit['quantity'],
                sl=risk_audit['sl_price'],
                tp=risk_audit['tp_price'],
                entry_price=last_close
            )
            await notifier.send_trade_alert(
                symbol=symbol,
                direction=direction,
                win_prob=win_prob,
                entry=last_close,
                tp=risk_audit['tp_price'],
                sl=risk_audit['sl_price'],
                regime=regime,
                semi_automated=False
            )
        else:
            await audit_rejection(symbol, direction, win_prob, threshold, regime, risk_audit['reason'], last_close, sl_price, tp_price)
    else:
        # Log to rejection database table
        await audit_rejection(symbol, direction, win_prob, threshold, regime, "LOW_PROBABILITY", last_close, sl_price, tp_price)

async def periodic_tasks_loop():
    """Background loop executing price audits, EV stats calculation and periodic performance reporting."""
    while True:
        try:
            # 1. Update prices for signal outcome tracking
            await monitor_rejected_signals(current_prices)
            
            # 2. Monitor Daily Drawdown Circuit Breakers limits
            try:
                balance = await binance_client.get_margin_balance()
                if balance > 0:
                    await circuit_breaker.check_drawdown_limits(balance, binance_client)
            except Exception as e_drawdown:
                print(f"[WARNING] Drawdown check failed: {e_drawdown}")
            
            # 3. Check for baseline model threshold drift warnings
            await check_calibration_drift(notifier)
            
            # 4. Periodically send system summaries every 30 minutes
            paper_stats = paper_tracker.get_stats()
            open_positions = paper_tracker.get_formatted_open_positions()
            ev_stats = await calculate_missed_expected_value()
            system_health = (
                f"Active | Paper WR: {paper_stats['win_rate']:.1f}% ({paper_stats['wins']}W/{paper_stats['losses']}L) | "
                f"PnL: ${paper_stats['total_pnl']:+.2f} | Rejection EV: ${ev_stats.get('missed_ev_usd', 0.0):.2f}"
            )
            
            await notifier.send_summary_report(open_positions=open_positions, system_health=system_health)
            
        except Exception as e:
            print(f"[SYSTEM LOOP ERROR] Exception in periodic task runner: {e}")
            
        await asyncio.sleep(1800) # Run every 30 minutes

async def main():
    print("==================================================")
    print("   ALPHAQUANT QUANT ENGINE CORE EXECUTION LAYER   ")
    print("==================================================")
    
    # 1. Timezone Enforcement Check
    # Ensure local clock matches UTC expectations
    now = datetime.now(timezone.utc)
    print(f"[SYSTEM] Engine Boot time: {now.strftime('%Y-%m-%d %H:%M:%S')} UTC")

    # 2. Initialize CCXT execution client market definitions
    await binance_client.initialize()

    # 3. Run automated 5-point sanity test before opening network sockets
    is_valid = await run_5point_sanity_check(binance_client)
    if not is_valid:
        print("[CRITICAL] Production validation suite failed. Terminating start-up process.")
        sys.exit(1)

    # 4. Database Hypertable initialization
    await init_db()
    
    # 5. Load pre-trained models
    load_ml_brains()

    # 6. Start Telegram confirmation polling task
    asyncio.create_task(notifier.start_confirmation_polling(
        on_confirm_cb=handle_confirmed_trade,
        on_skip_cb=handle_skipped_trade
    ))
    
    # 7. Start Rejection Outcome & EV auditor loop
    asyncio.create_task(periodic_tasks_loop())

    # 8. Start Database Maintenance loop
    asyncio.create_task(start_maintenance_schedule_loop())

    # 9. Start Async WebSocket Data Ingestion feed
    collector = BinanceFuturesCollector(TARGET_SYMBOLS, on_candle_closed=handle_candle_closed)
    
    # 10. Start Watchdog tracking loops
    asyncio.create_task(watchdog.run_watchdog_loop(collector))
    asyncio.create_task(watchdog.run_heartbeat_loop())
    
    try:
        await collector.start()
    except (asyncio.CancelledError, KeyboardInterrupt):
        print("[SYSTEM] Interruption signal received.")
    finally:
        # 8. Graceful Shutdown Implementation
        print("[SYSTEM] Initiating Graceful Shutdown...")
        await collector.stop()
        
        # Cancel any active limit brackets
        for symbol in TARGET_SYMBOLS:
            try:
                await binance_client.cancel_all_open_orders(symbol)
            except Exception as e:
                print(f"[ERROR] Failed to cancel open orders for {symbol} on shutdown: {e}")
                
        await binance_client.close()
        notifier.stop_polling()
        print("[SYSTEM] Sockets and databases closed. Sizing engines detached cleanly.")

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n[SYSTEM] Execution terminated manually.")
