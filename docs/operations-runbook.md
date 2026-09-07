# Operations Runbook: Standard Operating Procedures (SOP)

## 1. Daily Operator Routine

1. **Check Service Health**:
   ```bash
   sudo systemctl status aq-paper-quant.service aq-live-main.service
   ```
2. **Review Telegram Daily Performance Summary**:
   Confirm win rate %, total completed trades, and that no unexpected circuit breaker warnings fired.
3. **Inspect Active Log Stream**:
   ```bash
   sudo journalctl -u aq-paper-quant.service -f --no-pager
   ```

---

## 2. Emergency Procedures: Emergency Kill Switch

> [!CAUTION]
> **Immediate Execution Halt**: If an abnormal market event, catastrophic exchange bug, or unexpected order flood occurs, execute the emergency kill switch immediately:

```bash
# 1. Stop all bot services instantly
sudo systemctl stop aq-paper-quant.service aq-live-main.service aq-live-scalper.service

# 2. Terminate any lingering python background processes
sudo pkill -9 -f "main_v7.py"
sudo pkill -9 -f "ai_quant_bot"

# 3. Verify all processes are terminated
ps aux | grep python
```

---

## 3. Operational Management Commands

### How to Run in `SIGNAL_ONLY` Mode:
Edit `.env` setting `SIGNAL_ONLY=True` and `SIMULATION_MODE=True`, then restart the service:
```bash
sudo systemctl restart aq-paper-quant.service
```

### How to Inspect Live Paper Positions & Trade History:
```bash
tail -n 20 /home/kasun/repository/AlphaQuant-ML-Trading-AI-BOT-/trading_log_paper.csv
```

### How to Rotate API Keys or Telegram Tokens:
1. Update values inside `/home/kasun/repository/AlphaQuant-ML-Trading-AI-BOT-/.env`.
2. Ensure permissions remain restricted: `chmod 600 .env`.
3. Restart services:
   ```bash
   sudo systemctl restart aq-paper-quant.service aq-live-main.service
   ```
