import os

# AlphaQuant SCALPER_HUNT Configuration File

# --- System Settings ---
LOG_FILE = "trading_log_scalper.csv"
STATE_FILE = "live_engine_state_scalper.json"
LIVE_TRADING_ENABLED = True

# --- Binance Futures Testnet (Demo Trading) Settings ---
BINANCE_API_KEY = os.getenv("BINANCE_API_KEY", "")
BINANCE_API_SECRET = os.getenv("BINANCE_API_SECRET", "")
USE_TESTNET = os.getenv("USE_TESTNET", "True").lower() in ("true", "1", "yes")

# Validate live credentials on import if live trading is active
if not USE_TESTNET:
    if not BINANCE_API_KEY or not BINANCE_API_SECRET:
        raise ValueError("FATAL: Live trading requested (USE_TESTNET=False) but BINANCE_API_KEY/SECRET are not set in environment!")

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
    "SOL/USDT", "NEAR/USDT", "SUI/USDT", "HBAR/USDT",
    "XRP/USDT", "LINK/USDT", "AVAX/USDT", "DOGE/USDT", "DOT/USDT"
]

# --- ML Model & Scalping Parameters ---
TIMEZONE = "Europe/Stockholm"
ESTIMATED_FEE_PCT = 0.0008
INITIAL_BALANCE = 10.49
RISK_PER_TRADE_USD = 0.2
MAX_ACTIVE_TRADES = 3
MAX_POSITION_SIZE_USD = 50.0

# 🚀 Scalping Thresholds (Equalized and raised for safety)
LONG_CONFIDENCE_THRESHOLD = 52.0
SHORT_CONFIDENCE_THRESHOLD = 52.0

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
REGIME_ADAPTIVE_THRESHOLD_ENABLED = True

ASSET_RISK_TIERS = {
    "SOL/USDT":  1.00,
    "SUI/USDT":  1.00,
    "AVAX/USDT": 1.00,
    "DOGE/USDT": 1.00,
    "XRP/USDT":  1.00,
    "HBAR/USDT": 1.00,
    "LINK/USDT": 1.00,
    "DOT/USDT":  1.00,
    "NEAR/USDT": 1.00,
}

# --- Dynamic Overrides from Auto-Tuner ---
import json
overrides_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "dynamic_overrides.json")
if os.path.exists(overrides_path):
    try:
        with open(overrides_path, "r") as f:
            overrides = json.load(f)
            if "ASSET_RISK_TIERS" in overrides:
                for k, v in overrides["ASSET_RISK_TIERS"].items():
                    ASSET_RISK_TIERS[k] = v
            if "EXCLUDED_ASSETS" in overrides:
                for asset in overrides["EXCLUDED_ASSETS"]:
                    if asset in TARGET_ASSETS:
                        TARGET_ASSETS.remove(asset)
    except Exception as e:
        print(f"[WARNING] Failed to load dynamic overrides in config: {e}")

