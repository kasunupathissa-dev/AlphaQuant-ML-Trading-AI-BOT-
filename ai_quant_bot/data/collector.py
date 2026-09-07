import asyncio
import logging
from typing import List, Callable
import ccxt.pro as ccxtpro
import pandas as pd
from datetime import datetime, timezone
from ai_quant_bot.data.redis_buffer import RedisCandleBuffer
from ai_quant_bot.data.database import AsyncSessionLocal, OHLCVBar
from sqlalchemy.dialects.postgresql import insert

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

class BinanceFuturesCollector:
    """Async WebSocket Market Data Ingestion Engine for Binance Futures (USDT-M)."""

    def __init__(self, symbols: List[str], on_candle_closed: Callable[[str, pd.DataFrame], None]):
        self.symbols = symbols
        self.on_candle_closed = on_candle_closed
        self.exchange = ccxtpro.binance({
            'options': {'defaultType': 'future'},
            'enableRateLimit': True,
        })
        self.redis_buffer = RedisCandleBuffer()
        self.is_running = False
        self.warmed_up = {s: False for s in symbols}

    async def warm_up_redis_buffers(self):
        """Pre-populates Redis buffers with historical 1m candles via REST API."""
        logging.info("[COLLECTOR] Warm-up phase: fetching historical 1m bars...")
        for symbol in self.symbols:
            try:
                # Fetch last 150 historical bars to warm up the feature pipeline
                historical_candles = await self.exchange.fetch_ohlcv(symbol, timeframe='1m', limit=150)
                if not historical_candles:
                    continue
                
                await self.redis_buffer.clear_buffer(symbol)
                for candle in historical_candles:
                    bar_time = pd.to_datetime(candle[0], unit='ms', utc=True)
                    candle_dict = {
                        'timestamp': bar_time.isoformat(),
                        'open': float(candle[1]),
                        'high': float(candle[2]),
                        'low': float(candle[3]),
                        'close': float(candle[4]),
                        'volume': float(candle[5]),
                    }
                    await self.redis_buffer.push_candle(symbol, candle_dict)
                    
                    # Store historical bars in PostgreSQL database as well
                    async with AsyncSessionLocal() as session:
                        stmt = insert(OHLCVBar).values(
                            timestamp=bar_time,
                            symbol=symbol,
                            timeframe='1m',
                            open=candle[1],
                            high=candle[2],
                            low=candle[3],
                            close=candle[4],
                            volume=candle[5]
                        ).on_conflict_do_nothing(index_elements=['symbol', 'timeframe', 'timestamp'])
                        await session.execute(stmt)
                        await session.commit()
                        
                self.warmed_up[symbol] = True
                logging.info(f"[COLLECTOR] Warmed up Redis buffer for {symbol} with {len(historical_candles)} bars.")
            except Exception as e:
                logging.error(f"[ERROR] Failed to warm up {symbol}: {e}")

    async def _save_candle_to_db(self, symbol: str, candle: dict):
        """Saves a single candle asynchronously to PostgreSQL."""
        try:
            async with AsyncSessionLocal() as session:
                stmt = insert(OHLCVBar).values(
                    timestamp=pd.to_datetime(candle['timestamp']),
                    symbol=symbol,
                    timeframe='1m',
                    open=candle['open'],
                    high=candle['high'],
                    low=candle['low'],
                    close=candle['close'],
                    volume=candle['volume']
                ).on_conflict_do_nothing(index_elements=['symbol', 'timeframe', 'timestamp'])
                await session.execute(stmt)
                await session.commit()
        except Exception as e:
            logging.error(f"[ERROR] Failed to write candle to DB for {symbol}: {e}")

    async def _watch_ohlcv_stream(self, symbol: str):
        """Streams 1m candles and handles completed candle transitions."""
        last_timestamp = None
        running_bar = None
        while self.is_running:
            try:
                ohlcv = await self.exchange.watch_ohlcv(symbol, timeframe='1m')
                if not ohlcv or len(ohlcv) == 0:
                    continue
                
                current_bar = ohlcv[-1]
                bar_time_ms = current_bar[0]
                
                # Closed candle detection
                if last_timestamp is not None and bar_time_ms > last_timestamp:
                    closed_bar = running_bar if running_bar is not None else (ohlcv[-2] if len(ohlcv) >= 2 else current_bar)
                    closed_time = pd.to_datetime(closed_bar[0], unit='ms', utc=True)
                    
                    candle_dict = {
                        'timestamp': closed_time.isoformat(),
                        'open': float(closed_bar[1]),
                        'high': float(closed_bar[2]),
                        'low': float(closed_bar[3]),
                        'close': float(closed_bar[4]),
                        'volume': float(closed_bar[5]),
                    }
                    
                    # Push to Redis buffer and save to database
                    await self.redis_buffer.push_candle(symbol, candle_dict)
                    asyncio.create_task(self._save_candle_to_db(symbol, candle_dict))
                    
                    # Read updated sliding window DataFrame and fire candle callback
                    df_buffer = await self.redis_buffer.get_candles(symbol, limit=300)
                    if not df_buffer.empty:
                        asyncio.create_task(self.on_candle_closed(symbol, df_buffer))
                        
                last_timestamp = bar_time_ms
                running_bar = current_bar

            except Exception as e:
                logging.error(f"Error in OHLCV stream for {symbol}: {e}")
                await asyncio.sleep(2)

    async def _watch_trades_stream(self, symbol: str):
        """Streams real-time trades (can hook CVD delta accumulation here)."""
        while self.is_running:
            try:
                await self.exchange.watch_trades(symbol)
            except Exception as e:
                logging.error(f"Error in Trade stream for {symbol}: {e}")
                await asyncio.sleep(2)

    async def start(self):
        """Starts asynchronous stream workers for all monitored symbols."""
        self.is_running = True
        
        # Warm up the buffer from historical bars first
        await self.warm_up_redis_buffers()
        
        logging.info(f"Connecting to Binance Futures WebSockets for: {self.symbols}")
        tasks = []
        for symbol in self.symbols:
            tasks.append(asyncio.create_task(self._watch_ohlcv_stream(symbol)))
            tasks.append(asyncio.create_task(self._watch_trades_stream(symbol)))
            
        await asyncio.gather(*tasks)

    async def stop(self):
        """Gracefully closes exchange and Redis connections."""
        self.is_running = False
        await self.exchange.close()
        await self.redis_buffer.close()
        logging.info("WebSocket connections and Redis clients closed cleanly.")
