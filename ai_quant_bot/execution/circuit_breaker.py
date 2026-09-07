import time
import asyncio
from ai_quant_bot.monitoring.telegram_notifier import TelegramNotifier

class AutomatedCircuitBreaker:
    """Production Quantitative Circuit Breaker protecting capital against extreme drawdown and volatility."""
    
    def __init__(self, notifier: TelegramNotifier):
        self.notifier = notifier
        self.consecutive_losses = 0
        self.volatility_halt_until = 0.0
        self.drawdown_halt_until = 0.0
        self.daily_starting_equity = None
        self.max_drawdown_pct = 0.05  # -5% limit
        self.max_spread_pct = 0.0008  # 0.08% limit

    def check_spread(self, bid: float, ask: float) -> bool:
        """Returns True if the current bid-ask spread is within the 0.08% safety margin."""
        if bid <= 0 or ask <= 0:
            return False
        spread_pct = (ask - bid) / bid
        if spread_pct > self.max_spread_pct:
            print(f"[CIRCUIT BREAKER] Rejecting order: spread too wide ({spread_pct * 100.0:.3f}% > {self.max_spread_pct * 100.0:.2f}%)")
            return False
        return True

    def register_trade_outcome(self, status: str):
        """Registers trade outcome and implements the consecutive loss lock rules."""
        # Assume status is either 'WIN' or 'LOSS'
        if status.upper() in ('WIN', 'PROFIT', 'TAKE PROFIT'):
            self.consecutive_losses = 0
        else:
            self.consecutive_losses += 1
            if self.consecutive_losses >= 3:
                self.volatility_halt_until = time.time() + (4 * 3600)  # Lock for 4 hours
                print(f"[CIRCUIT BREAKER] 3 consecutive losses hit. Volatility lock active until {self.volatility_halt_until}")
                asyncio.create_task(self.notifier.send_message(
                    "🚨 *[CIRCUIT BREAKER TRIP]*\n3 consecutive losses hit. Halting strategy execution for *4 hours* to let volatility settle."
                ))

    async def check_drawdown_limits(self, current_equity: float, binance_client) -> bool:
        """
        Monitors daily starting equity. Trips circuit breaker if drawdown hits -5%, 
        cancelling limit orders and closing open positions.
        """
        now = time.time()
        
        # Initialize daily starting equity
        if self.daily_starting_equity is None:
            self.daily_starting_equity = current_equity
            return False
            
        drawdown = (current_equity - self.daily_starting_equity) / self.daily_starting_equity
        if drawdown <= -self.max_drawdown_pct:
            self.drawdown_halt_until = now + (24 * 3600)  # Halt for 24 hours
            print(f"[CIRCUIT BREAKER CRITICAL] Daily drawdown reached {drawdown * 100.0:.2f}%. Tripping breaker.")
            
            # Dispatch Alert
            await self.notifier.send_message(
                f"🚨 *[CRITICAL CIRCUIT BREAKER TRIPPED]*\n"
                f"Daily portfolio drawdown hit `{drawdown * 100.0:.2f}%` (Limit: `-{self.max_drawdown_pct * 100.0:.1f}%`).\n"
                f"• *Action*: Cancelling all open orders, closing all active positions to market, and pausing execution for *24 hours*."
            )
            
            # Execute emergency system cleanup
            try:
                # Close all open limit brackets and market exit active positions
                # Note: binance_client.cancel_all_open_orders and market close can be executed here
                await binance_client.exchange.cancel_all_orders()
                # Query open positions and exit them
                positions = await binance_client.exchange.fetch_positions()
                for pos in positions:
                    contracts = float(pos.get('contracts', 0.0))
                    if contracts > 0:
                        symbol = pos['symbol']
                        side = "sell" if pos['side'] == "long" else "buy"
                        print(f"[EMERGENCY CLOSE] Market closing position for {symbol}: {side} {contracts}")
                        await binance_client.exchange.create_order(
                            symbol=symbol,
                            type='market',
                            side=side,
                            amount=contracts
                        )
            except Exception as e:
                print(f"[ERROR] Failed to execute emergency cleanup actions: {e}")
                
            return True
            
        return False

    def is_execution_halted(self) -> bool:
        """Checks if any circuit breaker halts are currently active."""
        now = time.time()
        if now < self.volatility_halt_until:
            return True
        if now < self.drawdown_halt_until:
            return True
        return False

    def reset_daily_equity(self, starting_equity: float):
        """Resets starting balance checkpoint daily."""
        self.daily_starting_equity = starting_equity
        print(f"[CIRCUIT BREAKER] Reset starting daily equity checkpoint to ${starting_equity:.2f}")
