import asyncio
import ccxt.async_support as ccxt
from unified_quant_bot.config.config import (
    BINANCE_API_KEY, BINANCE_API_SECRET, USE_TESTNET, SIMULATION_MODE
)

class BinanceExecutionClient:
    """Binance Futures execution client with simulated paper mode fallback."""

    def __init__(self):
        self.use_testnet = USE_TESTNET
        self.simulation_mode = SIMULATION_MODE
        self.exchange = None
        self.market_definitions = {}

    async def initialize(self):
        options = {'defaultType': 'future'}
        if self.use_testnet:
            options['testnet'] = True

        self.exchange = ccxt.binance({
            'apiKey': BINANCE_API_KEY,
            'secret': BINANCE_API_SECRET,
            'enableRateLimit': True,
            'options': options
        })

        try:
            markets = await self.exchange.load_markets()
            self.market_definitions = markets
            print(f"[BINANCE] Initialized markets. Testnet: {self.use_testnet}, Simulation: {self.simulation_mode}")
        except Exception as e:
            print(f"[BINANCE] Init warning: {e}")

    async def get_margin_balance(self) -> float:
        if self.simulation_mode or not BINANCE_API_KEY:
            return 1000.0 # Default virtual demo balance

        try:
            balance = await self.exchange.fetch_balance()
            return float(balance.get('USDT', {}).get('total', 1000.0))
        except Exception as e:
            return 1000.0

    async def close(self):
        if self.exchange:
            await self.exchange.close()
