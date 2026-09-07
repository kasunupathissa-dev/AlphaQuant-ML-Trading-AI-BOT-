# Current System Architecture Overview

## 1. Architectural Landscape

The current codebase represents a multi-generational quantitative trading repository with three co-existing bot architectures deployed across the host server:

```mermaid
graph TB
    subgraph Market Data Layer
        BN_WS[Binance Futures WebSockets]
        BN_REST[Binance Futures REST API]
    end

    subgraph Service Tier - Systemd
        S1[aq-live-main.service<br/>main_v7.py]
        S2[aq-live-scalper.service<br/>scalper_hunt/main_v7.py]
        S3[aq-paper-quant.service<br/>ai_quant_bot/main.py]
        S4[dashboard_app.py<br/>Port 8080]
        S5[async_ingestion.py<br/>Microstructure Daemon]
    end

    subgraph Storage & Cache
        REDIS[(Redis 7.0<br/>Ring Buffers)]
        PG[(PostgreSQL 16 / TimescaleDB<br/>ai_quant_db)]
        CSV_LOGS[Flat File CSV Logs<br/>trading_log_*.csv]
    end

    subgraph Monitoring & Telemetry
        TG[Telegram Bot API<br/>Private Channel]
        WEB_UI[Web Dashboard UI<br/>HTML5 / CanvasJS]
    end

    BN_WS --> S1
    BN_WS --> S2
    BN_WS --> S3
    BN_WS --> S5

    BN_REST --> S1
    BN_REST --> S2
    BN_REST --> S3

    S3 <--> REDIS
    S3 <--> PG
    S1 <--> CSV_LOGS
    S2 <--> CSV_LOGS
    S3 <--> CSV_LOGS

    S1 --> TG
    S2 --> TG
    S3 --> TG

    CSV_LOGS --> S4
    PG --> S4
    S4 --> WEB_UI
```

---

## 2. Inventory of Current Components

| Component | Physical Path | Primary Role | Execution Engine | Status |
| :--- | :--- | :--- | :--- | :--- |
| **Bot 1: Main Engine** | `main_v7.py` | 15m Trend & Reversion Strategy | Procedural Async Loop | Active (Demo / Testnet) |
| **Bot 2: Scalper Hunt** | `scalper_hunt/main_v7.py` | 15m Fast Scalping Variant | Procedural Async Loop | Active (Demo / Testnet) |
| **Bot 3: Paper Quant** | `ai_quant_bot/main.py` | 1m Async WebSocket Paper Engine | Layered Async Engine | Active (Simulated Paper) |
| **Feature Generator** | `feature_generator_v7.py` | Batch Feature Vector Processing | Pandas / NumPy | Active (Offline/Daemon) |
| **Async Ingestion** | `async_ingestion.py` | Tick, Liquidation, & OI Ingestion | WebSocket Pipeline | Active Daemon |
| **Web Dashboard** | `dashboard_app.py` | Multi-Bot Analytics HTTP Server | Python `http.server` | Active (Port 8080) |
| **Auto Trainer** | `auto_trainer_daemon.py` | Periodic ML Model Retraining | Scikit-Learn / XGBoost | Active Daemon |

---

## 3. Current Data Ingestion & Storage Topology

1. **Redis In-Memory Tier**:
   * Utilized by `ai_quant_bot` to store circular candlestick ring buffers under keys `candles:{symbol}`.
   * Capped via atomic Redis pipelines executing `RPUSH` followed by `LTRIM key -500 -1`.
2. **PostgreSQL / TimescaleDB Tier**:
   * Database: `ai_quant_db` (hosted locally on port 5432).
   * Tables:
     * `ohlcv_bars`: Stores normalized 1-minute historical candlestick data.
     * `funding_rates`: Historical 8-hour funding rates and calculated $Z$-scores.
     * `signal_rejections`: Audit table capturing every rejected trade candidate, rejection category, win probability, and forward-tested hypothetical outcome.
3. **CSV Flat File Tier**:
   * `trading_log_v8.csv`: Trade execution log for AlphaQuant V8.2 (Live Main).
   * `trading_log_scalper.csv`: Trade execution log for SCALPER_HUNT.
   * `trading_log_paper.csv`: Real-time trade log for the Paper Quant engine.
   * `trading_features_v8.csv`: Raw feature matrix dump for executed trades.

---

## 4. Current Execution & Telemetry Topology

* **Telegram Confirmation & Alerting Gateway**:
  * Utilizes Telegram Bot API (`https://api.telegram.org/bot<TOKEN>/`) via synchronous `requests.post` or async `loop.run_in_executor`.
  * Alerts include Trade Proposals, Execution Confirmations, Trade Close/PnL summaries, System Performance Reports, and Watchdog health pings.
* **Web Dashboard**:
  * Standalone HTTP server listening on `0.0.0.0:8080`.
  * Provides REST API endpoints (`/api/stats`, `/api/trades`, `/api/performance`, `/api/rejections`) that dynamically parse CSV logs and PostgreSQL tables.

---

## 5. Architectural Health Assessment

```mermaid
pie title Architectural Health & Tech Debt Distribution
    "Clean Layered Code (ai_quant_bot)" : 30
    "Monolithic Procedural Debt (main_v7)" : 45
    "Duplicate Logic (scalper_hunt)" : 15
    "Daemons & Utilities" : 10
```

* **Strengths**: High computational performance, zero external framework overhead, direct CCXT integration, and resilient Redis buffer architecture in Bot 3.
* **Weaknesses**: Significant code duplication between `main_v7.py` and `scalper_hunt/main_v7.py`, tight coupling of alerting with strategy execution, and lack of unified configuration management.
