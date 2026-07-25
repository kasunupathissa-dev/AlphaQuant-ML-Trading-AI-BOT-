# AlphaQuant V7 Configuration File

# --- System Settings ---
LOG_FILE = "trading_log_v7.csv"
STATE_FILE = "live_engine_state.json"
LIVE_TRADING_ENABLED = False

# --- Target Assets ---
TARGET_ASSETS = [
    "BTC/USDT", "ETH/USDT", "SOL/USDT", "BNB/USDT", "ADA/USDT", 
    "XRP/USDT", "LINK/USDT", "AVAX/USDT", "DOGE/USDT", "DOT/USDT"
]

# --- Telegram Notifications ---
# These should be set as environment variables for security
# TELEGRAM_TOKEN = "YOUR_TELEGRAM_TOKEN"
# TELEGRAM_CHAT_ID = "YOUR_TELEGRAM_CHAT_ID"

# --- ML Model & Trading Parameters ---
# This section will be expanded as we implement the "Shotgun" architecture
# and centralize more parameters.
MODEL_CONFIDENCE_THRESHOLD = 55.0 # Example: Minimum probability to consider a trade
ATR_STOP_LOSS_MULTIPLIER = 1.0
ATR_TAKE_PROFIT_MULTIPLIER = 1.5
INFERENCE_INTERVAL_SECONDS = 3600 # Production: 1 Hour (3,600s)

