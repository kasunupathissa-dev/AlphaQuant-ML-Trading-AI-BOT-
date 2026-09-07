#!/bin/bash

# ========================================================
# AlphaQuant Auto Tuning & Report Deployment Script
# ========================================================

echo "[INFO] Creating systemd service files..."

# 1. Optimizer Service & Timer
sudo tee /etc/systemd/system/aq-optimizer.service > /dev/null <<EOF
[Unit]
Description=AlphaQuant Dynamic Asset Optimizer Service
After=network.target

[Service]
Type=oneshot
User=kasun
WorkingDirectory=/home/kasun/repository/AlphaQuant-ML-Trading-AI-BOT-
ExecStart=/home/kasun/repository/AlphaQuant-ML-Trading-AI-BOT-/aq_env/bin/python /home/kasun/repository/AlphaQuant-ML-Trading-AI-BOT-/dynamic_asset_optimizer.py
EOF

sudo tee /etc/systemd/system/aq-optimizer.timer > /dev/null <<EOF
[Unit]
Description=Run AlphaQuant Dynamic Asset Optimizer Daily

[Timer]
OnCalendar=*-*-* 07:30:00
Persistent=true

[Install]
WantedBy=timers.target
EOF

# 2. Report Service & Timer
sudo tee /etc/systemd/system/aq-report.service > /dev/null <<EOF
[Unit]
Description=AlphaQuant Daily Performance Report Service
After=network.target mysql.service

[Service]
Type=oneshot
User=kasun
WorkingDirectory=/home/kasun/repository/AlphaQuant-ML-Trading-AI-BOT-
EnvironmentFile=/home/kasun/repository/AlphaQuant-ML-Trading-AI-BOT-/.env
ExecStart=/home/kasun/repository/AlphaQuant-ML-Trading-AI-BOT-/aq_env/bin/python /home/kasun/repository/AlphaQuant-ML-Trading-AI-BOT-/daily_report_daemon.py
EOF


sudo tee /etc/systemd/system/aq-report.timer > /dev/null <<EOF
[Unit]
Description=Run AlphaQuant Daily Performance Report Service Daily

[Timer]
OnCalendar=*-*-* 08:00:00
Persistent=true

[Install]
WantedBy=timers.target
EOF

echo "[INFO] Reloading systemd daemon..."
sudo systemctl daemon-reload

echo "[INFO] Enabling and starting timers..."
sudo systemctl enable aq-optimizer.timer
sudo systemctl start aq-optimizer.timer
sudo systemctl enable aq-report.timer
sudo systemctl start aq-report.timer

echo "[INFO] Checking timers status..."
sudo systemctl list-timers --all | grep aq-

echo "[SUCCESS] Auto-tuning systemd services deployed successfully!"
