#!/bin/bash

# AlphaQuant SCALPER_HUNT Deployment Script

echo "=================================================="
echo "  DEPLOYING ALPHAQUANT: SCALPER_HUNT              "
echo "=================================================="

# Ensure script is run as root
if [ "$EUID" -ne 0 ]; then
  echo "[ERROR] Please run this script with sudo or as root."
  exit 1
fi

# Paths
SOURCE_DIR="/home/kasun/repository/AlphaQuant-ML-Trading-AI-BOT-"
TARGET_DIR="/home/kasun/repository/AlphaQuant-SCALPER-HUNT"

# Step 1: Create target directory if it doesn't exist
if [ ! -d "$TARGET_DIR" ]; then
    echo "[INFO] Creating SCALPER_HUNT directory..."
    mkdir -p "$TARGET_DIR"
fi

# Step 2: Copy base files (all pickle brains and scripts)
echo "[INFO] Copying core engine files and brain models..."
cp "$SOURCE_DIR"/*.pkl "$TARGET_DIR"/
cp "$SOURCE_DIR"/feature_library.py "$TARGET_DIR"/
cp "$SOURCE_DIR"/database_config.py "$TARGET_DIR"/

# Step 3: Copy custom scalper main and config
echo "[INFO] Overwriting with customized SCALPER_HUNT scripts..."
cp "$SOURCE_DIR"/scalper_hunt/config.py "$TARGET_DIR"/config.py
cp "$SOURCE_DIR"/scalper_hunt/main_v7.py "$TARGET_DIR"/main_v7.py

# Step 4: Setup python virtual env in target folder if it doesn't exist
if [ ! -d "$TARGET_DIR/aq_env" ]; then
    echo "[INFO] Creating isolated virtual environment..."
    python3 -m venv "$TARGET_DIR/aq_env"
    "$TARGET_DIR/aq_env/bin/pip" install --upgrade pip
    "$TARGET_DIR/aq_env/bin/pip" install -r "$SOURCE_DIR"/requirements.txt
fi

# Step 5: Setup systemd service for SCALPER_HUNT
SERVICE_FILE="/etc/systemd/system/aq-scalper-hunt.service"

echo "[INFO] Writing systemd service file..."
cat << EOF > $SERVICE_FILE
[Unit]
Description=AlphaQuant SCALPER_HUNT Trading Bot Service
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=$TARGET_DIR
ExecStart=$TARGET_DIR/aq_env/bin/python3 main_v7.py
Restart=always
RestartSec=10
Environment=PYTHONUNBUFFERED=1
EnvironmentFile=$REPO_DIR/.env

[Install]
WantedBy=multi-user.target
EOF

# Step 6: Restart systemd daemon and enable service
echo "[INFO] Registering and starting aq-scalper-hunt service..."
systemctl daemon-reload
systemctl enable aq-scalper-hunt
systemctl restart aq-scalper-hunt

echo "=================================================="
echo "  SCALPER_HUNT DEPLOYED AND STARTED SUCCESSFULLY  "
echo "=================================================="
systemctl status aq-scalper-hunt --no-pager -n 10
