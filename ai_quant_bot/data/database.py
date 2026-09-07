import asyncio
from datetime import datetime
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy import Column, Integer, BigInteger, String, Numeric, DateTime, Index
from ai_quant_bot.config.config import DB_URL

Base = declarative_base()

class OHLCVBar(Base):
    __tablename__ = "ohlcv_bars"
    
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime(timezone=True), nullable=False)
    symbol = Column(String(20), nullable=False)
    timeframe = Column(String(5), nullable=False)
    open = Column(Numeric(18, 8), nullable=False)
    high = Column(Numeric(18, 8), nullable=False)
    low = Column(Numeric(18, 8), nullable=False)
    close = Column(Numeric(18, 8), nullable=False)
    volume = Column(Numeric(20, 8), nullable=False)

    __table_args__ = (
        Index("idx_ohlcv_symbol_timeframe_timestamp", "symbol", "timeframe", "timestamp", unique=True),
    )

class FundingRate(Base):
    __tablename__ = "funding_rates"
    
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime(timezone=True), nullable=False)
    symbol = Column(String(20), nullable=False)
    funding_rate = Column(Numeric(12, 8), nullable=False)

    __table_args__ = (
        Index("idx_funding_symbol_timestamp", "symbol", "timestamp", unique=True),
    )

class SignalRejection(Base):
    __tablename__ = "signal_rejections"
    
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    symbol = Column(String(20), nullable=False)
    direction = Column(String(10), nullable=False)
    win_prob = Column(Numeric(6, 2), nullable=False)
    threshold = Column(Numeric(6, 2), nullable=False)
    regime = Column(String(20), nullable=False)
    reason = Column(String(100), nullable=False)
    entry_price = Column(Numeric(18, 8), nullable=True)
    sl_price = Column(Numeric(18, 8), nullable=True)
    tp_price = Column(Numeric(18, 8), nullable=True)
    status = Column(String(20), server_default="PENDING", default="PENDING", nullable=False)

# Async engine setup
engine = create_async_engine(DB_URL, echo=False, pool_size=10, max_overflow=20)
AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

async def init_db():
    """Initializes the database tables."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("[DATABASE] PostgreSQL schema initialized successfully.")

async def get_db_session() -> AsyncSession:
    """Dependency helper for database session."""
    async with AsyncSessionLocal() as session:
        yield session
