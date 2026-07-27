#!/bin/bash

# ==============================================================================
# AlphaQuant Web Dashboard Automated Deployment Script
# Target: https://tradebot.yugadiviya.lk
# ==============================================================================

# Ensure script is run as root
if [ "$EUID" -ne 0 ]; then
  echo "[ERROR] Please run this script with sudo or as root."
  exit 1
fi

REPO_DIR="/home/kasun/repository/AlphaQuant-ML-Trading-AI-BOT-"
DOMAIN="tradebot.yugadiviya.lk"
PORT=8080

echo "=================================================="
# Syncing code
echo "[1/5] Updating code repository..."
cd "$REPO_DIR" || exit
git checkout -- *.pkl
git pull origin main

# Create Systemd Service File
echo "[2/5] Setting up Systemd Service..."
cat << EOF > /etc/systemd/system/aq-dashboard.service
[Unit]
Description=AlphaQuant Web Dashboard Service
After=network.target

[Service]
User=root
WorkingDirectory=$REPO_DIR
ExecStart=/usr/bin/python3 dashboard_app.py $PORT
Restart=always

[Install]
WantedBy=multi-user.target
EOF

# Reload and restart service
systemctl daemon-reload
systemctl enable aq-dashboard
systemctl restart aq-dashboard
echo "[SUCCESS] aq-dashboard service is running."

# Install Nginx if not installed
echo "[3/5] Checking Nginx installation..."
if ! command -v nginx &> /dev/null; then
    echo "Nginx not found. Installing..."
    apt-get update
    apt-get install nginx -y
    systemctl start nginx
    systemctl enable nginx
fi

# Create Nginx server block config
echo "[4/5] Configuring Nginx Reverse Proxy..."
cat << EOF > /etc/nginx/sites-available/$DOMAIN
server {
    listen 80;
    server_name $DOMAIN;

    location / {
        proxy_pass http://127.0.0.1:$PORT;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }
}
EOF

# Link Nginx config if not linked
if [ ! -f /etc/nginx/sites-enabled/$DOMAIN ]; then
    ln -s /etc/nginx/sites-available/$DOMAIN /etc/nginx/sites-enabled/
fi

# Test Nginx syntax and reload
nginx -t
if [ $? -eq 0 ]; then
    systemctl reload nginx
    echo "[SUCCESS] Nginx configuration reloaded successfully."
else
    echo "[ERROR] Nginx configuration test failed. Please check files."
    exit 1
fi

# Set up SSL with Certbot
echo "[5/5] Configuring SSL Certificates via Certbot..."
apt-get install certbot python3-certbot-nginx -y

# Request certificate (Nginx mode)
certbot --nginx -d $DOMAIN --non-interactive --agree-tos -m "kasunupathissadev@gmail.com" --redirect

echo "=================================================="
echo "[SUCCESS] AlphaQuant Web Dashboard deployed successfully!"
echo "Url: https://$DOMAIN"
echo "=================================================="
