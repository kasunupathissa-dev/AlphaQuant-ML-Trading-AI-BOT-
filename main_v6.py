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

# 🟢 V6.9 Upgrade: Final Production Version with Verbose Logging
from database_config import get_db_engine
from feature_library import calculate_features_and_signals

# =====================================================================
# ALPHAQUANT V6.9: FINAL PRODUCTION ENGINE
# =====================================================================

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

LOG_FILE = "trading_log_v6.csv"
STATE_FILE = "live_engine_state.json"
LIVE_TRADING_ENABLED = False 

TARGET_ASSETS = [
    "BTC/USDT", "ETH/USDT", "SOL/USDT", "BNB/USDT", "ADA/USDT", 
    "XRP/USDT", "LINK/USDT", "AVAX/USDT", "DOGE/USDT", "DOT/USDT"
]

# --- State Management & Globals ---
active_trades, live_prices, asset_locks, specialized_brains = [], {}, {}, {}
telemetry_timer = time.time() 
asset_recent_results = {asset: [] for asset in TARGET_ASSETS} 
asset_penalty_box = {} 

def save_state():
    state = {"asset_penalty_box": asset_penalty_box, "asset_recent_results": asset_recent_results, "active_trades": active_trades}
    with open(STATE_FILE, 'w') as f: json.dump(state, f, indent=4)
    print("[INFO] Bot state saved.")

def load_state():
    global asset_penalty_box, asset_recent_results, active_trades
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, 'r') as f: state = json.load(f)
            asset_penalty_box = state.get("asset_penalty_box", {})
            asset_recent_results = state.get("asset_recent_results", {asset: [] for asset in TARGET_ASSETS})
            active_trades = state.get("active_trades", [])
            print("[SUCCESS] Bot state loaded from file.")
        except json.JSONDecodeError: print("[WARNING] Could not decode state file. Starting fresh.")
    else: print("[INFO] No state file found. Starting fresh.")

def send_telegram_message(msg):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        print("[DEBUG] Telegram secrets not set, skipping notification.")
        return
    
    print(f"[DEBUG] Attempting to send Telegram message to chat ID: {TELEGRAM_CHAT_ID}...")
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        response = requests.post(url, json={"chat_id": TELEGRAM_CHAT_ID, "text": msg, "parse_mode": "Markdown"}, timeout=10)
        
        print(f"[DEBUG] Telegram API Response Status: {response.status_code}")
        print(f"[DEBUG] Telegram API Response Body: {response.text}")

        if response.status_code != 200:
            print(f"[ERROR] Failed to send Telegram message.")
            if response.status_code == 401 or response.status_code == 404:
                print("[FATAL] Telegram Unauthorized or Not Found. The TELEGRAM_TOKEN is likely incorrect.")
            elif response.status_code == 400 and "chat not found" in response.text:
                 print("[FATAL] Telegram Chat Not Found. The TELEGRAM_CHAT_ID is incorrect or you haven't started a chat with the bot.")

    except requests.exceptions.RequestException as e:
        print(f"[ERROR] Telegram request failed due to a network error: {e}")

def log_trade_to_csv(trade):
    file_exists = os.path.isfile(LOG_FILE)
    with open(LOG_FILE, mode="a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if not file_exists: writer.writerow(["Timestamp", "Asset", "Direction", "Entry", "TP", "SL", "Status", "AI_Prob", "PNL", "SignalType"])
        writer.writerow([time.strftime("%Y-%m-%d %H:%M:%S"), trade["asset"], trade["direction"], f"{trade['entry']:.4f}", f"{trade['tp']:.4f}", f"{trade['sl']:.4f}", trade["status"], f"{trade['ai_prob']:.2f}%", f"{trade['pnl']:.2f}", trade["signal_type"]])

class AlphaQuantV6:
    def __init__(self):
        print("==================================================")
        print("  ALPHAQUANT V6.9: FINAL PRODUCTION ENGINE        ")
        print("==================================================")
        
        if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID: print("[WARNING] Telegram secrets not set. Notifications are disabled.")

        load_state()

        for asset in TARGET_ASSETS:
            safe_filename = asset.replace("/", "_") + "_brain.pkl"
            if os.path.exists(safe_filename):
                specialized_brains[asset] = joblib.load(safe_filename)
        
        if not specialized_brains: exit("[FATAL] No brains loaded.")
            
        self.exchange = ccxtpro.binance({'enableRateLimit': True, 'options': {'defaultType': 'future'}})
        self.running = True
        self.tasks = []
        
        send_telegram_message(f"🚀 *[AlphaQuant V6.9]*\nProduction Engine LIVE.")

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
                tickers = await self.exchange.watch_tickers(TARGET_ASSETS)
                for symbol, ticker in tickers.items():
                    live_prices[symbol] = ticker['last']
                    await self.manage_active_trades(symbol, ticker['last'])
            except Exception as e:
                print(f"[ERROR] Main ticker stream failed: {e}. Reconnecting in 10 seconds...")
                await asyncio.sleep(10)

    async def manage_active_trades(self, symbol, current_price):
        global active_trades
        trade_closed = False
        updated_trades = [t for t in active_trades if t['asset'] != symbol]

        for trade in [t for t in active_trades if t['asset'] == symbol]:
            is_closed, result, pnl = False, "", 0.0
            notional = trade['position_size']
            
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
                
                msg = f"🔔 *[V6.9] TRADE CLOSED*\n• {symbol} | {trade['direction']} ({trade['signal_type']})\n• Status: {result}, PNL: ${pnl:.2f}"
                
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
                await asyncio.sleep(900)
                if not self.running: break
                print(f"[{datetime.now().strftime('%H:%M:%S')}] Executing V6.9 Multi-Signal Inference...")

                for asset in TARGET_ASSETS:
                    if asset in asset_penalty_box and time.time() < asset_penalty_box[asset]: continue
                    elif asset in asset_penalty_box: del asset_penalty_box[asset]
                    if asset not in specialized_brains or asset_locks.get(asset, False): continue
                    
                    try:
                        ohlcv = await self.exchange.fetch_ohlcv(asset, "1h", limit=250)
                        df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
                        feature_df = calculate_features_and_signals(df)
                        last_closed = feature_df.iloc[-2]
                        
                        features_list = ['dist_ema_50', 'dist_ema_200', 'atr_pct', 'volume_zscore', 'adx_14', 'bb_width']
                        if last_closed[features_list].isna().any(): continue
                            
                        signal_found = None
                        for signal_type in ["TREND", "BREAKOUT", "REVERSION"]:
                            for direction in ["LONG", "SHORT"]:
                                model_key = f"{signal_type}_{direction}"
                                if last_closed[f"primary_{signal_type.lower()}_{direction.lower()}"] == 1 and model_key in specialized_brains[asset]:
                                    signal_found = (signal_type, direction, model_key)
                                    break
                            if signal_found: break
                        
                        if not signal_found: continue
                        
                        signal_type, direction, model_key = signal_found
                        X_live = pd.DataFrame([last_closed[features_list]])
                        brain_pack = specialized_brains[asset][model_key]
                        base_threshold = max(brain_pack['threshold'] * 100, 50.0)
                        
                        xgb_proba = brain_pack['xgb_model'].predict_proba(X_live)[0][1]
                        lgb_proba = brain_pack['lgb_model'].predict_proba(X_live)[0][1]
                        win_prob = ((xgb_proba + lgb_proba) / 2.0) * 100
                        
                        print(f"  -> {asset} {direction} ({signal_type}): True Prob: {win_prob:.2f}%")
                        
                        if win_prob >= base_threshold:
                            entry_price = live_prices.get(asset, last_closed['close'])
                            atr_val = last_closed['atr']
                            sl, tp = (entry_price - atr_val, entry_price + atr_val * 1.5) if direction == "LONG" else (entry_price + atr_val, entry_price - atr_val * 1.5)
                            target_risk = 10.0 * (1.0 + (win_prob - base_threshold) / 100.0)
                            position_size = (target_risk / abs(entry_price - sl)) * entry_price
                            
                            active_trades.append({"asset": asset, "direction": direction, "entry": entry_price, "sl": sl, "tp": tp, "status": "OPEN", "ai_prob": win_prob, "position_size": position_size, "pnl": 0.0, "signal_type": signal_type})
                            asset_locks[asset] = True
                            save_state()
                            
                            msg = (f"🧠 *[V6.9] {signal_type} SIGNAL EXECUTED*\n• {asset} | {direction}\n• Risk: ${target_risk:,.2f}\n• Entry: ${entry_price:,.4f}\n• AI Prob: *{win_prob:.2f}%*")
                            send_telegram_message(msg)
                    except Exception as e:
                        print(f"[ERROR] Inference failed for {asset}: {e}")
            except asyncio.CancelledError: break

    async def run(self):
        await self.reconcile_open_positions()
        print("[SYSTEM] Booting V6.9 Asynchronous Event Loop...")
        self.tasks.append(asyncio.create_task(self.watch_all_tickers()))
        self.tasks.append(asyncio.create_task(self.ml_inference_loop()))
        print(f"[SUCCESS] Async Websockets Live. V6.9 Meta-Agents actively hunting.")
        try: await asyncio.gather(*self.tasks)
        except asyncio.CancelledError: pass

    async def shutdown(self):
        print("\n[SYSTEM] V6.9 Async Engine Shutting Down Gracefully...")
        self.running = False
        for task in self.tasks: task.cancel()
        await asyncio.gather(*self.tasks, return_exceptions=True)
        if self.exchange: await self.exchange.close()

if __name__ == "__main__":
    import sys
    if sys.platform == 'win32': asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    engine = AlphaQuantV6()
    try: asyncio.run(engine.run())
    except KeyboardInterrupt:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(engine.shutdown())
        loop.close()