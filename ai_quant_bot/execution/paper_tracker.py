import os
import csv
from datetime import datetime, timezone
import pandas as pd

class PaperTradeTracker:
    """Manages persistent virtual trade logging, position tracking, and win rate analysis."""

    def __init__(self, log_path: str = None):
        if log_path is None:
            # Default to root repository directory
            repo_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            self.log_path = os.path.join(repo_root, "trading_log_paper.csv")
        else:
            self.log_path = log_path
            
        self.active_positions = {}
        self._ensure_log_file()
        self._load_active_positions()

    def _ensure_log_file(self):
        """Creates the CSV file with standard columns if it doesn't exist."""
        if not os.path.exists(self.log_path):
            with open(self.log_path, mode='w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow([
                    "trade_id", "timestamp", "symbol", "direction",
                    "entry", "sl", "tp", "quantity", "status",
                    "win_prob", "pnl", "exit_price", "exit_time"
                ])

    def _load_active_positions(self):
        """Loads pending/open positions from CSV on boot."""
        if not os.path.exists(self.log_path):
            return
            
        try:
            df = pd.read_csv(self.log_path)
            if df.empty:
                return
            open_trades = df[df['status'] == 'OPEN']
            for _, row in open_trades.iterrows():
                self.active_positions[row['trade_id']] = row.to_dict()
        except Exception as e:
            print(f"[PAPER TRACKER] Warning: Failed to reload open trades: {e}")

    def record_entry(self, symbol: str, direction: str, entry: float, sl: float, tp: float, quantity: float, win_prob: float) -> dict:
        """Logs a newly executed paper trade and stores it in active tracking."""
        trade_id = f"sim_{int(datetime.now(timezone.utc).timestamp())}_{symbol.replace('/', '_')}"
        now_str = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')
        
        trade = {
            "trade_id": trade_id,
            "timestamp": now_str,
            "symbol": symbol,
            "direction": direction,
            "entry": float(entry),
            "sl": float(sl),
            "tp": float(tp),
            "quantity": float(quantity),
            "status": "OPEN",
            "win_prob": f"{win_prob:.2f}%",
            "pnl": 0.0,
            "exit_price": 0.0,
            "exit_time": ""
        }
        
        self.active_positions[trade_id] = trade
        
        with open(self.log_path, mode='a', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=list(trade.keys()))
            writer.writerow(trade)
            
        return trade

    def update_positions(self, candle_dict_or_prices: dict) -> list:
        """
        Evaluates active positions against latest high/low/close prices to check TP/SL hits.
        Returns a list of closed trade summary dicts.
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
                    status = "LOSS"
                    exit_price = sl
            elif direction == "SHORT":
                if low <= tp:
                    is_closed = True
                    status = "PROFIT"
                    exit_price = tp
                elif high >= sl:
                    is_closed = True
                    status = "LOSS"
                    exit_price = sl

            if is_closed:
                pnl = (exit_price - entry) * quantity if direction == "LONG" else (entry - exit_price) * quantity
                pos["status"] = status
                pos["exit_price"] = exit_price
                pos["pnl"] = round(pnl, 4)
                pos["exit_time"] = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')

                trades_to_remove.append(trade_id)
                closed_events.append(pos.copy())
                self._update_trade_in_csv(pos)

        # Remove closed trades from active memory
        for t_id in trades_to_remove:
            self.active_positions.pop(t_id, None)

        return closed_events

    def _update_trade_in_csv(self, pos: dict):
        """Updates a specific trade row in the CSV file atomically."""
        if not os.path.exists(self.log_path):
            return
        try:
            df = pd.read_csv(self.log_path)
            trade_id = pos.get('trade_id')
            mask = df['trade_id'] == trade_id
            if mask.any():
                for col, val in pos.items():
                    df.loc[mask, col] = val
                df.to_csv(self.log_path, index=False)
        except Exception as e:
            print(f"[PAPER TRACKER] Update trade error: {e}")

    def get_stats(self) -> dict:
        """Calculates win rate and PnL statistics for paper trades."""
        if not os.path.exists(self.log_path):
            return {
                "total_trades": 0, "wins": 0, "losses": 0,
                "win_rate": 0.0, "total_pnl": 0.0, "open_trades": len(self.active_positions)
            }
            
        try:
            df = pd.read_csv(self.log_path)
            if df.empty:
                return {
                    "total_trades": 0, "wins": 0, "losses": 0,
                    "win_rate": 0.0, "total_pnl": 0.0, "open_trades": len(self.active_positions)
                }

            completed = df[df['status'].isin(['PROFIT', 'LOSS'])]
            total_trades = len(completed)
            wins = len(completed[completed['status'] == 'PROFIT'])
            losses = len(completed[completed['status'] == 'LOSS'])
            win_rate = (wins / total_trades * 100.0) if total_trades > 0 else 0.0
            total_pnl = float(completed['pnl'].sum()) if 'pnl' in completed.columns else 0.0

            return {
                "total_trades": total_trades,
                "wins": wins,
                "losses": losses,
                "win_rate": round(win_rate, 2),
                "total_pnl": round(total_pnl, 2),
                "open_trades": len(self.active_positions)
            }
        except Exception as e:
            print(f"[PAPER TRACKER] Stats calculation error: {e}")
            return {
                "total_trades": 0, "wins": 0, "losses": 0,
                "win_rate": 0.0, "total_pnl": 0.0, "open_trades": len(self.active_positions)
            }

    def get_formatted_open_positions(self) -> list:
        """Returns a list of active position dictionaries formatted for Telegram summary reports."""
        res = []
        for pos in self.active_positions.values():
            entry = float(pos["entry"])
            qty = float(pos["quantity"])
            notional = entry * qty
            res.append({
                "symbol": pos["symbol"],
                "direction": pos["direction"],
                "notional": notional,
                "pnl": 0.0 # PnL is tracked at resolution
            })
        return res
