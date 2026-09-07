import json
import pandas as pd
from redis.asyncio import Redis
from ai_quant_bot.config.config import REDIS_URL

class RedisCandleBuffer:
    """Async Redis Ring Buffer for real-time OHLCV candles."""
    
    def __init__(self):
        self.client = Redis.from_url(REDIS_URL, decode_responses=True)
        
    async def push_candle(self, symbol: str, candle: dict, max_len: int = 500):
        """Pushes a candle to the list and prunes it to max_len."""
        key = f"candles:{symbol}"
        # Serialize datetime object if present
        if isinstance(candle.get('timestamp'), pd.Timestamp):
            candle = candle.copy()
            candle['timestamp'] = candle['timestamp'].isoformat()
            
        data = json.dumps(candle)
        async with self.client.pipeline(transaction=True) as pipe:
            pipe.rpush(key, data)
            pipe.ltrim(key, -max_len, -1)
            await pipe.execute()

    async def get_candles(self, symbol: str, limit: int = 300) -> pd.DataFrame:
        """Fetches the last N candles and returns a pandas DataFrame."""
        key = f"candles:{symbol}"
        raw_items = await self.client.lrange(key, -limit, -1)
        if not raw_items:
            return pd.DataFrame()
            
        candles = []
        for item in raw_items:
            try:
                c = json.loads(item)
                if 'timestamp' in c:
                    c['timestamp'] = pd.to_datetime(c['timestamp'])
                candles.append(c)
            except Exception:
                continue
                
        df = pd.DataFrame(candles)
        if not df.empty and 'timestamp' in df.columns:
            df = df.set_index('timestamp')
        return df

    async def clear_buffer(self, symbol: str):
        """Clears the buffer key for the symbol."""
        key = f"candles:{symbol}"
        await self.client.delete(key)

    async def close(self):
        """Closes the Redis client connection."""
        await self.client.close()
