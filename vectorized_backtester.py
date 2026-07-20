import sqlite3
import pandas as pd
import numpy as np

DB_NAME = "alphaquant_ml_v4.db"

class VectorizedBacktester:
    def __init__(self, initial_capital=1000.0, leverage=10, taker_fee_pct=0.0004):
        self.initial_capital = initial_capital
        self.leverage = leverage
        self.taker_fee_pct = taker_fee_pct 
        
        print("==================================================")
        print("  ALPHAQUANT V4.0: VECTORIZED BACKTEST ENGINE     ")
        print("==================================================")

    def calculate_ema(self, series, span):
        return series.ewm(span=span, adjust=False).mean()

    def calculate_atr(self, df, period=14):
        high_low = df['high'] - df['low']
        high_close = np.abs(df['high'] - df['close'].shift())
        low_close = np.abs(df['low'] - df['close'].shift())
        ranges = pd.concat([high_low, high_close, low_close], axis=1)
        return np.max(ranges, axis=1).rolling(window=period).mean()

    def load_historical_data(self, asset):
        print(f"[SYSTEM] Loading historical data for {asset}...")
        conn = sqlite3.connect(DB_NAME)
        query = f"SELECT timestamp, datetime, open, high, low, close, volume FROM market_data_1h WHERE asset = '{asset}' ORDER BY timestamp ASC"
        df = pd.read_sql_query(query, conn)
        conn.close()
        
        if df.empty:
            print(f"[ERROR] No data found for {asset}. Run data_ingestion.py first.")
            return None
            
        df['datetime'] = pd.to_datetime(df['datetime'])
        df.set_index('datetime', inplace=True)
        return df

    def generate_signals(self, df):
        print("[SYSTEM] Vectorizing trading logic (EMAs, ATR, Signals)...")
        
        df['ema_50'] = self.calculate_ema(df['close'], 50)
        df['ema_200'] = self.calculate_ema(df['close'], 200)
        df['atr'] = self.calculate_atr(df, 14)
        
        df['prev_close'] = df['close'].shift(1)
        df['prev_ema_50'] = df['ema_50'].shift(1)
        df['prev_ema_200'] = df['ema_200'].shift(1)
        df['prev_atr'] = df['atr'].shift(1)

        df['is_bullish'] = (df['prev_close'] > df['prev_ema_50']) & (df['prev_close'] > df['prev_ema_200'])
        df['is_bearish'] = (df['prev_close'] < df['prev_ema_50']) & (df['prev_close'] < df['prev_ema_200'])
        
        df['entry_price'] = df['open']
        
        df['sl_offset'] = df['prev_atr'] * 1.5
        df['tp_offset'] = df['sl_offset'] * 2.0
        
        df['signal'] = 0 
        df['tp_target'] = np.nan
        df['sl_target'] = np.nan
        
        long_condition = df['is_bullish'] == True
        df.loc[long_condition, 'signal'] = 1
        df.loc[long_condition, 'sl_target'] = df['entry_price'] - df['sl_offset']
        df.loc[long_condition, 'tp_target'] = df['entry_price'] + df['tp_offset']
        
        short_condition = df['is_bearish'] == True
        df.loc[short_condition, 'signal'] = -1
        df.loc[short_condition, 'sl_target'] = df['entry_price'] + df['sl_offset']
        df.loc[short_condition, 'tp_target'] = df['entry_price'] - df['tp_offset']

        return df.dropna(subset=['signal', 'tp_target', 'sl_target'])

    def run_backtest(self, df):
        print("[SYSTEM] Simulating execution and resolving trades...")
        
        trades = []
        in_trade = False
        trade_type = 0
        entry_price = 0
        tp_target = 0
        sl_target = 0
        entry_time = None
        
        for index, row in df.iterrows():
            if not in_trade:
                if row['signal'] == 1:
                    in_trade = True
                    trade_type = 1
                    entry_price = row['entry_price']
                    tp_target = row['tp_target']
                    sl_target = row['sl_target']
                    entry_time = index
                elif row['signal'] == -1:
                    in_trade = True
                    trade_type = -1
                    entry_price = row['entry_price']
                    tp_target = row['tp_target']
                    sl_target = row['sl_target']
                    entry_time = index
            else:
                hit_tp = False
                hit_sl = False
                exit_price = 0
                
                if trade_type == 1: 
                    if row['low'] <= sl_target:
                        hit_sl = True
                        exit_price = sl_target
                    elif row['high'] >= tp_target:
                        hit_tp = True
                        exit_price = tp_target
                
                elif trade_type == -1: 
                    if row['high'] >= sl_target:
                        hit_sl = True
                        exit_price = sl_target
                    elif row['low'] <= tp_target:
                        hit_tp = True
                        exit_price = tp_target
                
                if hit_tp or hit_sl:
                    margin = 100.0 
                    notional_size = margin * self.leverage
                    
                    if trade_type == 1:
                        price_change_pct = (exit_price - entry_price) / entry_price
                    else:
                        price_change_pct = (entry_price - exit_price) / entry_price
                        
                    gross_pnl = notional_size * price_change_pct
                    
                    fees = (notional_size * self.taker_fee_pct) * 2
                    net_pnl = gross_pnl - fees
                    
                    trades.append({
                        'entry_time': entry_time,
                        'exit_time': index,
                        'type': 'LONG' if trade_type == 1 else 'SHORT',
                        'result': 'WIN' if hit_tp else 'LOSS',
                        'net_pnl': net_pnl
                    })
                    
                    in_trade = False 

        return pd.DataFrame(trades)

    def generate_tear_sheet(self, trades_df, asset):
        if trades_df.empty:
            print(f"\n[RESULTS] No trades executed for {asset}.")
            return

        print(f"\n==================================================")
        print(f"  BACKTEST RESULTS: {asset} ")
        print(f"==================================================")
        
        total_trades = len(trades_df)
        wins = len(trades_df[trades_df['result'] == 'WIN'])
        losses = len(trades_df[trades_df['result'] == 'LOSS'])
        win_rate = (wins / total_trades) * 100
        
        gross_profit = trades_df[trades_df['net_pnl'] > 0]['net_pnl'].sum()
        gross_loss = abs(trades_df[trades_df['net_pnl'] < 0]['net_pnl'].sum())
        net_profit = trades_df['net_pnl'].sum()
        
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else float('inf')
        
        trades_df['cumulative_pnl'] = trades_df['net_pnl'].cumsum()
        trades_df['peak'] = trades_df['cumulative_pnl'].cummax()
        trades_df['drawdown'] = trades_df['cumulative_pnl'] - trades_df['peak']
        max_drawdown = trades_df['drawdown'].min()
        
        print(f"Total Trades:      {total_trades}")
        print(f"Win Rate:          {win_rate:.2f}% ({wins} W / {losses} L)")
        print(f"Net Profit:        ${net_profit:.2f} USDT")
        print(f"Profit Factor:     {profit_factor:.2f}")
        print(f"Max Drawdown:      ${max_drawdown:.2f} USDT")
        
        if profit_factor > 1.5 and win_rate >= 33.0:
            print("\n[VERDICT] 🟢 STRATEGY IS MATHEMATICALLY SOUND.")
        elif profit_factor > 1.0:
            print("\n[VERDICT] 🟡 STRATEGY IS BREAKEVEN / WEAK. Needs optimization.")
        else:
            print("\n[VERDICT] 🔴 STRATEGY IS BLEEDING MONEY. Do not deploy.")
        print("==================================================\n")

if __name__ == "__main__":
    tester = VectorizedBacktester()
    
    asset = "BTC/USDT"
    df = tester.load_historical_data(asset)
    
    if df is not None:
        signal_df = tester.generate_signals(df)
        trades = tester.run_backtest(signal_df)
        tester.generate_tear_sheet(trades, asset)