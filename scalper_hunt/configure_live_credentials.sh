#!/bin/bash
if [ "$#" -ne 2 ]; then
    echo "Usage: sudo $0 <BINANCE_API_KEY> <BINANCE_API_SECRET>"
    exit 1
fi

KEY=$1
SECRET=$2

SERVICE_FILE="/etc/systemd/system/aq-scalper-hunt.service"

if [ ! -f "$SERVICE_FILE" ]; then
    echo "Error: Service file $SERVICE_FILE not found."
    exit 1
fi

# Remove any existing BINANCE_API_KEY/SECRET/USE_TESTNET env lines if they exist
sudo sed -i '/Environment=BINANCE_API_KEY=/d' $SERVICE_FILE
sudo sed -i '/Environment=BINANCE_API_SECRET=/d' $SERVICE_FILE
sudo sed -i '/Environment=USE_TESTNET=/d' $SERVICE_FILE

# Append new env variables before the [Install] block
sudo sed -i '/\[Install\]/i Environment=BINANCE_API_KEY='"$KEY"'' $SERVICE_FILE
sudo sed -i '/\[Install\]/i Environment=BINANCE_API_SECRET='"$SECRET"'' $SERVICE_FILE
sudo sed -i '/\[Install\]/i Environment=USE_TESTNET=False' $SERVICE_FILE

echo "Service file updated successfully."
echo "Reloading systemd daemon..."
sudo systemctl daemon-reload
echo "Restarting aq-scalper-hunt service..."
sudo systemctl restart aq-scalper-hunt.service
echo "Service restarted. Checking status..."
sudo systemctl status aq-scalper-hunt.service --no-pager
