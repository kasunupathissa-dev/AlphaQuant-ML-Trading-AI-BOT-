"""
Hyperliquid & On-Chain Elite Whales Ingestion Engine:
Tracks real-time on-chain large whale wallets directly from Hyperliquid L1 DEX.
Features strict cooldowns, high conviction filters ($50k+ notional), and zero spam.
"""

import asyncio
import aiohttp
import time
import json
import logging
from typing import Dict, List, Any, Optional

logger = logging.getLogger(__name__)

class HyperliquidWhaleCollector:
    def __init__(self, target_coins: Optional[List[str]] = None, min_account_value: float = 50000.0):
        self.target_coins = target_coins or ["BTC", "ETH", "SOL", "SUI", "LINK", "AVAX"]
        self.min_account_value = min_account_value
        self.session: Optional[aiohttp.ClientSession] = None
        self.is_running: bool = False
        self.whale_callbacks: List[Any] = []
        
        # Curated active whale pool
        self.tracked_wallets: set = set([
            "0x839eeee12aa7fa673b1c03fafcf0688b5c9a7375",
            "0x7fdafde5cfb5465924316eced2d3715494c517d1",
            "0x5078c2e1f0ec7e05ee9ec3e5f2cf2eec55979269",
            "0xdfda0a66d03a1135f6ea3671158c3db0ce44d2d6",
            "0x010461c14e146ac35fe42271bdc1134ee31c703a",
            "0x7717a7a245d9f950e586822b8c9b46863ed7bd7e",
            "0xecb63caa47c7c4e77f60f1ce858cf28dc2b82b00",
            "0xfeee942a06d2f8012823ccde7bf7bcbcaa29a09f",
            "0x28473085ba4aa761eb541914f50a75dd685cd47b"
        ])
        
        self.seen_whale_positions: set = set()
        self.last_alert_by_symbol: Dict[str, float] = {} # Per-symbol cooldown
        self.last_alert_by_wallet: Dict[str, float] = {} # Per-wallet cooldown
        self.is_baseline_established: bool = False
        self.api_url = "https://api.hyperliquid.xyz/info"

    def register_whale_callback(self, callback):
        """Registers async callback function fired when an on-chain whale opens a fresh position."""
        self.whale_callbacks.append(callback)

    async def get_session(self) -> aiohttp.ClientSession:
        if self.session is None or self.session.closed:
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AlphaQuant/4.0",
                "Content-Type": "application/json"
            }
            timeout = aiohttp.ClientTimeout(total=10)
            self.session = aiohttp.ClientSession(headers=headers, timeout=timeout)
        return self.session

    async def discover_active_whale_wallets(self):
        """Scans recent executed trades to discover active high-volume whale wallets."""
        session = await self.get_session()
        new_wallets = set()
        for coin in self.target_coins:
            try:
                payload = {"type": "recentTrades", "coin": coin}
                async with session.post(self.api_url, json=payload) as resp:
                    if resp.status == 200:
                        trades = await resp.json()
                        for t in trades:
                            users = t.get("users", [])
                            for u in users:
                                if u and u.startswith("0x") and u not in self.tracked_wallets:
                                    new_wallets.add(u)
            except Exception as e:
                logger.debug(f"[HYPERLIQUID] Trade discovery notice for {coin}: {e}")
            await asyncio.sleep(0.05)

        if new_wallets:
            for w in new_wallets:
                self.tracked_wallets.add(w)
                if self.is_baseline_established:
                    asyncio.create_task(self._baseline_single_wallet(w))

    async def _baseline_single_wallet(self, wallet_address: str):
        """Silently records existing positions for a newly discovered wallet."""
        try:
            state = await self.inspect_wallet_state(wallet_address)
            if state:
                for p in state.get("asset_positions", []):
                    pos = p.get("position", {})
                    coin = pos.get("coin", "")
                    size = float(pos.get("szi", 0.0))
                    if size != 0:
                        pos_key = f"HL_{wallet_address}_{coin}"
                        self.seen_whale_positions.add(pos_key)
        except Exception:
            pass

    async def inspect_wallet_state(self, wallet_address: str) -> Optional[Dict[str, Any]]:
        """Queries on-chain clearinghouseState for a specific wallet address."""
        session = await self.get_session()
        try:
            payload = {"type": "clearinghouseState", "user": wallet_address}
            async with session.post(self.api_url, json=payload) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    margin_summary = data.get("marginSummary", {})
                    account_val = float(margin_summary.get("accountValue", 0.0))
                    
                    if account_val >= self.min_account_value:
                        return {
                            "wallet": wallet_address,
                            "account_value": account_val,
                            "total_ntl_pos": float(margin_summary.get("totalNtlPos", 0.0)),
                            "total_margin_used": float(margin_summary.get("totalMarginUsed", 0.0)),
                            "asset_positions": data.get("assetPositions", [])
                        }
        except Exception as e:
            logger.debug(f"[HYPERLIQUID] Wallet query notice for {wallet_address[:10]}: {e}")
        return None

    async def poll_whale_positions(self):
        """Polls whale wallets and dispatches high-conviction fresh entry signals with strict cooldowns."""
        now = time.time()
        wallets_to_check = list(self.tracked_wallets)
        tasks = [self.inspect_wallet_state(w) for w in wallets_to_check]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        for res in results:
            if not isinstance(res, dict) or not res.get("wallet"):
                continue

            wallet = res["wallet"]
            account_val = res["account_value"]
            total_ntl = res["total_ntl_pos"]
            positions = res.get("asset_positions", [])

            for p in positions:
                pos = p.get("position", {})
                size = float(pos.get("szi", 0.0))
                if size == 0:
                    continue

                coin = pos.get("coin", "")
                if coin not in self.target_coins:
                    continue

                direction = "LONG" if size > 0 else "SHORT"
                entry_px = float(pos.get("entryPx", 0.0))
                pos_value = float(pos.get("positionValue", 0.0))
                unrealized_pnl = float(pos.get("unrealizedPnl", 0.0))
                roe = float(pos.get("returnOnEquity", 0.0)) * 100.0
                
                lev_data = pos.get("leverage", {})
                leverage = lev_data.get("value", 10) if isinstance(lev_data, dict) else 10

                # 1. High Institutional Size Filter: Minimum $40,000+ Position Size
                if entry_px <= 0 or pos_value < 40000.0:
                    continue

                # 2. Strict Freshness Filter: ROE must be within [-1.5%, +1.5%]
                # If trade is already moving in profit/loss, it is NOT fresh!
                if abs(roe) > 1.5:
                    pos_key = f"HL_{wallet}_{coin}"
                    self.seen_whale_positions.add(pos_key)
                    continue

                # 3. Position Key (NO micro price fluctuation duplicates!)
                pos_key = f"HL_{wallet}_{coin}"

                # 4. Strict Cooldowns:
                # Minimum 45 minutes cooldown per symbol to prevent multiple whale spam on the same asset
                if now - self.last_alert_by_symbol.get(coin, 0.0) < 2700:
                    continue
                # Minimum 4 hours cooldown per wallet
                if now - self.last_alert_by_wallet.get(wallet, 0.0) < 14400:
                    continue

                if pos_key not in self.seen_whale_positions:
                    self.seen_whale_positions.add(pos_key)
                    self.last_alert_by_symbol[coin] = now
                    self.last_alert_by_wallet[wallet] = now

                    if self.is_baseline_established:
                        if direction == "LONG":
                            tp_price = round(entry_px * 1.030, 4)
                            sl_price = round(entry_px * 0.985, 4)
                        else:
                            tp_price = round(entry_px * 0.970, 4)
                            sl_price = round(entry_px * 1.015, 4)

                        whale_meta = {
                            "wallet": wallet,
                            "account_value": account_val,
                            "total_ntl": total_ntl,
                            "explorer_url": f"https://app.hyperliquid.xyz/explorer/address/{wallet}"
                        }

                        position_meta = {
                            "symbol": f"{coin}/USDT",
                            "coin": coin,
                            "direction": direction,
                            "entry": entry_px,
                            "tp": tp_price,
                            "sl": sl_price,
                            "leverage": leverage,
                            "position_value": pos_value,
                            "unrealized_pnl": unrealized_pnl,
                            "roe": roe
                        }

                        logger.info(f"[HYPERLIQUID_WHALE] 🌊 Clean Fresh Entry: {coin} {direction} (${pos_value:,.0f}) by {wallet[:8]}...")
                        for cb in self.whale_callbacks:
                            try:
                                if asyncio.iscoroutinefunction(cb):
                                    await cb(whale_meta, position_meta)
                                else:
                                    cb(whale_meta, position_meta)
                            except Exception as e:
                                logger.error(f"[HYPERLIQUID] Callback dispatch error: {e}")

    async def run_loop(self, poll_interval_seconds: int = 30):
        """Continuous async polling loop."""
        self.is_running = True
        logger.info("[HYPERLIQUID_WHALE] Ingestion Engine started. Monitoring On-Chain DEX Whales...")

        await self.discover_active_whale_wallets()
        await self.poll_whale_positions()
        
        self.is_baseline_established = True
        logger.info(f"[HYPERLIQUID_WHALE] Baseline established across {len(self.tracked_wallets)} whale wallets.")

        cycle_count = 0
        while self.is_running:
            try:
                cycle_count += 1
                if cycle_count % 20 == 0:
                    await self.discover_active_whale_wallets()

                await self.poll_whale_positions()
            except Exception as e:
                logger.error(f"[HYPERLIQUID_WHALE] Polling loop error: {e}")

            await asyncio.sleep(poll_interval_seconds)

    async def close(self):
        self.is_running = False
        if self.session and not self.session.closed:
            await self.session.close()
