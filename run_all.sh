#!/bin/bash

echo "=========================================="
echo "   ALPHAQUANT SYSTEM STARTUP SCRIPT"
echo "=========================================="

# Activate virtual environment if it exists in local directory
if [ -d "aq_env" ]; then
    echo "[INFO] Activating virtual environment..."
    source aq_env/bin/activate
fi

# Step 1: Run Retraining
echo "[1/3] Retraining ML Models with manual calibration..."
python3 model_training_v7.py
if [ $? -ne 0 ]; then
    echo "[ERROR] Model training failed! Aborting startup."
    exit 1
fi
echo "[SUCCESS] Model training complete."

# Step 2: Stop any existing dashboard/bot processes
echo "[2/3] Cleaning up any old dashboard or bot processes..."
pkill -f "python3 dashboard_app.py" 2>/dev/null
pkill -f "python3 main_v7.py" 2>/dev/null
sleep 2

# Step 3: Start Dashboard in background
echo "[3/3] Launching Dashboard in background..."
nohup python3 -u dashboard_app.py > dashboard.log 2>&1 &
DASHBOARD_PID=$!
echo "  - Dashboard running with PID: $DASHBOARD_PID (Logs: dashboard.log)"

# Step 4: Start Trading Bot in background
echo "Launching Live Trading Bot in background..."
nohup python3 -u main_v7.py > bot.log 2>&1 &
BOT_PID=$!
echo "  - Trading Bot running with PID: $BOT_PID (Logs: bot.log)"

echo "=========================================="
echo "   ALPHAQUANT STARTUP COMPLETE"
echo "=========================================="
echo "To view bot output: tail -f bot.log"
echo "To view dashboard output: tail -f dashboard.log"
