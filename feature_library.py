import pandas as pd
import numpy as np
import config

# ==================================================
# ALPHAQUANT V8.3: SHOTGUN FEATURE LIBRARY
# ==================================================
# This module centralizes all feature calculation logic.
# Scaled dynamically to support 15M timeframe.
# ==================================================

def calculate_zscore(series, period=30):
    """Calculates the rolling Z-score to identify statistical anomalies."""
    mean = series.rolling(window=period).mean()
    std = series.rolling(window=period).std()
    return np.where(std > 1e-8, (series - mean) / std, 0)

def calculate_atr(df, period=14):
    """Calculates Average True Range."""
    high_low = df['high'] - df['low']
    high_close = np.abs(df['high'] - df['close'].shift())
    low_close = np.abs(df['low'] - df['close'].shift())
    ranges = pd.concat([high_low, high_close, low_close], axis=1)
    return np.max(ranges, axis=1).rolling(window=period).mean()

def calculate_rsi(series, period=14):
    """Calculates Wilder's Relative Strength Index."""
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    ema_gain = gain.ewm(com=period-1, adjust=False).mean()
    ema_loss = loss.ewm(com=period-1, adjust=False).mean()
    rs = ema_gain / (ema_loss + 1e-9)
    return 100 - (100 / (1 + rs))

def calculate_macd(series, fast=12, slow=26, signal=9):
    """Calculates MACD Histogram."""
    ema_fast = series.ewm(span=fast, adjust=False).mean()
    ema_slow = series.ewm(span=slow, adjust=False).mean()
    macd = ema_fast - ema_slow
    signal_line = macd.ewm(span=signal, adjust=False).mean()
    return macd - signal_line

def calculate_supertrend(df, period=10, multiplier=3):
    """Calculates SuperTrend Direction (1 for Bullish, -1 for Bearish)."""
    atr = calculate_atr(df, period)
    hl2 = (df['high'] + df['low']) / 2
    
    upper_band = hl2 + (multiplier * atr)
    lower_band = hl2 - (multiplier * atr)
    
    # Make writable copies of numpy arrays
    upper_band_vals = upper_band.values.copy()
    lower_band_vals = lower_band.values.copy()
    close_vals = df['close'].values
    direction = [1] * len(df)
    
    for i in range(1, len(df)):
        curr_close = close_vals[i]
        prev_close = close_vals[i-1]
        prev_upper = upper_band_vals[i-1]
        prev_lower = lower_band_vals[i-1]
        
        if curr_close < prev_upper:
            upper_band_vals[i] = min(upper_band_vals[i], prev_upper)
        if curr_close > prev_lower:
            lower_band_vals[i] = max(lower_band_vals[i], prev_lower)
            
        if prev_close > prev_upper:
            direction[i] = 1
        elif prev_close < prev_lower:
            direction[i] = -1
        else:
            direction[i] = direction[i-1]
            
    return pd.Series(direction, index=df.index, dtype=float)

def calculate_choppiness_index(df, period=14):
    """Calculates Choppiness Index (0-100)."""
    tr = np.maximum(df['high'] - df['low'], 
                    np.maximum(np.abs(df['high'] - df['close'].shift()), 
                               np.abs(df['low'] - df['close'].shift())))
    atr_sum = tr.rolling(window=period).sum()
    high_max = df['high'].rolling(window=period).max()
    low_min = df['low'].rolling(window=period).min()
    range_hl = np.maximum(high_max - low_min, 1e-8)
    return 100 * np.log10(atr_sum / range_hl) / np.log10(period)

def calculate_features_for_shotgun(df):
    """
    Calculates all price-derived features for the Shotgun architecture.
    Indicators dynamically scale lookbacks according to config.py.
    """
    features = df.copy()
    
    # --- Base Indicators (Dynamic Scale) ---
    features['ema_50'] = features['close'].ewm(span=config.EMA_FAST_PERIOD, adjust=False).mean()
    features['ema_200'] = features['close'].ewm(span=config.EMA_SLOW_PERIOD, adjust=False).mean()
    features['atr'] = calculate_atr(features, config.ATR_PERIOD)

    # Bollinger Bands
    sma_20 = features['close'].rolling(window=20).mean()
    std_20 = features['close'].rolling(window=20).std()
    features['bb_width'] = ((sma_20 + (std_20 * 2)) - (sma_20 - (std_20 * 2))) / sma_20
    
    # --- ADX Calculation (Dynamic Scale) ---
    plus_dm = features['high'].diff()
    minus_dm = -features['low'].diff()
    plus_dm = np.where((plus_dm > minus_dm) & (plus_dm > 0), plus_dm, 0.0)
    minus_dm = np.where((minus_dm > plus_dm) & (minus_dm > 0), minus_dm, 0.0)
    
    tr_series = pd.Series(np.max([
        features['high'] - features['low'], 
        np.abs(features['high'] - features['close'].shift()), 
        np.abs(features['low'] - features['close'].shift())
    ], axis=0), index=df.index)
    
    alpha = 1 / config.ATR_PERIOD
    plus_di = 100 * (pd.Series(plus_dm).ewm(alpha=alpha, adjust=False).mean() / tr_series.ewm(alpha=alpha, adjust=False).mean())
    minus_di = 100 * (pd.Series(minus_dm).ewm(alpha=alpha, adjust=False).mean() / tr_series.ewm(alpha=alpha, adjust=False).mean())
    dx = 100 * np.abs(plus_di - minus_di) / (plus_di + minus_di + 1e-8)
    features['adx_14'] = dx.ewm(alpha=alpha, adjust=False).mean()

    # --- New Technical Indicator Pool (DTIP) ---
    features['rsi_14'] = calculate_rsi(features['close'], 14)
    features['macd_hist'] = calculate_macd(features['close'], 12, 26, 9)
    features['supertrend_direction'] = calculate_supertrend(features, 10, 3)
    features['chop_index'] = calculate_choppiness_index(features, 14)

    # Volume Z-score
    vol_period = 120 if config.TIMEFRAME == "15m" else 30
    features['volume_zscore'] = calculate_zscore(features['volume'], vol_period)
    
    features['dist_ema_50'] = (features['close'] - features['ema_50']) / features['ema_50']
    features['dist_ema_200'] = (features['close'] - features['ema_200']) / features['ema_200']
    features['atr_pct'] = features['atr'] / features['close']
    
    # --- Primary Signal Trigger (Binary Confirmation Input) ---
    features['prev_close'] = features['close'].shift(1)
    features['prev_ema_50'] = features['ema_50'].shift(1)
    
    # Crossover Signals
    trend_long = np.where((features['prev_close'] <= features['prev_ema_50']) & (features['close'] > features['ema_50']) & (features['ema_50'] > features['ema_200']), 1, 0)
    trend_short = np.where((features['prev_close'] >= features['prev_ema_50']) & (features['close'] < features['ema_50']) & (features['ema_50'] < features['ema_200']), 1, 0)
    
    # Breakout Signals (BB Squeeze + Close breakout)
    bb_squeeze_thresh = features['bb_width'].expanding(min_periods=100).quantile(0.10)
    is_squeeze = features['bb_width'].shift(1) < bb_squeeze_thresh
    upper_band, lower_band = sma_20 + (std_20 * 2), sma_20 - (std_20 * 2)
    breakout_long = np.where(is_squeeze & (features['close'] > upper_band), 1, 0)
    breakout_short = np.where(is_squeeze & (features['close'] < lower_band), 1, 0)
    
    # Reversion Signals (Extreme Overstretched Price)
    price_zscore = calculate_zscore(features['close'], 200)
    reversion_long = np.where(price_zscore < -3.0, 1, 0)
    reversion_short = np.where(price_zscore > 3.0, 1, 0)
    
    # Combine signals: 1 for LONG, 0 for SHORT, -1 for NONE
    primary_signal = np.full(len(features), -1, dtype=int)
    trigger_category = np.full(len(features), 0, dtype=int)
    
    # Apply conditions
    long_conditions = (trend_long == 1) | (breakout_long == 1) | (reversion_long == 1)
    short_conditions = (trend_short == 1) | (breakout_short == 1) | (reversion_short == 1)
    
    primary_signal[long_conditions] = 1
    primary_signal[short_conditions] = 0
    
    # Assign categories
    # 1: TREND
    primary_trend = (trend_long == 1) | (trend_short == 1)
    trigger_category[primary_trend] = 1
    # 2: BREAKOUT
    primary_breakout = (breakout_long == 1) | (breakout_short == 1)
    trigger_category[primary_breakout] = 2
    # 3: REVERSION
    primary_reversion = (reversion_long == 1) | (reversion_short == 1)
    trigger_category[primary_reversion] = 3
    
    features['primary_signal'] = primary_signal
    features['trigger_category'] = trigger_category
    
    features.replace([np.inf, -np.inf], np.nan, inplace=True)
    features.dropna(inplace=True)
    return features

def calculate_features_and_signals(df):
    """Legacy compatibility wrapper for V6.5 feature store."""
    features = calculate_features_for_shotgun(df)
    
    # Re-calculate individual legacy columns for database insertion compatibility
    features['prev_close'] = features['close'].shift(1)
    features['prev_ema_50'] = features['ema_50'].shift(1)
    features['primary_trend_long'] = np.where((features['prev_close'] <= features['prev_ema_50']) & (features['close'] > features['ema_50']) & (features['ema_50'] > features['ema_200']), 1, 0)
    features['primary_trend_short'] = np.where((features['prev_close'] >= features['prev_ema_50']) & (features['close'] < features['ema_50']) & (features['ema_50'] < features['ema_200']), 1, 0)
    
    sma_20 = features['close'].rolling(window=20).mean()
    std_20 = features['close'].rolling(window=20).std()
    bb_squeeze_thresh = features['bb_width'].expanding(min_periods=100).quantile(0.10)
    is_squeeze = features['bb_width'].shift(1) < bb_squeeze_thresh
    upper_band, lower_band = sma_20 + (std_20 * 2), sma_20 - (std_20 * 2)
    features['primary_breakout_long'] = np.where(is_squeeze & (features['close'] > upper_band), 1, 0)
    features['primary_breakout_short'] = np.where(is_squeeze & (features['close'] < lower_band), 1, 0)
    
    price_zscore = calculate_zscore(features['close'], 200)
    features['primary_reversion_long'] = np.where(price_zscore < -3.0, 1, 0)
    features['primary_reversion_short'] = np.where(price_zscore > 3.0, 1, 0)
    
    return features
