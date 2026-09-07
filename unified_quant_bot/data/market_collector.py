import asyncio
import ccxt.pro as ccxtpro
import pandas as pd
import time
from datetime import datetime, timezone
from typing import Callable, Dict, List
from unified_quant_bot.config.config import ALL_SYMBOLS, TARGET_SYMBOLS, TIMEFRAMES
from unified_quant_bot.data.redis_store import RedisStore
from unified_quant_bot.data.database_schema import AsyncSessionLocal, OHLCVBar, LiquidationEvent, DerivativesMetric

class UnifiedMarketCollector:
    """Ingests multi-timeframe candles, tick trades, order book depth, liquidations, and funding rates."""

    def __init__(self, redis_store: RedisStore):
        self.redis_store = redis_store
        self.exchange = ccxtpro.binance({
            'enableRateLimit': True,
            'options': {
                'defaultType': 'future'
            }
        })
        self.running = True
        self.candle_callbacks = []
        self.liquidation_callbacks = []

    def register_candle_callback(self, cb: Callable):
        self.candle_callbacks.append(cb)

    def register_liquidation_callback(self, cb: Callable):
        self.liquidation_callbacks.append(cb)

    async def prewarm_buffers(self):
        """Fetches initial 150 historical bars per timeframe and populates Redis."""
        print("[COLLECTOR] Pre-warming Redis buffers across multi-timeframe feeds...")
        for symbol in ALL_SYMBOLS:
            for tf in TIMEFRAMES:
                try:
                    bars = await self.exchange.fetch_ohlcv(symbol, timeframe=tf, limit=150)
                    for b in bars:
                        bar_dict = {
                            "timestamp": b[0],
                            "open": float(b[1]),
                            "high": float(b[2]),
                            "low": float(b[3]),
                            "close": float(b[4]),
                            "volume": float(b[5])
                        }
                        await self.redis_store.append_candle(symbol, tf, bar_dict)
                except Exception as e:
                    print(f"[COLLECTOR] Pre-warm warning for {symbol} ({tf}): {e}")
                    await asyncio.sleep(0.5)

    async def watch_ohlcv_stream(self, symbol: str, timeframe: str = "1m"):
        """Continuous async WebSocket loop for OHLCV bars."""
        while self.running:
            try:
                candles = await self.exchange.watch_ohlcv(symbol, timeframe=timeframe)
                if candles:
                    latest = candles[-1]
                    bar_dict = {
                        "timestamp": latest[0],
                        "open": float(latest[1]),
                        "high": float(latest[2]),
                        "low": float(latest[3]),
                        "close": float(latest[4]),
                        "volume": float(latest[5])
                    }
                    await self.redis_store.append_candle(symbol, timeframe, bar_dict)
                    
                    # Persist closed 1m / 15m bars to DB
                    try:
                        async with AsyncSessionLocal() as db:
                            ts_dt = datetime.fromtimestamp(latest[0]/1000, timezone.utc)
                            bar_obj = OHLCVBar(
                                timestamp=ts_dt,
                                symbol=symbol,
                                timeframe=timeframe,
                                open=bar_dict['open'],
                                high=bar_dict['high'],
                                low=bar_dict['low'],
                                close=bar_dict['close'],
                                volume=bar_dict['volume']
                            )
                            await db.merge(bar_obj)
                            await db.commit()
                    except Exception:
                        pass

                    # Notify callbacks upon closed bars
                    for cb in self.candle_callbacks:
                        asyncio.create_task(cb(symbol, timeframe, bar_dict))

            except Exception as e:
                await asyncio.sleep(5)

    async def watch_trades_stream(self, symbol: str):
        """Continuous sub-second trade stream calculating tick CVD."""
        while self.running:
            try:
                trades = await self.exchange.watch_trades(symbol)
                for t in trades:
                    price = float(t.get('price', 0.0))
                    amount = float(t.get('amount', 0.0))
                    side = t.get('side', 'buy')
                    ts = int(t.get('timestamp', int(time.time() * 1000)))
                    await self.redis_store.append_tick_trade(symbol, price, amount, side, ts)
                await asyncio.sleep(0.02)
            except Exception as e:
                await asyncio.sleep(5)

    async def watch_orderbook_stream(self, symbol: str):
        """Continuous L2 orderbook depth snapshot stream."""
        while self.running:
            try:
                ob = await self.exchange.watch_order_book(symbol, limit=20)
                bids = ob.get('bids', [])
                asks = ob.get('asks', [])
                if bids and asks:
                    bid_vol = sum(b[1] for b in bids[:10])
                    ask_vol = sum(a[1] for a in asks[:10])
                    imbalance = bid_vol / ask_vol if ask_vol > 0 else 1.0
                    spread = asks[0][0] - bids[0][0]
                    await self.redis_store.update_orderbook_snapshot(symbol, imbalance, spread, bid_vol, ask_vol)
                await asyncio.sleep(0.05)
            except Exception as e:
                await asyncio.sleep(5)

    async def start_all_streams(self):
        """Launches concurrent background streams for all target assets."""
        tasks = []
        for symbol in ALL_SYMBOLS:
            # 1m and 15m candle streams
            tasks.append(asyncio.create_task(self.watch_ohlcv_stream(symbol, "1m")))
            tasks.append(asyncio.create_task(self.watch_ohlcv_stream(symbol, "15m")))
            # Raw tick & CVD stream
            tasks.append(asyncio.create_task(self.watch_trades_stream(symbol)))
            # L2 Order Book depth stream
            tasks.append(asyncio.create_task(self.watch_orderbook_stream(symbol)))
            
        print(f"[COLLECTOR] Successfully launched {len(tasks)} concurrent async market data streams.")
        await asyncio.gather(*tasks, return_exceptions=True)

    async def close(self):
        self.running = False
        await self.exchange.close()
