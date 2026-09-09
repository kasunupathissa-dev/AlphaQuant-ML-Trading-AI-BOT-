import os
import csv
import json
import asyncio
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Any
from unified_quant_bot.config.config import REPO_ROOT

def generate_progress_bar(win_rate_pct: float, length: int = 10) -> str:
    filled = int(round((win_rate_pct / 100.0) * length))
    filled = max(0, min(length, filled))
    return "█" * filled + "░" * (length - filled)

class HourlySummaryEngine:
    """
    Executes automated hourly performance summary reporting (Design 1: Institutional Executive).
    Aggregates settlements in the last 60 minutes, evaluates active open positions, and sends Telegram digest.
    """

    def __init__(self, log_path: str = None, state_path: str = None):
        self.log_path = log_path or os.path.join(REPO_ROOT, "trading_log_paper.csv")
        self.state_path = state_path or os.path.join(REPO_ROOT, "live_engine_state.json")

    def build_summary_message(self, test_mode: bool = False) -> str:
        now_utc = datetime.now(timezone.utc)
        one_hour_ago = now_utc - timedelta(hours=1)
        
        start_str = one_hour_ago.strftime('%H:00')
        end_str = now_utc.strftime('%H:00')
        today_date_str = now_utc.strftime('%Y-%m-%d')

        # 1. Read settled trades from trading_log_paper.csv
        hourly_closed = []
        today_closed = []
        
        if os.path.exists(self.log_path):
            try:
                with open(self.log_path, 'r', encoding='utf-8', errors='ignore') as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        st = row.get('status', '').upper()
                        if st not in ('PROFIT', 'LOSS', 'WIN', 'TP_HIT', 'SL_HIT'):
                            continue

                        exit_t_str = row.get('exit_time') or row.get('timestamp') or ""
                        try:
                            exit_dt = datetime.strptime(exit_t_str[:19], '%Y-%m-%d %H:%M:%S').replace(tzinfo=timezone.utc)
                            # Today check
                            if exit_t_str.startswith(today_date_str):
                                today_closed.append(row)
                            # Past 60 minutes check
                            if exit_dt >= one_hour_ago or test_mode:
                                hourly_closed.append(row)
                        except Exception:
                            if test_mode or exit_t_str.startswith(today_date_str):
                                today_closed.append(row)
                                hourly_closed.append(row)
            except Exception as e:
                print(f"[HOURLY SUMMARY] Read log error: {e}")

        # If test mode and no trades in last hour, use latest closed trades for preview
        if test_mode and len(hourly_closed) > 5:
            hourly_closed = hourly_closed[-4:]

        # 2. Compute Hourly Metrics
        wins = sum(1 for t in hourly_closed if t.get('status', '').upper() in ('PROFIT', 'WIN', 'TP_HIT') or float(t.get('pnl', 0.0) or 0.0) > 0)
        losses = len(hourly_closed) - wins
        tot_closed = len(hourly_closed)
        hr_wr = (wins / tot_closed * 100.0) if tot_closed > 0 else 0.0
        hr_pnl = sum(float(t.get('pnl', 0.0) or 0.0) for t in hourly_closed)

        # 3. Compute Today's Cumulative Metrics
        td_wins = sum(1 for t in today_closed if t.get('status', '').upper() in ('PROFIT', 'WIN', 'TP_HIT') or float(t.get('pnl', 0.0) or 0.0) > 0)
        td_tot = len(today_closed)
        cum_wr = (td_wins / td_tot * 100.0) if td_tot > 0 else 0.0
        cum_pnl = sum(float(t.get('pnl', 0.0) or 0.0) for t in today_closed) if today_closed else hr_pnl

        gauge_bar = generate_progress_bar(hr_wr if tot_closed > 0 else (cum_wr if td_tot > 0 else 50.0), 10)
        pnl_sign = "+" if hr_pnl >= 0 else ""
        cum_sign = "+" if cum_pnl >= 0 else ""

        if tot_closed > 0:
            hr_wr_str = f"*{hr_wr:.1f}%* `[{gauge_bar}]`"
            wr_emoji = "🟢" if hr_wr >= 50 else "🔴"
            hr_trades_str = f"*{tot_closed} Total* (*{wins}W / {losses}L*)"
        else:
            hr_wr_str = f"`Flat / In Sync (0 Settled in 1H)`"
            wr_emoji = "⚪"
            hr_trades_str = "*0 Closed* (Scanning 24 Streams)"

        if td_tot > 0:
            today_cum_str = f"*{cum_sign}${cum_pnl:.2f}* (Win Rate: *{cum_wr:.1f}%* | *{td_wins}W / {td_tot - td_wins}L*)"
        else:
            today_cum_str = f"*{cum_sign}${cum_pnl:.2f}* (All-Time Active)"

        # 4. Read Live State and Active Positions
        active_positions = []
        live_prices = {}
        smart_money = {}

        if os.path.exists(self.state_path):
            try:
                with open(self.state_path, 'r', encoding='utf-8') as f:
                    s_data = json.load(f)
                    if isinstance(s_data, dict):
                        active_positions = s_data.get("active_trades", [])
                        live_prices = s_data.get("live_prices", {})
                        smart_money = s_data.get("smart_money", {})
            except Exception as e:
                print(f"[HOURLY SUMMARY] Read state error: {e}")

        # 5. Format Closed Positions Block
        closed_lines = []
        if hourly_closed:
            for idx, t in enumerate(hourly_closed[-6:], 1):
                sym = t.get('symbol', t.get('asset', 'UNKNOWN'))
                dir_str = t.get('direction', 'LONG').upper()
                dir_em = "🟢" if dir_str == "LONG" else "🔴"
                entry_p = float(t.get('entry', 0.0) or 0.0)
                exit_p = float(t.get('exit_price', 0.0) or entry_p)
                pnl = float(t.get('pnl', 0.0) or 0.0)
                pnl_str = f"{'+' if pnl >= 0 else ''}${pnl:.2f}"
                st_badge = "✅ TP HIT" if pnl > 0 else "❌ SL HIT"
                closed_lines.append(f"{idx}. {dir_em} *{sym}* `{dir_str}` | `${entry_p:.4f}` ➔ `${exit_p:.4f}` | `{pnl_str}` ({st_badge})")
        else:
            closed_lines.append("• _No settled positions in the last 60 minutes._")

        # 6. Format Active Open Positions Block
        active_lines = []
        if active_positions:
            for idx, pos in enumerate(active_positions, 1):
                sym = pos.get('asset', pos.get('symbol', 'UNKNOWN'))
                dir_str = pos.get('direction', 'LONG').upper()
                dir_em = "🟢" if dir_str == "LONG" else "🔴"
                entry_p = float(pos.get('entry', 0.0) or 0.0)
                qty = float(pos.get('quantity', 1.0) or 1.0)
                curr_p = float(live_prices.get(sym, entry_p))
                
                u_pnl = (curr_p - entry_p) * qty if dir_str == 'LONG' else (entry_p - curr_p) * qty
                u_pct = ((curr_p - entry_p) / entry_p * 100.0) if dir_str == 'LONG' else ((entry_p - curr_p) / entry_p * 100.0)
                
                pnl_str = f"{'+' if u_pnl >= 0 else ''}${u_pnl:.2f}"
                pct_str = f"{'+' if u_pct >= 0 else ''}{u_pct:.2f}%"
                active_lines.append(f"{idx}. {dir_em} *{sym}* `{dir_str}` | Entry: `${entry_p:.4f}` | Live: `${curr_p:.4f}` (`{pnl_str}` / `{pct_str}`)")
        else:
            active_lines.append("• _All positions flat. Engine continuously scanning 24 market streams._")

        closed_block = "\n".join(closed_lines)
        active_block = "\n".join(active_lines)

        next_hour = (now_utc + timedelta(hours=1)).strftime('%H:00 UTC')

        # Design 1: Institutional Executive Layout
        msg = (
            f"⚡ *[ALPHAQUANT] ⚡ HOURLY PERFORMANCE SUMMARY*\n"
            f"🕒 *Period*: `{start_str} - {end_str} UTC` | Status: 🟢 `ONLINE`\n\n"
            f"📊 *HOURLY METRICS*:\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"• *Hourly Win Rate*: {wr_emoji} {hr_wr_str}\n"
            f"• *Trades Executed*: {hr_trades_str}\n"
            f"• *Net Realized P&L*: *{pnl_sign}${hr_pnl:.2f} USD*\n"
            f"• *Today's Cumulative*: {today_cum_str}\n\n"
            f"📜 *CLOSED POSITIONS (LAST 1H)*:\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"{closed_block}\n\n"
            f"⚡ *ACTIVE OPEN POSITIONS ({len(active_positions)} ACTIVE)*:\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"{active_block}\n\n"
            f"🛡️ *Risk Guard*: `Operational` | Next Report: `{next_hour}`"
        )
        return msg
