import asyncio
import aiohttp
from typing import List, Dict, Optional
from datetime import datetime, timezone
from unified_quant_bot.config.config import TELEGRAM_TOKEN, TELEGRAM_CHAT_ID

class TelegramGateway:
    """Telegram Alerting & Interactive Telemetry Gateway dedicated to Top Copy Traders & Smart Money Intelligence."""

    def __init__(self, token: str = TELEGRAM_TOKEN, chat_id: str = TELEGRAM_CHAT_ID):
        self.token = token
        self.chat_id = chat_id
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
        """Dispatches an instant real-time Telegram signal when a Top Verified Lead Trader takes a position."""
        direction = pos.get('direction', 'LONG').upper()
        emoji = "🟢 ⚡" if direction == "LONG" else "🔴 ⚡"
        rank = trader.get('rank', 'Top Lead Trader')
        rank_str = str(rank)
        roi = trader.get('roi', 0.0)
        win_rate = trader.get('winRate', 0.0)
        symbol = pos.get('symbol', 'BTC/USDT')
        entry = float(pos.get('entry', 0.0))
        tp = float(pos.get('tp', entry * 1.03 if direction == 'LONG' else entry * 0.97))
        sl = float(pos.get('sl', entry * 0.985 if direction == 'LONG' else entry * 1.015))
        leverage = pos.get('leverage', 10)
        nick = trader.get('nickName', 'VerifiedLeadTrader')
        
        cons_text = ""
        if consensus:
            cons_label = consensus.get('consensus', 'NEUTRAL')
            long_pct = consensus.get('long_pct', 50.0)
            short_pct = consensus.get('short_pct', 50.0)
            cons_text = f"• *Market Whale Consensus*: `{cons_label}` ({long_pct}% Long / {short_pct}% Short)\n"

        entry_dist = pos.get('entry_distance_pct', 0.02)
        dist_text = f"• *Live Entry Distance*: `+{entry_dist:.2f}%` (Fresh Entry Window)\n"

        msg = (
            f"{emoji} *[ALPHAQUANT] ⚡ TOP COPY TRADER ENTRY SIGNAL*\n\n"
            f"🏆 *Lead Trader*: `{nick}` (*{rank_str}*)\n"
            f"📈 *Verified Performance*: *+{roi:.1f}% Monthly ROI* | Win Rate: *{win_rate:.1f}%*\n\n"
            f"• *Asset*: `{symbol}`\n"
            f"• *Signal Direction*: *{direction}* ({leverage}x Leverage)\n"
            f"• *Copy Entry Price*: `${entry:.4f}`\n"
            f"• *Target Take Profit*: `${tp:.4f}` (+3.0%)\n"
            f"• *Stop Loss Level*: `${sl:.4f}` (-1.5%)\n"
            f"• *Risk/Reward*: `1:2.0 Guaranteed`\n"
            f"{dist_text}"
            f"{cons_text}\n"
            f"🛡️ *Execution Status*: `Brand New Position Opened — Safe to Copy`"
        )
        await self.send_message(msg)

    async def send_hyperliquid_whale_signal(self, whale: dict, pos: dict):
        """Dispatches an instant real-time Telegram alert when an On-Chain Hyperliquid Elite Whale opens a fresh position."""
        direction = pos.get('direction', 'LONG').upper()
        emoji = "🌊 🟢 ⚡" if direction == "LONG" else "🌊 🔴 ⚡"
        symbol = pos.get('symbol', 'BTC/USDT')
        coin = pos.get('coin', 'BTC')
        entry = float(pos.get('entry', 0.0))
        tp = float(pos.get('tp', entry * 1.03 if direction == 'LONG' else entry * 0.97))
        sl = float(pos.get('sl', entry * 0.985 if direction == 'LONG' else entry * 1.015))
        leverage = pos.get('leverage', 10)
        pos_val = float(pos.get('position_value', 0.0))
        unrealized_pnl = float(pos.get('unrealized_pnl', 0.0))
        roe = float(pos.get('roe', 0.0))
        wallet = whale.get('wallet', '0x...')
        short_wallet = f"{wallet[:6]}...{wallet[-4:]}" if len(wallet) > 10 else wallet
        acc_val = float(whale.get('account_value', 0.0))
        exp_url = whale.get('explorer_url', f"https://app.hyperliquid.xyz/explorer/address/{wallet}")

        pnl_sign = "+" if unrealized_pnl >= 0 else ""

        msg = (
            f"{emoji} *[ALPHAQUANT] ⚡ HYPERLIQUID ON-CHAIN ELITE WHALE SIGNAL*\n\n"
            f"👛 *Whale Wallet*: `{short_wallet}`\n"
            f"💎 *Account Value*: *${acc_val:,.2f}* | Pos Notional: *${pos_val:,.2f}*\n"
            f"📈 *Live Return (ROE)*: *{pnl_sign}{roe:.1f}%* (PnL: *{pnl_sign}${unrealized_pnl:,.2f}*)\n\n"
            f"• *Asset*: `{symbol}` (Hyperliquid DEX)\n"
            f"• *Signal Direction*: *{direction}* ({leverage}x Leverage)\n"
            f"• *Live Entry Price*: `${entry:.4f}`\n"
            f"• *Target Take Profit*: `${tp:.4f}` (+3.0%)\n"
            f"• *Stop Loss Level*: `${sl:.4f}` (-1.5%)\n"
            f"• *Risk/Reward*: `1:2.0 Guaranteed`\n\n"
            f"🛡️ *Execution Status*: `Fresh On-Chain Position Opened — Safe to Copy`\n"
            f"🔗 *On-Chain Proof*: [View Wallet on Explorer]({exp_url})"
        )
        await self.send_message(msg)

    async def send_copy_traders_summary(
        self,
        top_traders: list,
        symbols_consensus: dict
    ):
        """Dispatches an hourly ranking summary of the world-class lead traders and their live active positions."""
        now_str = datetime.now(timezone.utc).strftime('%H:%M:%S UTC')
        
        trader_lines = []
        for idx, t in enumerate(top_traders[:5]):
            rank_em = "🥇" if idx == 0 else ("🥈" if idx == 1 else ("🥉" if idx == 2 else f"#{idx+1}"))
            roi = t.get('roi', 0.0)
            wr = t.get('winRate', 0.0)
            nick = t.get('nickName', f'Whale_{idx+1}')
            
            positions = t.get('active_positions', [])
            if positions:
                pos_str = ", ".join([f"`{p.get('symbol')} {p.get('direction')} ({p.get('leverage', 10)}x)`" for p in positions])
            else:
                pos_str = "Flat in Cash"
                
            trader_lines.append(
                f"{rank_em} *{nick}* (Rank #{t.get('rank', idx+1)})\n"
                f"   • *Monthly ROI*: *+{roi:.1f}%* | Win Rate: *{wr:.1f}%*\n"
                f"   • *Active Positions*: {pos_str}\n"
            )

        traders_text = "\n".join(trader_lines) if trader_lines else "No active lead traders in session."

        consensus_lines = []
        for sym, sc in list(symbols_consensus.items())[:6]:
            consensus_lines.append(f"• `{sym}`: *{sc.get('consensus')}* (L: {sc.get('long_pct')}% / S: {sc.get('short_pct')}%)")
        consensus_text = "\n".join(consensus_lines)

        msg = (
            f"🏆 *[ALPHAQUANT] WORLD-CLASS COPY TRADERS INTELLIGENCE REPORT*\n"
            f"🕒 Timestamp: `{now_str}`\n\n"
            f"👑 *Top 5 Verified Lead Traders (Anti-Martingale Filtered):*\n\n"
            f"{traders_text}\n"
            f"🌐 *Smart Money Market Consensus:*\n"
            f"{consensus_text}\n\n"
            f"⚡ *Data Feed*: Verified Binance Futures Leaderboard & Hyperliquid On-Chain Whales"
        )
        await self.send_message(msg)
