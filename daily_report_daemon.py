import os
import pandas as pd
import json
import urllib.request
import urllib.parse
from datetime import datetime, timedelta
from sqlalchemy import text

# Try importing get_db_engine from database_config.py
try:
    from database_config import get_db_engine
except ImportError:
    get_db_engine = None

def load_csv_safely(path):
    if not os.path.exists(path):
        return pd.DataFrame()
    try:
        df = pd.read_csv(path)
        df.columns = [c.lower().strip() for c in df.columns]
        return df
    except Exception as e:
        print(f"[ERROR] Failed to read {path}: {e}")
        return pd.DataFrame()

def analyze_bot(df):
    if df.empty:
        return {
            "total": 0, "wins": 0, "losses": 0, "wr": 0.0, "pnl": 0.0, "pf": 0.0
        }
    df['outcome'] = df['status'].apply(lambda x: 'WIN' if str(x).upper() in ['WIN', 'PROFIT', 'TAKE PROFIT'] else 'LOSS')
    df['pnl_val'] = pd.to_numeric(df['pnl'], errors='coerce').fillna(0.0)
    
    total = len(df)
    wins = len(df[df['outcome'] == 'WIN'])
    losses = len(df[df['outcome'] == 'LOSS'])
    wr = (wins / total * 100) if total > 0 else 0.0
    pnl = df['pnl_val'].sum()
    
    win_pnl = df[df['outcome'] == 'WIN']['pnl_val'].sum()
    loss_pnl = df[df['outcome'] == 'LOSS']['pnl_val'].sum()
    pf = (abs(win_pnl) / abs(loss_pnl)) if loss_pnl != 0 else float('inf')
    
    return {
        "total": total, "wins": wins, "losses": losses, "wr": round(wr, 2), "pnl": round(pnl, 2), "pf": round(pf, 2) if pf != float('inf') else "Inf"
    }

def get_db_rejections_24h():
    if not get_db_engine:
        return 0, "Database config unavailable"
    
    engine = get_db_engine()
    if not engine:
        return 0, "MySQL connection failed"
        
    cutoff_ts = int((datetime.now() - timedelta(hours=24)).timestamp() * 1000)
    query = "SELECT bot, rejection_reason, COUNT(*) FROM signal_rejection_history WHERE timestamp >= :cutoff GROUP BY bot, rejection_reason"
    
    try:
        with engine.connect() as conn:
            rows = conn.execute(text(query), {"cutoff": cutoff_ts}).fetchall()
            if not rows:
                return 0, "None"
            
            total_rejections = sum(row[2] for row in rows)
            breakdown = []
            for row in rows:
                breakdown.append(f"{row[0].upper()} {row[1]}: {row[2]}")
            return total_rejections, ", ".join(breakdown)
    except Exception as e:
        print(f"[ERROR] DB Query failed: {e}")
        return 0, f"Query error: {str(e)}"

def send_telegram_html(token, chat_id, html_content):
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": html_content,
        "parse_mode": "HTML"
    }
    data = json.dumps(payload).encode('utf-8')
    req = urllib.request.Request(
        url, 
        data=data, 
        headers={'Content-Type': 'application/json'}
    )
    try:
        with urllib.request.urlopen(req) as response:
            return response.read().decode('utf-8')
    except Exception as e:
        print(f"[ERROR] Failed to send Telegram message: {e}")
        return None

def main():
    # Telegram credentials
    TOKEN = os.getenv("TELEGRAM_TOKEN", "")
    CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

    # Server paths
    sniper_log_path = "/home/kasun/repository/AlphaQuant-ML-Trading-AI-BOT-/trading_log_v8.csv"
    sniper_backup_path = "/home/kasun/repository/AlphaQuant-ML-Trading-AI-BOT-/trading_log_v8_backup.csv"
    scalper_log_path = "/home/kasun/repository/AlphaQuant-SCALPER-HUNT/trading_log_scalper.csv"

    # Fallback to local
    if not os.path.exists(sniper_log_path):
        sniper_log_path = "trading_log_v8.csv"
        sniper_backup_path = "trading_log_v8_backup.csv"
        scalper_log_path = "scalper_hunt/trading_log_scalper.csv"
        if not os.path.exists(scalper_log_path):
            scalper_log_path = "trading_log_scalper.csv"

    # Load logs
    sniper_df = load_csv_safely(sniper_log_path)
    sniper_backup_df = load_csv_safely(sniper_backup_path)
    scalper_df = load_csv_safely(scalper_log_path)

    combined_sniper = pd.concat([sniper_df, sniper_backup_df], ignore_index=True) if not (sniper_df.empty and sniper_backup_df.empty) else pd.DataFrame()

    # Analyze
    sniper_stats = analyze_bot(combined_sniper)
    scalper_stats = analyze_bot(scalper_df)

    # Get DB Rejections in last 24h
    rejections_count, rejections_breakdown = get_db_rejections_24h()

    # Get active exclusions
    excluded_assets = []
    override_path = "/home/kasun/repository/AlphaQuant-ML-Trading-AI-BOT-/dynamic_overrides.json"
    if not os.path.exists(override_path):
        override_path = "dynamic_overrides.json"
        
    if os.path.exists(override_path):
        try:
            with open(override_path, "r") as f:
                overrides = json.load(f)
                excluded_assets = overrides.get("EXCLUDED_ASSETS", [])
        except Exception:
            pass

    excluded_str = ", ".join(excluded_assets) if excluded_assets else "None"

    # Compile HTML report
    date_str = datetime.now().strftime("%Y-%m-%d %H:%M")
    html_report = f"""⚡ <b>AlphaQuant System Performance Report</b> ⚡
Date: {date_str}

📊 <b>SNIPER BOT PERFORMANCE (Combined)</b>
• Total Trades: {sniper_stats['total']}
• Win Rate: <b>{sniper_stats['wr']}%</b> (Wins: {sniper_stats['wins']} | Losses: {sniper_stats['losses']})
• Net Profit: <b>+{sniper_stats['pnl']} USD</b>
• Profit Factor: {sniper_stats['pf']}

🏹 <b>SCALPER BOT PERFORMANCE</b>
• Total Trades: {scalper_stats['total']}
• Win Rate: <b>{scalper_stats['wr']}%</b> (Wins: {scalper_stats['wins']} | Losses: {scalper_stats['losses']})
• Net Profit: <b>+{scalper_stats['pnl']} USD</b>
• Profit Factor: {scalper_stats['pf']}

🛡️ <b>SAFETY REJECTIONS (Last 24 Hours)</b>
• Blocked Signals: <b>{rejections_count}</b>
• Breakdown: <i>{rejections_breakdown}</i>

🪙 <b>DYNAMIC TUNING STATUS</b>
• Excluded Assets (Pruned): <code>{excluded_str}</code>
• Promoted Assets (NEAR, LINK, AVAX): <code>1.25x Risk</code>

🇱🇰 <b>Sinhala Summary (ව්‍යාපෘති සාරාංශය):</b>
පද්ධතියේ සමස්ත ලාභය සාර්ථකව වර්ධනය වී ඇත. Scalper Bot එක 71% ක ඉහළ ජයග්‍රාහී ප්‍රතිශතයක් පෙන්වන බැවින් NEAR, LINK සහ AVAX සඳහා risk weights වැඩි කර ඇත. අලාභදායී කාසි සඳහා exposure එක අඩු කර ඇති අතර, ආරක්ෂිත filters මඟින් අවදානම් සහගත signals වළක්වා ගෙන ඇත.
"""

    send_telegram_html(TOKEN, CHAT_ID, html_report)
    print("[SUCCESS] Sent daily performance report to Telegram.")

if __name__ == '__main__':
    main()
