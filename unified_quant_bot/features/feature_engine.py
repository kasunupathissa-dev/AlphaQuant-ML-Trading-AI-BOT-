import numpy as np
import pandas as pd
from typing import Dict, List, Optional

class FeatureEngine:
    """Calculates quantitative features: 12-indicator ML vector, Microstructure CVD, L2 Depth Imbalance."""

    @staticmethod
    def calculate_indicators(df: pd.DataFrame) -> pd.DataFrame:
        """Calculates indicators on historical OHLCV dataframe."""
        if len(df) < 50:
            return df

        df = df.copy()
        close = df['close']
        high = df['high']
        low = df['low']
        volume = df['volume']

        # 1. EMAs
        ema_9 = close.ewm(span=9, adjust=False).mean()
        ema_21 = close.ewm(span=21, adjust=False).mean()
        ema_50 = close.ewm(span=50, adjust=False).mean()
        ema_200 = close.ewm(span=min(200, len(df)), adjust=False).mean()

        df['ema_9'] = ema_9
        df['ema_21'] = ema_21
        df['ema_50'] = ema_50
        df['ema_200'] = ema_200
        df['dist_ema_50'] = (close - ema_50) / (ema_50 + 1e-9)
        df['dist_ema_200'] = (close - ema_200) / (ema_200 + 1e-9)

        # 2. True Range & ATR
        tr = pd.concat([
            high - low,
            (high - close.shift(1)).abs(),
            (low - close.shift(1)).abs()
        ], axis=1).max(axis=1)
        atr_14 = tr.rolling(window=14).mean().fillna(tr)
        df['atr_14'] = atr_14
        df['atr_pct'] = atr_14 / (close + 1e-9)

        # 3. Volume Z-Score
        vol_mean = volume.rolling(window=min(120, len(df))).mean()
        vol_std = volume.rolling(window=min(120, len(df))).std().replace(0, 1.0)
        df['volume_zscore'] = ((volume - vol_mean) / vol_std).fillna(0.0)

        # 4. ADX (14-period Wilder's)
        up_move = high - high.shift(1)
        down_move = low.shift(1) - low
        plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0.0)
        minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0.0)
        
        tr_smooth = tr.rolling(14).sum().replace(0, 1e-9)
        plus_di = 100 * (pd.Series(plus_dm, index=df.index).rolling(14).sum() / tr_smooth)
        minus_di = 100 * (pd.Series(minus_dm, index=df.index).rolling(14).sum() / tr_smooth)
        dx = (100 * (plus_di - minus_di).abs() / (plus_di + minus_di + 1e-9)).fillna(0.0)
        df['adx_14'] = dx.rolling(14).mean().fillna(20.0)

        # 5. Bollinger Bands & Width
        sma_20 = close.rolling(20).mean()
        std_20 = close.rolling(20).std().replace(0, 1e-9)
        upper_bb = sma_20 + (2.0 * std_20)
        lower_bb = sma_20 - (2.0 * std_20)
        df['bb_upper'] = upper_bb
        df['bb_lower'] = lower_bb
        df['bb_width'] = (upper_bb - lower_bb) / (sma_20 + 1e-9)

        # 6. RSI (14-period)
        delta = close.diff()
        gain = delta.clip(lower=0)
        loss = -delta.clip(upper=0)
        avg_gain = gain.rolling(14).mean()
        avg_loss = loss.rolling(14).mean().replace(0, 1e-9)
        rs = avg_gain / avg_loss
        df['rsi_14'] = (100 - (100 / (1 + rs))).fillna(50.0)

        # 7. MACD Histogram
        ema_12 = close.ewm(span=12, adjust=False).mean()
        ema_26 = close.ewm(span=26, adjust=False).mean()
        macd_line = ema_12 - ema_26
        signal_line = macd_line.ewm(span=9, adjust=False).mean()
        df['macd_hist'] = macd_line - signal_line

        # 8. Supertrend Direction (ATR Multiplier 3.0)
        hl2 = (high + low) / 2.0
        upper_band = hl2 + (3.0 * atr_14)
        lower_band = hl2 - (3.0 * atr_14)
        supertrend_dir = np.where(close > upper_band.shift(1), 1.0, np.where(close < lower_band.shift(1), -1.0, 1.0))
        df['supertrend_direction'] = supertrend_dir

        # 9. Choppiness Index (14-period)
        atr_sum = tr.rolling(14).sum()
        highest_h = high.rolling(14).max()
        lowest_l = low.rolling(14).min()
        range_hl = (highest_h - lowest_l).replace(0, 1e-9)
        chop = 100.0 * (np.log10(atr_sum / range_hl) / np.log10(14))
        # 10. RVOL (Relative Volume)
        vol_sma_20 = volume.rolling(20).mean().replace(0, 1.0)
        df['rvol'] = (volume / vol_sma_20).fillna(1.0)

        # 11. ATR Compression (ATR 14 / ATR 50)
        atr_50 = tr.rolling(50).mean().replace(0, 1e-9)
        df['atr_compression'] = (atr_14 / atr_50).fillna(1.0)

        # Default zero placeholders for model compatibility
        df['funding_rate_zscore'] = 0.0
        df['oi_zscore'] = 0.0

        return df

    @staticmethod
    def extract_12_feature_vector(df: pd.DataFrame, n_features: int = 12) -> np.ndarray:
        """Extracts the feature vector matching serialized ML brain models (12 or 14 features)."""
        expected_cols = [
            'dist_ema_50', 'dist_ema_200', 'atr_pct', 'volume_zscore', 'adx_14',
            'bb_width', 'funding_rate_zscore', 'oi_zscore', 'rsi_14', 'macd_hist',
            'supertrend_direction', 'chop_index', 'rvol', 'atr_compression'
        ]
        
        last_row = df.iloc[-1] if not df.empty else None
        if last_row is None:
            return np.zeros((1, n_features))

        cols_to_use = expected_cols[:n_features]
        vec = [float(last_row.get(col, 0.0)) for col in cols_to_use]
        return np.array(vec).reshape(1, -1)
