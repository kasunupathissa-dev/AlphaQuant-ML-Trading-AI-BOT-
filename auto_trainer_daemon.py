import time
import schedule
import subprocess
import sys
from datetime import datetime

def job():
    print(f"\n==================================================")
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] STARTING WEEKLY AUTO-TRAIN CYCLE")
    print(f"==================================================")
    
    scripts = [
        "data_ingestion.py",
        "feature_generator_v3.py",
        "label_generator_v3.py",
        "model_training_calibrated.py"
    ]
    
    for script in scripts:
        print(f"-> Running {script}...")
        try:
            # We use sys.executable to ensure we use the virtual environment's Python
            result = subprocess.run([sys.executable, script], check=True, capture_output=True, text=True)
            print(f"   [SUCCESS] {script} finished.")
        except subprocess.CalledProcessError as e:
            print(f"   [FATAL ERROR] {script} failed!\n{e.stderr}")
            print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] AUTO-TRAIN ABORTED.")
            return

    print(f"==================================================")
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] AUTO-TRAIN CYCLE COMPLETE.")
    print(f"Live engine will automatically hot-swap new brains.")
    print(f"==================================================\n")

if __name__ == "__main__":
    print("==================================================")
    print("  ALPHAQUANT V4.3: CONTINUOUS LEARNING DAEMON     ")
    print("==================================================")
    print("Daemon active. Waiting for scheduled execution...")
    
    # Schedule the job to run every Sunday at 02:00 AM server time
    schedule.every().sunday.at("02:00").do(job)
    
    # For testing purposes, you can uncomment this to run it immediately once:
    # job()
    
    while True:
        schedule.run_pending()
        time.sleep(60)