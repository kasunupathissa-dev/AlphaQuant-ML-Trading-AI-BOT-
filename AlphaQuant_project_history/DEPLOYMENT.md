# AlphaQuant Deployment Guide

This document provides the standard operating procedure for deploying the AlphaQuant V7 system to a production Ubuntu server.

## 1. Initial Server Setup

1.  **Provision Server:** A clean Ubuntu 22.04 LTS server is recommended.
2.  **Install System Dependencies:** Install Python, Git, MySQL, and the necessary build tools.
    ```bash
    sudo apt-get update
    sudo apt-get install -y python3-pip python3-venv python3-dev git mysql-server pkg-config libmariadb-dev-compat libmariadb-dev
    ```
3.  **Secure MySQL:** Run `sudo mysql_secure_installation` and follow the prompts.

## 2. Database Setup

1.  **Log into MySQL:** `sudo mysql -u root -p`
2.  **Create Database and User:** Execute the following SQL commands, replacing the password with a strong, generated secret.
    ```sql
    CREATE DATABASE alphaquant_v5;
    CREATE USER 'aq_user'@'localhost' IDENTIFIED BY 'YourSecurePasswordHere';
    GRANT ALL PRIVILEGES ON alphaquant_v5.* TO 'aq_user'@'localhost';
    FLUSH PRIVILEGES;
    exit;
    ```

## 3. Code Deployment

1.  **Clone Repository:** `git clone <your_private_repo_url>`
2.  **Create & Activate Environment:**
    ```bash
    cd AlphaQuant-ML-Trading-AI-BOT-
    python3 -m venv aq_env
    source aq_env/bin/activate
    ```
3.  **Install Dependencies:** `pip install -r requirements.txt`

## 4. Secrets Management

Set the following environment variables. For a permanent setup, add these `export` commands to the end of your `~/.bashrc` file.

```bash
export DB_PASS="YourSecurePasswordHere"
export TELEGRAM_TOKEN="Your_Telegram_Bot_Token"
export TELEGRAM_CHAT_ID="Your_Personal_Chat_ID"
```
After editing `~/.bashrc`, run `source ~/.bashrc` to apply the changes.

## 5. Initial Model Training

Before the first run, you must generate the AI models on the server.

```bash
# Ensure your virtual environment is active
source aq_env/bin/activate

# Run the master pipeline
python run_full_pipeline_v7.py
```

## 6. Launching Production Services

Use `screen` to run the two main services in the background.

1.  **Kill Any Old Processes (Safety Check):** `sudo killall -9 screen; screen -wipe`
2.  **Launch Live Engine:** `screen -S v6_live -d -m python main_v7.py`
3.  **Launch Auto-Trainer Daemon:** `screen -S v6_daemon -d -m python auto_trainer_daemon.py`

## 7. Monitoring & Health Checks

-   **Check Running Services:** Use `screen -ls` to verify both `v6_live` and `v6_daemon` are `(Detached)`.
-   **View Live Console:** Use `screen -r v6_live` to attach to the main bot's console. Detach with `Ctrl+A`, `D`.
-   **Check System Health:** Use `htop` to monitor CPU/Memory and `df -h` to monitor disk space.
-   **Check Telegram:** You should receive a startup notification from both services.

## 8. Rollback Procedure

If a new deployment introduces a critical bug, follow these steps to roll back to the previous stable version:

1.  **Stop Services:** `sudo killall -9 screen`
2.  **Revert Code:** Use `git` to check out the last known-good commit or tag.
    ```bash
    git checkout v7.5 # Example of checking out a stable tag
    ```
3.  **Relaunch Services:** Follow the launch procedure in Step 6.
