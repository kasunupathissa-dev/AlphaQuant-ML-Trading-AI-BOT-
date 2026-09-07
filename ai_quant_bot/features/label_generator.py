import numpy as np
import pandas as pd

class TripleBarrierLabeler:
    """
    Labels financial time series based on path-dependent Take-Profit,
    Stop-Loss, and Time-Horizon barriers.
    """

    @staticmethod
    def generate_barriers_and_labels(
        df: pd.DataFrame,
        atr_col: str = 'atr_14',
        sl_mult: float = 1.0,
        tp_mult: float = 1.5,
        horizon_bars: int = 15
    ) -> pd.DataFrame:
        """
        Labels:
            1.0 = Win (Hit TP before SL and before time expiry)
            0.0 = Loss (Hit SL before TP)
            np.nan = Inconclusive / uncompleted window (to be cleanly dropped)
        """
        df_out = df.copy()
        
        # Initialize with np.nan to prevent fabricated loss corruption
        df_out['target_long'] = np.nan
        df_out['target_short'] = np.nan

        highs = df['high'].values
        lows = df['low'].values
        closes = df['close'].values
        atrs = df[atr_col].values
        n = len(df)

        for i in range(n - horizon_bars):
            entry_price = closes[i]
            current_atr = atrs[i]

            if np.isnan(current_atr) or current_atr <= 0:
                continue

            # --- LONG BARRIERS (1:1.5 RRR) ---
            long_tp = entry_price + (tp_mult * current_atr)
            long_sl = entry_price - (sl_mult * current_atr)

            for j in range(1, horizon_bars + 1):
                idx = i + j
                if highs[idx] >= long_tp and lows[idx] > long_sl:
                    df_out.iat[i, df_out.columns.get_loc('target_long')] = 1.0
                    break
                elif lows[idx] <= long_sl:
                    df_out.iat[i, df_out.columns.get_loc('target_long')] = 0.0
                    break

            # --- SHORT BARRIERS (1:1.5 RRR) ---
            short_tp = entry_price - (tp_mult * current_atr)
            short_sl = entry_price + (sl_mult * current_atr)

            for j in range(1, horizon_bars + 1):
                idx = i + j
                if lows[idx] <= short_tp and highs[idx] < short_sl:
                    df_out.iat[i, df_out.columns.get_loc('target_short')] = 1.0
                    break
                elif highs[idx] >= short_sl:
                    df_out.iat[i, df_out.columns.get_loc('target_short')] = 0.0
                    break

        return df_out
