# AlphaQuant SCALPER_HUNT Configuration File

# --- System Settings ---
LOG_FILE = "trading_log_scalper.csv"
STATE_FILE = "live_engine_state_scalper.json"
LIVE_TRADING_ENABLED = False

# --- Binance Futures Testnet (Demo Trading) Settings ---
BINANCE_API_KEY = "X0djHJJWnlj5ynaZvVKdiq0krjTVr9i5m42f0YS9WJaMr7tIZfKTahj1pAStliSc"
BINANCE_API_SECRET = "pG1xQQLlZDWiImnMJnWCKX9MdvtYL1kiS1IG5d2HHqDbsPDSkGKMBVqEvD1MoMjF"
USE_TESTNET = True

# --- Timeframe Settings ---
TIMEFRAME = "15m"  # 15M target
INFERENCE_INTERVAL_SECONDS = 900  # 15 minutes (900s)

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
    "BTC/USDT", "ETH/USDT", "SOL/USDT", "NEAR/USDT", "1000PEPE/USDT", 
    "XRP/USDT", "LINK/USDT", "AVAX/USDT", "DOGE/USDT", "DOT/USDT"
]

# --- ML Model & Scalping Parameters ---
TIMEZONE = "Europe/Stockholm"
ESTIMATED_FEE_PCT = 0.0008
RISK_PER_TRADE_USD = 5.0
MAX_ACTIVE_TRADES = 3
MAX_POSITION_SIZE_USD = 500.0

# 🚀 Scalping Thresholds (Lowered for frequent trading)
LONG_CONFIDENCE_THRESHOLD = 51.5
SHORT_CONFIDENCE_THRESHOLD = 49.5  

# 🚀 Tight TP/SL (Scalper exits)
ATR_STOP_LOSS_MULTIPLIER = 0.8
ATR_TAKE_PROFIT_MULTIPLIER = 0.8
MAX_PRICE_DEVIATION_PCT = 0.005

# --- Dynamic Filters ---
# Block late-night Stockholm hours
BLOCKED_HOURS = []

# Enable/Disable economic event blockout filter
NEWS_BLOCKOUT_ENABLED = True
NEWS_BLOCKOUT_WINDOW_MINUTES = 60

# 🚀 Veto Disabled for active pullback/counter-trend scalping
MULTITIMEFRAME_VETO_ENABLED = False

# Enable/Disable market regime adaptive confidence threshold adjustments
REGIME_ADAPTIVE_THRESHOLD_ENABLED = False
