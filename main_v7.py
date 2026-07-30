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
try:
    from zoneinfo import ZoneInfo
except ImportError:
    ZoneInfo = None

# 🟢 V8.2 Upgrade: JSON Serialization Fix
import config 
from database_config import get_db_engine
from feature_library import calculate_features_for_shotgun, calculate_zscore

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
    state = {
        "asset_penalty_box": asset_penalty_box,
        "asset_recent_results": asset_recent_results,
        "active_trades": active_trades,
        "signal_funnel": signal_funnel,
        "live_prices": live_prices
    }
    with open(config.STATE_FILE, 'w') as f:
        # Use the custom NumpyEncoder to prevent type errors
        json.dump(state, f, indent=4, cls=NumpyEncoder)
    print("[INFO] Bot state saved.")

def load_state():
    global asset_penalty_box, asset_recent_results, active_trades, signal_funnel
    if os.path.exists(config.STATE_FILE):
        try:
            with open(config.STATE_FILE, 'r') as f: state = json.load(f)
            asset_penalty_box = state.get("asset_penalty_box", {})
            asset_recent_results = state.get("asset_recent_results", {asset: [] for asset in config.TARGET_ASSETS})
            active_trades = state.get("active_trades", [])
            signal_funnel = state.get("signal_funnel", {"generated": 0, "rejected_regime": 0, "rejected_threshold": 0, "executed": 0})
            print("[SUCCESS] Bot state loaded from file.")
        except json.JSONDecodeError: print("[WARNING] Could not decode state file. Starting fresh.")
    else: print("[INFO] No state file found. Starting fresh.")

def send_telegram_message(msg):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID: return
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

def log_trade_to_csv(trade):
    file_exists = os.path.isfile(config.LOG_FILE)
    with open(config.LOG_FILE, mode="a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if not file_exists: writer.writerow(["Timestamp", "Asset", "Direction", "Entry", "TP", "SL", "Status", "AI_Prob", "PNL", "SignalType"])
        writer.writerow([get_local_time().strftime("%Y-%m-%d %H:%M:%S"), trade["asset"], trade["direction"], f"{trade['entry']:.4f}", f"{trade['tp']:.4f}", f"{trade['sl']:.4f}", trade["status"], f"{trade['ai_prob']:.2f}%", f"{trade['pnl']:.2f}", "SHOTGUN"])

class AlphaQuantV8_2:
    def __init__(self):
        print("==================================================")
        print("  ALPHAQUANT V8.2: SERIALIZATION-FIXED ENGINE     ")
        print("==================================================")
        
        if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID: print("[WARNING] Telegram secrets not set.")

        load_state()

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
            
        self.exchange_pro = ccxtpro.binance({'options': {'defaultType': 'future'}})
        self.exchange_reg = ccxt.binance({'options': {'defaultType': 'future'}})
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
                await asyncio.sleep(30)  # Check every 30 seconds
                if not self.running: break
                
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
        trade_closed = False
        updated_trades = [t for t in active_trades if t['asset'] != symbol]

        for trade in [t for t in active_trades if t['asset'] == symbol]:
            is_closed, result, pnl = False, "", 0.0
            notional = trade.get('position_size', 100)
            
            if trade['direction'] == "LONG":
                if current_price >= trade['tp']: is_closed, result, pnl = True, "PROFIT", notional * ((trade['tp'] - trade['entry']) / trade['entry'])
                elif current_price <= trade['sl']: is_closed, result, pnl = True, "LOSS", notional * ((trade['sl'] - trade['entry']) / trade['entry'])
            else: 
                if current_price <= trade['tp']: is_closed, result, pnl = True, "PROFIT", notional * ((trade['entry'] - trade['tp']) / trade['entry'])
                elif current_price >= trade['sl']: is_closed, result, pnl = True, "LOSS", notional * ((trade['entry'] - trade['sl']) / trade['entry'])

            if is_closed:
                trade_closed = True
                trade.update({'status': result, 'pnl': pnl})
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

    async def ml_inference_loop(self):
        while self.running:
            try:
                await asyncio.sleep(getattr(config, 'INFERENCE_INTERVAL_SECONDS', 3600)) 
                if not self.running: break
                
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
                        ohlcv = await self.exchange_pro.fetch_ohlcv(asset, config.TIMEFRAME, limit=fetch_limit)
                        df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
                        
                        feature_df = calculate_features_for_shotgun(df)
                        
                        funding_history = self.exchange_reg.fetch_funding_rate_history(asset, limit=100)
                        oi_tf = '15m' if config.TIMEFRAME == '15m' else '1h'
                        oi_history = self.exchange_reg.fetch_open_interest_history(asset, oi_tf, limit=100)
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
                        
                        prediction = brain_pack['model'].predict(X_live)[0]
                        probabilities = brain_pack['model'].predict_proba(X_live)[0]
                        
                        if prediction == 2: continue

                        # 🟢 V8.5 Funnel: Increment generated signal count
                        signal_funnel["generated"] += 1
                        save_state()

                        direction = "LONG" if prediction == 1 else "SHORT"
                        win_prob = probabilities[prediction] * 100
                        
                        # 🟢 V8.5 Upgrade: Support direction-specific thresholds (LONG vs SHORT)
                        if direction == "LONG":
                            base_threshold = getattr(config, 'LONG_CONFIDENCE_THRESHOLD', 65.0)
                        else:
                            base_threshold = getattr(config, 'SHORT_CONFIDENCE_THRESHOLD', 60.0)
                            
                        # Support asset-and-direction specific overrides, else asset overrides, else base_threshold
                        threshold = getattr(config, 'ASSET_SPECIFIC_THRESHOLDS', {}).get(f"{asset}_{direction}", 
                                    getattr(config, 'ASSET_SPECIFIC_THRESHOLDS', {}).get(asset, base_threshold))
                                    
                        if win_prob >= threshold:
                            # 🟢 V8.4 Chop Filter Check: Prevent entering trades in choppy/sideways markets
                            chop_series = calculate_choppiness_index(df, 14)
                            last_chop = chop_series.iloc[-1]
                            last_adx = last_closed['adx_14']
                            
                            if last_chop > 61.8 and last_adx < 20:
                                print(f"[REJECT] {asset} signal rejected. Market is in Chop/Sideways regime (Chop: {last_chop:.2f} > 61.8, ADX: {last_adx:.2f} < 20).")
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
                                continue
                                
                            atr_val = last_closed['atr']
                            sl = entry_price - atr_val * config.ATR_STOP_LOSS_MULTIPLIER if direction == "LONG" else entry_price + atr_val * config.ATR_STOP_LOSS_MULTIPLIER
                            tp = entry_price + atr_val * config.ATR_TAKE_PROFIT_MULTIPLIER if direction == "LONG" else entry_price - atr_val * config.ATR_TAKE_PROFIT_MULTIPLIER
                            target_risk = 10.0
                            position_size = (target_risk / abs(entry_price - sl)) * entry_price
                            
                            # 🟢 V8.5 Funnel: Increment executed counter
                            signal_funnel["executed"] += 1
                            
                            # 🟢 V8.5 Dynamic Signal Classification (Trend vs Reversion)
                            dist_50 = last_closed['dist_ema_50']
                            if (direction == "LONG" and dist_50 > 0) or (direction == "SHORT" and dist_50 < 0):
                                signal_type = "TREND"
                            else:
                                signal_type = "REVERSION"
                            
                            # 🟢 V8.5 active_trades metadata: Include entry_time (timestamp) and signal_type
                            active_trades.append({
                                "asset": asset, "direction": direction, "entry": entry_price, "sl": sl, "tp": tp, 
                                "status": "OPEN", "ai_prob": win_prob, "position_size": position_size, "pnl": 0.0,
                                "entry_time": time.time(),
                                "signal_type": signal_type
                            })
                            asset_locks[asset] = True
                            save_state()
                        else:
                            # 🟢 V8.5 Funnel: Increment threshold rejection counter
                            signal_funnel["rejected_threshold"] += 1
                            save_state()
                            
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