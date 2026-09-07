import redis.asyncio as redis
import json
import pandas as pd
from typing import List, Dict, Optional
from unified_quant_bot.config.config import REDIS_HOST, REDIS_PORT

class RedisStore:
    """Manages high-speed circular buffers for candles, tick trades, CVD, and L2 depth."""
    
    def __init__(self, host: str = REDIS_HOST, port: int = REDIS_PORT, db: int = 0):
        self.redis_client = redis.Redis(host=host, port=port, db=db, decode_responses=True)
        self.candle_capacity = 500
        self.trade_capacity = 1000

    async def append_candle(self, symbol: str, timeframe: str, bar: dict):
        """Appends closed candlestick to circular sliding buffer."""
        key = f"candles:{symbol}:{timeframe}"
        raw = json.dumps(bar)
        async with self.redis_client.pipeline(transaction=True) as pipe:
            pipe.rpush(key, raw)
            pipe.ltrim(key, -self.candle_capacity, -1)
            await pipe.execute()

    async def get_candles_dataframe(self, symbol: str, timeframe: str = "1m") -> pd.DataFrame:
        """Retrieves in-memory candlestick buffer as Pandas DataFrame."""
        key = f"candles:{symbol}:{timeframe}"
        items = await self.redis_client.lrange(key, 0, -1)
        if not items:
            return pd.DataFrame()
            
        data = [json.loads(item) for item in items]
        df = pd.DataFrame(data)
        if 'timestamp' in df.columns:
            df['timestamp'] = pd.to_numeric(df['timestamp'], errors='coerce')
        for col in ['open', 'high', 'low', 'close', 'volume']:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce')
        return df

    async def update_orderbook_snapshot(self, symbol: str, bid_ask_imbalance: float, spread: float, top_bid_vol: float, top_ask_vol: float):
        """Stores latest L2 orderbook snapshot."""
        key = f"orderbook:{symbol}"
        payload = {
            "imbalance": bid_ask_imbalance,
            "spread": spread,
            "top_bid_vol": top_bid_vol,
            "top_ask_vol": top_ask_vol
        }
        await self.redis_client.set(key, json.dumps(payload), ex=300)

    async def get_orderbook_snapshot(self, symbol: str) -> dict:
        """Retrieves latest orderbook snapshot."""
        key = f"orderbook:{symbol}"
        raw = await self.redis_client.get(key)
        if not raw:
            return {"imbalance": 1.0, "spread": 0.0, "top_bid_vol": 0.0, "top_ask_vol": 0.0}
        return json.loads(raw)

    async def append_tick_trade(self, symbol: str, price: float, amount: float, side: str, timestamp_ms: int):
        """Stores sub-second trade execution and updates 1m CVD."""
        key = f"ticks:{symbol}"
        delta = amount if side == "buy" else -amount
        raw = json.dumps({"p": price, "q": amount, "s": side, "d": delta, "t": timestamp_ms})
        async with self.redis_client.pipeline(transaction=True) as pipe:
            pipe.rpush(key, raw)
            pipe.ltrim(key, -self.trade_capacity, -1)
            # Update running 1m CVD
            pipe.incrbyfloat(f"cvd:{symbol}", delta)
            await pipe.execute()

    async def get_cvd(self, symbol: str) -> float:
        """Retrieves running Cumulative Volume Delta."""
        raw = await self.redis_client.get(f"cvd:{symbol}")
        return float(raw) if raw else 0.0

    async def close(self):
        """Closes Redis connection."""
        await self.redis_client.aclose()
