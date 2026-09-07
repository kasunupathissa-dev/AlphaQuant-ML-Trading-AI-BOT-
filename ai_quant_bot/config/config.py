import os

# --- Binance Futures API Configuration ---
BINANCE_API_KEY = os.getenv("BINANCE_API_KEY", "")
BINANCE_API_SECRET = os.getenv("BINANCE_API_SECRET", "")
USE_TESTNET = os.getenv("USE_TESTNET", "False").lower() in ("true", "1", "yes")

# --- Telegram Notifications ---
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

# --- Database & Cache Configurations ---
# Connection details for TimescaleDB/Postgres and Redis
DB_PASS = os.getenv("DB_PASS", "")
DB_URL = os.getenv("DB_URL", f"postgresql+asyncpg://kazzr:{DB_PASS}@localhost/ai_quant_db" if DB_PASS else "postgresql+asyncpg://kazzr@localhost/ai_quant_db")
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")


# --- Quantitative Strategy parameters ---
RISK_PER_TRADE_PCT = 0.01          # Risk 1% of total equity per setup
MIN_REWARD_RISK_RATIO = 1.5         # Minimum 1:1.5 Risk-to-Reward Ratio
MAX_ACTIVE_TRADES = 3               # Max concurrent open trade brackets

# Target Assets to monitor (excluding BTC for small wallet margin safety)
TARGET_SYMBOLS = [
    "SOL/USDT", "NEAR/USDT", "SUI/USDT", "HBAR/USDT",
    "XRP/USDT", "LINK/USDT", "AVAX/USDT", "DOGE/USDT", "DOT/USDT"
]

# --- Dry-Run / Paper Trading Simulation ---
SIMULATION_MODE = os.getenv("SIMULATION_MODE", "True").lower() in ("true", "1", "yes")

# --- Log Rotation Constraints ---
LOG_MAX_BYTES = 5 * 1024 * 1024  # 5MB per log file
LOG_ROTATION_BACKUPS = 5         # Keep up to 5 historical backups
