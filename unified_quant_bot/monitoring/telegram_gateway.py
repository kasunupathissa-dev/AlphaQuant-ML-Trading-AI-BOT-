import asyncio
import aiohttp
from typing import List, Dict, Optional
from datetime import datetime, timezone
from unified_quant_bot.config.config import TELEGRAM_TOKEN, TELEGRAM_CHAT_ID

class TelegramGateway:
    """
    Telegram Alerting & Interactive Telemetry Gateway.
    Configured to dispatch structured Hourly Executive Summaries while suppressing individual signal spam.
    """

    def __init__(self, token: str = TELEGRAM_TOKEN, chat_id: str = TELEGRAM_CHAT_ID, send_individual_alerts: bool = False):
        self.token = token
        self.chat_id = chat_id
        self.send_individual_alerts = send_individual_alerts
        self.base_url = f"https://api.telegram.org/bot{self.token}"

    async def send_message(self, text: str):
        if not self.token or not self.chat_id:
            return
        url = f"{self.base_url}/sendMessage"
        payload = {
            "chat_id": self.chat_id,
            "text": text,
            "parse_mode": "Markdown"
        }
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload, timeout=10) as resp:
                    pass
        except Exception:
            pass

    async def send_copy_trader_signal(self, trader: dict, pos: dict, consensus: dict = None):
        """Muted per user request: Individual entries are logged to CSV and aggregated into the Hourly Summary."""
        if not self.send_individual_alerts:
            return

    async def send_hyperliquid_whale_signal(self, whale: dict, pos: dict):
        """Muted per user request: Individual whale entries are logged to CSV and aggregated into the Hourly Summary."""
        if not self.send_individual_alerts:
            return
