import numpy as np
import pandas as pd

class FeatureEngineering:
    """Production Feature Engineering Engine aligned with V8 Shotgun architecture."""

    @staticmethod
    def calculate_atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
        """Computes Average True Range (ATR)."""
        high_low = df['high'] - df['low']
        high_close = (df['high'] - df['close'].shift(1)).abs()
        low_close = (df['low'] - df['close'].shift(1)).abs()
        tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        return tr.rolling(window=period).mean()

    @staticmethod
    def calculate_adx(df: pd.DataFrame, period: int = 14) -> pd.Series:
        """Computes standard Wilder's ADX."""
        plus_dm = df['high'].diff()
        minus_dm = -df['low'].diff()
        plus_dm = np.where((plus_dm > minus_dm) & (plus_dm > 0), plus_dm, 0.0)
        minus_dm = np.where((minus_dm > plus_dm) & (minus_dm > 0), minus_dm, 0.0)
        
        tr = FeatureEngineering.calculate_atr(df, period=1) * period
        
        plus_di = 100 * (pd.Series(plus_dm, index=df.index).ewm(alpha=1/period, adjust=False).mean() / tr)
        minus_di = 100 * (pd.Series(minus_dm, index=df.index).ewm(alpha=1/period, adjust=False).mean() / tr)
        
        dx = (abs(plus_di - minus_di) / (plus_di + minus_di + 1e-9)) * 100
        adx = dx.ewm(alpha=1/period, adjust=False).mean()
        return adx.fillna(0.0)

    @staticmethod
    def calculate_rsi(series: pd.Series, period: int = 14) -> pd.Series:
        """Calculates Wilder's Relative Strength Index."""
        delta = series.diff()
        gain = delta.clip(lower=0)
        loss = -delta.clip(upper=0)
        ema_gain = gain.ewm(com=period-1, adjust=False).mean()
        ema_loss = loss.ewm(com=period-1, adjust=False).mean()
        rs = ema_gain / (ema_loss + 1e-9)
        return 100 - (100 / (1 + rs))

    @staticmethod
    def calculate_macd(series: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9) -> pd.Series:
        """Calculates MACD Histogram."""
        ema_fast = series.ewm(span=fast, adjust=False).mean()
        ema_slow = series.ewm(span=slow, adjust=False).mean()
        macd = ema_fast - ema_slow
        signal_line = macd.ewm(span=signal, adjust=False).mean()
        return macd - signal_line

    @staticmethod
    def calculate_supertrend(df: pd.DataFrame, period: int = 10, multiplier: float = 3.0) -> pd.Series:
        """Calculates SuperTrend Direction (1 for Bullish, -1 for Bearish)."""
        atr = FeatureEngineering.calculate_atr(df, period)
        hl2 = (df['high'] + df['low']) / 2
        
        upper_band = hl2 + (multiplier * atr)
        lower_band = hl2 - (multiplier * atr)
        
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

    @staticmethod
    def calculate_choppiness_index(df: pd.DataFrame, period: int = 14) -> pd.Series:
        """Calculates Choppiness Index (0-100)."""
        tr = pd.concat([
            df['high'] - df['low'],
            (df['high'] - df['close'].shift(1)).abs(),
            (df['low'] - df['close'].shift(1)).abs()
        ], axis=1).max(axis=1)
        atr_sum = tr.rolling(window=period).sum()
        high_max = df['high'].rolling(window=period).max()
        low_min = df['low'].rolling(window=period).min()
        range_hl = (high_max - low_min).clip(lower=1e-8)
        return 100 * np.log10(atr_sum / range_hl) / np.log10(period)

    @staticmethod
    def calculate_zscore(series: pd.Series, period: int = 30) -> pd.Series:
        """Calculates the rolling Z-score."""
        mean = series.rolling(window=period).mean()
        std = series.rolling(window=period).std()
        return np.where(std > 1e-8, (series - mean) / std, 0.0)

    @classmethod
    def generate_full_feature_vector(cls, df: pd.DataFrame) -> pd.DataFrame:
        """Compiles clean, aligned feature vector required by the pre-trained brain classifiers."""
        feats = pd.DataFrame(index=df.index)
        
        # Base indicators
        ema_50 = df['close'].ewm(span=50, adjust=False).mean()
        ema_200 = df['close'].ewm(span=200, adjust=False).mean()
        atr = cls.calculate_atr(df, 14)
        
        # Required model features
        feats['dist_ema_50'] = (df['close'] - ema_50) / ema_50
        feats['dist_ema_200'] = (df['close'] - ema_200) / ema_200
        feats['atr_pct'] = atr / df['close']
        feats['volume_zscore'] = cls.calculate_zscore(df['volume'], 30)
        feats['adx_14'] = cls.calculate_adx(df, 14)
        
        sma_20 = df['close'].rolling(window=20).mean()
        std_20 = df['close'].rolling(window=20).std()
        feats['bb_width'] = ((sma_20 + (std_20 * 2)) - (sma_20 - (std_20 * 2))) / sma_20
        
        feats['funding_rate_zscore'] = 0.0
        feats['oi_zscore'] = 0.0
        feats['rsi_14'] = cls.calculate_rsi(df['close'], 14)
        feats['macd_hist'] = cls.calculate_macd(df['close'], 12, 26, 9)
        feats['supertrend_direction'] = cls.calculate_supertrend(df, 10, 3)
        feats['chop_index'] = cls.calculate_choppiness_index(df, 14)
        
        # Keep extra features expected by the orchestration loop
        ema_9 = df['close'].ewm(span=9, adjust=False).mean()
        ema_21 = df['close'].ewm(span=21, adjust=False).mean()
        feats['ema_spread_fast'] = (ema_9 - ema_21) / df['close']
        feats['ema_spread_slow'] = (ema_21 - ema_50) / df['close']
        feats['atr_14'] = atr
        
        return feats.dropna()
