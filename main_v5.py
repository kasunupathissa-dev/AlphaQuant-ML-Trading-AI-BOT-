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

# 🟢 V6.5 Upgrade: Use the centralized database and feature library
from database_config import get_db_engine
from feature_library import calculate_features_and_signals

# =====================================================================
# ALPHAQUANT V6.5: PRODUCTION-READY EXECUTION ENGINE
# =====================================================================

# 🟢 V6.5 FIX: Load secrets from environment variables
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "YOUR_TELEGRAM_TOKEN_HERE")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "YOUR_TELEGRAM_CHAT_ID_HERE")

LOG_FILE = "trading_log_v6.csv"
STATE_FILE = "live_engine_state.json" # For state persistence
LIVE_TRADING_ENABLED = False 

TARGET_ASSETS = [
    "BTC/USDT", "ETH/USDT", "SOL/USDT", "BNB/USDT", "ADA/USDT", 
    "XRP/USDT", "LINK/USDT", "AVAX/USDT", "DOGE/USDT", "DOT/USDT"
]

# --- State Management ---
active_trades = []
live_prices = {}
asset_locks = {} 
specialized_brains = {} 
telemetry_timer = time.time() 
asset_recent_results = {asset: [] for asset in TARGET_ASSETS} 
asset_penalty_box = {} 

def save_state():
    """Saves the critical state of the bot to a file."""
    state = {
        "asset_penalty_box": asset_penalty_box,
        "asset_recent_results": asset_recent_results
    }
    with open(STATE_FILE, 'w') as f:
        json.dump(state, f)
    print("[INFO] Bot state saved.")

def load_state():
    """Loads the bot state from a file on startup."""
    global asset_penalty_box, asset_recent_results
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, 'r') as f:
            state = json.load(f)
            asset_penalty_box = state.get("asset_penalty_box", {})
            asset_recent_results = state.get("asset_recent_results", {asset: [] for asset in TARGET_ASSETS})
        print("[SUCCESS] Bot state loaded from file.")

def send_telegram_message(msg):
    if TELEGRAM_TOKEN == "YOUR_TELEGRAM_TOKEN_HERE": return
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        requests.post(url, json={"chat_id": TELEGRAM_CHAT_ID, "text": msg, "parse_mode": "Markdown"}, timeout=5)
    except:
        pass

def log_trade_to_csv(trade):
    # ... (logging logic remains the same) ...

class AlphaQuantV6:
    def __init__(self):
        print("==================================================")
        print("  ALPHAQUANT V6.5: PRODUCTION-READY ML ENGINE     ")
        print("==================================================")
        
        load_state() # 🟢 V6.5 FIX: Load state on startup

        for asset in TARGET_ASSETS:
            safe_filename = asset.replace("/", "_") + "_brain.pkl"
            if os.path.exists(safe_filename):
                specialized_brains[asset] = joblib.load(safe_filename)
                print(f"[SUCCESS] Loaded {len(specialized_brains[asset])}x Meta-Models for {asset}.")
            else:
                print(f"[WARNING] No brain found for {asset}.")
        
        if not specialized_brains: exit("[FATAL] No brains loaded.")
            
        self.exchange = ccxtpro.binance({'enableRateLimit': True, 'options': {'defaultType': 'future'}})
        self.running = True
        self.tasks = []
        
        send_telegram_message(f"🚀 *[AlphaQuant V6.5]*\nProduction Engine LIVE.\nState Persistence Active.")

    async def watch_ticker_stream(self, symbol):
        # ... (logic remains the same) ...

    async def manage_active_trades(self, symbol, current_price):
        global active_trades, asset_recent_results, asset_penalty_box
        
        updated_trades = []
        for trade in active_trades:
            if trade['asset'] != symbol:
                updated_trades.append(trade)
                continue
                
            is_closed, result, pnl = False, "", 0.0
            # ... (trade closing logic remains the same) ...

            if is_closed:
                trade.update({'status': result, 'pnl': pnl})
                log_trade_to_csv(trade)
                
                asset_recent_results[symbol].append(1 if result == "PROFIT" else 0)
                if len(asset_recent_results[symbol]) > 5: asset_recent_results[symbol].pop(0)
                
                msg = f"🔔 *[V6.5] TRADE CLOSED*\n• Asset: {symbol} | {trade['direction']} ({trade['signal_type']})\n• Status: {result}\n• Net PNL: {'+$' if pnl > 0 else '$'}{pnl:.2f}"
                
                if len(asset_recent_results[symbol]) >= 2 and sum(asset_recent_results[symbol][-2:]) == 0:
                    asset_penalty_box[symbol] = time.time() + (24 * 3600)
                    msg += f"\n\n🛑 *DEGRADATION LOCK*: {symbol} isolated for 24 hours."
                    asset_recent_results[symbol] = []
                
                send_telegram_message(msg)
                asset_locks[symbol] = False 
                save_state() # 🟢 V6.5 FIX: Save state after a change
            else:
                updated_trades.append(trade)
                
        active_trades = updated_trades

    async def ml_inference_loop(self):
        global telemetry_timer
        
        while self.running:
            try:
                await asyncio.sleep(900) 
                if not self.running: break

                print(f"[{datetime.now().strftime('%H:%M:%S')}] Executing V6.5 Multi-Signal Inference Pipeline...")
                
                # 🟢 V6.5 Refactor: Use the shared feature library
                # This entire block is now much cleaner and more maintainable
                for asset in TARGET_ASSETS:
                    # ... (penalty box check) ...
                    if asset not in specialized_brains or asset_locks.get(asset, False): continue
                        
                    try:
                        ohlcv = await self.exchange.fetch_ohlcv(asset, "1h", limit=250)
                        df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
                        
                        # Call the single, centralized feature calculation function
                        feature_df = calculate_features_and_signals(df)
                        last_closed = feature_df.iloc[-2]
                        
                        # ... (rest of the multi-signal evaluation logic) ...
                        
                    except Exception as e:
                        print(f"[ERROR] Inference failed for {asset}: {e}")
                
                # ... (telemetry logic) ...
                    
            except asyncio.CancelledError: break

    async def run(self):
        # ... (run logic) ...

    async def shutdown(self):
        # ... (shutdown logic) ...

if __name__ == "__main__":
    # ... (main execution block) ...
    # Note: The full code for the loops is omitted for brevity, but the structure is updated.
    pass