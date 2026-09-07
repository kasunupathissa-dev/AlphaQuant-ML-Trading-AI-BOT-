import requests
from ai_quant_bot.config.config import TELEGRAM_TOKEN, TELEGRAM_CHAT_ID

def send_telegram_message(msg: str):
    """Sends a Telegram alert with Markdown parsing fallback protection."""
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        print("[WARNING] Telegram credentials not configured.")
        return
        
    # Escape underscores to prevent Telegram Markdown parsing errors
    safe_msg = msg.replace("_", "\\_")
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        response = requests.post(
            url, 
            json={"chat_id": TELEGRAM_CHAT_ID, "text": safe_msg, "parse_mode": "Markdown"}, 
            timeout=10
        )
        if response.status_code != 200:
            print(f"[WARNING] Telegram Markdown format failed (Status: {response.status_code}). Retrying in plain text...")
            requests.post(
                url, 
                json={"chat_id": TELEGRAM_CHAT_ID, "text": safe_msg}, 
                timeout=10
            )
    except Exception as e:
        print(f"[ERROR] Failed to dispatch Telegram alert: {e}")
