import os
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# Operating Mode Flags
USE_TESTNET = os.getenv("USE_TESTNET", "True").lower() in ("true", "1", "yes")
SIMULATION_MODE = os.getenv("SIMULATION_MODE", "True").lower() in ("true", "1", "yes")
SIGNAL_ONLY = os.getenv("SIGNAL_ONLY", "False").lower() in ("true", "1", "yes")

# Binance API Credentials
BINANCE_API_KEY = os.getenv("BINANCE_API_KEY", "")
BINANCE_API_SECRET = os.getenv("BINANCE_API_SECRET", "")

# Telegram Alerting
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

# Database Configuration (PostgreSQL / TimescaleDB)
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = int(os.getenv("DB_PORT", "5432"))
DB_NAME = os.getenv("DB_NAME", "ai_quant_db")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASS = os.getenv("DB_PASS", "")

# Redis Configuration
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))

# Target Tradable Assets (Institutional Grade High-Performing Universe)
TARGET_SYMBOLS = [
    "BTC/USDT",
    "ETH/USDT",
    "SOL/USDT",
    "LINK/USDT",
    "SUI/USDT",
    "AVAX/USDT"
]

# Macro Pinned Symbols for Regime & Correlation Analysis
MACRO_SYMBOLS = [
    "BTC/USDT",
    "ETH/USDT"
]

ALL_SYMBOLS = list(set(TARGET_SYMBOLS + MACRO_SYMBOLS))

# Multi-Timeframe List
TIMEFRAMES = ["1m", "5m", "15m", "1h"]

# Risk & Governance Limits
MAX_RISK_PER_TRADE_PCT = float(os.getenv("MAX_RISK_PER_TRADE_PCT", "1.0"))
MAX_CONCURRENT_POSITIONS = int(os.getenv("MAX_CONCURRENT_POSITIONS", "3"))
DAILY_DRAWDOWN_LIMIT_PCT = float(os.getenv("DAILY_DRAWDOWN_LIMIT_PCT", "2.5"))
MAX_SPREAD_PCT = float(os.getenv("MAX_SPREAD_PCT", "0.15"))
MIN_RRR = float(os.getenv("MIN_RRR", "2.0"))
STALE_FEED_TIMEOUT_SECONDS = int(os.getenv("STALE_FEED_TIMEOUT_SECONDS", "120"))

# Base Paths
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPO_ROOT = os.path.dirname(BASE_DIR)
ASSETS_YAML_PATH = os.path.join(BASE_DIR, "config", "assets.yaml")
TRADING_LOG_PAPER_PATH = os.path.join(REPO_ROOT, "trading_log_paper.csv")
