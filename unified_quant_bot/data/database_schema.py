import asyncio
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy import Column, String, Float, DateTime, Integer, BigInteger, Text, func
from unified_quant_bot.config.config import DB_USER, DB_PASS, DB_HOST, DB_PORT, DB_NAME

Base = declarative_base()

class OHLCVBar(Base):
    """Stores normalized multi-timeframe candlestick data."""
    __tablename__ = 'ohlcv_bars'
    timestamp = Column(DateTime(timezone=True), primary_key=True)
    symbol = Column(String(20), primary_key=True)
    timeframe = Column(String(10), primary_key=True, default='1m')
    open = Column(Float, nullable=False)
    high = Column(Float, nullable=False)
    low = Column(Float, nullable=False)
    close = Column(Float, nullable=False)
    volume = Column(Float, nullable=False)

class LiquidationEvent(Base):
    """Captures real-time forced liquidation cascade events."""
    __tablename__ = 'liquidation_events'
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    symbol = Column(String(20), nullable=False, index=True)
    side = Column(String(10), nullable=False) # LONG or SHORT (liquidated position side)
    quantity = Column(Float, nullable=False)
    price = Column(Float, nullable=False)
    usd_value = Column(Float, nullable=False)

class DerivativesMetric(Base):
    """Tracks funding rate, open interest, and long/short ratio history."""
    __tablename__ = 'derivatives_metrics'
    timestamp = Column(DateTime(timezone=True), primary_key=True)
    symbol = Column(String(20), primary_key=True)
    funding_rate = Column(Float, nullable=True)
    funding_zscore = Column(Float, nullable=True)
    open_interest = Column(Float, nullable=True)
    oi_zscore = Column(Float, nullable=True)
    long_short_ratio = Column(Float, nullable=True)

class MacroSentimentMetric(Base):
    """Stores global macroeconomic sentiment (Fear & Greed, BTC Dominance, News score)."""
    __tablename__ = 'macro_sentiment_metrics'
    timestamp = Column(DateTime(timezone=True), primary_key=True, server_default=func.now())
    fear_and_greed_score = Column(Integer, nullable=True)
    fear_and_greed_sentiment = Column(String(30), nullable=True)
    btc_dominance_pct = Column(Float, nullable=True)
    total_crypto_market_cap_usd = Column(Float, nullable=True)
    news_sentiment_score = Column(Float, nullable=True)
    latest_news_headline = Column(Text, nullable=True)

class SignalRejection(Base):
    """Audit table capturing filtered candidate setups for missed EV analysis."""
    __tablename__ = 'signal_rejections'
    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime(timezone=True), server_default=func.now())
    symbol = Column(String(20), nullable=False)
    direction = Column(String(10), nullable=False)
    strategy = Column(String(50), nullable=True)
    win_prob = Column(Float, nullable=False)
    threshold = Column(Float, nullable=False)
    regime = Column(String(20), nullable=True)
    rejection_reason = Column(String(50), nullable=False)
    entry_price = Column(Float, nullable=True)
    sl_price = Column(Float, nullable=True)
    tp_price = Column(Float, nullable=True)
    outcome_status = Column(String(20), default='PENDING')
    missed_pnl = Column(Float, default=0.0)

DATABASE_URL = f"postgresql+asyncpg://{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

engine = create_async_engine(DATABASE_URL, echo=False, pool_size=10, max_overflow=20)
AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

async def init_unified_db():
    """Initializes PostgreSQL schema and tables."""
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        print("[DATABASE] Unified PostgreSQL / TimescaleDB schema initialized.")
    except Exception as e:
        print(f"[DATABASE] Schema initialization warning: {e}")
