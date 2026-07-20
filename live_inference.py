import ccxt
import pandas as pd
import pandas_ta as ta
import joblib
import time
import os

MODEL_FILENAME = "xgboost_v4_model.pkl"

def run_live_ai_agent():
    print("==================================================")
    print("  ALPHAQUANT V4.0: LIVE MACHINE LEARNING ENGINE   ")
    print("==================================================")
    
    if not os.path.exists(MODEL_FILENAME):
        print(f"[FATAL] Model file '{MODEL_FILENAME}' not found. Run model_training.py first.")
        return

    # Load the trained "Brain"
    print("[SYSTEM] Loading XGBoost Neural Weights...")
    model = joblib.load(MODEL_FILENAME)
    
    # Initialize connection
    exchange = ccxt.binance({
        'enableRateLimit': True,
        'options': {'defaultType': 'future'}
    })
    
    target_asset = "BTC/USDT"
    print(f"[SYSTEM] Connecting to Binance Live Stream for {target_asset}...")
    
    while True:
        try:
            # 1. Fetch raw live data (Last 250 hours)
            ohlcv = exchange.fetch_ohlcv(target_asset, "1h", limit=250)
            df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            
            # 2. Re-create the exact features the model was trained on
            # Must exactly match the order and logic in feature_generator.py
            
            df['ema_50'] = ta.ema(df['close'], length=50)
            df['ema_200'] = ta.ema(df['close'], length=200)
            df['dist_ema_50'] = (df['close'] - df['ema_50']) / df['ema_50']
            df['dist_ema_200'] = (df['close'] - df['ema_200']) / df['ema_200']

            df['typ_price'] = (df['high'] + df['low'] + df['close']) / 3
            df['vwap'] = (df['typ_price'] * df['volume']).cumsum() / df['volume'].cumsum()
            df['dist_vwap'] = (df['close'] - df['vwap']) / df['vwap']

            df['atr'] = ta.atr(df['high'], df['low'], df['close'], length=14)
            df['atr_pct'] = df['atr'] / df['close']
            
            # Get the very last closed candle (Do not use current open candle to prevent repainting)
            last_closed_candle = df.iloc[-2]
            
            # 3. Create the input vector for the AI
            # Format: ['dist_ema_50', 'dist_ema_200', 'dist_vwap', 'atr_pct']
            live_features = pd.DataFrame([{
                'dist_ema_50': last_closed_candle['dist_ema_50'],
                'dist_ema_200': last_closed_candle['dist_ema_200'],
                'dist_vwap': last_closed_candle['dist_vwap'],
                'atr_pct': last_closed_candle['atr_pct']
            }])
            
            # 4. Ask the AI for a Prediction
            # Output is a probability array: [Probability of Loss, Probability of Win]
            probabilities = model.predict_proba(live_features)[0]
            win_probability = probabilities[1] * 100
            
            current_price = df['close'].iloc[-1]
            print(f"[{time.strftime('%H:%M:%S')}] {target_asset} @ ${current_price:,.2f} | AI Win Probability: {win_probability:.2f}%")
            
            # 5. Execution Logic (Only trade if AI is highly confident)
            if win_probability >= 85.0:
                print(f"  🚨 [EXECUTE] AI Confidence Threshold Exceeded! Probability: {win_probability:.2f}%. Firing LONG sequence...")
                # Execution logic would go here
            elif win_probability <= 15.0:
                print(f"  🚨 [EXECUTE] Inverse Logic: Extreme failure likelihood detected. Firing SHORT sequence...")
                # Short execution logic would go here
                
        except Exception as e:
            print(f"[ERROR] Live loop failure: {e}")
            
        # Sleep for a few minutes before querying the 1H chart again
        time.sleep(180)

if __name__ == "__main__":
    run_live_ai_agent()