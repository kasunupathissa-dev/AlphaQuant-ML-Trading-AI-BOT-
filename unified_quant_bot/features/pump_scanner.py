import pandas as pd
import numpy as np

class PumpScanner:
    r"""Detects sudden abnormal volume bursts ($Z \ge 3.0$) and high-volatility breakout spikes."""

    def __init__(self, volume_zscore_threshold: float = 3.0, price_surge_pct_threshold: float = 1.2):
        self.vol_z_thresh = volume_zscore_threshold
        self.surge_pct_thresh = price_surge_pct_threshold

    def scan(self, symbol: str, df_1m: pd.DataFrame) -> dict:
        """Evaluates 1m candlestick history for momentum pump characteristics."""
        if len(df_1m) < 30:
            return {"pump_detected": False}

        close = df_1m['close'].values
        volume = df_1m['volume'].values

        recent_vol = volume[-1]
        hist_vol_mean = np.mean(volume[-30:-1])
        hist_vol_std = np.std(volume[-30:-1]) + 1e-9

        vol_z = (recent_vol - hist_vol_mean) / hist_vol_std
        price_change_pct = ((close[-1] - close[-2]) / close[-2]) * 100.0

        is_pump = (vol_z >= self.vol_z_thresh) and (abs(price_change_pct) >= self.surge_pct_thresh)
        direction = "LONG" if price_change_pct > 0 else "SHORT"

        return {
            "pump_detected": bool(is_pump),
            "symbol": symbol,
            "direction": direction,
            "volume_zscore": round(float(vol_z), 2),
            "price_surge_pct": round(float(price_change_pct), 2),
            "close": float(close[-1])
        }
