import asyncio
import ccxt.pro as ccxtpro
import ccxt
from ai_quant_bot.config.config import BINANCE_API_KEY, BINANCE_API_SECRET, USE_TESTNET, SIMULATION_MODE

class BinanceFuturesExecutionClient:
    """Asynchronous Production Binance Futures CCXT Pro Execution Client."""

    def __init__(self):
        # ccxt.pro inherits standard async REST client capability
        self.exchange = ccxtpro.binance({
            'apiKey': BINANCE_API_KEY,
            'secret': BINANCE_API_SECRET,
            'options': {
                'defaultType': 'future',
                'adjustForTimeDifference': True
            },
            'enableRateLimit': True,
        })
        self.exchange.set_sandbox_mode(USE_TESTNET)
        self.markets = {}

    async def initialize(self):
        """Pre-loads markets to enable rapid symbol normalization and lot sizing audits."""
        self.markets = await self.exchange.load_markets()
        print("[EXECUTION] Binance CCXT Pro market data pre-loaded.")

    def normalize_ticker_symbol(self, symbol: str) -> str:
        """Normalizes any ticker symbol formatting (e.g. SOLUSDT, SOL_USDT) to CCXT standard."""
        sym_upper = symbol.upper().strip().replace("-", "/").replace("_", "/")
        if "USDT" in sym_upper and "/" not in sym_upper:
            sym_upper = sym_upper.replace("USDT", "/USDT")
        
        # Check standard futures suffix
        if ":" not in sym_upper and "USDT" in sym_upper:
            sym_upper = f"{sym_upper}:USDT"
            
        if sym_upper in self.markets:
            return self.markets[sym_upper]['symbol']
        return sym_upper

    def get_market_info(self, symbol: str) -> dict:
        """Fetches precision, limits, and steps for a specific normalized symbol."""
        norm_symbol = self.normalize_ticker_symbol(symbol)
        return self.markets.get(norm_symbol, {})

    async def execute_with_retry(self, func, *args, **kwargs):
        """Asynchronously wraps exchange calls with exponential backoff retries."""
        max_retries = 3
        delay = 1.0
        for attempt in range(max_retries):
            try:
                return await func(*args, **kwargs)
            except (ccxt.RateLimitExceeded, ccxt.DDoSProtection) as e:
                print(f"[EXECUTION RETRY] Rate limit hit on attempt {attempt+1}. Retrying in {delay}s... Error: {e}")
                await asyncio.sleep(delay)
                delay *= 2.0
            except (ccxt.InsufficientFunds, ccxt.InvalidOrder) as e:
                print(f"[EXECUTION FATAL] Exchange rejected request due to funds/validation: {e}")
                raise e
            except Exception as e:
                print(f"[EXECUTION RETRY] Error on attempt {attempt+1}. Retrying in {delay}s... Error: {e}")
                await asyncio.sleep(delay)
                delay *= 2.0
        raise Exception("Max execution retries exceeded.")

    async def submit_bracket_trade(self, symbol: str, direction: str, quantity: float, sl: float, tp: float, entry_price: float = None) -> dict:
        """
        Submits market entry order followed by stop-loss and take-profit bracket limits (OCO reduce-only).
        """
        norm_symbol = self.normalize_ticker_symbol(symbol)
        
        if SIMULATION_MODE:
            import time
            fill = entry_price if entry_price is not None else (sl + (tp - sl) / 2.5)
            print(f"[SIMULATION] Virtual order entry submitted for {norm_symbol}: {direction} quantity {quantity:.4f} at ${fill:.4f}")
            return {
                'success': True,
                'entry_id': f'sim_entry_{int(time.time())}',
                'sl_id': f'sim_sl_{int(time.time())}',
                'tp_id': f'sim_tp_{int(time.time())}',
                'filled_price': fill
            }

        side = "buy" if direction == "LONG" else "sell"
        exit_side = "sell" if side == "buy" else "buy"

        try:
            # 1. Enforce Leverage Limit
            try:
                await self.execute_with_retry(self.exchange.set_leverage, 20, norm_symbol)
            except Exception as e_lev:
                print(f"[WARNING] Failed to enforce leverage on {norm_symbol}: {e_lev}")

            # 2. Market Entry Order
            print(f"[EXECUTION] Submitting market entry: {side.upper()} {quantity:.4f} {norm_symbol}")
            entry_order = await self.execute_with_retry(
                self.exchange.create_order,
                symbol=norm_symbol,
                type='market',
                side=side,
                amount=quantity
            )
            filled_price = float(entry_order.get('average', entry_order.get('price', sl)))
            print(f"[EXECUTION] Market entry filled at ${filled_price:.4f}")

            # 3. Submit Stop Loss Order (reduceOnly Stop-Market)
            print(f"[EXECUTION] Submitting Stop-Loss at ${sl:.4f}")
            sl_params = {'stopPrice': sl, 'reduceOnly': True}
            sl_order = await self.execute_with_retry(
                self.exchange.create_order,
                symbol=norm_symbol,
                type='stop_market',
                side=exit_side,
                amount=quantity,
                params=sl_params
            )

            # 4. Submit Take Profit Order (reduceOnly Limit)
            print(f"[EXECUTION] Submitting Take-Profit at ${tp:.4f}")
            tp_params = {'reduceOnly': True}
            tp_order = await self.execute_with_retry(
                self.exchange.create_order,
                symbol=norm_symbol,
                type='limit',
                side=exit_side,
                amount=quantity,
                price=tp,
                params=tp_params
            )

            return {
                'success': True,
                'entry_id': entry_order['id'],
                'sl_id': sl_order['id'],
                'tp_id': tp_order['id'],
                'filled_price': filled_price
            }

        except Exception as e:
            print(f"[ERROR] Bracket trade submission failed for {norm_symbol}: {e}")
            return {'success': False, 'error': str(e)}

    async def get_margin_balance(self) -> float:
        """Fetches the current account margin balance."""
        try:
            balance = await self.execute_with_retry(self.exchange.fetch_balance)
            return float(balance.get('total', {}).get('USDT', 0.0))
        except Exception as e:
            print(f"[ERROR] Failed to fetch margin balance: {e}")
            return 0.0

    async def cancel_all_open_orders(self, symbol: str):
        """Cancels all open orders for the symbol."""
        norm_symbol = self.normalize_ticker_symbol(symbol)
        try:
            await self.execute_with_retry(self.exchange.cancel_all_orders, norm_symbol)
            print(f"[EXECUTION] Cancelled all open orders for {norm_symbol}")
        except Exception as e:
            print(f"[ERROR] Failed to cancel orders for {norm_symbol}: {e}")

    async def close(self):
        """Gracefully closes ccxt.pro sockets."""
        await self.exchange.close()
