# Current Deployment Architecture

## 1. Host Infrastructure Landscape

The platform is deployed on an Ubuntu Linux server hosted at `tradebot.yugadiviya.lk` (IP: `187.127.125.221`).

```mermaid
graph TD
    subgraph Host Server: Ubuntu Linux (tradebot.yugadiviya.lk)
        subgraph Systemd Service Supervision
            SVC1[aq-live-main.service<br/>PID: 546140]
            SVC2[aq-live-scalper.service<br/>PID: 546133]
            SVC3[aq-paper-quant.service<br/>PID: 546740]
            SVC4[dashboard_app.py<br/>PID: 498766]
            SVC5[async_ingestion.py<br/>PID: 399008]
            SVC6[auto_trainer_daemon.py<br/>PID: 398991]
        end
        
        subgraph Database Services
            PG_SVC[PostgreSQL 16 Service<br/>Port 5432]
            REDIS_SVC[Redis 7.0 Service<br/>Port 6379]
        end
        
        subgraph Security & Firewall
            UFW[UFW Firewall]
            F2B[Fail2Ban Service]
        end
    end
```

---

## 2. Systemd Service Unit Inventory

### 1. `aq-live-main.service`
* **File Path**: `/etc/systemd/system/aq-live-main.service`
* **Working Directory**: `/home/kasun/repository/AlphaQuant-ML-Trading-AI-BOT-`
* **ExecStart**: `/home/kasun/repository/AlphaQuant-ML-Trading-AI-BOT-/aq_env/bin/python3 main_v7.py`
* **Configuration**: `USE_TESTNET=True` (Active Demo Trading Mode).
* **Restart Policy**: `Restart=always`, `RestartSec=10`.

### 2. `aq-live-scalper.service`
* **File Path**: `/etc/systemd/system/aq-live-scalper.service`
* **Working Directory**: `/home/kasun/repository/AlphaQuant-SCALPER-HUNT`
* **ExecStart**: `/home/kasun/repository/AlphaQuant-SCALPER-HUNT/aq_env/bin/python3 main_v7.py`
* **Configuration**: `USE_TESTNET=True` (Active Demo Trading Mode).
* **Restart Policy**: `Restart=always`, `RestartSec=10`.

### 3. `aq-paper-quant.service`
* **File Path**: `/etc/systemd/system/aq-paper-quant.service`
* **Working Directory**: `/home/kasun/repository/AlphaQuant-ML-Trading-AI-BOT-`
* **ExecStart**: `/home/kasun/repository/AlphaQuant-ML-Trading-AI-BOT-/aq_env/bin/python3 /home/kasun/repository/AlphaQuant-ML-Trading-AI-BOT-/ai_quant_bot/main.py`
* **Configuration**: `SIMULATION_MODE=True`, Auto-Approval Active.
* **Restart Policy**: `Restart=always`, `RestartSec=10`.

---

## 3. Deployment Scripts & Utilities
* `deploy_alphaquant.sh`: Shell script to clone repository, configure virtualenv, and install systemd unit.
* `deploy_dashboard.sh`: Shell script to launch `dashboard_app.py` in the background.
* `deploy_scalper_hunt.sh`: Shell script to deploy the SCALPER_HUNT repository.
