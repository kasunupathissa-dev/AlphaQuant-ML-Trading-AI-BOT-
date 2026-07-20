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

# =====================================================================
# ALPHAQUANT V4.1: MULTI-MODEL ASYNC DEPLOYMENT ENGINE
# =====================================================================

LOG_FILE = "trading_log_v4.csv"
TELEGRAM_TOKEN = "8881201037:AAEYhqFD0d2FZ5W1l6uq3kb4Vuv385jGc34"
TELEGRAM_CHAT_ID = "6649046952"

LEVERAGE = 10
MAX_RISK_CAP_PCT = 15.0 
LIVE_TRADING_ENABLED = False 

TARGET_ASSETS = ["BTC/USDT", "ETH/USDT", "SOL/USDT", "BNB/USDT", "ADA/USDT", "XRP/USDT"]

active_trades = []
trade_history = []
live_prices = {}
live_orderbooks = {}
asset_locks = {} 
specialized_brains = {} # Holds the models and thresholds for each coin

def send_telegram_message(msg):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        requests.post(url, json={"chat_id": TELEGRAM_CHAT_ID, "text": msg, "parse_mode": "Markdown"}, timeout=5)
    except:
        pass

def log_trade_to_csv(trade):
    try:
        file_exists = os.path.isfile(LOG_FILE)
        headers = ["Timestamp", "Asset", "Direction", "Entry", "TP", "SL", "Status", "AI_Prob", "PNL"]
        with open(LOG_FILE, mode="a", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            if not file_exists: writer.writerow(headers)
            writer.writerow([
                time.strftime("%Y-%m-%d %H:%M:%S"), trade["asset"], trade["direction"],
                f"{trade['entry']:.4f}", f"{trade['tp']:.4f}", f"{trade['sl']:.4f}",
                trade["status"], f"{trade['ai_prob']:.2f}%", f"{trade['pnl']:.2f}"
            ])
    except Exception as e:
        print(f"[ERROR] CSV Logging Failure: {e}")

# Pure Pandas Indicator Implementations
def calculate_ema(series, span):
    return series.ewm(span=span, adjust=False).mean()

def calculate_rsi(series, period=14):
    delta = series.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

def calculate_atr(df, period=14):
    high_low = df['high'] - df['low']
    high_close = np.abs(df['high'] - df['close'].shift())
    low_close = np.abs(df['low'] - df['close'].shift())
    ranges = pd.concat([high_low, high_close, low_close], axis=1)
    return np.max(ranges, axis=1).rolling(window=period).mean()

def calculate_macd(series, fast=12, slow=26, signal=9):
    ema_fast = calculate_ema(series, fast)
    ema_slow = calculate_ema(series, slow)
    macd_line = ema_fast - ema_slow
    signal_line = calculate_ema(macd_line, signal)
    return macd_line - signal_line

def calculate_bb_width(series, period=20, std_dev=2):
    sma = series.rolling(window=period).mean()
    std = series.rolling(window=period).std()
    return ((sma + (std * std_dev)) - (sma - (std * std_dev))) / sma


class AlphaQuantV4_Multi:
    def __init__(self):
        print("==================================================")
        print("  ALPHAQUANT V4.1: LOADING MULTI-MODEL ENGINE     ")
        print("==================================================")
        
        # 🟢 V4.1: Load Individual Brains for each asset
        for asset in TARGET_ASSETS:
            safe_filename = asset.replace("/", "_") + "_brain.pkl"
            if os.path.exists(safe_filename):
                data = joblib.load(safe_filename)
                specialized_brains[asset] = {
                    'model': data['model'],
                    'threshold': data['optimal_threshold'] * 100 # Convert to percentage
                }
                print(f"[SUCCESS] Loaded Brain for {asset} (Threshold: {data['optimal_threshold']*100:.1f}%)")
            else:
                print(f"[WARNING] No brain found for {asset}. Skipping inference for this coin.")
        
        if not specialized_brains:
            print("[FATAL] No brains loaded. Run model_training_multi.py first.")
            exit()
            
        self.exchange = ccxtpro.binance({
            'enableRateLimit': True,
            'options': {'defaultType': 'future'}
        })
        self.running = True
        
        send_telegram_message(f"🚀 *[AlphaQuant V4.1]*\nMulti-Model Async ML Engine booting up.\nLoaded {len(specialized_brains)} Specialized Brains.")

    async def watch_ticker_stream(self, symbol):
        while self.running:
            try:
                ticker = await self.exchange.watch_ticker(symbol)
                live_prices[symbol] = ticker['last']
                await self.manage_active_trades(symbol, ticker['last'])
            except Exception as e:
                print(f"[ERROR] Ticker stream failed for {symbol}: {e}")
                await asyncio.sleep(5)

    async def watch_orderbook_stream(self, symbol):
        while self.running:
            try:
                orderbook = await self.exchange.watch_order_book(symbol, limit=20)
                bids, asks = orderbook['bids'], orderbook['asks']
                
                if bids and asks:
                    bid_vol = sum(b[1] for b in bids)
                    ask_vol = sum(a[1] for a in asks)
                    imbalance = bid_vol / ask_vol if ask_vol > 0 else 1.0
                    live_orderbooks[symbol] = imbalance
            except Exception as e:
                print(f"[ERROR] Orderbook stream failed for {symbol}: {e}")
                await asyncio.sleep(5)

    async def manage_active_trades(self, symbol, current_price):
        global active_trades
        
        updated_trades = []
        for trade in active_trades:
            if trade['asset'] != symbol:
                updated_trades.append(trade)
                continue
                
            is_closed, result, pnl = False, "", 0.0
            
            if trade['direction'] == "LONG":
                if current_price >= trade['tp']:
                    is_closed, result, pnl = True, "PROFIT", 100 * LEVERAGE * ((trade['tp'] - trade['entry']) / trade['entry'])
                elif current_price <= trade['sl']:
                    is_closed, result, pnl = True, "LOSS", 100 * LEVERAGE * ((trade['sl'] - trade['entry']) / trade['entry'])
            else: 
                if current_price <= trade['tp']:
                    is_closed, result, pnl = True, "PROFIT", 100 * LEVERAGE * ((trade['entry'] - trade['tp']) / trade['entry'])
                elif current_price >= trade['sl']:
                    is_closed, result, pnl = True, "LOSS", 100 * LEVERAGE * ((trade['entry'] - trade['sl']) / trade['entry'])

            if is_closed:
                trade['status'] = result
                trade['pnl'] = pnl
                trade_history.append(trade)
                log_trade_to_csv(trade)
                
                msg = f"🔔 *[V4.1 Multi-Model] TRADE CLOSED*\n• Asset: {symbol} | {trade['direction']}\n• Status: {result}\n• PNL ({LEVERAGE}x): {'+$' if pnl > 0 else '$'}{pnl:.2f}"
                send_telegram_message(msg)
                print(f"[{time.strftime('%H:%M:%S')}] {msg}")
                
                asset_locks[symbol] = False 
            else:
                updated_trades.append(trade)
                
        active_trades = updated_trades

    async def ml_inference_loop(self):
        while self.running:
            await asyncio.sleep(900)
            
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Executing Async ML Inference Pipeline...")
            
            for asset in TARGET_ASSETS:
                if asset not in specialized_brains or asset_locks.get(asset, False):
                    continue
                    
                try:
                    ohlcv = await self.exchange.fetch_ohlcv(asset, "1h", limit=250)
                    df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
                    
                    df['ema_20'] = calculate_ema(df['close'], 20)
                    df['ema_50'] = calculate_ema(df['close'], 50)
                    df['ema_200'] = calculate_ema(df['close'], 200)
                    
                    df['dist_ema_20'] = (df['close'] - df['ema_20']) / df['ema_20']
                    df['dist_ema_50'] = (df['close'] - df['ema_50']) / df['ema_50']
                    df['dist_ema_200'] = (df['close'] - df['ema_200']) / df['ema_200']
                    
                    macd_hist = calculate_macd(df['close'])
                    df['macd_hist_norm'] = macd_hist / df['close']
                        
                    rsi = calculate_rsi(df['close'], 14)
                    df['rsi_norm'] = (rsi - 50) / 50
                    
                    df['atr'] = calculate_atr(df, 14)
                    df['atr_pct'] = df['atr'] / df['close']
                    
                    df['bb_width'] = calculate_bb_width(df['close'])

                    df['candle_range'] = df['high'] - df['low']
                    df['buying_pressure_ratio'] = np.where(df['candle_range'] > 0, (df['close'] - df['low']) / df['candle_range'], 0.5)
                    df['bull_vol'] = df['volume'] * df['buying_pressure_ratio']
                    df['bear_vol'] = df['volume'] * (1 - df['buying_pressure_ratio'])
                    df['net_delta'] = df['bull_vol'] - df['bear_vol']
                    df['cvd_24h'] = df['net_delta'].rolling(24).sum()
                    df['vol_24h'] = df['volume'].rolling(24).sum()
                    df['cvd_norm'] = np.where(df['vol_24h'] > 0, df['cvd_24h'] / df['vol_24h'], 0)

                    df['fvg_bull_gap'] = df['low'] - df['high'].shift(2)
                    df['fvg_bear_gap'] = df['low'].shift(2) - df['high']
                    df['fvg_bull_intensity'] = np.where(df['fvg_bull_gap'] > 0, df['fvg_bull_gap'] / df['atr'], 0)
                    df['fvg_bear_intensity'] = np.where(df['fvg_bear_gap'] > 0, df['fvg_bear_gap'] / df['atr'], 0)
                    
                    last_closed = df.iloc[-2]
                    
                    features_list = [
                        'dist_ema_20', 'dist_ema_50', 'dist_ema_200', 'macd_hist_norm', 
                        'rsi_norm', 'atr_pct', 'bb_width', 'cvd_norm', 
                        'fvg_bull_intensity', 'fvg_bear_intensity'
                    ]
                    
                    if last_closed[features_list].isna().any():
                        continue
                        
                    X_live = pd.DataFrame([last_closed[features_list]])
                    
                    # 🟢 V4.1: Consult the SPECIALIZED brain for this exact asset
                    brain = specialized_brains[asset]['model']
                    required_threshold = specialized_brains[asset]['threshold']
                    
                    probabilities = brain.predict_proba(X_live)[0]
                    win_prob = probabilities[1] * 100 
                    
                    print(f"  -> {asset}: AI predicts {win_prob:.2f}% chance of Win (Needs {required_threshold:.1f}%)")
                    
                    direction = "LONG" if last_closed['dist_ema_50'] > 0 else "SHORT"
                    
                    if win_prob >= required_threshold:
                        entry_price = live_prices.get(asset, last_closed['close'])
                        atr_val = last_closed['atr']
                        
                        sl_offset = atr_val * 1.5
                        tp_offset = sl_offset * 2.0
                        
                        sl = entry_price - sl_offset if direction == "LONG" else entry_price + sl_offset
                        tp = entry_price + tp_offset if direction == "LONG" else entry_price - tp_offset
                        
                        risk_pct = abs((entry_price - sl) / entry_price) * LEVERAGE * 100
                        if risk_pct > MAX_RISK_CAP_PCT:
                            print(f"[BLOCKED] {asset} AI Signal ignored due to high risk cap ({risk_pct:.1f}%).")
                            continue
                            
                        active_trades.append({
                            "asset": asset, "direction": direction, "entry": entry_price, 
                            "sl": sl, "tp": tp, "status": "OPEN", "ai_prob": win_prob, "pnl": 0.0
                        })
                        
                        asset_locks[asset] = True
                        
                        msg = (f"🧠 *[V4.1] MULTI-MODEL SIGNAL EXECUTED*\n"
                               f"• Asset: {asset}\n"
                               f"• Action: {direction}\n"
                               f"• Entry: ${entry_price:,.4f}\n"
                               f"• TP: ${tp:,.4f} | SL: ${sl:,.4f}\n"
                               f"• AI Win Prob: *{win_prob:.2f}%* (Threshold: {required_threshold:.1f}%)")
                        print(msg)
                        send_telegram_message(msg)

                except Exception as e:
                    print(f"[ERROR] Inference failed for {asset}: {e}")

    async def run(self):
        print("[SYSTEM] Booting V4.1 Asynchronous Event Loop...")
        
        tasks = []
        for asset in TARGET_ASSETS:
            tasks.append(self.watch_ticker_stream(asset))
            tasks.append(self.watch_orderbook_stream(asset))
            
        tasks.append(self.ml_inference_loop())
        
        print(f"[SUCCESS] Async Websockets Live. ML Agents actively hunting.")
        await asyncio.gather(*tasks)
        await self.exchange.close()

if __name__ == "__main__":
    import sys
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        
    engine = AlphaQuantV4_Multi()
    
    try:
        asyncio.run(engine.run())
    except KeyboardInterrupt:
        print("\n[SYSTEM] V4.1 Async Engine Shutting Down Gracefully...")
        engine.running = False