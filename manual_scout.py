"""
AlphaQuant V8.2 — Manual Scalping Intelligence Scout
=====================================================
A standalone read-only market scanner. No trades are placed.
Sends a rich Telegram insight card every SCOUT_INTERVAL_SECONDS
for each asset that has a detectable bias (LONG, SHORT, or flags
neutral coins for avoidance).

Operator can also trigger an on-demand scan by sending /scan to
the Telegram bot.

Run as a separate systemd service: aq-scout.service
"""

import asyncio
import ccxt
import ccxt.pro as ccxtpro
import joblib
import json
import numpy as np
import os
import pandas as pd
import requests
import sys
import time
from datetime import datetime, timezone

# Path setup
sys.path.append("/home/kasun/repository/AlphaQuant-ML-Trading-AI-BOT-")
sys.path.append("c:/cry_agent/v_4_AQ_AI")

import config
from feature_library import calculate_features_for_shotgun

# Sklearn imports for joblib reconstruction
from sklearn.base import BaseEstimator, ClassifierMixin, clone
from sklearn.isotonic import IsotonicRegression
from sklearn.model_selection import cross_val_predict

class ManualCalibratedClassifier(BaseEstimator, ClassifierMixin):
    def __init__(self, estimator, cv=3):
        self.estimator = estimator
        self.cv = cv
        
    def fit(self, X, y, sample_weight=None):
        self.classes_ = np.unique(y)
        n_classes = len(self.classes_)
        
        fit_params = {}
        if sample_weight is not None:
            fit_params['sample_weight'] = sample_weight
            
        this_estimator = clone(self.estimator)
        oof_probs = cross_val_predict(
            this_estimator, X, y, cv=self.cv,
            method='predict_proba', params=fit_params
        )
        
        self.estimator_ = clone(self.estimator)
        if sample_weight is not None:
            self.estimator_.fit(X, y, sample_weight=sample_weight)
        else:
            self.estimator_.fit(X, y)
            
        self.calibrators_ = []
        for i, c in enumerate(self.classes_):
            y_bin = (y == c).astype(int)
            calibrator = IsotonicRegression(out_of_bounds='clip')
            calibrator.fit(oof_probs[:, i], y_bin)
            self.calibrators_.append(calibrator)
            
        return self

    def predict_proba(self, X):
        raw_probs = self.estimator_.predict_proba(X)
        calibrated_probs = np.zeros_like(raw_probs)
        
        for i, calibrator in enumerate(self.calibrators_):
            calibrated_probs[:, i] = calibrator.predict(raw_probs[:, i])
            
        row_sums = calibrated_probs.sum(axis=1, keepdims=True)
        row_sums[row_sums == 0] = 1.0
        calibrated_probs = calibrated_probs / row_sums
        return calibrated_probs
        
    def predict(self, X):
        probs = self.predict_proba(X)
        return self.classes_[np.argmax(probs, axis=1)]

# Telegram credentials
TELEGRAM_TOKEN   = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

# Scout settings
SCOUT_INTERVAL_SECONDS = 900     # Run full scan every 15 minutes (stays in sync with 15m candles)
TOP_COINS_TO_SEND      = 3      # Only Telegram the top N coins by AI win probability
MIN_AI_PROB_TO_SEND    = 45.0  # Ignore coins where max(long_prob, short_prob) < 45%
BRAIN_DIR              = "."   # Directory where *_brain.pkl files live

# Global flag for on-demand /scan trigger
scan_now_flag = None


def send_telegram(msg: str):
    """Send a Telegram message, escaping underscores to avoid Markdown errors."""
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        print("[WARNING] Telegram secrets not set.")
        return
    safe = msg.replace("_", "\\_")
    try:
        url  = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        resp = requests.post(
            url,
            json={"chat_id": TELEGRAM_CHAT_ID, "text": safe, "parse_mode": "Markdown"},
            timeout=10
        )
        if resp.status_code != 200:
            requests.post(url, json={"chat_id": TELEGRAM_CHAT_ID, "text": safe}, timeout=10)
    except Exception as e:
        print(f"[ERROR] Telegram send failed: {e}")


def calculate_zscore(series: pd.Series, period: int) -> pd.Series:
    mu  = series.rolling(window=period, min_periods=1).mean()
    std = series.rolling(window=period, min_periods=1).std().replace(0, 1e-8)
    return (series - mu) / std


def calculate_support_resistance(df: pd.DataFrame, close: float) -> dict:
    """
    Derive support and resistance levels from EMA, Bollinger Bands, and swing points.
    Returns dict with labelled 'supports' and 'resistances' lists.
    """
    ema50  = df['close'].ewm(span=50,  adjust=False).mean().iloc[-1]
    ema200 = df['close'].ewm(span=200, adjust=False).mean().iloc[-1]
    sma20  = df['close'].rolling(20).mean().iloc[-1]
    std20  = df['close'].rolling(20).std().iloc[-1]
    bb_upper = sma20 + 2 * std20
    bb_lower = sma20 - 2 * std20

    swing_high_20 = df['high'].rolling(20).max().iloc[-1]
    swing_low_20  = df['low'].rolling(20).min().iloc[-1]
    swing_high_50 = df['high'].rolling(50).max().iloc[-1]
    swing_low_50  = df['low'].rolling(50).min().iloc[-1]

    def tag(val):
        tol = close * 0.003
        if abs(val - ema50)         < tol: return f"EMA 50"
        if abs(val - ema200)        < tol: return f"EMA 200"
        if abs(val - bb_upper)      < tol * 2: return "BB Upper"
        if abs(val - bb_lower)      < tol * 2: return "BB Lower"
        if abs(val - swing_low_20)  < tol: return "20-bar Swing Low"
        if abs(val - swing_low_50)  < tol: return "50-bar Swing Low"
        if abs(val - swing_high_20) < tol: return "20-bar Swing High"
        if abs(val - swing_high_50) < tol: return "50-bar Swing High"
        return "Level"

    raw_sup = sorted([v for v in [ema50, ema200, bb_lower, swing_low_20, swing_low_50] if v < close], reverse=True)
    raw_res = sorted([v for v in [ema50, ema200, bb_upper, swing_high_20, swing_high_50] if v > close])

    def fmt(v): return f"`${v:,.4f}`  ({tag(v)})"

    supports    = [fmt(v) for v in raw_sup[:2]]
    resistances = [fmt(v) for v in raw_res[:2]]

    while len(supports)    < 2: supports.append(f"`${close * 0.985:,.4f}`  (ATR estimate)")
    while len(resistances) < 2: resistances.append(f"`${close * 1.015:,.4f}`  (ATR estimate)")

    return {"supports": supports, "resistances": resistances,
            "ema50": ema50, "ema200": ema200, "bb_upper": bb_upper, "bb_lower": bb_lower}


def build_insight_card(asset: str, brain_pack: dict, last: pd.Series,
                       df: pd.DataFrame, long_thresh: float, short_thresh: float) -> str:
    """Build a full Telegram insight card string for one asset."""
    features_list = brain_pack['features']
    close = float(last['close'])

    # AI probabilities
    try:
        X = pd.DataFrame([last[features_list]], columns=features_list)
        probs      = brain_pack['model'].predict_proba(X)[0]
        long_prob  = round(probs[1] * 100, 1)
        short_prob = round(probs[0] * 100, 1)
    except Exception as e:
        return f"WARNING [{asset}] AI inference failed: {e}"

    if max(long_prob, short_prob) < MIN_AI_PROB_TO_SEND:
        return ""

    # Bias
    if long_prob >= short_prob:
        bias        = "LONG UP"
        bias_emoji  = "GREEN"
        ai_prob     = long_prob
        threshold   = long_thresh
    else:
        bias        = "SHORT DOWN"
        bias_emoji  = "RED"
        ai_prob     = short_prob
        threshold   = short_thresh

    if ai_prob >= threshold:
        thresh_badge = "ABOVE BOT THRESHOLD - Bot may also auto-trade"
    elif ai_prob >= threshold - 10:
        thresh_badge = "NEAR BOT THRESHOLD - Manual opportunity"
    else:
        thresh_badge = "BELOW BOT THRESHOLD - Your analysis required"

    # Indicators
    rsi       = float(last.get('rsi_14',              50))
    adx       = float(last.get('adx_14',               0))
    macd_hist = float(last.get('macd_hist',             0))
    chop      = float(last.get('chop_index',           50))
    atr       = float(last.get('atr',        close * 0.01))
    atr_comp  = float(last.get('atr_compression',      1.0))
    rvol      = float(last.get('rvol',                 1.0))
    supertrend = int(last.get('supertrend_direction',   0))
    funding   = float(last.get('funding_rate_zscore',   0))
    oi_z      = float(last.get('oi_zscore',             0))

    regime      = "CHOPPY" if chop > 55 or adx < 20 else ("TRENDING" if chop < 45 and adx > 25 else "NORMAL")
    regime_icon = "WARNING" if regime == "CHOPPY" else ("CHECK" if regime == "TRENDING" else "")
    regime_note = ("Use smaller position size, tighter SL" if regime == "CHOPPY"
                   else "Strong trend - momentum entries preferred" if regime == "TRENDING"
                   else "Neutral regime - standard sizing")

    st_txt   = "BULLISH" if supertrend == 1 else "BEARISH"
    rsi_note = ("Overbought" if rsi > 70 else "Oversold" if rsi < 30
                else "Bullish" if rsi > 55 else "Bearish" if rsi < 45 else "Neutral")
    macd_lbl = "Bullish momentum" if macd_hist > 0 else "Bearish momentum"
    fund_note = ("Crowded LONGS - short squeeze risk" if funding > 1.5
                 else "Crowded SHORTS - long squeeze risk" if funding < -1.5 else "Neutral")
    oi_note  = ("OI building - trend continuation" if oi_z > 1.5
                else "OI declining - trend exhaustion" if oi_z < -1.5 else "Neutral")
    rvol_note = (f"{rvol:.2f}x Volume spike" if rvol > 1.5
                 else f"{rvol:.2f}x Low volume" if rvol < 0.7 else f"{rvol:.2f}x Normal")

    # Entry zone
    half_atr = atr * 0.5
    entry_low  = close - half_atr * 0.3
    entry_high = close + half_atr * 0.3
    if "LONG" in bias:
        sl_price = close - atr * config.ATR_STOP_LOSS_MULTIPLIER * 0.9
        tp_price = close + atr * config.ATR_TAKE_PROFIT_MULTIPLIER
    else:
        sl_price = close + atr * config.ATR_STOP_LOSS_MULTIPLIER * 0.9
        tp_price = close - atr * config.ATR_TAKE_PROFIT_MULTIPLIER

    sl_pct = abs(sl_price - close) / close * 100
    tp_pct = abs(tp_price - close) / close * 100
    rr     = round(tp_pct / sl_pct, 2) if sl_pct > 0 else 0.0

    # Support/Resistance
    levels = calculate_support_resistance(df, close)
    sup1, sup2 = levels['supports']
    res1, res2 = levels['resistances']

    # Risk notes
    risk_notes = [f"• Regime: {regime} — {regime_note}"]
    if atr_comp < 0.45: risk_notes.append("• ATR SQUEEZE — wait for confirmed breakout candle close")
    if rvol < 0.7:      risk_notes.append("• Low volume — await volume confirmation")
    if funding > 1.5 and "LONG" in bias:  risk_notes.append("• High long funding — tight SL advised")
    if funding < -1.5 and "SHORT" in bias: risk_notes.append("• High short funding — tight SL advised")
    if chop > 60:       risk_notes.append("• Very choppy — consider skipping or 50% size")
    risk_str = "\n".join(risk_notes)

    squeeze_line = "  FIRE ATR SQUEEZE DETECTED — breakout likely soon\n" if atr_comp < 0.45 else ""
    ts           = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    ticker_name  = asset.replace("/", "-")
    bias_arrow   = "UP" if "LONG" in bias else "DOWN"
    bias_icon    = "\U0001f7e2" if "LONG" in bias else "\U0001f534"

    msg = (
        f"{bias_icon} *[SCOUT] {ticker_name} — {bias_arrow} {bias.split()[0]} BIAS*\n"
        f"===================================\n"
        f"*Price:*  `${close:,.4f}`  |  *TF:* `{config.TIMEFRAME}`  |  *Regime:* `{regime}`\n"
        f"\n"
        f"\U0001f4d0 *KEY PRICE LEVELS*\n"
        f"  \U0001f7e2 Support 1:    {sup1}\n"
        f"  \U0001f7e2 Support 2:    {sup2}\n"
        f"  \U0001f534 Resistance 1: {res1}\n"
        f"  \U0001f534 Resistance 2: {res2}\n"
        f"\n"
        f"\U0001f3af *SUGGESTED ENTRY ZONE*\n"
        f"  Entry Zone: `${entry_low:,.4f}` to `${entry_high:,.4f}`\n"
        f"  Stop Loss:  `${sl_price:,.4f}`  (-{sl_pct:.2f}%)\n"
        f"  TP Target:  `${tp_price:,.4f}`  (+{tp_pct:.2f}%)\n"
        f"  R:R Ratio:  `1 : {rr:.2f}`\n"
        f"\n"
        f"\U0001f9e0 *AI INTELLIGENCE*\n"
        f"  LONG  Win Prob:  `{long_prob:.1f}%`  (Bot gate: `{long_thresh:.0f}%`)\n"
        f"  SHORT Win Prob:  `{short_prob:.1f}%`  (Bot gate: `{short_thresh:.0f}%`)\n"
        f"  Status:  `{thresh_badge}`\n"
        f"\n"
        f"\U0001f4ca *INDICATOR SNAPSHOT*\n"
        f"  RSI 14:       `{rsi:.1f}`  ({rsi_note})\n"
        f"  MACD Hist:    `{macd_hist:+.4f}`  ({macd_lbl})\n"
        f"  Supertrend:   `{st_txt}`\n"
        f"  Chop Index:   `{chop:.1f}`  ({'Choppy' if chop > 55 else 'Directional'})\n"
        f"  ADX:          `{adx:.1f}`  ({'Strong' if adx > 25 else 'Weak' if adx < 15 else 'Moderate'})\n"
        f"  ATR Compress: `{atr_comp:.3f}`\n"
        f"\n"
        f"\U0001f4b8 *MICROSTRUCTURE*\n"
        f"  Funding Z: `{funding:+.2f}`  ({fund_note})\n"
        f"  OI Z:      `{oi_z:+.2f}`  ({oi_note})\n"
        f"  RVOL:      {rvol_note}\n"
        f"\n"
        f"\u26a0\ufe0f *RISK NOTES*\n"
        f"{squeeze_line}"
        f"{risk_str}\n"
        f"\n"
        f"_Generated: {ts}_"
    )
    return msg


async def run_scout_cycle(brains: dict, exchange):
    """Scan all assets, rank by AI win probability, send top 3 insight cards."""
    print(f"\n[{datetime.now().strftime('%H:%M:%S')}] === MANUAL SCOUT CYCLE STARTED ===")

    # Phase 1: collect scores for all assets silently
    ranked = []  # list of (max_prob, asset, card_str)

    for asset in config.TARGET_ASSETS:
        if asset not in brains:
            print(f"  [SKIP] {asset}: No brain loaded.")
            continue
        try:
            fetch_limit = 1600 if config.TIMEFRAME == "15m" else 250
            ohlcv = await asyncio.to_thread(
                exchange.fetch_ohlcv, asset, config.TIMEFRAME, limit=fetch_limit
            )
            df = pd.DataFrame(ohlcv, columns=['timestamp','open','high','low','close','volume'])

            feature_df = calculate_features_for_shotgun(df)

            # Funding + OI
            funding_history = await asyncio.to_thread(exchange.fetch_funding_rate_history, asset, limit=100)
            oi_tf           = '15m' if config.TIMEFRAME == '15m' else '1h'
            oi_history      = await asyncio.to_thread(exchange.fetch_open_interest_history, asset, oi_tf, limit=100)
            funding_df      = pd.DataFrame(funding_history)[['timestamp','fundingRate']]
            oi_df           = pd.DataFrame(oi_history)[['timestamp','openInterestAmount']]
            funding_df['timestamp'] = pd.to_datetime(funding_df['timestamp'], unit='ms')
            oi_df['timestamp']      = pd.to_datetime(oi_df['timestamp'],      unit='ms')
            resample_rule           = '15min' if config.TIMEFRAME == '15m' else '1h'
            funding_df = funding_df.set_index('timestamp').resample(resample_rule).last()
            oi_df      = oi_df.set_index('timestamp').resample(resample_rule).last()
            z_period   = 120 if config.TIMEFRAME == "15m" else 30
            funding_df['funding_rate_zscore'] = calculate_zscore(funding_df['fundingRate'],        z_period)
            oi_df['oi_zscore']               = calculate_zscore(oi_df['openInterestAmount'],       z_period)

            feature_df['datetime'] = pd.to_datetime(feature_df['timestamp'], unit='ms')
            feature_df = feature_df.set_index('datetime')
            final_df   = feature_df.join(funding_df[['funding_rate_zscore']]).join(oi_df[['oi_zscore']])
            final_df['funding_rate_zscore'] = final_df['funding_rate_zscore'].fillna(0)
            final_df['oi_zscore']           = final_df['oi_zscore'].fillna(0)
            final_df.dropna(inplace=True)

            if len(final_df) < 5:
                print(f"  [SKIP] {asset}: Not enough data.")
                continue

            last = final_df.iloc[-1]

            base_long    = getattr(config, 'LONG_CONFIDENCE_THRESHOLD',  55.0)
            base_short   = getattr(config, 'SHORT_CONFIDENCE_THRESHOLD', 53.0)
            asset_thresh = getattr(config, 'ASSET_SPECIFIC_THRESHOLDS', {})
            long_thresh  = asset_thresh.get(f"{asset}_LONG",  asset_thresh.get(asset, base_long))
            short_thresh = asset_thresh.get(f"{asset}_SHORT", asset_thresh.get(asset, base_short))

            card = build_insight_card(asset, brains[asset], last, df, long_thresh, short_thresh)

            if card:
                # Extract the AI prob that was used for ranking (max of long/short)
                features_list = brains[asset]['features']
                X = pd.DataFrame([last[features_list]], columns=features_list)
                probs = brains[asset]['model'].predict_proba(X)[0]
                max_prob = max(probs[1] * 100, probs[0] * 100)
                ranked.append((max_prob, asset, card))
                print(f"  [SCORED] {asset}: {max_prob:.1f}% AI prob")
            else:
                print(f"  [SKIP] {asset}: Below MIN-AI-PROB threshold.")

        except Exception as e:
            print(f"  [ERROR] {asset}: {e}")

    # Phase 2: sort by AI probability descending, send top N
    ranked.sort(key=lambda x: x[0], reverse=True)
    top_n = ranked[:TOP_COINS_TO_SEND]

    if not top_n:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] No qualifying coins this cycle.")
        return

    # Send a header summary first
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    summary_lines = []
    for rank_i, (prob, asset, _) in enumerate(top_n, 1):
        ticker = asset.replace("/", "-")
        summary_lines.append(f"  {rank_i}. *{ticker}*  `{prob:.1f}%`")
    summary_msg = (
        f"\U0001f3af *[MANUAL SCOUT] Top {TOP_COINS_TO_SEND} Opportunities*\n"
        f"{'=' * 32}\n"
        + "\n".join(summary_lines)
        + f"\n\n_Sending full insight cards now..._\n_Scanned: {ts}_"
    )
    send_telegram(summary_msg)
    await asyncio.sleep(1.5)

    # Send full card for each top coin
    for prob, asset, card in top_n:
        send_telegram(card)
        print(f"  [SENT] {asset}: Insight card delivered. (AI: {prob:.1f}%)")
        await asyncio.sleep(1.5)

    print(f"[{datetime.now().strftime('%H:%M:%S')}] Scout cycle complete. Sent top {len(top_n)}/{len(config.TARGET_ASSETS)} coins.")


def load_brains() -> dict:
    brains = {}
    for asset in config.TARGET_ASSETS:
        fname = os.path.join(BRAIN_DIR, asset.replace("/", "_") + "_brain.pkl")
        if os.path.exists(fname):
            try:
                data = joblib.load(fname)
                if 'model' in data and 'features' in data:
                    brains[asset] = data
                    print(f"[INFO] Loaded brain: {asset}")
            except Exception as e:
                print(f"[WARNING] Could not load {fname}: {e}")
    return brains


async def telegram_command_listener():
    """Poll Telegram for /scan commands to trigger on-demand scans."""
    if not TELEGRAM_TOKEN:
        return
    last_update_id = None
    print("[INFO] Telegram /scan listener active.")
    while True:
        try:
            url    = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getUpdates"
            params = {"timeout": 30, "offset": last_update_id}
            resp   = await asyncio.to_thread(requests.get, url, params=params, timeout=35)
            data   = resp.json()
            for update in data.get("result", []):
                last_update_id = update["update_id"] + 1
                text = update.get("message", {}).get("text", "").strip().lower()
                if text.startswith("/scan"):
                    send_telegram("SEARCH *[SCOUT]* On-demand scan triggered...")
                    scan_now_flag.set()
        except Exception as e:
            print(f"[WARN] Telegram poll error: {e}")
        await asyncio.sleep(2)


async def main():
    global scan_now_flag
    scan_now_flag = asyncio.Event()

    print("=" * 50)
    print("  ALPHAQUANT V8.2 - MANUAL SCALPING SCOUT")
    print("=" * 50)

    brains = load_brains()
    if not brains:
        print("[FATAL] No brains loaded.")
        return

    exchange = ccxt.binance({'enableRateLimit': True, 'options': {'defaultType': 'future'}})

    send_telegram(
        f"TELESCOPE *[MANUAL SCOUT]* Service started.\n"
        f"Scanning `{len(brains)}` assets every `{SCOUT_INTERVAL_SECONDS // 60}` minutes.\n"
        f"Min AI prob to send card: `{MIN_AI_PROB_TO_SEND:.0f}%`\n"
        f"Send `/scan` for an instant on-demand scan."
    )

    asyncio.create_task(telegram_command_listener())

    # First scan immediately on startup
    await run_scout_cycle(brains, exchange)

    while True:
        try:
            try:
                await asyncio.wait_for(scan_now_flag.wait(), timeout=SCOUT_INTERVAL_SECONDS)
                scan_now_flag.clear()
            except asyncio.TimeoutError:
                pass
            await run_scout_cycle(brains, exchange)
        except Exception as e:
            print(f"[ERROR] {e}")
            await asyncio.sleep(30)


if __name__ == "__main__":
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())
