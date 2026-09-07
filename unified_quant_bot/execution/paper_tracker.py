import os
import csv
import json
from datetime import datetime, timezone
import pandas as pd
from unified_quant_bot.config.config import TRADING_LOG_PAPER_PATH

class PaperTracker:
    """
    High-Fidelity Paper Trading Simulation Engine:
    Maintains active virtual positions, resolves TP/SL hits against live price streams, and computes live win rate.
    """

    def __init__(self, log_path: str = TRADING_LOG_PAPER_PATH):
        self.log_path = log_path
        self.active_positions = {}
        self._ensure_log_file()
        self._load_active_positions()

    def _ensure_log_file(self):
        if not os.path.exists(self.log_path):
            with open(self.log_path, mode='w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow([
                    "trade_id", "timestamp", "symbol", "direction",
                    "strategy", "entry", "sl", "tp", "quantity", "status",
                    "win_prob", "pnl", "exit_price", "exit_time"
                ])

    def _load_active_positions(self):
        if not os.path.exists(self.log_path):
            return
        try:
            df = pd.read_csv(self.log_path, on_bad_lines='skip')
            if df.empty:
                return
            if 'status' in df.columns:
                open_trades = df[df['status'] == 'OPEN']
                for _, row in open_trades.iterrows():
                    self.active_positions[row['trade_id']] = row.to_dict()
        except Exception as e:
            print(f"[PAPER] Open trades load warning: {e}")

    def _sync_state_file(self, live_prices: dict = None, smart_money: dict = None):
        """Writes active positions and engine status to live_engine_state.json for web dashboard."""
        try:
            from unified_quant_bot.config.config import REPO_ROOT
            state_file = os.path.join(REPO_ROOT, "live_engine_state.json")
            active_list = []
            for tid, pos in self.active_positions.items():
                sym = pos.get('symbol', '')
                entry_p = float(pos.get('entry', 0.0))
                qty = float(pos.get('quantity', 0.0))
                pos_size = entry_p * qty
                active_list.append({
                    "trade_id": tid,
                    "asset": sym,
                    "direction": pos.get('direction', 'LONG'),
                    "strategy": pos.get('strategy', 'ShotgunMomentumStrategy'),
                    "entry": entry_p,
                    "sl": float(pos.get('sl', 0.0)),
                    "tp": float(pos.get('tp', 0.0)),
                    "position_size": pos_size if pos_size > 0 else 100.0,
                    "quantity": qty,
                    "win_prob": pos.get('win_prob', '68.50%'),
                    "entry_time": datetime.now(timezone.utc).timestamp(),
                    "half_closed": False
                })

            existing_sm = {}
            if os.path.exists(state_file):
                try:
                    with open(state_file, 'r', encoding='utf-8') as f:
                        old_d = json.load(f)
                        if isinstance(old_d, dict):
                            existing_sm = old_d.get("smart_money", {})
                except Exception:
                    pass

            state_data = {
                "is_active": True,
                "bot_type": "unified",
                "trade_mode": "BOTH",
                "last_update": datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC'),
                "active_trades": active_list,
                "live_prices": live_prices or {},
                "smart_money": smart_money or existing_sm,
                "asset_penalty_box": {},
                "asset_recent_results": {},
                "latest_errors": []
            }

            with open(state_file, 'w', encoding='utf-8') as f:
                json.dump(state_data, f, indent=4)
        except Exception as e:
            print(f"[PAPER] State sync warning: {e}")

    def record_entry(
        self,
        symbol: str,
        direction: str,
        strategy: str,
        entry: float,
        sl: float,
        tp: float,
        quantity: float,
        win_prob: float
    ) -> dict:
        trade_id = f"sim_{int(datetime.now(timezone.utc).timestamp())}_{symbol.replace('/', '_')}"
        now_str = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')

        trade = {
            "trade_id": trade_id,
            "timestamp": now_str,
            "symbol": symbol,
            "direction": direction,
            "strategy": strategy,
            "entry": float(entry),
            "sl": float(sl),
            "tp": float(tp),
            "quantity": float(quantity),
            "status": "OPEN",
            "win_prob": f"{win_prob:.2f}%",
            "pnl": 0.0,
            "exit_price": 0.0,
            "exit_time": "",
            "initial_sl": float(sl),
            "peak_price": float(entry),
            "trough_price": float(entry),
            "trailing_active": False
        }

        self.active_positions[trade_id] = trade

        with open(self.log_path, mode='a', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=list(trade.keys()))
            writer.writerow(trade)

        self._sync_state_file({symbol: float(entry)})
        return trade

    def update_positions(self, candle_dict_or_prices: dict) -> list:
        """
        Evaluates active virtual positions against live candle high/low/close prices.
        Returns resolved closed position dicts.
        """
        closed_events = []
        if not self.active_positions:
            return closed_events

        trades_to_remove = []

        for trade_id, pos in list(self.active_positions.items()):
            symbol = pos["symbol"]
            price_data = candle_dict_or_prices.get(symbol)
            if not price_data:
                continue

            if isinstance(price_data, dict):
                high = float(price_data.get('high', price_data.get('close', 0.0)))
                low = float(price_data.get('low', price_data.get('close', 0.0)))
                close = float(price_data.get('close', 0.0))
            else:
                high = low = close = float(price_data)

            direction = pos["direction"]
            entry = float(pos["entry"])
            sl = float(pos["sl"])
            tp = float(pos["tp"])
            quantity = float(pos["quantity"])

            # Calculate dynamic ATR distance baseline
            init_sl = float(pos.get("initial_sl", sl))
            approx_atr = abs(entry - init_sl) / 1.5 if abs(entry - init_sl) > 0 else (entry * 0.01)

            # 🟢 Dynamic Volatility Trailing Stop Ratchet:
            if direction == "LONG":
                if high > float(pos.get("peak_price", entry)):
                    pos["peak_price"] = high
                
                # If unrealized profit reached >= 1.0x ATR -> activate trailing profit protection
                if (high - entry) >= (1.0 * approx_atr):
                    pos["trailing_active"] = True
                    be_level = entry + (0.2 * approx_atr)
                    trailing_sl = pos["peak_price"] - (1.5 * approx_atr)
                    new_sl = max(sl, max(be_level, trailing_sl))
                    if new_sl > sl:
                        sl = round(new_sl, 4)
                        pos["sl"] = sl

            elif direction == "SHORT":
                if low < float(pos.get("trough_price", entry)):
                    pos["trough_price"] = low
                
                # If unrealized profit reached >= 1.0x ATR -> activate trailing profit protection
                if (entry - low) >= (1.0 * approx_atr):
                    pos["trailing_active"] = True
                    be_level = entry - (0.2 * approx_atr)
                    trailing_sl = pos["trough_price"] + (1.5 * approx_atr)
                    new_sl = min(sl, min(be_level, trailing_sl))
                    if new_sl < sl:
                        sl = round(new_sl, 4)
                        pos["sl"] = sl

            is_closed = False
            status = "OPEN"
            exit_price = close

            if direction == "LONG":
                if high >= tp:
                    is_closed = True
                    status = "PROFIT"
                    exit_price = tp
                elif low <= sl:
                    is_closed = True
                    status = "PROFIT" if pos.get("trailing_active", False) and sl > entry else "LOSS"
                    exit_price = sl
            elif direction == "SHORT":
                if low <= tp:
                    is_closed = True
                    status = "PROFIT"
                    exit_price = tp
                elif high >= sl:
                    is_closed = True
                    status = "PROFIT" if pos.get("trailing_active", False) and sl < entry else "LOSS"
                    exit_price = sl

            if is_closed:
                # Deduct simulated 0.10% taker fee roundtrip
                gross_pnl = (exit_price - entry) * quantity if direction == "LONG" else (entry - exit_price) * quantity
                fee_deduction = (entry * quantity * 0.0005) + (exit_price * quantity * 0.0005)
                net_pnl = gross_pnl - fee_deduction

                pos["status"] = status
                pos["exit_price"] = exit_price
                pos["pnl"] = round(net_pnl, 4)
                pos["exit_time"] = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')

                trades_to_remove.append(trade_id)
                closed_events.append(pos.copy())
                self._update_trade_in_csv(pos)

        for t_id in trades_to_remove:
            self.active_positions.pop(t_id, None)

        # Sync active positions and latest prices with live dashboard state
        price_map = {}
        for s, p_data in candle_dict_or_prices.items():
            if isinstance(p_data, dict):
                price_map[s] = float(p_data.get('close', p_data.get('high', 0.0)))
            elif isinstance(p_data, (int, float)):
                price_map[s] = float(p_data)
        self._sync_state_file(price_map)

        return closed_events

    def _update_trade_in_csv(self, pos: dict):
        if not os.path.exists(self.log_path):
            return
        try:
            df = pd.read_csv(self.log_path, on_bad_lines='skip', dtype=str).fillna('')
            trade_id = str(pos.get('trade_id'))
            mask = df['trade_id'] == trade_id
            if mask.any():
                for col, val in pos.items():
                    if col in df.columns:
                        df.loc[mask, col] = str(val)
                df.to_csv(self.log_path, index=False)
        except Exception as e:
            print(f"[PAPER] CSV sync error: {e}")

    def get_stats(self) -> dict:
        if not os.path.exists(self.log_path):
            return {
                "total_trades": 0, "wins": 0, "losses": 0,
                "win_rate": 0.0, "total_pnl": 0.0, "open_trades": len(self.active_positions)
            }
        try:
            df = pd.read_csv(self.log_path, on_bad_lines='skip')
            if df.empty:
                return {
                    "total_trades": 0, "wins": 0, "losses": 0,
                    "win_rate": 0.0, "total_pnl": 0.0, "open_trades": len(self.active_positions)
                }

            completed = df[df['status'].isin(['PROFIT', 'LOSS'])]
            total = len(completed)
            wins = len(completed[completed['status'] == 'PROFIT'])
            losses = len(completed[completed['status'] == 'LOSS'])
            win_rate = (wins / total * 100.0) if total > 0 else 0.0
            total_pnl = float(completed['pnl'].sum()) if 'pnl' in completed.columns else 0.0

            return {
                "total_trades": total,
                "wins": wins,
                "losses": losses,
                "win_rate": round(win_rate, 2),
                "total_pnl": round(total_pnl, 2),
                "open_trades": len(self.active_positions)
            }
        except Exception as e:
            return {
                "total_trades": 0, "wins": 0, "losses": 0,
                "win_rate": 0.0, "total_pnl": 0.0, "open_trades": len(self.active_positions)
            }

    def get_formatted_open_positions(self) -> list:
        res = []
        for pos in self.active_positions.values():
            entry = float(pos["entry"])
            qty = float(pos["quantity"])
            res.append({
                "symbol": pos["symbol"],
                "direction": pos["direction"],
                "notional": round(entry * qty, 2),
                "strategy": pos.get("strategy", "N/A")
            })
        return res
