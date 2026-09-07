import asyncio
import aiohttp
import xml.etree.ElementTree as ET
import re
from datetime import datetime, timezone
from unified_quant_bot.data.database_schema import AsyncSessionLocal, MacroSentimentMetric

class MacroSentimentEngine:
    """Ingests Fear & Greed, BTC Dominance, CoinGecko fundamentals, and crypto news headlines."""

    def __init__(self):
        self.fear_and_greed_score = 50
        self.fear_and_greed_sentiment = "Neutral"
        self.btc_dominance_pct = 56.5
        self.total_crypto_market_cap_usd = 2.4e12
        self.news_sentiment_score = 0.0 # -1.0 to +1.0
        self.latest_headline = "Market in balanced equilibrium"

    async def fetch_fear_and_greed(self, session: aiohttp.ClientSession):
        """Fetches Fear & Greed Index from alternative.me API."""
        try:
            url = "https://api.alternative.me/fng/?limit=1"
            async with session.get(url, timeout=10) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    item = data['data'][0]
                    self.fear_and_greed_score = int(item['value'])
                    self.fear_and_greed_sentiment = item['value_classification']
        except Exception as e:
            pass

    async def fetch_coingecko_global(self, session: aiohttp.ClientSession):
        """Fetches Global Market Cap and BTC Dominance from CoinGecko."""
        try:
            url = "https://api.coingecko.com/api/v3/global"
            async with session.get(url, timeout=10) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    market_data = data.get('data', {})
                    self.btc_dominance_pct = float(market_data.get('market_cap_percentage', {}).get('btc', 56.5))
                    self.total_crypto_market_cap_usd = float(market_data.get('total_market_cap', {}).get('usd', 2.4e12))
        except Exception as e:
            pass

    async def fetch_news_sentiment(self, session: aiohttp.ClientSession):
        """Ingests CoinDesk & Cointelegraph RSS feeds and computes keyword sentiment score."""
        rss_urls = [
            "https://www.coindesk.com/arc/outboundfeeds/rss/",
            "https://cointelegraph.com/rss"
        ]
        
        bullish_keywords = ["surge", "rally", "breakout", "bullish", "approval", "high", "gain", "partnership", "inflow"]
        bearish_keywords = ["crash", "drop", "dump", "bearish", "hack", "exploit", "sec", "ban", "outflow", "lawsuit"]
        
        headlines = []
        for url in rss_urls:
            try:
                async with session.get(url, timeout=10) as resp:
                    if resp.status == 200:
                        text = await resp.text()
                        root = ET.fromstring(text)
                        for item in root.findall('.//item/title')[:5]:
                            if item.text:
                                headlines.append(item.text.strip())
            except Exception:
                continue

        if headlines:
            self.latest_headline = headlines[0]
            score = 0
            for h in headlines:
                h_lower = h.lower()
                for b in bullish_keywords:
                    if re.search(r'\b' + b + r'\b', h_lower):
                        score += 1
                for b in bearish_keywords:
                    if re.search(r'\b' + b + r'\b', h_lower):
                        score -= 1
                        
            # Normalize to range [-1.0, 1.0]
            self.news_sentiment_score = max(-1.0, min(1.0, score / (len(headlines) * 2.0)))

    async def update_all_macro_metrics(self):
        """Runs periodic fetch and commits snapshot to PostgreSQL."""
        async with aiohttp.ClientSession() as session:
            await asyncio.gather(
                self.fetch_fear_and_greed(session),
                self.fetch_coingecko_global(session),
                self.fetch_news_sentiment(session),
                return_exceptions=True
            )
            
        try:
            async with AsyncSessionLocal() as db:
                metric = MacroSentimentMetric(
                    fear_and_greed_score=self.fear_and_greed_score,
                    fear_and_greed_sentiment=self.fear_and_greed_sentiment,
                    btc_dominance_pct=self.btc_dominance_pct,
                    total_crypto_market_cap_usd=self.total_crypto_market_cap_usd,
                    news_sentiment_score=self.news_sentiment_score,
                    latest_news_headline=self.latest_headline
                )
                db.add(metric)
                await db.commit()
        except Exception as e:
            pass

    def get_macro_snapshot(self) -> dict:
        """Returns in-memory macro sentiment snapshot."""
        return {
            "fear_and_greed_score": self.fear_and_greed_score,
            "fear_and_greed_sentiment": self.fear_and_greed_sentiment,
            "btc_dominance_pct": self.btc_dominance_pct,
            "total_crypto_market_cap_usd": self.total_crypto_market_cap_usd,
            "news_sentiment_score": self.news_sentiment_score,
            "latest_headline": self.latest_headline
        }
