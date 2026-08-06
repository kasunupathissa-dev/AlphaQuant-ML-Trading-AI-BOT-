import os

# AlphaQuant V8 Configuration File

# --- System Settings ---
LOG_FILE = "trading_log_v8.csv"
STATE_FILE = "live_engine_state.json"
LIVE_TRADING_ENABLED = False

# --- Binance Futures Testnet (Demo Trading) Settings ---
BINANCE_API_KEY = os.getenv("BINANCE_API_KEY", "X0djHJJWnlj5ynaZvVKdiq0krjTVr9i5m42f0YS9WJaMr7tIZfKTahj1pAStliSc")
BINANCE_API_SECRET = os.getenv("BINANCE_API_SECRET", "pG1xQQLlZDWiImnMJnWCKX9MdvtYL1kiS1IG5d2HHqDbsPDSkGKMBVqEvD1MoMjF")
USE_TESTNET = os.getenv("USE_TESTNET", "True").lower() in ("true", "1", "yes")

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
    "BTC/USDT", "SOL/USDT", "NEAR/USDT", "SUI/USDT", "HBAR/USDT",
    "XRP/USDT", "LINK/USDT", "AVAX/USDT", "DOGE/USDT", "DOT/USDT"
]

# --- ML Model & Trading Parameters ---
# 🟢 V8.5 Upgrade: System timezone synchronization & estimated transaction fee percentage
TIMEZONE = "Europe/Stockholm"
ESTIMATED_FEE_PCT = 0.0008
RISK_PER_TRADE_USD = 5.0
MAX_ACTIVE_TRADES = 3
MAX_POSITION_SIZE_USD = 500.0

# 🟢 V8.5 Upgrade: Direction-specific confidence thresholds
LONG_CONFIDENCE_THRESHOLD = 55.0
SHORT_CONFIDENCE_THRESHOLD = 53.0  

ATR_STOP_LOSS_MULTIPLIER = 1.0     # Optimized baseline for SL
ATR_TAKE_PROFIT_MULTIPLIER = 1.5    # Optimized baseline for TP
MAX_PRICE_DEVIATION_PCT = 0.005    # Max price deviation (0.5%) to prevent chasing extended entries

# --- Suggestion 3: Asymmetric Risk Scaling per Asset Category ---
# Maps each asset to a risk multiplier applied against RISK_PER_TRADE_USD.
# High-alpha coins with strong directional moves get full risk.
# Institutional/anchored coins with tighter ranges get standard risk.
# Micro/new coins get 75% risk as a precaution.
ASSET_RISK_TIERS = {
    # High Alpha — Strong directional, over-filtered historically
    "SOL/USDT":  1.00,
    "SUI/USDT":  1.00,
    "AVAX/USDT": 1.00,
    "DOGE/USDT": 1.00,
    "XRP/USDT":  1.00,
    "HBAR/USDT": 1.00,
    # Institutional Anchors — Range/correlated, standard risk
    "BTC/USDT":  1.00,
    "LINK/USDT": 1.00,
    "DOT/USDT":  1.00,
    # Micro / New — Lower conviction, reduced risk
    "NEAR/USDT": 0.75,
}

# Per-asset threshold overrides — merged with direction-specific base thresholds.
# High-alpha assets get a -5% lower gate to reduce over-filtering.
# Institutional anchors stay at default. Leave empty to use base thresholds.
ASSET_SPECIFIC_THRESHOLDS = {
    "SOL/USDT":  50.0,
    "SUI/USDT":  50.0,
    "AVAX/USDT": 50.0,
    "DOGE/USDT": 50.0,
    "XRP/USDT":  50.0,
    "HBAR/USDT": 50.0,
}

# --- Dynamic Filters (Time, Events, & Multi-Timeframe) ---
# List of local Stockholm hours (0-23) during which signal generation is disabled.
# By default, we block late-night/early-morning quiet periods: 23:00 to 02:00 Stockholm time (noise/whipsaw hours).
BLOCKED_HOURS = []

# Enable/Disable economic event blockout filter
NEWS_BLOCKOUT_ENABLED = True
# Block signals X minutes before and after a high-impact news event
NEWS_BLOCKOUT_WINDOW_MINUTES = 60

# Enable/Disable 1H trend alignment check for 15M signals
MULTITIMEFRAME_VETO_ENABLED = True

# Enable/Disable market regime adaptive confidence threshold adjustments
REGIME_ADAPTIVE_THRESHOLD_ENABLED = True

