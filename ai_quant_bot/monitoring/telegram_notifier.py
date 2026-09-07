import asyncio
import json
import requests
import pandas as pd
from typing import Callable
from ai_quant_bot.config.config import TELEGRAM_TOKEN, TELEGRAM_CHAT_ID

class TelegramNotifier:
    """Production Asynchronous Telegram Alert and Manual Confirmation Gate Client."""

    def __init__(self):
        self.token = TELEGRAM_TOKEN
        self.chat_id = TELEGRAM_CHAT_ID
        self.is_polling = False
        self.last_update_id = 0

    def _send_request(self, method: str, payload: dict) -> dict:
        """Helper to send synchronous HTTP post requests to Telegram API."""
        url = f"https://api.telegram.org/bot{self.token}/{method}"
        try:
            response = requests.post(url, json=payload, timeout=10)
            if response.status_code == 200:
                return response.json()
            else:
                print(f"[TELEGRAM WARNING] request failed: {response.status_code} - {response.text}")
        except Exception as e:
            print(f"[TELEGRAM ERROR] Exception in API call {method}: {e}")
        return {}

    async def send_message(self, text: str):
        """Dispatches a simple text message to the configured channel."""
        payload = {"chat_id": self.chat_id, "text": text.replace("_", "\\_"), "parse_mode": "Markdown"}
        await asyncio.to_thread(self._send_request, "sendMessage", payload)

    async def send_trade_alert(
        self,
        symbol: str,
        direction: str,
        win_prob: float,
        entry: float,
        tp: float,
        sl: float,
        regime: str,
        semi_automated: bool = True
    ):
        """Dispatches structured trade alerts to Telegram with confirmation callbacks."""
        msg = (
            f"⚡ *[ALPHAQUANT AI] TRADE ALERT PROPOSAL*\n\n"
            f"• *Asset*: `{symbol}`\n"
            f"• *Direction*: `{direction}`\n"
            f"• *AI Win Probability*: `{win_prob:.2f}%`\n"
            f"• *Entry Target*: `${entry:.4f}`\n"
            f"• *Take Profit*: `${tp:.4f}`\n"
            f"• *Stop Loss*: `${sl:.4f}`\n"
            f"• *Market Regime*: `{regime}`\n\n"
            f"Status: *Awaiting confirmation*" if semi_automated else "Status: *Executing automatically*"
        )
        
        payload = {
            "chat_id": self.chat_id,
            "text": msg,
            "parse_mode": "Markdown"
        }

        # Add manual gate inline buttons if semi_automated
        if semi_automated:
            callback_data = f"confirm|{symbol}|{direction}|{entry}|{sl}|{tp}"
            # Ensure callback data stays below Telegram's 64 bytes limit
            if len(callback_data) > 64:
                # Compressed fallback callback string
                callback_data = f"c|{symbol}|{direction}|{entry:.2f}|{sl:.2f}|{tp:.2f}"

            payload["reply_markup"] = {
                "inline_keyboard": [
                    [
                        {"text": "✅ CONFIRM ENTRY", "callback_data": callback_data},
                        {"text": "❌ SKIP", "callback_data": f"skip|{symbol}"}
                    ]
                ]
            }

        await asyncio.to_thread(self._send_request, "sendMessage", payload)

    async def send_summary_report(self, open_positions: list, system_health: str):
        """Dispatches regular diagnostic summaries of current status."""
        pos_text = "No open positions."
        if open_positions:
            pos_text = "\n".join([
                f"• `{p['symbol']}` | {p['direction']} | Size: `${p['notional']:.2f}` | PnL: `${p['pnl']:.2f}`"
                for p in open_positions
            ])
            
        msg = (
            f"📊 *[SYSTEM PERFORMANCE REPORT]*\n\n"
            f"*Open Positions*:\n{pos_text}\n\n"
            f"• *System Health*: `{system_health}`\n"
            f"• *Timestamp*: `{pd.Timestamp.now(tz='UTC').strftime('%Y-%m-%d %H:%M:%S')} UTC`"
        )
        
        payload = {
            "chat_id": self.chat_id,
            "text": msg,
            "parse_mode": "Markdown"
        }
        await asyncio.to_thread(self._send_request, "sendMessage", payload)

    async def start_confirmation_polling(self, on_confirm_cb: Callable, on_skip_cb: Callable):
        """Asynchronously polls for confirmation callbacks via getUpdates."""
        self.is_polling = True
        print("[TELEGRAM] Starting confirmation polling loop...")
        
        while self.is_polling:
            try:
                payload = {
                    "offset": self.last_update_id + 1,
                    "timeout": 20,
                    "allowed_updates": ["callback_query"]
                }
                
                updates = await asyncio.to_thread(self._send_request, "getUpdates", payload)
                if not updates or "result" not in updates:
                    await asyncio.sleep(2)
                    continue

                for update in updates["result"]:
                    self.last_update_id = update["update_id"]
                    
                    if "callback_query" in update:
                        cb_query = update["callback_query"]
                        cb_id = cb_query["id"]
                        cb_data = cb_query["data"]
                        message = cb_query.get("message", {})
                        msg_id = message.get("message_id")
                        
                        parts = cb_data.split("|")
                        action = parts[0]
                        
                        if action in ("confirm", "c") and len(parts) >= 6:
                            symbol = parts[1]
                            direction = parts[2]
                            entry = float(parts[3])
                            sl = float(parts[4])
                            tp = float(parts[5])
                            
                            # Fire confirmation callback
                            asyncio.create_task(on_confirm_cb(symbol, direction, entry, sl, tp))
                            
                            # Acknowledge Telegram API and update card text
                            self._send_request("answerCallbackQuery", {"callback_query_id": cb_id, "text": "Trade Confirmed!"})
                            
                            updated_text = message.get("text", "") + "\n\n✅ *Trade Executed & Bracket Placed.*"
                            self._send_request("editMessageText", {
                                "chat_id": self.chat_id,
                                "message_id": msg_id,
                                "text": updated_text,
                                "parse_mode": "Markdown"
                            })
                            
                        elif action == "skip" and len(parts) >= 2:
                            symbol = parts[1]
                            asyncio.create_task(on_skip_cb(symbol))
                            
                            self._send_request("answerCallbackQuery", {"callback_query_id": cb_id, "text": "Trade Skipped."})
                            updated_text = message.get("text", "") + "\n\n❌ *Trade Skipped by User.*"
                            self._send_request("editMessageText", {
                                "chat_id": self.chat_id,
                                "message_id": msg_id,
                                "text": updated_text,
                                "parse_mode": "Markdown"
                            })

            except Exception as e:
                print(f"[TELEGRAM ERROR] Error in polling cycle: {e}")
                await asyncio.sleep(5)
                
            await asyncio.sleep(1)

    def stop_polling(self):
        """Stops the polling loop."""
        self.is_polling = False
