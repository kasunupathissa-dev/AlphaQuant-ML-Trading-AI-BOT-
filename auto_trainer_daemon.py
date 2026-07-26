import time
import schedule
import subprocess
import sys
from datetime import datetime
import os

# 🟢 V7.1 Upgrade: Import the shared Telegram function
def send_telegram_message(msg):
    TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
    TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        print("[WARNING] Telegram secrets not set, cannot send notification.")
        return
    try:
        import requests
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        requests.post(url, json={"chat_id": TELEGRAM_CHAT_ID, "text": msg, "parse_mode": "Markdown"}, timeout=10)
    except Exception as e:
        print(f"[ERROR] Failed to send Telegram message: {e}")

def job():
    start_time = datetime.now()
    print(f"\n==================================================")
    print(f"[{start_time.strftime('%Y-%m-%d %H:%M:%S')}] STARTING WEEKLY AUTO-TRAIN CYCLE")
    print(f"==================================================")
    send_telegram_message("🤖 *[V7.1 Auto-Train]*\nStarting weekly model retraining cycle...")

    try:
        # 🟢 V8.3 Upgrade: Run the master V8 15M pipeline script
        result = subprocess.run(
            [sys.executable, "run_full_pipeline_v8.py"], 
            check=True, 
            capture_output=True, 
            text=True,
            timeout=3600 # Add a 1-hour timeout for safety
        )
        
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds() / 60.0
        
        print(f"==================================================")
        print(f"[{end_time.strftime('%Y-%m-%d %H:%M:%S')}] AUTO-TRAIN CYCLE COMPLETE.")
        print(f"Duration: {duration:.2f} minutes.")
        print(f"==================================================\n")
        
        success_message = (f"✅ *[V7.1 Auto-Train]*\n"
                         f"Weekly model retraining cycle completed successfully.\n"
                         f"Duration: *{duration:.2f} minutes*.\n"
                         f"New AI brains are now live.")
        send_telegram_message(success_message)

    except subprocess.CalledProcessError as e:
        error_message = (f"❌ *[V7.1 Auto-Train]*\n"
                         f"FATAL ERROR during model retraining!\n\n"
                         f"*Error Log:*\n"
                         f"```\n{e.stderr[-1000:]}\n```") # Send last 1000 chars of error
        send_telegram_message(error_message)
        print(f"   [FATAL ERROR] Pipeline failed!\n{e.stderr}")
    except subprocess.TimeoutExpired:
        send_telegram_message("❌ *[V7.1 Auto-Train]*\nFATAL ERROR: Retraining cycle timed out after 1 hour.")
        print("[FATAL ERROR] Pipeline timed out.")

if __name__ == "__main__":
    print("==================================================")
    print("  ALPHAQUANT V7.1: CONTINUOUS LEARNING DAEMON     ")
    print("==================================================")
    
    # Send startup notification
    send_telegram_message("🟢 *[V7.1 Auto-Train]*\nDaemon service started. Waiting for schedule.")
    print("Daemon active. Waiting for scheduled execution every Sunday at 02:00...")
    
    schedule.every().sunday.at("02:00").do(job)
    
    while True:
        schedule.run_pending()
        time.sleep(60)