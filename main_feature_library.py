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

    # Bollinger Bands (using scaled period of fast EMA / 10 to keep proportion, or fixed 20. Let's keep 20)
    sma_20 = features['close'].rolling(window=20).mean()
    std_20 = features['close'].rolling(window=20).std()
    features['bb_width'] = ((sma_20 + (std_20 * 2)) - (sma_20 - (std_20 * 2))) / sma_20
    
    # --- ADX Calculation (Dynamic Scale) ---
    plus_dm = features['high'].diff()
    minus_dm = features['low'].diff()
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

    # --- Final Feature Vector Columns ---
    # Lookbacks for volume z-score: 30 for 1H, 120 for 15M (matches ~30 hours)
    vol_period = 120 if config.TIMEFRAME == "15m" else 30
    features['volume_zscore'] = calculate_zscore(features['volume'], vol_period)
    
    features['dist_ema_50'] = (features['close'] - features['ema_50']) / features['ema_50']
    features['dist_ema_200'] = (features['close'] - features['ema_200']) / features['ema_200']
    features['atr_pct'] = features['atr'] / features['close']
    
    return features

def calculate_features_and_signals(df):
    """
    Main function to calculate all price-derived features and primary signals.
    (Legacy function, kept for compatibility/reference)
    """
    features = calculate_features_for_shotgun(df)

    # --- Primary Signal Generation ---
    features['prev_close'] = features['close'].shift(1)
    features['prev_ema_50'] = features['ema_50'].shift(1)
    features['primary_trend_long'] = np.where((features['prev_close'] <= features['prev_ema_50']) & (features['close'] > features['ema_50']) & (features['ema_50'] > features['ema_200']), 1, 0)
    features['primary_trend_short'] = np.where((features['prev_close'] >= features['prev_ema_50']) & (features['close'] < features['ema_50']) & (features['ema_50'] < features['ema_200']), 1, 0)
    
    sma_20 = features['close'].rolling(window=20).mean()
    std_20 = features['close'].rolling(window=20).std()
    bb_squeeze_thresh = features['bb_width'].quantile(0.10)
    is_squeeze = features['bb_width'].shift(1) < bb_squeeze_thresh
    upper_band, lower_band = sma_20 + (std_20 * 2), sma_20 - (std_20 * 2)
    features['primary_breakout_long'] = np.where(is_squeeze & (features['close'] > upper_band), 1, 0)
    features['primary_breakout_short'] = np.where(is_squeeze & (features['close'] < lower_band), 1, 0)
    
    price_zscore = calculate_zscore(features['close'], 200)
    features['primary_reversion_long'] = np.where(price_zscore < -3.0, 1, 0)
    features['primary_reversion_short'] = np.where(price_zscore > 3.0, 1, 0)
    
    return features
