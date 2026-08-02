#!/bin/bash

# ==============================================================================
# AlphaQuant Production Multi-Service Deployment Script
# Targets: Live Bot, Web Dashboard, and Weekly Auto-Trainer Daemon
# ==============================================================================

# Ensure script is run as root
if [ "$EUID" -ne 0 ]; then
  echo "[ERROR] Please run this script with sudo or as root."
  exit 1
fi

REPO_DIR="/home/kasun/repository/AlphaQuant-ML-Trading-AI-BOT-"
PORT=8080

# 🟢 V8.4 Upgrade: Detect virtual environment dynamically to avoid ModuleNotFoundErrors in Systemd
if [ -f "$REPO_DIR/aq_env/bin/python3" ]; then
  PYTHON_BIN="$REPO_DIR/aq_env/bin/python3"
  echo "[INFO] Found virtual environment. Using python: $PYTHON_BIN"
elif [ -f "$REPO_DIR/.venv/bin/python3" ]; then
  PYTHON_BIN="$REPO_DIR/.venv/bin/python3"
  echo "[INFO] Found .venv environment. Using python: $PYTHON_BIN"
else
  PYTHON_BIN="/usr/bin/python3"
  echo "[WARNING] No virtual environment found. Using system python: $PYTHON_BIN"
fi

echo "=================================================="
echo " Starting Full AlphaQuant System Deployment..."
echo "=================================================="

# 1. Sync code from Git
echo "[1/4] Updating repository code..."
cd "$REPO_DIR" || exit
git checkout -- *.pkl
git pull origin main

# 2. Setup Systemd Service for Live Trading Bot (main_v7.py)
echo "[2/4] Configuring Systemd Service: aq-live..."
cat << EOF > /etc/systemd/system/aq-live.service
[Unit]
Description=AlphaQuant Live Trading Bot Service
After=network.target

[Service]
User=root
WorkingDirectory=$REPO_DIR
ExecStart=$PYTHON_BIN main_v7.py
Restart=always
RestartSec=10
Environment=PYTHONUNBUFFERED=1
EnvironmentFile=-$REPO_DIR/.env

[Install]
WantedBy=multi-user.target
EOF

# 3. Setup Systemd Service for Web Dashboard (dashboard_app.py)
echo "[3/4] Configuring Systemd Service: aq-dashboard..."
cat << EOF > /etc/systemd/system/aq-dashboard.service
[Unit]
Description=AlphaQuant Web Dashboard Service
After=network.target

[Service]
User=root
WorkingDirectory=$REPO_DIR
ExecStart=$PYTHON_BIN dashboard_app.py $PORT
Restart=always
RestartSec=10
Environment=PYTHONUNBUFFERED=1
EnvironmentFile=-$REPO_DIR/.env

[Install]
WantedBy=multi-user.target
EOF

# 4. Setup Systemd Service for Auto-Trainer Daemon (auto_trainer_daemon.py)
echo "[4/4] Configuring Systemd Service: aq-trainer..."
cat << EOF > /etc/systemd/system/aq-trainer.service
[Unit]
Description=AlphaQuant Auto-Trainer Daemon Service
After=network.target

[Service]
User=root
WorkingDirectory=$REPO_DIR
ExecStart=$PYTHON_BIN auto_trainer_daemon.py
Restart=always
RestartSec=30
Environment=PYTHONUNBUFFERED=1
EnvironmentFile=-$REPO_DIR/.env

[Install]
WantedBy=multi-user.target
EOF

# Reload and apply configuration changes
echo "--------------------------------------------------"
echo " Applying service changes..."
echo "--------------------------------------------------"
systemctl daemon-reload

# Enable all services to start on boot
systemctl enable aq-live aq-dashboard aq-trainer

# Restart all services to apply the latest code changes
systemctl restart aq-live aq-dashboard aq-trainer

echo "=================================================="
echo " Checking Service Status..."
echo "=================================================="
sleep 2

# Display live status
systemctl status aq-live --no-pager -n 2
systemctl status aq-dashboard --no-pager -n 2
systemctl status aq-trainer --no-pager -n 2

echo "=================================================="
echo " [SUCCESS] All AlphaQuant Services deployed & restarted!"
echo " - Live Trading: aq-live"
echo " - Dashboard:    aq-dashboard (Port: $PORT)"
echo " - Auto-Trainer: aq-trainer (Sunday runs)"
echo "=================================================="
