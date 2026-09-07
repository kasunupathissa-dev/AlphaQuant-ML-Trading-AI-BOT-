# Failure Recovery & State Reconstruction

## 1. System Crash & Unexpected Restart Recovery

When an unexpected host reboot, process crash, or network outage occurs, the platform automatically executes a **State Reconstruction Protocol**:

```mermaid
sequenceDiagram
    autonumber
    participant SYS as Systemd Supervisor
    participant APP as AlphaQuant Engine
    participant DB as PostgreSQL / TimescaleDB
    participant EX as Exchange (Binance Futures)
    participant TG as Telegram Gateway

    SYS->>APP: Restart Process (Restart=always)
    APP->>APP: Execute 5-Point Production Sanity Suite
    APP->>DB: Query open positions from active database
    APP->>EX: Query live positions via fetch_positions()
    
    alt Local State Matches Exchange State
        APP->>TG: Send System Online Recovery Notice
        APP->>APP: Resume Normal Trading Loop
    else State Discrepancy Detected
        APP->>TG: Send CRITICAL: State Mismatch Detected
        APP->>APP: Enter Reconcile Mode (Do Not Open New Trades)
    end
```

---

## 2. Recovery Procedures for Specific Failure Modes

### A. Database Connection Loss
* **Behavior**: Application intercepts `asyncpg.PostgresConnectionError` or `psycopg2.OperationalError`.
* **Action**: Falls back to in-memory buffering and local CSV appending; retries DB reconnection every 10s with exponential backoff up to 60s.

### B. WebSocket Feed Disconnection
* **Behavior**: `WebSocketWatchdog` detects no activity on a symbol stream for $> 120\text{s}$.
* **Action**: Automatically terminates the stale socket, fetches backfill bars via REST, and establishes a fresh WebSocket listener.

### C. Exchange API Outage / HTTP 5xx
* **Behavior**: CCXT raises `ExchangeNotAvailable` or `RequestTimeout`.
* **Action**: Never retries blindly. Marks exchange health as degraded, skips current inference cycle, and awaits healthy ping response.
