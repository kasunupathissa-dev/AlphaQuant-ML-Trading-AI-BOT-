# Deployment Guide: Installation & Server Orchestration

## 1. System Requirements

* **Operating System**: Ubuntu 22.04 LTS or 24.04 LTS (x86_64).
* **Hardware**: Minimum 2 vCPUs, 4GB RAM (8GB recommended), 40GB SSD.
* **Dependencies**: Python 3.11+, PostgreSQL 15+ (with TimescaleDB extension), Redis 7.0+, Git, UFW.

---

## 2. Step-by-Step Server Setup

### Step 1: Install System Packages & Services
```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y python3-pip python3-venv postgresql postgresql-contrib redis-server git ufw
```

### Step 2: Configure PostgreSQL & Redis
```bash
# Create PostgreSQL database and user
sudo -u postgres psql -c "CREATE DATABASE ai_quant_db;"
sudo -u postgres psql -c "CREATE USER alphaquant WITH ENCRYPTED PASSWORD 'YOUR_STRONG_DB_PASSWORD';"
sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE ai_quant_db TO alphaquant;"

# Ensure Redis is running locally
sudo systemctl enable --now redis-server
```

### Step 3: Clone Repository & Setup Virtual Environment
```bash
cd /home/kasun/repository
git clone https://github.com/kasunupathissa-dev/AlphaQuant-ML-Trading-AI-BOT-.git
cd AlphaQuant-ML-Trading-AI-BOT-

python3 -m venv aq_env
source aq_env/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

### Step 4: Configure Secure Environment File
```bash
cp .env.example .env
chmod 600 .env
nano .env  # Populate TELEGRAM_TOKEN, TELEGRAM_CHAT_ID, DB_PASS
```

### Step 5: Install & Start Systemd Services
```bash
# Install Paper Quant service
sudo cp deploy/ai_quant_bot.service /etc/systemd/system/aq-paper-quant.service
sudo systemctl daemon-reload
sudo systemctl enable --now aq-paper-quant.service

# Check service status
sudo systemctl status aq-paper-quant.service
```
