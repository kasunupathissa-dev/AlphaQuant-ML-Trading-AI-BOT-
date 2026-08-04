import asyncio
import ccxt.pro as ccxtpro
import pandas as pd
import numpy as np
import joblib
import time
import requests
import os
import csv
from datetime import datetime
import json
import ccxt
import sys
import socket

# ⚙️ Singleton Process Lock (Prevents duplicate instances of main_v7.py)
lock_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
try:
    lock_socket.bind(('127.0.0.1', 9999))
except socket.error:
    print("[FATAL] Another instance of main_v7.py is already running. Exiting to prevent duplicate trades.")
    sys.exit(1)

try:
    from zoneinfo import ZoneInfo
except ImportError:
    ZoneInfo = None

# 🟢 V8.2 Upgrade: JSON Serialization Fix
import config 
from database_config import get_db_engine
from feature_library import calculate_features_for_shotgun, calculate_zscore

# Initialize global database engine for rejection logger
global_db_engine = None
try:
    global_db_engine = get_db_engine()
except Exception as e:
    print(f"[WARNING] Database connection failed on init: {e}")

# 🟢 V8.5 Calibration Class definition to support unpickling
def log_signal_rejection(engine, asset, direction, win_prob, threshold, regime, reason):
    """
    Logs rejected signals to the database, falling back to a local CSV file if connection fails.
    """
    timestamp = int(time.time() * 1000)
    try:
        from sqlalchemy import text
        query = """
        INSERT INTO signal_rejection_history (timestamp, asset, direction, win_prob, threshold, regime, rejection_reason)
        VALUES (:timestamp, :asset, :direction, :win_prob, :threshold, :regime, :reason)
        """
        with engine.connect() as connection:
            connection.execute(text(query), {
                "timestamp": timestamp,
                "asset": asset,
                "direction": direction,
                "win_prob": float(win_prob),
                "threshold": float(threshold),
                "regime": regime,
                "reason": reason
            })
            connection.commit()
    except Exception as e:
        print(f"[WARNING] Database rejection logging failed: {e}. Writing to CSV fallback.")
        csv_file = "signal_rejections_fallback.csv"
        try:
            file_exists = os.path.exists(csv_file)
            with open(csv_file, mode='a', newline='') as f:
                writer = csv.writer(f)
                if not file_exists:
                    writer.writerow(["timestamp", "asset", "direction", "win_prob", "threshold", "regime", "rejection_reason"])
                writer.writerow([timestamp, asset, direction, win_prob, threshold, regime, reason])
        except Exception as csv_err:
            print(f"[ERROR] CSV fallback writing failed: {csv_err}")

from sklearn.base import BaseEstimator, ClassifierMixin, clone
from sklearn.isotonic import IsotonicRegression
from sklearn.model_selection import cross_val_predict

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
            
        this_estimator = clone(self.estimator)
        oof_probs = cross_val_predict(
            this_estimator, X, y, cv=self.cv,
            method='predict_proba', params=fit_params
        )
        
        self.estimator_ = clone(self.estimator)
        if sample_weight is not None:
            self.estimator_.fit(X, y, sample_weight=sample_weight)
        else:
            self.estimator_.fit(X, y)
            
        self.calibrators_ = []
        for i, c in enumerate(self.classes_):
            y_bin = (y == c).astype(int)
            calibrator = IsotonicRegression(out_of_bounds='clip')
            calibrator.fit(oof_probs[:, i], y_bin)
            self.calibrators_.append(calibrator)
            
        return self
        
    def predict_proba(self, X):
        raw_probs = self.estimator_.predict_proba(X)
        calibrated_probs = np.zeros_like(raw_probs)
        
        for i, calibrator in enumerate(self.calibrators_):
            calibrated_probs[:, i] = calibrator.predict(raw_probs[:, i])
            
        row_sums = calibrated_probs.sum(axis=1, keepdims=True)
        row_sums[row_sums == 0] = 1.0
        calibrated_probs = calibrated_probs / row_sums
        return calibrated_probs
        
    def predict(self, X):
        probs = self.predict_proba(X)
        return self.classes_[np.argmax(probs, axis=1)]

# =====================================================================
# ALPHAQUANT V8.2: SERIALIZATION-FIXED ENGINE
# =====================================================================

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

# --- State Management & Globals ---
active_trades, live_prices, asset_locks, brains = [], {}, {}, {}
telemetry_timer = time.time() 
asset_recent_results = {asset: [] for asset in config.TARGET_ASSETS} 
asset_penalty_box = {} 
signal_funnel = {"generated": 0, "rejected_regime": 0, "rejected_threshold": 0, "executed": 0}
trade_mode = "BOTH"
rejected_signal_tracker = []
last_audit_time = time.time()

def get_local_time():
    """Returns the current datetime in the Stockholm timezone (or fallback UTC+2)."""
    tz_name = getattr(config, 'TIMEZONE', 'Europe/Stockholm')
    if ZoneInfo is not None:
        try:
            return datetime.now(ZoneInfo(tz_name))
        except Exception:
            pass
    # Fallback to Stockholm summer time (UTC+2)
    from datetime import timezone, timedelta
    return datetime.now(timezone.utc) + timedelta(hours=2)

def is_news_blockout_active():
    """
    Checks if a high-impact economic news event is scheduled within the blockout window.
    Economic calendar is retrieved from a public JSON endpoint.
    """
    if not getattr(config, 'NEWS_BLOCKOUT_ENABLED', True):
        return False
        
    try:
        # Fetch public economic calendar (Forex Factory JSON feed)
        url = "https://nfs.faireconomy.media/lul_calendar.json"
        response = requests.get(url, timeout=5)
        if response.status_code != 200:
            return False
            
        events = response.json()
        now_utc = datetime.now(timezone.utc).replace(tzinfo=None)
        window_sec = getattr(config, 'NEWS_BLOCKOUT_WINDOW_MINUTES', 60) * 60
        
        # High-impact keywords for crypto volatility
        high_impact_keywords = ["CPI", "FOMC", "Fed Interest Rate Decision", "Non-Farm Employment Change", "Unemployment Rate", "Powell Speech"]
        
        for event in events:
            impact = event.get("impact", "").lower()
            title = event.get("title", "")
            
            is_high_impact = (impact == "high") or any(kw in title for kw in high_impact_keywords)
            if not is_high_impact:
                continue
                
            date_str = event.get("date")
            if not date_str:
                continue
                
            try:
                # Parse date (ISO 8601)
                event_time = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
                # Convert event time to UTC and strip timezone info for simple comparison
                event_time_utc = event_time.astimezone(timezone.utc).replace(tzinfo=None)
                
                time_diff = abs((event_time_utc - now_utc).total_seconds())
                if time_diff <= window_sec:
                    print(f"[NEWS BLOCKOUT] High-impact event detected: '{title}' at {date_str} (Diff: {time_diff/60:.1f} mins). Blocking signals.")
                    return True
            except Exception:
                continue
    except Exception as e:
        print(f"[WARNING] Could not check economic calendar: {e}. Defaulting to safe (False).")
        
    return False

# 🟢 V8.2 FIX: Custom JSON encoder to handle NumPy data types
class NumpyEncoder(json.JSONEncoder):
    """ Special json encoder for numpy types """
    def default(self, obj):
        if isinstance(obj, np.integer):
            return int(obj)
        elif isinstance(obj, np.floating):
            return float(obj)
        elif isinstance(obj, np.ndarray):
            return obj.tolist()
        return json.JSONEncoder.default(self, obj)

def save_state():
    global last_state_mtime
    state = {}
    if os.path.exists(config.STATE_FILE):
        try:
            with open(config.STATE_FILE, 'r') as f:
                state = json.load(f)
        except Exception:
            state = {}
            
    state.update({
        "asset_penalty_box": asset_penalty_box,
        "asset_recent_results": asset_recent_results,
        "active_trades": active_trades,
        "signal_funnel": signal_funnel,
        "live_prices": live_prices,
        "trade_mode": trade_mode,
        "rejected_signal_tracker": rejected_signal_tracker,
        "last_audit_time": last_audit_time
    })
    
    with open(config.STATE_FILE, 'w') as f:
        # Use the custom NumpyEncoder to prevent type errors
        json.dump(state, f, indent=4, cls=NumpyEncoder)
    try:
        last_state_mtime = os.path.getmtime(config.STATE_FILE)
    except Exception:
        last_state_mtime = 0
    # print("[INFO] Bot state saved.")

last_state_load_time = 0
last_state_mtime = 0

def load_state(force=False):
    global asset_penalty_box, asset_recent_results, active_trades, signal_funnel, trade_mode, last_state_load_time, last_state_mtime, rejected_signal_tracker, last_audit_time
    
    if not os.path.exists(config.STATE_FILE):
        return
        
    try:
        mtime = os.path.getmtime(config.STATE_FILE)
    except Exception:
        mtime = 0
        
    current_time = time.time()
    # Skip loading only if file mtime hasn't changed, we're not forcing, and less than 1.5 seconds have elapsed
    if not force and mtime == last_state_mtime and (current_time - last_state_load_time < 1.5):
        return
        
    last_state_load_time = current_time
    last_state_mtime = mtime
    
    try:
        with open(config.STATE_FILE, 'r') as f: state = json.load(f)
        asset_penalty_box = state.get("asset_penalty_box", {})
        asset_recent_results = state.get("asset_recent_results", {asset: [] for asset in config.TARGET_ASSETS})
        active_trades = state.get("active_trades", [])
        signal_funnel = state.get("signal_funnel", {"generated": 0, "rejected_regime": 0, "rejected_threshold": 0, "executed": 0})
        trade_mode = state.get("trade_mode", "BOTH")
        rejected_signal_tracker = state.get("rejected_signal_tracker", [])
        last_audit_time = state.get("last_audit_time", time.time())
        # print("[SUCCESS] Bot state loaded from file (synchronized).")
    except json.JSONDecodeError: print("[WARNING] Could not decode state file. Starting fresh.")
    except Exception as e: print(f"[WARNING] Failed to load state file: {e}")

def log_backend_error(category, message):
    global last_state_mtime
    timestamp = get_local_time().strftime("%Y-%m-%d %H:%M:%S")
    # 1. Log to file
    try:
        with open("backend_errors.log", "a", encoding="utf-8") as ef:
            ef.write(f"[{timestamp}] [{category}] {message}\n")
    except Exception as log_err:
        print(f"[ERROR] Failed to write to backend_errors.log: {log_err}")
    
    # 2. Append to state latest_errors
    try:
        state_file_path = config.STATE_FILE
        state = {}
        if os.path.exists(state_file_path):
            with open(state_file_path, 'r') as f:
                state = json.load(f)
        
        errors = state.get("latest_errors", [])
        errors.append({
            "timestamp": timestamp,
            "category": category,
            "message": message
        })
        # Limit to 10 latest errors
        if len(errors) > 10:
            errors.pop(0)
        
        state["latest_errors"] = errors
        with open(state_file_path, 'w') as f:
            json.dump(state, f, indent=4, cls=NumpyEncoder)
        last_state_mtime = os.path.getmtime(state_file_path)
    except Exception as state_err:
        print(f"[ERROR] Failed to update latest_errors in state: {state_err}")

def send_telegram_message(msg):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID: return
    # Global replacement of underscores with hyphens to prevent Telegram Markdown 400 errors
    msg = msg.replace("_", "-")
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        response = requests.post(url, json={"chat_id": TELEGRAM_CHAT_ID, "text": msg, "parse_mode": "Markdown"}, timeout=10)
        if response.status_code != 200:
            print(f"[ERROR] Failed to send Telegram message. Status: {response.status_code}")
    except requests.exceptions.RequestException as e:
        print(f"[ERROR] Telegram request failed: {e}")

def calculate_choppiness_index(df, period=14):
    """Calculates Choppiness Index (0-100)."""
    tr = np.maximum(df['high'] - df['low'], 
                    np.maximum(np.abs(df['high'] - df['close'].shift()), 
                               np.abs(df['low'] - df['close'].shift())))
    atr_sum = tr.rolling(window=period).sum()
    high_max = df['high'].rolling(window=period).max()
    low_min = df['low'].rolling(window=period).min()
    range_hl = np.maximum(high_max - low_min, 1e-8)
    return 100 * np.log10(atr_sum / range_hl) / np.log10(period)

def log_trade_features_to_csv(trade):
    features_log_file = "trading_features_v8.csv"
    file_exists = os.path.isfile(features_log_file)
    entry_feats = trade.get("entry_features", {})
    if not entry_feats:
        return
        
    headers = ["Timestamp", "Asset", "Direction", "Status", "PNL", "AI_Prob"] + list(entry_feats.keys())
    row = [
        get_local_time().strftime("%Y-%m-%d %H:%M:%S"),
        trade["asset"],
        trade["direction"],
        trade["status"],
        f"{trade['pnl']:.2f}",
        f"{trade['ai_prob']:.2f}%"
    ] + [f"{val:.6f}" for val in entry_feats.values()]
    
    with open(features_log_file, mode="a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow(headers)
        writer.writerow(row)

async def execute_testnet_order(exchange, symbol, direction, amount, close_full=False):
    if not getattr(config, 'USE_TESTNET', False) or not getattr(config, 'BINANCE_API_KEY', ''):
        return None
    try:
        side = 'buy' if direction == 'LONG' else 'sell'
        
        # Synchronize exact contract size from exchange for full exits (TP/SL/manual closes)
        if close_full:
            try:
                positions = await asyncio.to_thread(exchange.fetch_positions, [symbol])
                for p in positions:
                    if p['symbol'].split(':')[0] == symbol:
                        contracts = abs(p.get('contracts', 0.0))
                        if contracts > 0.0:
                            amount = contracts
                            print(f"[TESTNET] Synced remaining contracts from exchange for full close: {amount:.6f}")
                        break
            except Exception as sync_err:
                print(f"[WARNING] Failed to fetch actual contracts for {symbol}: {sync_err}. Falling back to default amount.")

        # Auto-configure leverage to 20x prior to placing order on Binance
        try:
            await asyncio.to_thread(exchange.set_leverage, 20, symbol)
            print(f"[TESTNET] Automatically set leverage to 20x for {symbol}")
        except Exception as lev_err:
            print(f"[WARNING] Failed to set leverage to 20x for {symbol}: {lev_err}")

        order = await asyncio.to_thread(
            exchange.create_market_order,
            symbol=symbol,
            side=side,
            amount=amount
        )
        order_id = order.get('id')
        print(f"[TESTNET] Placed {side.upper()} order for {amount:.6f} {symbol}. Order ID: {order_id}")
        return order_id
    except Exception as e:
        log_backend_error("Binance API", f"Failed to execute Testnet order for {symbol} ({direction}): {e}")
        return None

def log_trade_to_csv(trade):
    file_exists = os.path.isfile(config.LOG_FILE)
    with open(config.LOG_FILE, mode="a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if not file_exists: writer.writerow(["Timestamp", "Asset", "Direction", "Entry", "TP", "SL", "Status", "AI_Prob", "PNL", "SignalType"])
        writer.writerow([get_local_time().strftime("%Y-%m-%d %H:%M:%S"), trade["asset"], trade["direction"], f"{trade['entry']:.4f}", f"{trade['tp']:.4f}", f"{trade['sl']:.4f}", trade["status"], f"{trade['ai_prob']:.2f}%", f"{trade['pnl']:.2f}", "SHOTGUN"])
    log_trade_features_to_csv(trade)

def track_rejected_signal(asset, direction, win_prob, threshold, entry_price, atr_val, reason, regime="NORMAL"):
    global rejected_signal_tracker
    sl = entry_price - atr_val * config.ATR_STOP_LOSS_MULTIPLIER if direction == "LONG" else entry_price + atr_val * config.ATR_STOP_LOSS_MULTIPLIER
    tp = entry_price + atr_val * config.ATR_TAKE_PROFIT_MULTIPLIER if direction == "LONG" else entry_price - atr_val * config.ATR_TAKE_PROFIT_MULTIPLIER
    
    # Check if this asset/direction is already pending in the tracker to avoid double-tracking
    existing = [s for s in rejected_signal_tracker if s["asset"] == asset and s["direction"] == direction and s["status"] == "PENDING"]
    if existing:
        return
        
    rejected_signal_tracker.append({
        "asset": asset,
        "direction": direction,
        "win_prob": win_prob,
        "threshold": threshold,
        "entry_price": entry_price,
        "sl": sl,
        "tp": tp,
        "reason": reason,
        "status": "PENDING",
        "timestamp": time.time(),
        "target_risk": config.RISK_PER_TRADE_USD
    })
    save_state()
    
    # 🟢 Write rejection metadata to SQL Database / CSV fallback
    log_signal_rejection(global_db_engine, asset, direction, win_prob, threshold, regime, reason)

class AlphaQuantV8_2:
    def __init__(self):
        print("==================================================")
        print("  ALPHAQUANT V8.2: SERIALIZATION-FIXED ENGINE     ")
        print("==================================================")
        
        if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID: print("[WARNING] Telegram secrets not set.")

        load_state()

        # Load optimal thresholds overrides if available
        opt_file = "optimal_thresholds.json"
        if os.path.exists(opt_file):
            try:
                with open(opt_file, 'r') as f:
                    opt_thresh = json.load(f)
                if not hasattr(config, 'ASSET_SPECIFIC_THRESHOLDS'):
                    config.ASSET_SPECIFIC_THRESHOLDS = {}
                config.ASSET_SPECIFIC_THRESHOLDS.update(opt_thresh)
                print(f"[INFO] Loaded optimal threshold overrides from {opt_file}: {opt_thresh}")
            except Exception as e:
                print(f"[WARNING] Failed to load optimal thresholds file: {e}")

        for asset in config.TARGET_ASSETS:
            safe_filename = asset.replace("/", "_") + "_brain.pkl"
            if os.path.exists(safe_filename):
                try:
                    brain_data = joblib.load(safe_filename)
                    if 'model' in brain_data and 'features' in brain_data:
                        brains[asset] = brain_data
                        print(f"[INFO] Loaded V8 brain for {asset}.")
                    else:
                        print(f"[WARNING] Incompatible brain format for {asset}. Discarding.")
                except Exception as e:
                    print(f"[ERROR] Could not load brain for {asset}: {e}")
        
        if not brains: exit("[FATAL] No valid V8 brains loaded. Please run the V8 pipeline.")
            
        exchange_config = {
            'apiKey': getattr(config, 'BINANCE_API_KEY', ''),
            'secret': getattr(config, 'BINANCE_API_SECRET', ''),
            'enableRateLimit': True,
            'options': {
                'defaultType': 'future',
                'adjustForTimeDifference': True
            }
        }
        self.exchange_pro = ccxtpro.binance(exchange_config)
        self.exchange_reg = ccxt.binance(exchange_config)
        
        # Public production client for fetching market data analytics (funding rate, open interest, etc.)
        self.public_exchange = ccxt.binance({
            'enableRateLimit': True,
            'options': {
                'defaultType': 'future'
            }
        })
        
        if getattr(config, 'USE_TESTNET', False):
            self.exchange_pro.enable_demo_trading(True)
            self.exchange_reg.enable_demo_trading(True)
            print("[INFO] Connected to Binance Futures Demo Trading Mode.")
        self.running = True
        self.tasks = []
        
        send_telegram_message(f"🚀 *[AlphaQuant V8.2]*\nSerialization-Fixed Engine LIVE. Loaded {len(brains)}/{len(config.TARGET_ASSETS)} models.")

    async def reconcile_open_positions(self):
        print("[INFO] Reconciling open positions...")
        if active_trades:
            print(f"[INFO] Found {len(active_trades)} trades in state file. Re-adopting...")
            for trade in active_trades: asset_locks[trade['asset']] = True
        else:
            print("[INFO] No open positions in state file.")

    async def watch_all_tickers(self):
        while self.running:
            try:
                assets_to_watch = list(brains.keys())
                tickers = await self.exchange_pro.watch_tickers(assets_to_watch)
                for symbol, ticker in tickers.items():
                    live_prices[symbol] = ticker['last']
                    await self.manage_active_trades(symbol, ticker['last'])
            except Exception as e:
                err_msg = f"⚠️ *[V8.2] Main Ticker Stream Failed*\nError: `{e}`\nReconnecting in 10 seconds..."
                print(f"[ERROR] Main ticker stream failed: {e}. Reconnecting...")
                send_telegram_message(err_msg)
                await asyncio.sleep(10)

    async def fallback_price_monitor(self):
        print("[SYSTEM] Starting REST Fallback Price Monitor...")
        while self.running:
            try:
                await asyncio.sleep(15)  # Check every 15 seconds
                if not self.running: break
                
                # Fetch live positions from Binance Demo/Testnet if active to sync P&L / ROI
                binance_positions = {}
                if getattr(config, 'USE_TESTNET', False) and getattr(config, 'BINANCE_API_KEY', ''):
                    try:
                        positions = await asyncio.to_thread(self.exchange_reg.fetch_positions)
                        for p in positions:
                            contracts = p.get('contracts', 0.0)
                            unpnl = p.get('unrealizedPnl', 0.0)
                            if (contracts is not None and contracts > 0.0) or (unpnl is not None and unpnl != 0.0):
                                symbol = p['symbol'].split(':')[0] # Normalize BTC/USDT:USDT to BTC/USDT
                                binance_positions[symbol] = p
                    except Exception as pos_err:
                        print(f"[WARNING] Failed to fetch live positions from Binance API: {pos_err}")

                global active_trades
                load_state()
                state_updated = False
                
                # Update local active trades with live Binance data
                for t in active_trades:
                    symbol = t['asset']
                    if symbol in binance_positions:
                        pos = binance_positions[symbol]
                        t['binance_pnl'] = pos.get('unrealizedPnl')
                        t['binance_roi'] = pos.get('percentage')
                        t['binance_leverage'] = pos.get('leverage')
                        state_updated = True
                
                if state_updated:
                    save_state()
                
                active_symbols = list(set([t['asset'] for t in active_trades]))
                if not active_symbols:
                    continue
                
                print(f"[SYSTEM] Fallback polling {len(active_symbols)} active assets via REST...")
                for symbol in active_symbols:
                    try:
                        ticker = await asyncio.to_thread(self.exchange_reg.fetch_ticker, symbol)
                        current_price = ticker.get('last')
                        if current_price is not None:
                            live_prices[symbol] = current_price
                            await self.manage_active_trades(symbol, current_price)
                    except Exception as poll_err:
                        print(f"[WARNING] REST fallback fetch failed for {symbol}: {poll_err}")
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"[ERROR] Fallback price monitor failed: {e}")


    async def manage_active_trades(self, symbol, current_price):
        global active_trades
        if asset_locks.get(symbol, False):
            return
        load_state()
        trade_closed = False
        updated_trades = [t for t in active_trades if t['asset'] != symbol]

        for trade in [t for t in active_trades if t['asset'] == symbol]:
            is_closed, result, pnl = False, "", 0.0
            notional = trade.get('position_size', 100)
            
            # --- Dynamic Trailing Stop-Loss Logic ---
            entry_atr = trade.get('entry_atr')
            if entry_atr is None:
                # Fallback calculation if entry_atr is missing from state
                entry_atr = abs(trade['tp'] - trade['entry']) / 1.5
                
            # --- Partial Take Profit (Runner Logic) ---
            if not trade.get('half_closed', False):
                if trade['direction'] == "LONG":
                    # Partial TP activation threshold (price reached Entry + 1.0x ATR)
                    if current_price >= trade['entry'] + entry_atr:
                        half_pnl = (notional / 2) * ((current_price - trade['entry']) / trade['entry'])
                        trade['locked_pnl'] = trade.get('locked_pnl', 0.0) + half_pnl
                        trade['position_size'] = notional / 2
                        trade['sl'] = trade['entry'] # Move SL to entry (breakeven)
                        trade['half_closed'] = True
                        trade_closed = True
                        
                        # Execute Testnet order for partial TP (sell to reduce LONG)
                        await execute_testnet_order(
                            self.exchange_reg,
                            symbol=symbol,
                            direction='SHORT',
                            amount=(notional / 2) / trade['entry']
                        )
                        
                        msg = (
                            f"🔔 *[V8.2] PARTIAL TP EXECUTED*\n"
                            f"• *Asset*: {symbol} | LONG\n"
                            f"• *Closed 50%* at: `${current_price:,.4f}`\n"
                            f"• *Locked PnL*: *${half_pnl:+.2f}*\n"
                            f"• *SL moved to breakeven*: `${trade['entry']:,.4f}`"
                        )
                        send_telegram_message(msg)
                else:
                    # Partial TP activation threshold (price reached Entry - 1.0x ATR)
                    if current_price <= trade['entry'] - entry_atr:
                        half_pnl = (notional / 2) * ((trade['entry'] - current_price) / trade['entry'])
                        trade['locked_pnl'] = trade.get('locked_pnl', 0.0) + half_pnl
                        trade['position_size'] = notional / 2
                        trade['sl'] = trade['entry'] # Move SL to entry (breakeven)
                        trade['half_closed'] = True
                        trade_closed = True
                        
                        # Execute Testnet order for partial TP (buy to reduce SHORT)
                        await execute_testnet_order(
                            self.exchange_reg,
                            symbol=symbol,
                            direction='LONG',
                            amount=(notional / 2) / trade['entry']
                        )
                        
                        msg = (
                            f"🔔 *[V8.2] PARTIAL TP EXECUTED*\n"
                            f"• *Asset*: {symbol} | SHORT\n"
                            f"• *Closed 50%* at: `${current_price:,.4f}`\n"
                            f"• *Locked PnL*: *${half_pnl:+.2f}*\n"
                            f"• *SL moved to breakeven*: `${trade['entry']:,.4f}`"
                        )
                        send_telegram_message(msg)

            if trade['direction'] == "LONG":
                # Update highest watermark
                trade['highest_price'] = max(trade.get('highest_price', trade['entry']), current_price)
                # Check activation threshold (price reached Entry + 1.0x ATR)
                if current_price >= trade['entry'] + entry_atr:
                    trade['trailing_active'] = True
                # Shift SL if trailing is active
                if trade.get('trailing_active', False):
                    new_sl = trade['highest_price'] - entry_atr
                    if trade['sl'] < new_sl:
                        trade['sl'] = new_sl
                        trade_closed = True # SL updated, persist state
            else:
                # Update lowest watermark
                trade['lowest_price'] = min(trade.get('lowest_price', trade['entry']), current_price)
                # Check activation threshold (price reached Entry - 1.0x ATR)
                if current_price <= trade['entry'] - entry_atr:
                    trade['trailing_active'] = True
                # Shift SL if trailing is active
                if trade.get('trailing_active', False):
                    new_sl = trade['lowest_price'] + entry_atr
                    if trade['sl'] > new_sl:
                        trade['sl'] = new_sl
                        trade_closed = True # SL updated, persist state

            # --- Check Exits ---
            if trade['direction'] == "LONG":
                if current_price >= trade['tp']: 
                    is_closed = True
                    remaining_pnl = trade['position_size'] * ((trade['tp'] - trade['entry']) / trade['entry'])
                elif current_price <= trade['sl']: 
                    is_closed = True
                    remaining_pnl = trade['position_size'] * ((trade['sl'] - trade['entry']) / trade['entry'])
            else: 
                if current_price <= trade['tp']: 
                    is_closed = True
                    remaining_pnl = trade['position_size'] * ((trade['entry'] - trade['tp']) / trade['entry'])
                elif current_price >= trade['sl']: 
                    is_closed = True
                    remaining_pnl = trade['position_size'] * ((trade['entry'] - trade['sl']) / trade['entry'])

            if is_closed:
                # Lock asset immediately to prevent duplicate concurrent close executions
                if asset_locks.get(symbol, False):
                    continue
                asset_locks[symbol] = True
                
                trade_closed = True
                pnl = trade.get('locked_pnl', 0.0) + remaining_pnl
                result = "PROFIT" if pnl >= 0 else "LOSS"
                trade.update({'status': result, 'pnl': pnl})
                
                # Execute Testnet order on exit (opposite direction)
                exit_direction = 'SHORT' if trade['direction'] == 'LONG' else 'LONG'
                try:
                    await execute_testnet_order(
                        self.exchange_reg,
                        symbol=symbol,
                        direction=exit_direction,
                        amount=trade['position_size'] / trade['entry'],
                        close_full=True
                    )
                except Exception as close_order_err:
                    print(f"[ERROR] Failed to execute Testnet close order for {symbol}: {close_order_err}")
                
                log_trade_to_csv(trade)
                
                asset_recent_results[symbol].append(1 if result == "PROFIT" else 0)
                if len(asset_recent_results[symbol]) > 5: asset_recent_results[symbol].pop(0)
                
                status_icon = "🟢" if result == "PROFIT" else "🔴"
                msg = (
                    f"{status_icon} 🔔 *[V8.2] TRADE CLOSED*\n"
                    f"• *Asset*: {symbol} | *Direction*: {trade['direction']}\n"
                    f"• *Status*: *{result}* | *Net PnL*: *${pnl:+.2f}*\n"
                    f"• *Entry Price*: ${trade['entry']:,.4f}\n"
                    f"• *Exit Price*: ${current_price:,.4f}\n"
                    f"• *Take Profit (TP)*: ${trade['tp']:,.4f}\n"
                    f"• *Stop Loss (SL)*: ${trade['sl']:,.4f}"
                )
                
                if len(asset_recent_results[symbol]) >= 2 and sum(asset_recent_results[symbol][-2:]) == 0:
                    asset_penalty_box[symbol] = time.time() + (24 * 3600)
                    msg += f"\n\n🛑 *DEGRADATION LOCK*: {symbol} isolated for 24 hours."
                    asset_recent_results[symbol] = []
                
                send_telegram_message(msg)
                asset_locks[symbol] = False 
            else:
                updated_trades.append(trade)
                
        active_trades = updated_trades
        if trade_closed: save_state()

    def audit_rejected_signals(self):
        global rejected_signal_tracker
        current_time = time.time()
        for sig in rejected_signal_tracker:
            if sig["status"] != "PENDING":
                continue
            
            asset = sig["asset"]
            price_key = f"{asset}:USDT"
            current_price = live_prices.get(price_key)
            if not current_price:
                continue
                
            entry = sig["entry_price"]
            tp = sig["tp"]
            sl = sig["sl"]
            direction = sig["direction"]
            
            hit_tp = False
            hit_sl = False
            
            if direction == "LONG":
                if current_price >= tp:
                    hit_tp = True
                elif current_price <= sl:
                    hit_sl = True
            else:
                if current_price <= tp:
                    hit_tp = True
                elif current_price >= sl:
                    hit_sl = True
                    
            if hit_tp:
                sig["status"] = "WIN"
                sig["close_price"] = current_price
                sig["outcome_time"] = current_time
                sig["pnl"] = sig["target_risk"] * (config.ATR_TAKE_PROFIT_MULTIPLIER / config.ATR_STOP_LOSS_MULTIPLIER)
            elif hit_sl:
                sig["status"] = "LOSS"
                sig["close_price"] = current_price
                sig["outcome_time"] = current_time
                sig["pnl"] = -sig["target_risk"]
            elif (current_time - sig["timestamp"]) >= 86400: # 24h timeout
                sig["outcome_time"] = current_time
                sig["close_price"] = current_price
                if direction == "LONG":
                    if current_price > entry:
                        sig["status"] = "WIN"
                        sig["pnl"] = sig["target_risk"] * 0.5
                    else:
                        sig["status"] = "LOSS"
                        sig["pnl"] = -sig["target_risk"]
                else:
                    if current_price < entry:
                        sig["status"] = "WIN"
                        sig["pnl"] = sig["target_risk"] * 0.5
                    else:
                        sig["status"] = "LOSS"
                        sig["pnl"] = -sig["target_risk"]
        save_state()

    def send_hourly_audit_summary(self):
        global rejected_signal_tracker, last_audit_time
        current_time = time.time()
        
        completed_sigs = [
            sig for sig in rejected_signal_tracker 
            if sig["status"] in ("WIN", "LOSS") 
            and (current_time - sig.get("outcome_time", 0)) <= 3600
        ]
        
        if not completed_sigs:
            send_telegram_message("📊 *[AlphaQuant V8.2] Hourly Rejection Audit*\n• *Status*: Active\n• *Signals Audited in Last Hour*: `0`\n• *Capital Saved*: `$0.00` (Market flat, no exits).")
            last_audit_time = current_time
            rejected_signal_tracker = [sig for sig in rejected_signal_tracker if sig["status"] == "PENDING"]
            save_state()
            return
            
        wins = [s for s in completed_sigs if s["status"] == "WIN"]
        losses = [s for s in completed_sigs if s["status"] == "LOSS"]
        
        total_wins_val = sum(s["pnl"] for s in wins)
        total_losses_val = sum(s["pnl"] for s in losses)
        net_hypothetical_pnl = total_wins_val + total_losses_val
        
        capital_saved = -net_hypothetical_pnl
        
        details = []
        for s in completed_sigs:
            direction_emoji = "🟢" if s["direction"] == "LONG" else "🔴"
            details.append(
                f"• {direction_emoji} *{s['asset']}* ({s['reason']}): "
                f"AI `{s['win_prob']:.1f}%` | outcome: *{s['status']}* (Hypothetical: `{s['pnl']:+.2f}`)"
            )
            
        details_str = "\n".join(details)
        
        msg = (
            f"📊 *[AlphaQuant V8.2] Hourly Rejection Audit*\n"
            f"• *Completed Audits*: `{len(completed_sigs)}` (Wins: `{len(wins)}` | Losses: `{len(losses)}`)\n"
            f"• *Net Hypothetical P&L*: `{net_hypothetical_pnl:+.2f} USD`\n"
            f"• *Capital Saved / Avoided*: *{capital_saved:+.2f} USD*\n\n"
            f"*Audited Signals Details*:\n{details_str}"
        )
        send_telegram_message(msg)
        
        last_audit_time = current_time
        rejected_signal_tracker = [sig for sig in rejected_signal_tracker if sig["status"] == "PENDING"]
        save_state()

    async def ml_inference_loop(self):
        first_run = True
        while self.running:
            try:
                if not first_run:
                    await asyncio.sleep(getattr(config, 'INFERENCE_INTERVAL_SECONDS', 900))
                else:
                    first_run = False
                    await asyncio.sleep(5)  # 5s startup delay for WS setup
                    
                if not self.running: break
                
                # Run Shadow Rejection Auditor
                self.audit_rejected_signals()
                if time.time() - last_audit_time >= 3600:
                    self.send_hourly_audit_summary()
                    
                # --- Time-of-Day Performance Filter ---
                local_time = get_local_time()
                blocked_hours = getattr(config, 'BLOCKED_HOURS', [])
                if local_time.hour in blocked_hours:
                    print(f"[{datetime.now().strftime('%H:%M:%S')}] [TIME FILTER] Skipping inference cycle. Hour {local_time.hour} is in BLOCKED_HOURS: {blocked_hours}")
                    continue
                    
                # --- News & Event Blockout System ---
                if await asyncio.to_thread(is_news_blockout_active):
                    print(f"[{datetime.now().strftime('%H:%M:%S')}] [NEWS FILTER] Skipping inference cycle. High-impact news event is nearby.")
                    continue
                
                load_state()
                send_telegram_message(f"🧠 *[V8.2] Starting Shotgun Inference Cycle on {len(brains)} assets...*")
                print(f"[{datetime.now().strftime('%H:%M:%S')}] Executing V8.2 Shotgun Pipeline...")

                for asset in brains.keys():
                    if asset in asset_penalty_box:
                        if time.time() >= asset_penalty_box[asset]:
                            del asset_penalty_box[asset]
                            save_state()
                        else:
                            continue
                    if asset_locks.get(asset, False): continue
                    
                    try:
                        fetch_limit = 1600 if config.TIMEFRAME == "15m" else 250
                        ohlcv = await asyncio.to_thread(self.public_exchange.fetch_ohlcv, asset, config.TIMEFRAME, limit=fetch_limit)
                        df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
                        
                        feature_df = calculate_features_for_shotgun(df)
                        
                        funding_history = await asyncio.to_thread(self.public_exchange.fetch_funding_rate_history, asset, limit=100)
                        oi_tf = '15m' if config.TIMEFRAME == '15m' else '1h'
                        oi_history = await asyncio.to_thread(self.public_exchange.fetch_open_interest_history, asset, oi_tf, limit=100)
                        funding_df = pd.DataFrame(funding_history)[['timestamp', 'fundingRate']]
                        oi_df = pd.DataFrame(oi_history)[['timestamp', 'openInterestAmount']]
                        funding_df['timestamp'] = pd.to_datetime(funding_df['timestamp'], unit='ms')
                        oi_df['timestamp'] = pd.to_datetime(oi_df['timestamp'], unit='ms')
                        
                        resample_rule = '15min' if config.TIMEFRAME == '15m' else '1h'
                        funding_df = funding_df.set_index('timestamp').resample(resample_rule).last()
                        oi_df = oi_df.set_index('timestamp').resample(resample_rule).last()
                        
                        z_period = 120 if config.TIMEFRAME == "15m" else 30
                        funding_df['funding_rate_zscore'] = calculate_zscore(funding_df['fundingRate'], z_period)
                        oi_df['oi_zscore'] = calculate_zscore(oi_df['openInterestAmount'], z_period)

                        feature_df['datetime'] = pd.to_datetime(feature_df['timestamp'], unit='ms')
                        feature_df = feature_df.set_index('datetime')
                        final_df = feature_df.join(funding_df[['funding_rate_zscore']]).join(oi_df[['oi_zscore']])
                        
                        final_df['funding_rate_zscore'] = final_df['funding_rate_zscore'].fillna(0)
                        final_df['oi_zscore'] = final_df['oi_zscore'].fillna(0)
                        final_df.dropna(inplace=True)

                        last_closed = final_df.iloc[-1]
                        
                        brain_pack = brains[asset]
                        features_list = brain_pack['features']

                        if last_closed[features_list].isna().any(): continue
                        
                        X_live = pd.DataFrame([last_closed[features_list]], columns=features_list)
                        
                        # Binary Confirmation Mechanism (BCM)
                        # Check if a primary technical signal is triggered at the last closed bar
                        primary_sig = int(last_closed['primary_signal'])
                        if primary_sig not in [0, 1]:
                            continue
                            
                        direction = "LONG" if primary_sig == 1 else "SHORT"
                        
                        probabilities = brain_pack['model'].predict_proba(X_live)[0]
                        # Win probability is the probability of class 1 (SUCCESS)
                        win_prob = probabilities[1] * 100

                        # 🟢 V8.5 Funnel: Increment generated signal count
                        signal_funnel["generated"] += 1
                        save_state()
                        
                        # 🟢 V8.5 Switch: Enforce Trade Mode direction settings
                        if trade_mode == "OFF":
                            print(f"[MODE REJECT] {asset} signal aborted. Trade Mode is OFF globally.")
                            continue
                        elif trade_mode == "LONG_ONLY" and direction != "LONG":
                            print(f"[MODE REJECT] {asset} {direction} signal aborted. Trade Mode is LONG_ONLY.")
                            continue
                        elif trade_mode == "SHORT_ONLY" and direction != "SHORT":
                            print(f"[MODE REJECT] {asset} {direction} signal aborted. Trade Mode is SHORT_ONLY.")
                            continue
                        
                        # 🟢 V8.5 Upgrade: Support direction-specific thresholds (LONG vs SHORT)
                        if direction == "LONG":
                            base_threshold = getattr(config, 'LONG_CONFIDENCE_THRESHOLD', 65.0)
                        else:
                            base_threshold = getattr(config, 'SHORT_CONFIDENCE_THRESHOLD', 60.0)
                            
                        # Support asset-and-direction specific overrides, else asset overrides, else base_threshold
                        threshold = getattr(config, 'ASSET_SPECIFIC_THRESHOLDS', {}).get(f"{asset}_{direction}", 
                                    getattr(config, 'ASSET_SPECIFIC_THRESHOLDS', {}).get(asset, base_threshold))
                                    
                        # 🟢 V8.6 Market Regime Adaptive Threshold Adjustment (Enhancement #3)
                        last_chop = float(last_closed['chop_index'])
                        last_adx = float(last_closed['adx_14'])
                        trigger_cat = int(last_closed['trigger_category'])
                        
                        regime = "NORMAL"
                        if last_chop > 55.0 or last_adx < 20.0:
                            regime = "CHOPPY"
                        elif last_chop < 45.0 and last_adx > 25.0:
                            regime = "TRENDING"
                            
                        regime_adjustment = 0.0
                        if regime == "CHOPPY":
                            if trigger_cat in [1, 2]: # TREND or BREAKOUT
                                regime_adjustment = 5.0 # Raise threshold by 5% to avoid whipsaws in chop
                        elif regime == "TRENDING":
                            if trigger_cat in [1, 2]: # TREND or BREAKOUT
                                regime_adjustment = -2.5 # Lower threshold by 2.5% to capture strong trend breakouts
                            elif trigger_cat == 3: # REVERSION
                                regime_adjustment = 5.0 # Raise threshold by 5% as reversion is risky in strong trend
                                
                        if getattr(config, 'REGIME_ADAPTIVE_THRESHOLD_ENABLED', True):
                            threshold += regime_adjustment
                            if regime_adjustment != 0.0:
                                print(f"  [REGIME ADJUST] {asset} in {regime} regime. Trigger Cat: {trigger_cat}. Adjusted threshold: {threshold:.2f}% (adjustment: {regime_adjustment:+.1f}%)")
                                    
                        if win_prob >= threshold:
                            # Enforce maximum concurrent active trades limit
                            max_allowed = getattr(config, 'MAX_ACTIVE_TRADES', 3)
                            if len(active_trades) >= max_allowed:
                                print(f"[REJECT] {asset} signal rejected. Maximum active trades limit reached ({len(active_trades)}/{max_allowed}).")
                                msg = (
                                    f"⚠️ *[AlphaQuant V8.2] SIGNAL REJECTED (MAX TRADES)*\n"
                                    f"• *Asset*: {asset} | *Direction*: {direction}\n"
                                    f"• *AI Win Prob*: `{win_prob:.2f}%` (Passed Threshold `{threshold:.2f}%`)\n"
                                    f"• *Reason*: Maximum active trades limit reached ({len(active_trades)}/{max_allowed})."
                                )
                                track_rejected_signal(asset, direction, win_prob, threshold, last_closed['close'], last_closed['atr'], "MAX_TRADES", regime)
                                send_telegram_message(msg)
                                continue

                            # 🟢 V8.5 Multi-Timeframe Veto Power Check
                            if getattr(config, 'MULTITIMEFRAME_VETO_ENABLED', True):
                                close_val = last_closed['close']
                                ema_fast = last_closed['ema_50']
                                ema_slow = last_closed['ema_200']
                                
                                if direction == "LONG" and not (close_val > ema_fast and ema_fast > ema_slow):
                                    print(f"[REJECT] {asset} LONG signal rejected. Higher-Timeframe trend is not bullish (Close: {close_val:.2f}, Fast EMA: {ema_fast:.2f}, Slow EMA: {ema_slow:.2f}).")
                                    msg = (
                                        f"⚠️ *[AlphaQuant V8.2] SIGNAL REJECTED (HTF TREND VETO)*\n"
                                        f"• *Asset*: {asset} | *Direction*: {direction}\n"
                                        f"• *AI Win Prob*: `{win_prob:.2f}%` (Passed Threshold `{threshold:.2f}%`)\n"
                                        f"• *Reason*: HTF trend not bullish (Close: {close_val:.2f}, EMA50: {ema_fast:.2f}, EMA200: {ema_slow:.2f})."
                                    )
                                    track_rejected_signal(asset, direction, win_prob, threshold, last_closed['close'], last_closed['atr'], "TREND_VETO", regime)
                                    send_telegram_message(msg)
                                    continue
                                elif direction == "SHORT" and not (close_val < ema_fast and ema_fast < ema_slow):
                                    print(f"[REJECT] {asset} SHORT signal rejected. Higher-Timeframe trend is not bearish (Close: {close_val:.2f}, Fast EMA: {ema_fast:.2f}, Slow EMA: {ema_slow:.2f}).")
                                    msg = (
                                        f"⚠️ *[AlphaQuant V8.2] SIGNAL REJECTED (HTF TREND VETO)*\n"
                                        f"• *Asset*: {asset} | *Direction*: {direction}\n"
                                        f"• *AI Win Prob*: `{win_prob:.2f}%` (Passed Threshold `{threshold:.2f}%`)\n"
                                        f"• *Reason*: HTF trend not bearish (Close: {close_val:.2f}, EMA50: {ema_fast:.2f}, EMA200: {ema_slow:.2f})."
                                    )
                                    track_rejected_signal(asset, direction, win_prob, threshold, last_closed['close'], last_closed['atr'], "TREND_VETO", regime)
                                    send_telegram_message(msg)
                                    continue
                                    
                            # 🟢 V8.4 Chop Filter Check: Prevent entering trades in choppy/sideways markets
                            chop_series = calculate_choppiness_index(df, 14)
                            last_chop = chop_series.iloc[-1]
                            last_adx = last_closed['adx_14']
                            
                            if last_chop > 61.8 and last_adx < 20:
                                print(f"[REJECT] {asset} signal rejected. Market is in Chop/Sideways regime (Chop: {last_chop:.2f} > 61.8, ADX: {last_adx:.2f} < 20).")
                                msg = (
                                    f"⚠️ *[AlphaQuant V8.2] SIGNAL REJECTED (EXTREME CHOP)*\n"
                                    f"• *Asset*: {asset} | *Direction*: {direction}\n"
                                    f"• *AI Win Prob*: `{win_prob:.2f}%` (Passed Threshold `{threshold:.2f}%`)\n"
                                    f"• *Reason*: Market in Extreme Chop/Sideways (Chop: {last_chop:.2f} > 61.8, ADX: {last_adx:.2f} < 20)."
                                )
                                track_rejected_signal(asset, direction, win_prob, threshold, last_closed['close'], last_closed['atr'], "EXTREME_CHOP", regime)
                                send_telegram_message(msg)
                                # 🟢 V8.5 Funnel: Increment regime rejection counter
                                signal_funnel["rejected_regime"] += 1
                                save_state()
                                continue
                                
                            # 🟢 V8.4 Correlation Check: Avoid simultaneous LONG/SHORT in highly correlated assets (BTC & ETH)
                            if asset in ("BTC/USDT", "ETH/USDT"):
                                correlated_pair = "ETH/USDT" if asset == "BTC/USDT" else "BTC/USDT"
                                active_correlated = [t for t in active_trades if t['asset'] == correlated_pair and t['direction'] == direction]
                                if active_correlated:
                                    print(f"[REJECT] {asset} {direction} signal rejected. Correlated asset {correlated_pair} already has an active {direction} trade.")
                                    msg = (
                                        f"⚠️ *[AlphaQuant V8.2] SIGNAL REJECTED (CORRELATION)*\n"
                                        f"• *Asset*: {asset} | *Direction*: {direction}\n"
                                        f"• *AI Win Prob*: `{win_prob:.2f}%` (Passed Threshold `{threshold:.2f}%`)\n"
                                        f"• *Reason*: Correlated asset {correlated_pair} already has an active {direction} trade."
                                    )
                                    track_rejected_signal(asset, direction, win_prob, threshold, last_closed['close'], last_closed['atr'], "CORRELATION", regime)
                                    send_telegram_message(msg)
                                    continue
                            # 🟢 V8.3 Upgrade: Fetch actual live price via REST to guarantee accuracy
                            # and prevent stale entry prices or inverted SL/TP parameters.
                            # Fallback: if the REST fetch fails or returns None, we explicitly use the
                            # last closed candle's close price (final amount) to avoid stale websocket data.
                            try:
                                ticker = await asyncio.to_thread(self.exchange_reg.fetch_ticker, asset)
                                entry_price = ticker.get('last') if ticker else None
                                if not entry_price or pd.isna(entry_price):
                                    raise ValueError("Ticker last price is empty or invalid")
                            except Exception as price_err:
                                print(f"[WARNING] REST live price fetch failed or empty for {asset}: {price_err}. Falling back to last closed candle price: {last_closed['close']}")
                                entry_price = last_closed['close']

                            # 🟢 V8.3 Slippage Boundary Check: Prevent chasing entries into extended markets
                            trigger_price = last_closed['close']
                            deviation = abs(entry_price - trigger_price) / trigger_price
                            if deviation > getattr(config, 'MAX_PRICE_DEVIATION_PCT', 0.005):
                                print(f"[REJECT] {asset} live price ${entry_price:,.4f} is too far from trigger ${trigger_price:,.4f} (Deviation: {deviation*100:.2f}% > Limit: {config.MAX_PRICE_DEVIATION_PCT*100:.2f}%). Rejecting trade entry.")
                                msg = (
                                    f"⚠️ *[AlphaQuant V8.2] SIGNAL REJECTED (SLIPPAGE)*\n"
                                    f"• *Asset*: {asset} | *Direction*: {direction}\n"
                                    f"• *AI Win Prob*: `{win_prob:.2f}%` (Passed Threshold `{threshold:.2f}%`)\n"
                                    f"• *Reason*: Live price ${entry_price:,.4f} deviates too far from trigger ${trigger_price:,.4f} (Deviation: {deviation*100:.2f}% > Limit: {config.MAX_PRICE_DEVIATION_PCT*100:.2f}%)."
                                )
                                track_rejected_signal(asset, direction, win_prob, threshold, entry_price, last_closed['atr'], "SLIPPAGE", regime)
                                send_telegram_message(msg)
                                continue
                                
                            atr_val = last_closed['atr']
                            sl = entry_price - atr_val * config.ATR_STOP_LOSS_MULTIPLIER if direction == "LONG" else entry_price + atr_val * config.ATR_STOP_LOSS_MULTIPLIER
                            tp = entry_price + atr_val * config.ATR_TAKE_PROFIT_MULTIPLIER if direction == "LONG" else entry_price - atr_val * config.ATR_TAKE_PROFIT_MULTIPLIER
                            # --- Dynamic Risk Sizing (Kelly-ATR Hybrid) ---
                            confidence_factor = 1.0 + (win_prob - threshold) / (100.0 - threshold)
                            atr_pct_val = last_closed['atr_pct']
                            vol_factor = 0.015 / max(atr_pct_val, 0.001)
                            volatility_factor = np.clip(vol_factor, 0.5, 1.5)
                            
                            base_risk = getattr(config, 'RISK_PER_TRADE_USD', 10.0)
                            target_risk = base_risk * confidence_factor * volatility_factor
                            # Cap absolute risk per trade at 2.0x base_risk to prevent over-exposure
                            target_risk = min(target_risk, base_risk * 2.0)
                            
                            position_size = (target_risk / abs(entry_price - sl)) * entry_price
                            # Cap position size to prevent insufficient margin on small wallets
                            max_pos = getattr(config, 'MAX_POSITION_SIZE_USD', 500.0)
                            if position_size > max_pos:
                                print(f"[SYSTEM] Capping position size for {asset} from ${position_size:.2f} to ${max_pos:.2f} to fit wallet margin requirements.")
                                position_size = max_pos
                            
                            # 🟢 V8.5 Funnel: Increment executed counter
                            signal_funnel["executed"] += 1
                            
                            # 🟢 V8.5 Dynamic Signal Classification (Trend vs Reversion)
                            dist_50 = last_closed['dist_ema_50']
                            if (direction == "LONG" and dist_50 > 0) or (direction == "SHORT" and dist_50 < 0):
                                signal_type = "TREND"
                            else:
                                signal_type = "REVERSION"
                            
                            # Place Testnet Entry Order if enabled
                            order_id = await execute_testnet_order(
                                self.exchange_reg,
                                symbol=asset,
                                direction=direction,
                                amount=position_size / entry_price
                            )
                            
                            # 🟢 V8.5 active_trades metadata: Include entry_time (timestamp) and signal_type
                            active_trades.append({
                                "asset": asset, "direction": direction, "entry": entry_price, "sl": sl, "tp": tp, 
                                "status": "OPEN", "ai_prob": win_prob, "position_size": position_size, "pnl": 0.0,
                                "entry_time": time.time(),
                                "signal_type": signal_type,
                                "entry_atr": atr_val,
                                "highest_price": entry_price,
                                "lowest_price": entry_price,
                                "trailing_active": False,
                                "half_closed": False,
                                "testnet_order_id": order_id,
                                "entry_features": {
                                    "dist_ema_50": float(last_closed['dist_ema_50']),
                                    "dist_ema_200": float(last_closed['dist_ema_200']),
                                    "atr_pct": float(last_closed['atr_pct']),
                                    "volume_zscore": float(last_closed['volume_zscore']),
                                    "adx_14": float(last_closed['adx_14']),
                                    "funding_rate_zscore": float(last_closed['funding_rate_zscore']),
                                    "oi_zscore": float(last_closed['oi_zscore']),
                                    "bb_width": float(last_closed['bb_width']),
                                    "rsi_14": float(last_closed['rsi_14']),
                                    "macd_hist": float(last_closed['macd_hist']),
                                    "supertrend_direction": float(last_closed['supertrend_direction']),
                                    "chop_index": float(last_closed['chop_index']),
                                    "trigger_category": int(last_closed['trigger_category'])
                                }
                            })
                            asset_locks[asset] = True
                            save_state()
                            
                            # Send Telegram Notification for executed trade
                            rr_ratio = config.ATR_TAKE_PROFIT_MULTIPLIER / config.ATR_STOP_LOSS_MULTIPLIER
                            sl_pct = (abs(entry_price - sl) / entry_price) * 100.0
                            tp_pct = (abs(tp - entry_price) / entry_price) * 100.0

                            msg = (
                                f"🧠 *[V8.2] SHOTGUN SIGNAL EXECUTED*\n"
                                f"• *Asset*: {asset} | *Direction*: *{direction}*\n"
                                f"• *Entry Price*: `${entry_price:,.4f}`\n"
                                f"• *Stop Loss (SL)*: `${sl:,.4f}` (-{sl_pct:.2f}%)\n"
                                f"• *Take Profit (TP)*: `${tp:,.4f}` (+{tp_pct:.2f}%)\n"
                                f"• *Position Size*: `${position_size:,.2f}` (Notional)\n"
                                f"• *Risk Amount*: `${target_risk:,.2f}` | *R:R*: `1:{rr_ratio:.1f}`\n"
                                f"• *AI Win Prob*: *{win_prob:.2f}%*"
                            )
                            send_telegram_message(msg)
                        else:
                            # 🟢 V8.5 Funnel: Increment threshold rejection counter
                            signal_funnel["rejected_threshold"] += 1
                            save_state()
                            msg = (
                                f"⚠️ *[AlphaQuant V8.2] SIGNAL REJECTED (LOW PROBABILITY)*\n"
                                f"• *Asset*: {asset} | *Direction*: {direction}\n"
                                f"• *AI Win Prob*: `{win_prob:.2f}%`\n"
                                f"• *Required Threshold*: `{threshold:.2f}%`\n"
                                f"• *Regime*: `{regime}` | *Trigger Cat*: `{trigger_cat}`\n"
                                f"• *Reason*: Under minimum ML confidence threshold."
                            )
                            track_rejected_signal(asset, direction, win_prob, threshold, last_closed['close'], last_closed['atr'], "LOW_PROB", regime)
                            send_telegram_message(msg)
                            
                    except Exception as e:
                        print(f"[ERROR] Inference failed for {asset}: {e}", file=sys.stderr)

                send_telegram_message("✅ *[V8.2] Shotgun Inference Cycle Complete.*")

            except asyncio.CancelledError: break

    async def run(self):
        await self.reconcile_open_positions()
        print("[SYSTEM] Booting V8.2 Asynchronous Event Loop...")
        self.tasks.append(asyncio.create_task(self.watch_all_tickers()))
        self.tasks.append(asyncio.create_task(self.fallback_price_monitor()))
        self.tasks.append(asyncio.create_task(self.ml_inference_loop()))
        print(f"[SUCCESS] Async Websockets Live. V8.2 Meta-Agents actively hunting on {len(brains)} assets.")
        try: await asyncio.gather(*self.tasks)
        except asyncio.CancelledError: pass

    async def shutdown(self):
        print("\n[SYSTEM] V8.2 Async Engine Shutting Down Gracefully...")
        self.running = False
        for task in self.tasks: task.cancel()
        await asyncio.gather(*self.tasks, return_exceptions=True)
        if self.exchange_pro: await self.exchange_pro.close()

if __name__ == "__main__":
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    
    engine = AlphaQuantV8_2()
    try:
        asyncio.run(engine.run())
    except KeyboardInterrupt:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            loop.create_task(engine.shutdown())
        else:
            loop.run_until_complete(engine.shutdown())
        loop.close()