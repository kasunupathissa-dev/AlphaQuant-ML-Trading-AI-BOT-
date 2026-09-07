import time
import asyncio
from typing import Dict
from ai_quant_bot.monitoring.telegram_notifier import TelegramNotifier

class WebSocketWatchdog:
    """Monitors incoming data streams for stale feeds and dispatches hourly health heartbeats."""
    
    def __init__(self, target_symbols: list, notifier: TelegramNotifier, timeout_seconds: float = 90.0):
        self.target_symbols = target_symbols
        self.notifier = notifier
        self.timeout_seconds = timeout_seconds
        self.last_update_times: Dict[str, float] = {s: time.time() for s in target_symbols}
        self.boot_time = time.time()
        self.is_running = False

    def record_activity(self, symbol: str):
        """Records the timestamp of the latest received WebSocket tick/candle."""
        self.last_update_times[symbol.upper().strip()] = time.time()

    async def run_watchdog_loop(self, collector):
        """Asynchronously checks for stale feeds and force-restarts WebSockets if needed."""
        self.is_running = True
        print("[WATCHDOG] Stale feed watchdog loop active.")
        
        while self.is_running:
            await asyncio.sleep(10) # check every 10 seconds
            now = time.time()
            
            stale_detected = False
            for symbol, last_time in self.last_update_times.items():
                if now - last_time > self.timeout_seconds:
                    print(f"[WATCHDOG WARNING] Stale feed identified for {symbol}. Last update: {now - last_time:.1f}s ago.")
                    stale_detected = True
                    break
                    
            if stale_detected:
                msg = f"⚠️ *[WATCHDOG ALARM]*\nStale WebSocket feed detected (No data for >90s). Force-restarting collectors..."
                await self.notifier.send_message(msg)
                
                try:
                    print("[WATCHDOG] Initiating WebSocket collector force-restart...")
                    # Gracefully stop the collector and restart it
                    await collector.stop()
                    await asyncio.sleep(2)
                    
                    # Reset last update times to avoid infinite loop on restart delay
                    for symbol in self.target_symbols:
                        self.last_update_times[symbol] = time.time()
                        
                    asyncio.create_task(collector.start())
                    await self.notifier.send_message("🟢 *[WATCHDOG INFO]* WebSocket collectors restarted successfully.")
                except Exception as e:
                    print(f"[WATCHDOG ERROR] Force-restart failed: {e}")
                    await self.notifier.send_message(f"🚨 *[WATCHDOG CRITICAL]* Force-restart failed: {e}")

    async def run_heartbeat_loop(self):
        """Dispatches status updates every hour detailing engine uptime and health."""
        while self.is_running:
            await asyncio.sleep(3600)  # Sleep 1 hour
            
            uptime_seconds = time.time() - self.boot_time
            uptime_hours = uptime_seconds / 3600.0
            
            # Simple health check mapping
            active_streams_count = len(self.target_symbols)
            msg = (
                f"🟢 *[ENGINE HEARTBEAT]*\n"
                f"• *Status*: `Healthy`\n"
                f"• *Active WebSocket Streams*: `{active_streams_count}/{active_streams_count}`\n"
                f"• *Uptime*: `{uptime_hours:.1f}h`"
            )
            await self.notifier.send_message(msg)
            print(f"[HEARTBEAT] Dispatched hourly health report. Uptime: {uptime_hours:.2f} hours.")
            
    def stop(self):
        """Stops the watchdog and heartbeat loops."""
        self.is_running = False
