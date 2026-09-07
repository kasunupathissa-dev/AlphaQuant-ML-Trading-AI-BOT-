import os
import pandas as pd
import json
from datetime import datetime, timedelta

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

def run_optimizer():
    # 1. Paths configurations
    sniper_log_path = "/home/kasun/repository/AlphaQuant-ML-Trading-AI-BOT-/trading_log_v8.csv"
    sniper_backup_path = "/home/kasun/repository/AlphaQuant-ML-Trading-AI-BOT-/trading_log_v8_backup.csv"
    scalper_log_path = "/home/kasun/repository/AlphaQuant-SCALPER-HUNT/trading_log_scalper.csv"

    # Local fallback for tests
    if not os.path.exists(sniper_log_path):
        sniper_log_path = "trading_log_v8.csv"
        sniper_backup_path = "trading_log_v8_backup.csv"
        scalper_log_path = "scalper_hunt/trading_log_scalper.csv"
        if not os.path.exists(scalper_log_path):
            scalper_log_path = "trading_log_scalper.csv"

    # 2. Load and merge files
    sniper_df = load_csv_safely(sniper_log_path)
    sniper_backup_df = load_csv_safely(sniper_backup_path)
    scalper_df = load_csv_safely(scalper_log_path)

    # Standardize column headers and format dates
    def process_df(df):
        if df.empty:
            return df
        # Ensure timestamp is parsed
        if 'timestamp' in df.columns:
            df['datetime'] = pd.to_datetime(df['timestamp'], errors='coerce')
        df['pnl_val'] = pd.to_numeric(df['pnl'], errors='coerce').fillna(0.0)
        df['outcome'] = df['status'].apply(lambda x: 'WIN' if str(x).upper() in ['WIN', 'PROFIT', 'TAKE PROFIT'] else 'LOSS')
        return df

    sniper_df = process_df(sniper_df)
    sniper_backup_df = process_df(sniper_backup_df)
    scalper_df = process_df(scalper_df)

    combined_sniper = pd.concat([sniper_df, sniper_backup_df], ignore_index=True) if not (sniper_df.empty and sniper_backup_df.empty) else pd.DataFrame()
    combined_sniper = process_df(combined_sniper)

    # 3. Filter for trailing 14 days
    cutoff_date = datetime.now() - timedelta(days=14)

    def filter_trailing(df):
        if df.empty or 'datetime' not in df.columns:
            return df
        # Filter rows in last 14 days
        return df[df['datetime'] >= cutoff_date]

    sniper_trailing = filter_trailing(combined_sniper)
    scalper_trailing = filter_trailing(scalper_df)

    # If trailing is empty, fallback to the entire dataset to make sure we don't start with empty profiles
    if sniper_trailing.empty:
        sniper_trailing = combined_sniper
    if scalper_trailing.empty:
        scalper_trailing = scalper_df

    # 4. Perform dynamic tuning
    # Base asset lists
    all_assets = [
        "BTC/USDT", "SOL/USDT", "NEAR/USDT", "SUI/USDT", "HBAR/USDT",
        "XRP/USDT", "LINK/USDT", "AVAX/USDT", "DOGE/USDT", "DOT/USDT"
    ]

    sniper_overrides = {"ASSET_RISK_TIERS": {}, "EXCLUDED_ASSETS": []}
    scalper_overrides = {"ASSET_RISK_TIERS": {}, "EXCLUDED_ASSETS": []}

    def compute_overrides(trailing_df, overrides_dict):
        if trailing_df.empty:
            return
        
        for asset, group in trailing_df.groupby('asset'):
            # Standardize symbol format
            symbol = str(asset).strip().upper()
            if "/" not in symbol and "_" in symbol:
                symbol = symbol.replace("_", "/")
            
            c_trades = len(group)
            if c_trades == 0:
                continue
            
            c_wins = len(group[group['outcome'] == 'WIN'])
            c_wr = (c_wins / c_trades) * 100
            c_pnl = group['pnl_val'].sum()

            # Rule 1: Promote Top Assets (WR > 65%)
            if c_wr >= 65.0 and c_trades >= 2:
                overrides_dict["ASSET_RISK_TIERS"][symbol] = 1.25
                print(f"[OPTIMIZER] Promoting {symbol} to 1.25x (Win Rate: {c_wr:.1f}%)")
            # Rule 2: Prune Weak Assets (WR < 40%)
            elif c_wr < 40.0 and c_trades >= 3:
                # If extremely poor (WR < 30% or severe drawdown) -> Exclude completely
                if c_wr < 30.0 or c_pnl < -10.0:
                    overrides_dict["EXCLUDED_ASSETS"].append(symbol)
                    print(f"[OPTIMIZER] Pruning (Excluding) {symbol} due to poor performance (Win Rate: {c_wr:.1f}%, P&L: {c_pnl:.2f})")
                else:
                    overrides_dict["ASSET_RISK_TIERS"][symbol] = 0.25
                    print(f"[OPTIMIZER] Reducing {symbol} exposure to 0.25x (Win Rate: {c_wr:.1f}%)")

    print("--- Tuning Sniper Bot Targets ---")
    compute_overrides(sniper_trailing, sniper_overrides)

    print("\n--- Tuning Scalper Bot Targets ---")
    compute_overrides(scalper_trailing, scalper_overrides)

    # 5. Save override JSON files
    sniper_dest = "/home/kasun/repository/AlphaQuant-ML-Trading-AI-BOT-/dynamic_overrides.json"
    scalper_dest = "/home/kasun/repository/AlphaQuant-SCALPER-HUNT/dynamic_overrides.json"

    # Local fallback for tests
    if not os.path.exists("/home/kasun/repository/AlphaQuant-ML-Trading-AI-BOT-"):
        sniper_dest = "dynamic_overrides.json"
        scalper_dest = "scalper_hunt/dynamic_overrides.json"

    try:
        with open(sniper_dest, "w") as f:
            json.dump(sniper_overrides, f, indent=2)
        print(f"\n[SUCCESS] Wrote Sniper dynamic overrides to {sniper_dest}")

        with open(scalper_dest, "w") as f:
            json.dump(scalper_overrides, f, indent=2)
        print(f"[SUCCESS] Wrote Scalper dynamic overrides to {scalper_dest}")
    except Exception as e:
        print(f"[ERROR] Failed to save overrides: {e}")

if __name__ == '__main__':
    run_optimizer()
