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
# ALPHAQUANT V4.4.1: DUAL-MODEL CONTINUOUS SIZING ENGINE (ASYNC FIX)
# =====================================================================

LOG_FILE = "trading_log_v4_4.csv"
TELEGRAM_TOKEN = "8881201037:AAEYhqFD0d2FZ5W1l6uq3kb4Vuv385jGc34"
TELEGRAM_CHAT_ID = "6649046952"

MAX_RISK_CAP_PCT = 15.0 
LIVE_TRADING_ENABLED = False 

TARGET_ASSETS = [
    "BTC/USDT", "ETH/USDT", "SOL/USDT", "BNB/USDT", "ADA/USDT", 
    "XRP/USDT", "LINK/USDT", "AVAX/USDT", "DOGE/USDT", "DOT/USDT"
]

active_trades = []
trade_history = []
live_prices = {}
asset_locks = {} 
specialized_brains = {} 
telemetry_timer = time.time() 

asset_recent_results = {asset: [] for asset in TARGET_ASSETS} 
asset_penalty_box = {} 

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
    except:
        pass

def calculate_ema(series, span):
    return series.ewm(span=span, adjust=False).mean()

def calculate_atr(df, period=14):
    high_low = df['high'] - df['low']
    high_close = np.abs(df['high'] - df['close'].shift())
    low_close = np.abs(df['low'] - df['close'].shift())
    ranges = pd.concat([high_low, high_close, low_close], axis=1)
    return np.max(ranges, axis=1).rolling(window=period).mean()

def calculate_choppiness_index(df, period=14):
    atr_1 = calculate_atr(df, 1)
    atr_sum = atr_1.rolling(window=period).sum()
    high_max = df['high'].rolling(window=period).max()
    low_min = df['low'].rolling(window=period).min()
    range_hl = np.maximum(high_max - low_min, 1e-8)
    return 100 * np.log10(atr_sum / range_hl) / np.log10(period)

def calculate_zscore(series, period=30):
    mean = series.rolling(window=period).mean()
    std = series.rolling(window=period).std()
    return np.where(std > 1e-8, (series - mean) / std, 0)

def calculate_bb_width(series, period=20, std_dev=2):
    sma = series.rolling(window=period).mean()
    std = series.rolling(window=period).std()
    return ((sma + (std * std_dev)) - (sma - (std * std_dev))) / sma


class AlphaQuantV4_Institutional:
    def __init__(self):
        print("==================================================")
        print("  ALPHAQUANT V4.4.1: DUAL-MODEL ML ENGINE         ")
        print("==================================================")
        
        for asset in TARGET_ASSETS:
            safe_filename = asset.replace("/", "_") + "_brain.pkl"
            if os.path.exists(safe_filename):
                data = joblib.load(safe_filename)
                specialized_brains[asset] = data
                print(f"[SUCCESS] Loaded Dual-Brains for {asset}.")
            else:
                print(f"[WARNING] No brain found for {asset}.")
        
        if not specialized_brains:
            print("[FATAL] No brains loaded.")
            exit()
            
        self.exchange = ccxtpro.binance({
            'enableRateLimit': True,
            'options': {'defaultType': 'future'}
        })
        self.running = True
        self.tasks = []
        
        send_telegram_message(f"🚀 *[AlphaQuant V4.4.1]*\nInstitutional ML Engine LIVE.\nMeta-Labeling & Continuous Sizing Active.")

    async def watch_ticker_stream(self, symbol):
        while self.running:
            try:
                ticker = await self.exchange.watch_ticker(symbol)
                live_prices[symbol] = ticker['last']
                await self.manage_active_trades(symbol, ticker['last'])
            except asyncio.CancelledError:
                break
            except Exception:
                await asyncio.sleep(5)

    async def manage_active_trades(self, symbol, current_price):
        global active_trades, asset_recent_results, asset_penalty_box
        
        updated_trades = []
        for trade in active_trades:
            if trade['asset'] != symbol:
                updated_trades.append(trade)
                continue
                
            is_closed, result, pnl = False, "", 0.0
            notional = trade['position_size']
            
            if trade['direction'] == "LONG":
                if current_price >= trade['tp']:
                    is_closed, result, pnl = True, "PROFIT", notional * ((trade['tp'] - trade['entry']) / trade['entry'])
                elif current_price <= trade['sl']:
                    is_closed, result, pnl = True, "LOSS", notional * ((trade['sl'] - trade['entry']) / trade['entry'])
            else: 
                if current_price <= trade['tp']:
                    is_closed, result, pnl = True, "PROFIT", notional * ((trade['entry'] - trade['tp']) / trade['entry'])
                elif current_price >= trade['sl']:
                    is_closed, result, pnl = True, "LOSS", notional * ((trade['entry'] - trade['sl']) / trade['entry'])

            if is_closed:
                trade['status'] = result
                trade['pnl'] = pnl
                trade_history.append(trade)
                log_trade_to_csv(trade)
                
                asset_recent_results[symbol].append(1 if result == "PROFIT" else 0)
                if len(asset_recent_results[symbol]) > 5:
                    asset_recent_results[symbol].pop(0)
                
                msg = f"🔔 *[V4.4.1] TRADE CLOSED*\n• Asset: {symbol} | {trade['direction']}\n• Status: {result}\n• Net PNL: {'+$' if pnl > 0 else '$'}{pnl:.2f}"
                print(f"[{time.strftime('%H:%M:%S')}] {msg}")
                
                if len(asset_recent_results[symbol]) >= 2 and sum(asset_recent_results[symbol][-2:]) == 0:
                    penalty_hours = 24
                    asset_penalty_box[symbol] = time.time() + (penalty_hours * 3600)
                    lock_msg = f"🛑 *[V4.4.1] DEGRADATION LOCK*\n• Asset: {symbol} isolated for {penalty_hours} hours."
                    msg += f"\n\n{lock_msg}"
                    print(lock_msg)
                    asset_recent_results[symbol] = []
                
                send_telegram_message(msg)
                asset_locks[symbol] = False 
            else:
                updated_trades.append(trade)
                
        active_trades = updated_trades

    async def ml_inference_loop(self):
        global telemetry_timer
        
        while self.running:
            try:
                await asyncio.sleep(900) 
                if not self.running: break

                print(f"[{datetime.now().strftime('%H:%M:%S')}] Executing Async Institutional ML Pipeline...")
                
                telemetry_report = "📊 *[V4.4.1] AI TELEMETRY HEARTBEAT*\n"
                should_send_telemetry = (time.time() - telemetry_timer) >= 43200 
                
                for asset in TARGET_ASSETS:
                    if asset in asset_penalty_box:
                        if time.time() < asset_penalty_box[asset]:
                            if should_send_telemetry:
                                telemetry_report += f"• {asset}: 🔒 LOCKED\n"
                            continue
                        else:
                            del asset_penalty_box[asset]

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
                        
                        df['atr'] = calculate_atr(df, 14)
                        df['atr_pct'] = df['atr'] / df['close']
                        
                        df['volatility_zscore'] = calculate_zscore(df['atr_pct'], 30)
                        df['chop_index'] = calculate_choppiness_index(df, 14)
                        
                        plus_dm = df['high'].diff()
                        minus_dm = df['low'].diff(-1)
                        plus_dm = np.where((plus_dm > minus_dm) & (plus_dm > 0), plus_dm, 0.0)
                        minus_dm = np.where((minus_dm > plus_dm) & (minus_dm > 0), minus_dm, 0.0)
                        tr = calculate_atr(df, 1)
                        plus_di = 100 * (pd.Series(plus_dm).ewm(alpha=1/14, adjust=False).mean() / tr.ewm(alpha=1/14, adjust=False).mean())
                        minus_di = 100 * (pd.Series(minus_dm).ewm(alpha=1/14, adjust=False).mean() / tr.ewm(alpha=1/14, adjust=False).mean())
                        dx = 100 * np.abs(plus_di - minus_di) / (plus_di + minus_di + 1e-8)
                        df['adx_14'] = dx.ewm(alpha=1/14, adjust=False).mean()

                        df['bb_width'] = calculate_bb_width(df['close'])

                        df['fvg_bull_gap'] = df['low'] - df['high'].shift(2)
                        df['fvg_bear_gap'] = df['low'].shift(2) - df['high']
                        df['fvg_bull_intensity'] = np.where(df['fvg_bull_gap'] > 0, df['fvg_bull_gap'] / df['atr'], 0)
                        df['fvg_bear_intensity'] = np.where(df['fvg_bear_gap'] > 0, df['fvg_bear_gap'] / df['atr'], 0)
                        
                        df['volume_zscore'] = calculate_zscore(df['volume'], 30)
                        
                        df['prev_close'] = df['close'].shift(1)
                        df['prev_ema_50'] = df['ema_50'].shift(1)
                        df['primary_long_signal'] = np.where((df['prev_close'] <= df['prev_ema_50']) & (df['close'] > df['ema_50']) & (df['ema_50'] > df['ema_200']), 1, 0)
                        df['primary_short_signal'] = np.where((df['prev_close'] >= df['prev_ema_50']) & (df['close'] < df['ema_50']) & (df['ema_50'] < df['ema_200']), 1, 0)

                        last_closed = df.iloc[-2]
                        
                        features_list = [
                            'dist_ema_20', 'dist_ema_50', 'dist_ema_200', 'atr_pct', 
                            'volatility_zscore', 'volume_zscore', 'chop_index', 'adx_14', 'bb_width', 
                            'fvg_bull_intensity', 'fvg_bear_intensity'
                        ]

                        if last_closed[features_list].isna().any():
                            continue
                            
                        is_choppy = last_closed['chop_index'] > 61.8 and last_closed['adx_14'] < 20
                        
                        direction = None
                        if last_closed['primary_long_signal'] == 1 and 'LONG' in specialized_brains[asset]:
                            direction = "LONG"
                        elif last_closed['primary_short_signal'] == 1 and 'SHORT' in specialized_brains[asset]:
                            direction = "SHORT"
                            
                        if not direction:
                            continue 
                            
                        X_live = pd.DataFrame([last_closed[features_list]])
                        brain = specialized_brains[asset][direction]['model']
                        base_threshold = max(specialized_brains[asset][direction]['threshold'] * 100, 50.0)
                        
                        probabilities = brain.predict_proba(X_live)[0]
                        win_prob = probabilities[1] * 100 
                        
                        if should_send_telemetry:
                            telemetry_report += f"• {asset} {direction}: {win_prob:.1f}% (Needs {base_threshold:.1f}%)\n"
                            
                        print(f"  -> {asset} {direction}: True Prob: {win_prob:.2f}%")
                        
                        if win_prob >= base_threshold:
                            entry_price = live_prices.get(asset, last_closed['close'])
                            atr_val = last_closed['atr']
                            
                            sl_offset = atr_val * 1.0 
                            tp_offset = atr_val * 1.5 
                            
                            sl = entry_price - sl_offset if direction == "LONG" else entry_price + sl_offset
                            tp = entry_price + tp_offset if direction == "LONG" else entry_price - tp_offset
                            
                            base_risk_dollars = 10.0
                            
                            if is_choppy:
                                target_risk = base_risk_dollars * 0.25 
                            else:
                                confidence_premium = (win_prob - base_threshold) / 100.0
                                target_risk = base_risk_dollars * (1.0 + confidence_premium)
                            
                            risk_per_unit = abs(entry_price - sl)
                            position_size = (target_risk / risk_per_unit) * entry_price
                            
                            active_trades.append({
                                "asset": asset, "direction": direction, "entry": entry_price, 
                                "sl": sl, "tp": tp, "status": "OPEN", "ai_prob": win_prob, 
                                "position_size": position_size, "pnl": 0.0
                            })
                            
                            asset_locks[asset] = True
                            
                            msg = (f"🧠 *[V4.4.1] META-SIGNAL EXECUTED*\n"
                                   f"• Asset: {asset}\n"
                                   f"• Action: {direction}\n"
                                   f"• Risk Size: ${target_risk:,.2f} {'(CHOP PENALTY)' if is_choppy else ''}\n"
                                   f"• Limit Entry: ${entry_price:,.4f}\n"
                                   f"• TP: ${tp:,.4f} | SL: ${sl:,.4f}\n"
                                   f"• AI Confidence: *{win_prob:.2f}%*")
                            print(msg)
                            send_telegram_message(msg)

                    except Exception as e:
                        print(f"[ERROR] Inference failed for {asset}: {e}")
                
                if should_send_telemetry:
                    telemetry_report += f"\n_Active Trades: {len(active_trades)} | Status: AI Monitoring_"
                    send_telegram_message(telemetry_report)
                    telemetry_timer = time.time() 
                    
            except asyncio.CancelledError:
                break

    async def run(self):
        print("[SYSTEM] Booting V4.4.1 Asynchronous Event Loop...")
        for asset in TARGET_ASSETS:
            self.tasks.append(asyncio.create_task(self.watch_ticker_stream(asset)))
        self.tasks.append(asyncio.create_task(self.ml_inference_loop()))
        print(f"[SUCCESS] Async Websockets Live. Dual-Model Meta-Agents actively hunting.")
        try:
            await asyncio.gather(*self.tasks)
        except asyncio.CancelledError:
            pass

    async def shutdown(self):
        print("\n[SYSTEM] V4.4.1 Async Engine Shutting Down Gracefully...")
        self.running = False
        for task in self.tasks:
            task.cancel()
        await asyncio.gather(*self.tasks, return_exceptions=True)
        if self.exchange:
            await self.exchange.close()
            print("[SYSTEM] Binance Websocket connections closed.")

if __name__ == "__main__":
    import sys
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        
    engine = AlphaQuantV4_Institutional()
    
    # 🟢 V4.4.1 FIX: Use modern asyncio.run() to prevent MainThread Event Loop crash on Python 3.12+
    try:
        asyncio.run(engine.run())
    except KeyboardInterrupt:
        # Spawn a new event loop just to cleanly close the ccxt connections
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(engine.shutdown())
        loop.close()