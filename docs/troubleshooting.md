# Troubleshooting Guide & Remediation Procedures

## 1. Diagnostic Decision Tree

```mermaid
flowchart TD
    PROBLEM[Issue Detected] --> T1{Is Telegram Error Firing?}
    T1 -->|Read Timeout / 429| SOL1[Telegram rate limit: increase sleep interval in polling loop]
    T1 -->|No| T2{Is Service Failing on Boot?}
    
    T2 -->|Database Auth Error| SOL2[Verify DB_PASS in .env and psql connection]
    T2 -->|ML Brain Missing| SOL3[Verify *_brain.pkl files exist in repository root]
    T2 -->|No| T3{Are Positions Not Closing?}
    
    T3 -->|CSV Sync Error| SOL4[Check write permissions on trading_log_*.csv]
    T3 -->|Stale WebSocket Feed| SOL5[Watchdog auto-restarts socket; check Binance ping]
```

---

## 2. Common Runtime Anomalies & Solutions

### Anomaly 1: `HTTPSConnectionPool Read timed out` on Telegram
* **Cause**: Telegram API long-polling timeout when network latency spikes.
* **Impact**: Non-fatal warning; polling loop automatically retries.
* **Fix**: Ensure timeout in `notifier.bot.get_updates(timeout=10)` is configured with a `try/except asyncio.TimeoutError` block.

### Anomaly 2: `Invalid API-key, IP, or permissions for action` (Code -2015)
* **Cause**: Binance API key does not have Futures trading enabled, or the host IP is not whitelisted on Binance.
* **Fix**: Whitelist `187.127.125.221` in the Binance API management portal or switch to `USE_TESTNET=True`.

### Anomaly 3: `Database Permissions / Connection Refused`
* **Cause**: PostgreSQL service stopped or `pg_hba.conf` rejecting md5/scram-sha-256 password.
* **Fix**: Run `sudo systemctl restart postgresql` and verify credentials via `psql -U postgres -d ai_quant_db`.
