import asyncio
import ccxt.pro as ccxtpro
import pandas as pd
import time
from datetime import datetime
import json
import config
from database_config import get_db_engine
from sqlalchemy import text

class AsyncMarketDataEngine:
    def __init__(self):
        # 🟢 V4.0 Async Websocket Client
        self.exchange = ccxtpro.binance({
            'enableRateLimit': True,
            'options': {
                'defaultType': 'future'
            }
        })
        self.running = True
        
        # In-memory stores for ultra-fast access
        self.live_prices = {}
        self.live_orderbooks = {}
        
        print("==================================================")
        print("  ALPHAQUANT V8.2: ASYNC WEBSOCKET INGESTION      ")
        print("==================================================")

    async def watch_ticker_stream(self, symbol):
        """
        Continuously listens to the websocket for real-time price updates
        without ever polling the REST API.
        """
        while self.running:
            try:
                # This line yields control until Binance pushes a new tick
                ticker = await self.exchange.watch_ticker(symbol)
                
                # Update in-memory price instantly
                self.live_prices[symbol] = ticker['last']
                
                # We do not print here because it would spam the console thousands of times per second
            except Exception as e:
                print(f"[ERROR] Websocket Ticker stream failed for {symbol}: {e}")
                await asyncio.sleep(5) # Backoff before reconnecting

    async def watch_orderbook_stream(self, symbol):
        """
        Maintains a live snapshot of the L2 Order Book via websockets.
        Crucial for calculating real-time imbalance and spoofing detection.
        """
        while self.running:
            try:
                orderbook = await self.exchange.watch_order_book(symbol, limit=20)
                
                # Calculate real-time bid/ask ratio (top 10 levels)
                bids = orderbook['bids']
                asks = orderbook['asks']
                
                if bids and asks:
                    bid_vol = sum(b[1] for b in bids[:10])
                    ask_vol = sum(a[1] for a in asks[:10])
                    imbalance = bid_vol / ask_vol if ask_vol > 0 else 1.0
                    
                    self.live_orderbooks[symbol] = {
                        'imbalance': imbalance,
                        'spread': asks[0][0] - bids[0][0]
                    }
                    
            except Exception as e:
                print(f"[ERROR] Websocket Orderbook stream failed for {symbol}: {e}")
                await asyncio.sleep(5)

    async def save_snapshots_to_db(self):
        """
        Periodically takes the ultra-fast in-memory websocket data
        and commits a snapshot to the MySQL database.
        """
        while self.running:
            # Wait 60 seconds between snapshots
            await asyncio.sleep(60)
            
            if not self.live_prices:
                continue
                
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Saving Async Market Snapshot to MySQL...")
            
            try:
                engine = get_db_engine()
                if engine is None:
                    print("[WARNING] MySQL Database engine is not available. Skipping snapshot.")
                    continue

                current_time = int(time.time() * 1000)
                
                with engine.connect() as conn:
                    # Create a specialized table for high-frequency snapshots in MySQL
                    conn.execute(text('''
                    CREATE TABLE IF NOT EXISTS hft_snapshots (
                        id INT AUTO_INCREMENT PRIMARY KEY,
                        asset VARCHAR(20) NOT NULL,
                        timestamp BIGINT NOT NULL,
                        price DOUBLE,
                        ob_imbalance DOUBLE,
                        spread DOUBLE,
                        INDEX idx_asset_timestamp (asset, timestamp)
                    )
                    '''))
                    conn.commit()

                    saved_count = 0
                    for asset in config.TARGET_ASSETS:
                        if asset in self.live_prices:
                            price = self.live_prices[asset]
                            ob_data = self.live_orderbooks.get(asset, {'imbalance': 1.0, 'spread': 0.0})
                            
                            conn.execute(text('''
                                INSERT INTO hft_snapshots (asset, timestamp, price, ob_imbalance, spread)
                                VALUES (:asset, :timestamp, :price, :ob_imbalance, :spread)
                            '''), {
                                'asset': asset,
                                'timestamp': current_time,
                                'price': price,
                                'ob_imbalance': ob_data['imbalance'],
                                'spread': ob_data['spread']
                            })
                            saved_count += 1
                            
                    conn.commit()
                    print(f"  -> MySQL Snapshot saved for {saved_count} assets.")
                
            except Exception as e:
                print(f"[ERROR] Failed to save snapshot: {e}")

    async def run(self):
        """
        The main orchestrator. It launches hundreds of concurrent websocket streams
        and manages them simultaneously on a single CPU thread.
        """
        print("[SYSTEM] Booting Asynchronous Coroutines...")
        
        tasks = []
        
        # Launch a ticker stream and an orderbook stream for EVERY asset simultaneously
        for asset in config.TARGET_ASSETS:
            tasks.append(self.watch_ticker_stream(asset))
            tasks.append(self.watch_orderbook_stream(asset))
            
        # Launch the database snapshot saver
        tasks.append(self.save_snapshots_to_db())
        
        print(f"[SUCCESS] {len(tasks)} Websocket streams established. Engine is live.")
        print("[SYSTEM] Awaiting Binance data push...")
        
        # Run all tasks concurrently forever
        await asyncio.gather(*tasks)
        
        # Clean up connections on exit
        await self.exchange.close()

if __name__ == "__main__":
    # Windows-specific fix for asyncio Event Loop
    import sys
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        
    engine = AsyncMarketDataEngine()
    
    try:
        # Start the Async Event Loop
        asyncio.run(engine.run())
    except KeyboardInterrupt:
        print("\n[SYSTEM] Async Engine Shutting Down...")
        engine.running = False