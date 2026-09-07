#!/bin/bash
# Deploy and start the AlphaQuant Manual Scalping Scout service

SERVER="kasun@tradebot.yugadiviya.lk"
KEY="$HOME/.ssh/kasun_key"
REPO="/home/kasun/repository/AlphaQuant-ML-Trading-AI-BOT-"
SERVICE="aq-scout"

echo "=== Deploying Manual Scalping Scout ==="

ssh -i "$KEY" -o StrictHostKeyChecking=no "$SERVER" << 'ENDSSH'
set -e
REPO="/home/kasun/repository/AlphaQuant-ML-Trading-AI-BOT-"
cd "$REPO"

# Create systemd service
sudo tee /etc/systemd/system/aq-scout.service > /dev/null << 'EOF'
[Unit]
Description=AlphaQuant Manual Scalping Intelligence Scout
After=network.target

[Service]
User=root
WorkingDirectory=/home/kasun/repository/AlphaQuant-ML-Trading-AI-BOT-
ExecStart=/home/kasun/repository/AlphaQuant-ML-Trading-AI-BOT-/aq_env/bin/python3 manual_scout.py
Restart=always
RestartSec=15
Environment=PYTHONUNBUFFERED=1
EnvironmentFile=/home/kasun/repository/AlphaQuant-ML-Trading-AI-BOT-/.env

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable aq-scout
sudo systemctl restart aq-scout
echo "=== aq-scout started ==="
sleep 5
sudo journalctl -u aq-scout -n 20 --no-pager
ENDSSH
