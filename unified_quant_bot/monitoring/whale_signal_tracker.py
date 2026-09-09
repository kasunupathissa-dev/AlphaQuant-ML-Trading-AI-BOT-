import os
import csv
import json
from datetime import datetime, timezone
import pandas as pd
from typing import Dict, List, Any, Optional
from unified_quant_bot.config.config import REPO_ROOT

WHALE_LOG_PATH = os.path.join(REPO_ROOT, "whale_copy_signals_log.csv")

WHALE_CSV_COLUMNS = [
    "signal_id", "timestamp", "signal_type", "source_name", "symbol", "direction",
    "entry_price", "tp_target", "sl_target", "tp1_target", "status",
    "peak_mfe_pct", "max_drawdown_pct", "realized_pnl_pct", "exit_price", "exit_time"
]

class WhaleSignalTracker:
    """
    Dedicated Tracking & Accuracy Evaluation Engine for Hyperliquid Whales & Binance Copy Trader Signals.
    Monitors live trajectory, calculates MFE/drawdowns, resolves TP/SL hits, and computes real-time accuracy.
    """

    def __init__(self, log_path: str = WHALE_LOG_PATH):
        self.log_path = log_path
        self.active_signals: Dict[str, Dict[str, Any]] = {}
        self._ensure_log_file()
        self._load_active_signals()

    def _ensure_log_file(self):
        if not os.path.exists(self.log_path):
            with open(self.log_path, mode='w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(WHALE_CSV_COLUMNS)

    def _load_active_signals(self):
        if not os.path.exists(self.log_path):
            return
        try:
            self.active_signals.clear()
            with open(self.log_path, 'r', encoding='utf-8', errors='ignore') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    if row.get('status', '').upper() == 'OPEN':
                        sid = row.get('signal_id')
                        if sid:
                            self.active_signals[sid] = dict(row)
        except Exception as e:
            print(f"[WHALE TRACKER] Load warning: {e}")

    def record_signal(
        self,
        signal_type: str,
        source_name: str,
        symbol: str,
        direction: str,
        entry_price: float,
        tp_target: Optional[float] = None,
        sl_target: Optional[float] = None
    ) -> dict:
        """Records a newly dispatched Whale or Copy Trader signal."""
        direction = direction.upper()
        now_ts = int(datetime.now(timezone.utc).timestamp())
        sig_id = f"sig_{now_ts}_{symbol.replace('/', '_')}_{direction}"
        now_str = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')

        entry = float(entry_price)
        tp = float(tp_target if tp_target else (entry * 1.03 if direction == "LONG" else entry * 0.97))
        sl = float(sl_target if sl_target else (entry * 0.985 if direction == "LONG" else entry * 1.015))
        tp1 = float(entry * 1.015 if direction == "LONG" else entry * 0.985)

        sig_data = {
            "signal_id": sig_id,
            "timestamp": now_str,
            "signal_type": signal_type,
            "source_name": source_name,
            "symbol": symbol,
            "direction": direction,
            "entry_price": entry,
            "tp_target": tp,
            "sl_target": sl,
            "tp1_target": tp1,
            "status": "OPEN",
            "peak_mfe_pct": 0.0,
            "max_drawdown_pct": 0.0,
            "realized_pnl_pct": 0.0,
            "exit_price": 0.0,
            "exit_time": ""
        }

        self.active_signals[sig_id] = sig_data

        with open(self.log_path, mode='a', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=WHALE_CSV_COLUMNS)
            writer.writerow({k: sig_data.get(k, "") for k in WHALE_CSV_COLUMNS})

        print(f"[WHALE TRACKER] Recorded new {signal_type} signal for {symbol} ({direction}) @ ${entry:.4f}")
        return sig_data

    def update_prices(self, price_dict_or_candles: dict) -> list:
        """
        Evaluates active signals against real-time high/low/close prices.
        Returns list of resolved signal events.
        """
        resolved_events = []
        if not self.active_signals or not price_dict_or_candles:
            return resolved_events

        signals_to_remove = []

        for sig_id, sig in list(self.active_signals.items()):
            symbol = sig.get("symbol")
            p_data = price_dict_or_candles.get(symbol)
            if not p_data:
                continue

            if isinstance(p_data, dict):
                high = float(p_data.get('high', p_data.get('close', 0.0)))
                low = float(p_data.get('low', p_data.get('close', 0.0)))
                close = float(p_data.get('close', 0.0))
            else:
                high = low = close = float(p_data)

            direction = sig.get("direction", "LONG").upper()
            entry = float(sig.get("entry_price", 0.0) or 0.0)
            tp = float(sig.get("tp_target", 0.0) or 0.0)
            sl = float(sig.get("sl_target", 0.0) or 0.0)

            if entry <= 0:
                continue

            # Update Peak MFE and Drawdown
            if direction == "LONG":
                mfe = ((high - entry) / entry) * 100.0
                mae = ((low - entry) / entry) * 100.0
                curr_peak = float(sig.get("peak_mfe_pct", 0.0) or 0.0)
                curr_draw = float(sig.get("max_drawdown_pct", 0.0) or 0.0)
                sig["peak_mfe_pct"] = round(max(curr_peak, mfe), 2)
                sig["max_drawdown_pct"] = round(min(curr_draw, mae), 2)

                # Dynamic Breakeven & Trailing SL adjustment
                if sig["peak_mfe_pct"] >= 1.0 and sl < entry:
                    sl = entry * 1.001 # Move SL to Breakeven (+0.1% buffer)
                    sig["sl_target"] = round(sl, 4)

                is_resolved = False
                status = "OPEN"
                exit_p = close
                ret_pct = 0.0

                if high >= tp:
                    is_resolved = True
                    status = "TP_HIT"
                    exit_p = tp
                    ret_pct = 3.0
                elif sig["peak_mfe_pct"] >= 1.2 and low <= sl:
                    is_resolved = True
                    status = "TP1_HIT"
                    exit_p = sl
                    ret_pct = 0.8
                elif low <= sl:
                    is_resolved = True
                    status = "BE_HIT" if sl >= entry else "SL_HIT"
                    exit_p = sl
                    ret_pct = 0.1 if sl >= entry else -1.5
            else: # SHORT
                mfe = ((entry - low) / entry) * 100.0
                mae = ((entry - high) / entry) * 100.0
                curr_peak = float(sig.get("peak_mfe_pct", 0.0) or 0.0)
                curr_draw = float(sig.get("max_drawdown_pct", 0.0) or 0.0)
                sig["peak_mfe_pct"] = round(max(curr_peak, mfe), 2)
                sig["max_drawdown_pct"] = round(min(curr_draw, mae), 2)

                # Dynamic Breakeven & Trailing SL adjustment
                if sig["peak_mfe_pct"] >= 1.0 and sl > entry:
                    sl = entry * 0.999 # Move SL to Breakeven (+0.1% buffer)
                    sig["sl_target"] = round(sl, 4)

                is_resolved = False
                status = "OPEN"
                exit_p = close
                ret_pct = 0.0

                if low <= tp:
                    is_resolved = True
                    status = "TP_HIT"
                    exit_p = tp
                    ret_pct = 3.0
                elif sig["peak_mfe_pct"] >= 1.2 and high >= sl:
                    is_resolved = True
                    status = "TP1_HIT"
                    exit_p = sl
                    ret_pct = 0.8
                elif high >= sl:
                    is_resolved = True
                    status = "BE_HIT" if sl <= entry else "SL_HIT"
                    exit_p = sl
                    ret_pct = 0.1 if sl <= entry else -1.5

            if is_resolved:
                sig["status"] = status
                sig["exit_price"] = exit_p
                sig["realized_pnl_pct"] = ret_pct
                sig["exit_time"] = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')

                signals_to_remove.append(sig_id)
                resolved_events.append(sig.copy())
                self._update_signal_in_csv(sig)
                print(f"[WHALE TRACKER] Signal {sig_id} ({symbol} {direction}) RESOLVED: {status} @ ${exit_p:.4f} ({ret_pct:+.1f}%)")

        for s_id in signals_to_remove:
            self.active_signals.pop(s_id, None)

        return resolved_events

    def _update_signal_in_csv(self, sig: dict):
        if not os.path.exists(self.log_path):
            return
        try:
            sig_id = str(sig.get('signal_id'))
            updated_rows = []
            with open(self.log_path, 'r', encoding='utf-8', errors='ignore') as f:
                reader = csv.DictReader(f)
                fields = reader.fieldnames or WHALE_CSV_COLUMNS
                for row in reader:
                    if row.get('signal_id') == sig_id:
                        for k, v in sig.items():
                            if k in fields:
                                row[k] = str(v)
                    updated_rows.append(row)

            with open(self.log_path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=fields)
                writer.writeheader()
                writer.writerows(updated_rows)
        except Exception as e:
            print(f"[WHALE TRACKER] CSV update error: {e}")

    def get_accuracy_metrics(self) -> dict:
        """Computes statistical accuracy breakdown of all historical whale and copy trader signals."""
        if not os.path.exists(self.log_path):
            return {
                "total_signals": 0, "tp_hits": 0, "sl_hits": 0,
                "full_tp_winrate": 0.0, "partial_tp_rate": 0.0, "avg_peak_mfe": 0.0,
                "signals": []
            }
        try:
            signals = []
            with open(self.log_path, 'r', encoding='utf-8', errors='ignore') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    signals.append(row)

            completed = [s for s in signals if s.get('status', '').upper() in ('TP_HIT', 'TP1_HIT', 'BE_HIT', 'SL_HIT', 'WIN', 'LOSS', 'PROFIT')]
            tp_hits = sum(1 for s in completed if s.get('status', '').upper() in ('TP_HIT', 'TP1_HIT', 'BE_HIT', 'WIN', 'PROFIT') or float(s.get('realized_pnl_pct', 0.0) or 0.0) > 0)
            sl_hits = len(completed) - tp_hits
            total_comp = len(completed)

            full_winrate = (tp_hits / total_comp * 100.0) if total_comp > 0 else 0.0

            # Partial TP1 (+1.5%) reach rate
            partial_hits = sum(1 for s in signals if float(s.get('peak_mfe_pct', 0.0) or 0.0) >= 1.5)
            partial_rate = (partial_hits / len(signals) * 100.0) if len(signals) > 0 else 0.0

            # Average Peak MFE
            mfes = [float(s.get('peak_mfe_pct', 0.0) or 0.0) for s in signals]
            avg_mfe = (sum(mfes) / len(mfes)) if mfes else 0.0

            return {
                "total_signals": len(signals),
                "active_signals": len(self.active_signals),
                "completed_signals": total_comp,
                "tp_hits": tp_hits,
                "sl_hits": sl_hits,
                "full_tp_winrate": round(full_winrate, 2),
                "partial_tp_rate": round(partial_rate, 2),
                "avg_peak_mfe": round(avg_mfe, 2),
                "signals": signals[::-1][:50]
            }
        except Exception as e:
            print(f"[WHALE TRACKER] Metrics calculation error: {e}")
            return {
                "total_signals": 0, "tp_hits": 0, "sl_hits": 0,
                "full_tp_winrate": 0.0, "partial_tp_rate": 0.0, "avg_peak_mfe": 0.0,
                "signals": []
            }
