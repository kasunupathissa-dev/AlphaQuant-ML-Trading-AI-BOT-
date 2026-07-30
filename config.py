# AlphaQuant V8 Configuration File

# --- System Settings ---
LOG_FILE = "trading_log_v8.csv"
STATE_FILE = "live_engine_state.json"
LIVE_TRADING_ENABLED = False

# --- Timeframe Settings ---
TIMEFRAME = "15m"  # "15m" or "1h"
INFERENCE_INTERVAL_SECONDS = 900  # 15 minutes (900s) for 15m, 3600s for 1h

# --- Indicator Settings (Auto-scaled) ---
if TIMEFRAME == "15m":
    EMA_FAST_PERIOD = 200            # Matches the temporal scale of 1H EMA-50 (~50 hours)
    EMA_SLOW_PERIOD = 800            # Matches the temporal scale of 1H EMA-200 (~200 hours)
    ATR_PERIOD = 56                  # Smooths out noise for the shorter timeframe
    BARRIER_TIME_LIMIT_HOURS = 24    # Equivalent to 96 bars on 15M (lookahead horizon)
else:
    EMA_FAST_PERIOD = 50
    EMA_SLOW_PERIOD = 200
    ATR_PERIOD = 14
    BARRIER_TIME_LIMIT_HOURS = 24

# --- Target Assets ---
TARGET_ASSETS = [
    "BTC/USDT", "ETH/USDT", "SOL/USDT", "BNB/USDT", "ADA/USDT", 
    "XRP/USDT", "LINK/USDT", "AVAX/USDT", "DOGE/USDT", "DOT/USDT"
]

# --- ML Model & Trading Parameters ---
# 🟢 V8.5 Upgrade: System timezone synchronization & estimated transaction fee percentage
TIMEZONE = "Europe/Stockholm"
ESTIMATED_FEE_PCT = 0.0008

# 🟢 V8.5 Upgrade: Direction-specific confidence thresholds
LONG_CONFIDENCE_THRESHOLD = 65.0
SHORT_CONFIDENCE_THRESHOLD = 60.0  

ATR_STOP_LOSS_MULTIPLIER = 1.0     # Optimized baseline for SL
ATR_TAKE_PROFIT_MULTIPLIER = 1.5    # Optimized baseline for TP
MAX_PRICE_DEVIATION_PCT = 0.005    # Max price deviation (0.5%) to prevent chasing extended entries
