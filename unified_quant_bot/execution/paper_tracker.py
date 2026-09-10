import os
import csv
import json
from datetime import datetime, timezone
import pandas as pd
from unified_quant_bot.config.config import TRADING_LOG_PAPER_PATH, REPO_ROOT

CSV_COLUMNS = [
    "trade_id", "timestamp", "symbol", "direction",
    "strategy", "entry", "sl", "tp", "quantity", "status",
    "win_prob", "pnl", "exit_price", "exit_time",
    "initial_sl", "peak_price", "trough_price", "trailing_active"
]

class PaperTracker:
    """
    High-Fidelity Paper Trading Simulation Engine:
    Maintains active virtual positions, resolves TP/SL hits against live price streams, and computes live win rate.
    """

    def __init__(self, log_path: str = TRADING_LOG_PAPER_PATH):
        self.log_path = log_path
        self.active_positions = {}
        self.all_live_prices = {}
        self._ensure_log_file()
        self._load_active_positions()

    def _ensure_log_file(self):
        if not os.path.exists(self.log_path):
            with open(self.log_path, mode='w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(CSV_COLUMNS)
        else:
            # Check if header matches CSV_COLUMNS
            try:
                with open(self.log_path, 'r', encoding='utf-8', errors='ignore') as f:
                    first_line = f.readline().strip()
                if not first_line.startswith("trade_id") or len(first_line.split(",")) < len(CSV_COLUMNS):
                    self._normalize_existing_csv()
            except Exception as e:
                print(f"[PAPER] Header check error: {e}")

    def _normalize_existing_csv(self):
        """Fixes existing CSV if columns or headers were mismatched."""
        try:
            if not os.path.exists(self.log_path):
                return
            rows = []
            with open(self.log_path, 'r', encoding='utf-8', errors='ignore') as f:
                reader = csv.reader(f)
                header = next(reader, None)
                for r in reader:
                    if not r or len(r) < 8:
                        continue
                    # Pad or truncate to 18 fields
                    row_dict = {}
                    if header and len(header) == len(r):
                        for k, v in zip(header, r):
                            row_dict[k] = v
                    else:
                        for i, val in enumerate(r):
                            if i < len(CSV_COLUMNS):
                                row_dict[CSV_COLUMNS[i]] = val
                    
                    full_row = [str(row_dict.get(col, "")) for col in CSV_COLUMNS]
                    rows.append(full_row)

            with open(self.log_path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(CSV_COLUMNS)
                writer.writerows(rows)
            print(f"[PAPER] Normalized {len(rows)} rows in {self.log_path} to standard {len(CSV_COLUMNS)}-column schema.")
        except Exception as e:
            print(f"[PAPER] CSV normalization error: {e}")

    def get_active_symbols(self) -> set:
        """Returns set of symbols currently having active open positions."""
        return {p.get("symbol") for p in self.active_positions.values() if p.get("symbol")}

    def _load_active_positions(self):
        if not os.path.exists(self.log_path):
            return
        try:
            self.active_positions.clear()
            with open(self.log_path, 'r', encoding='utf-8', errors='ignore') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    if row.get('status', '').upper() == 'OPEN':
                        tid = row.get('trade_id')
                        if tid:
                            self.active_positions[tid] = dict(row)
        except Exception as e:
            print(f"[PAPER] Open trades load warning: {e}")

    def _sync_state_file(self, live_prices: dict = None, smart_money: dict = None):
        """Writes active positions and engine status to live_engine_state.json for web dashboard."""
        try:
            state_file = os.path.join(REPO_ROOT, "live_engine_state.json")
            if live_prices:
                self.all_live_prices.update(live_prices)

            active_list = []
            for tid, pos in self.active_positions.items():
                sym = pos.get('symbol', '')
                entry_p = float(pos.get('entry', 0.0) or 0.0)
                qty = float(pos.get('quantity', 0.0) or 1.0)
                pos_size = entry_p * qty
                active_list.append({
                    "trade_id": tid,
                    "asset": sym,
                    "direction": pos.get('direction', 'LONG'),
                    "strategy": pos.get('strategy', 'StatisticalMeanReversionStrategy'),
                    "entry": entry_p,
                    "sl": float(pos.get('sl', 0.0) or 0.0),
                    "tp": float(pos.get('tp', 0.0) or 0.0),
                    "position_size": pos_size if pos_size > 0 else 100.0,
                    "quantity": qty,
                    "win_prob": pos.get('win_prob', '75.00%'),
                    "entry_time": float(pos.get('entry_time', 0.0) or datetime.now(timezone.utc).timestamp()),
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
                "live_prices": self.all_live_prices,
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
            "win_prob": f"{float(win_prob):.2f}%" if isinstance(win_prob, (int, float)) else str(win_prob),
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
            writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS)
            writer.writerow({k: trade.get(k, "") for k in CSV_COLUMNS})

        self.all_live_prices[symbol] = float(entry)
        self._sync_state_file({symbol: float(entry)})
        return trade

    def update_positions(self, candle_dict_or_prices: dict) -> list:
        """
        Evaluates active virtual positions against live candle high/low/close prices.
        Returns resolved closed position dicts.
        """
        # 1. Update in-memory live price map
        if candle_dict_or_prices:
            for s, p_data in candle_dict_or_prices.items():
                if isinstance(p_data, dict):
                    self.all_live_prices[s] = float(p_data.get('close', p_data.get('high', 0.0)))
                elif isinstance(p_data, (int, float)):
                    self.all_live_prices[s] = float(p_data)

        closed_events = []
        if not self.active_positions:
            self._sync_state_file(self.all_live_prices)
            return closed_events

        # 2. Check if any position was manually closed in CSV externally by dashboard
        try:
            with open(self.log_path, 'r', encoding='utf-8', errors='ignore') as f:
                reader = csv.DictReader(f)
                open_tids = {row['trade_id'] for row in reader if row.get('status', '').upper() == 'OPEN'}
            
            for tid in list(self.active_positions.keys()):
                if tid not in open_tids:
                    print(f"[PAPER] Position {tid} was closed externally via dashboard. Removing from tracker.")
                    self.active_positions.pop(tid, None)
        except Exception:
            pass

        trades_to_remove = []

        for trade_id, pos in list(self.active_positions.items()):
            symbol = pos["symbol"]
            price_data = candle_dict_or_prices.get(symbol) if candle_dict_or_prices else None
            if not price_data and symbol in self.all_live_prices:
                price_data = self.all_live_prices[symbol]
                
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
            init_sl = float(pos.get("initial_sl", sl) or sl)
            approx_atr = abs(entry - init_sl) / 1.5 if abs(entry - init_sl) > 0 else (entry * 0.01)

            # 🟢 Dynamic Fee-Immune Volatility Trailing Stop Ratchet:
            min_fee_buffer = entry * 0.0025 # Guaranteed +0.25% buffer to cover 0.10% roundtrip taker fee + clear profit
            min_activation_profit = max(entry * 0.006, 1.0 * approx_atr) # Requires at least +0.60% gross move to activate trailing

            if direction == "LONG":
                peak_p = float(pos.get("peak_price", entry) or entry)
                if high > peak_p:
                    pos["peak_price"] = high
                
                # Activate trailing profit protection only after reaching >= +0.60% / 1.0x ATR
                if (high - entry) >= min_activation_profit:
                    pos["trailing_active"] = True
                    be_level = entry + max(0.3 * approx_atr, min_fee_buffer)
                    trailing_sl = float(pos["peak_price"]) - (1.2 * approx_atr)
                    new_sl = max(sl, max(be_level, trailing_sl))
                    if new_sl > sl:
                        sl = round(new_sl, 4)
                        pos["sl"] = sl

            elif direction == "SHORT":
                trough_p = float(pos.get("trough_price", entry) or entry)
                if low < trough_p:
                    pos["trough_price"] = low
                
                # Activate trailing profit protection only after reaching >= +0.60% / 1.0x ATR
                if (entry - low) >= min_activation_profit:
                    pos["trailing_active"] = True
                    be_level = entry - max(0.3 * approx_atr, min_fee_buffer)
                    trailing_sl = float(pos["trough_price"]) + (1.2 * approx_atr)
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
                final_status = "PROFIT" if net_pnl > 0 else "LOSS"
                pos["status"] = final_status
                pos["exit_price"] = exit_price
                pos["pnl"] = round(net_pnl, 4)
                pos["exit_time"] = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')

                trades_to_remove.append(trade_id)
                closed_events.append(pos.copy())
                self._update_trade_in_csv(pos)
                print(f"[PAPER] Trade {trade_id} ({symbol} {direction}) CLOSED with {final_status} at ${exit_price:.4f} (Net P&L: ${net_pnl:.2f})")


        for t_id in trades_to_remove:
            self.active_positions.pop(t_id, None)

        self._sync_state_file(self.all_live_prices)
        return closed_events

    def _update_trade_in_csv(self, pos: dict):
        if not os.path.exists(self.log_path):
            return
        try:
            trade_id = str(pos.get('trade_id'))
            updated_rows = []
            found = False
            with open(self.log_path, 'r', encoding='utf-8', errors='ignore') as f:
                reader = csv.DictReader(f)
                fields = reader.fieldnames or CSV_COLUMNS
                for row in reader:
                    if row.get('trade_id') == trade_id:
                        for k, v in pos.items():
                            if k in fields:
                                row[k] = str(v)
                        found = True
                    updated_rows.append(row)

            if found:
                with open(self.log_path, 'w', newline='', encoding='utf-8') as f:
                    writer = csv.DictWriter(f, fieldnames=fields)
                    writer.writeheader()
                    writer.writerows(updated_rows)
        except Exception as e:
            print(f"[PAPER] CSV sync error: {e}")

    def get_stats(self) -> dict:
        if not os.path.exists(self.log_path):
            return {
                "total_trades": 0, "wins": 0, "losses": 0,
                "win_rate": 0.0, "total_pnl": 0.0, "open_trades": len(self.active_positions)
            }
        try:
            completed = []
            with open(self.log_path, 'r', encoding='utf-8', errors='ignore') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    st = row.get('status', '').upper()
                    if st in ('PROFIT', 'LOSS', 'WIN'):
                        try:
                            row['pnl'] = float(row.get('pnl', 0.0) or 0.0)
                        except ValueError:
                            row['pnl'] = 0.0
                        completed.append(row)

            total = len(completed)
            wins = sum(1 for r in completed if r.get('status', '').upper() in ('PROFIT', 'WIN') or r['pnl'] > 0)
            losses = total - wins
            win_rate = (wins / total * 100.0) if total > 0 else 0.0
            total_pnl = sum(r['pnl'] for r in completed)

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
            entry = float(pos.get("entry", 0.0) or 0.0)
            qty = float(pos.get("quantity", 0.0) or 0.0)
            res.append({
                "symbol": pos.get("symbol", ""),
                "direction": pos.get("direction", "LONG"),
                "notional": round(entry * qty, 2),
                "strategy": pos.get("strategy", "N/A")
            })
        return res
