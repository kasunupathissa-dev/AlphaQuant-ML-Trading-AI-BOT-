# Gemini Code History & Comprehensive Project Architecture Guide: AlphaQuant ML Trading AI

This document serves as the master historical log, architectural record, and complete reference guide for the **AlphaQuant ML Trading AI** system. It aggregates all key development milestones, architectural decision records (ADRs), bug resolution histories, module dependencies, and Telegram notification specifications from `AlphaQuant_project_history` and current codebase evolution (V4.0 to V8.2+).

---

## 1. Executive Summary & Core Strategy

* **Project Objective**: Build a 24/7 autonomous, institutional-grade quantitative trading bot targeting statistical arbitrage opportunities in cryptocurrency futures (Binance USDT-M Futures).
* **Core Philosophy**: ML Meta-Labeling / Ensemble Classification on 1-hour candles combining price action indicators (EMA, ATR, ADX, Bollinger Bands), statistical features (Z-scores of Volume, Funding Rates, Open Interest), and Marcos Lopez de Prado's **Triple Barrier Method**.
* **Current Status**: **Production-Ready (Live Paper/Real-Trading Engine V8.2)** operating on top 10 liquid crypto pairs (`BTC/USDT`, `ETH/USDT`, `SOL/USDT`, `BNB/USDT`, `ADA/USDT`, `XRP/USDT`, `LINK/USDT`, `AVAX/USDT`, `DOGE/USDT`, `DOT/USDT`).

---

## 2. Version Evolution History (V4.0 -> V8.2)

### V4.0 – V4.4: Early Machine Learning & Specialized Brains
* **V4.0 - V4.1**: Introduced initial async engine using CCXT REST/WebSockets and single-model XGBoost predictions.
* **V4.4 (Institutional)**: Implemented continuous position sizing based on model probability confidence and ATR stop-loss multipliers. Introduced daily telemetry Telegram reports.

### V6.5 – V6.9: Production Hardening & Code Centralization
* **V6.5**: Added **State Persistence** ([`live_engine_state.json`](file:///c:/cry_agent/v_4_AQ_AI/live_engine_state.json)) to reload open trades and degradation locks on bot restart. Removed hardcoded credentials in favor of environment variables (`os.getenv`). Centralized indicator math into [`feature_library.py`](file:///c:/cry_agent/v_4_AQ_AI/feature_library.py).
* **V6.6**: Fixed label generation `NaN` data corruption bug ([`CR-001`](file:///c:/cry_agent/v_4_AQ_AI/AlphaQuant_project_history/BUGS.md)) by initializing labels to `0.0` (Loss/No-Trade) instead of `NaN`.
* **V6.8**: Rearchitected WebSocket streams to use a single multiplexed connection (`watch_tickers`) in `ccxt.pro`, resolving ping-pong keepalive timeouts.
* **V6.9**: Hardened Telegram error handling for invalid tokens/chat IDs.

### V7.0 – V7.6: Multi-Signal Ensemble Engine
* **V7.0 - V7.1**: Integrated LightGBM alongside XGBoost ([`ADR-001`](file:///c:/cry_agent/v_4_AQ_AI/AlphaQuant_project_history/DECISIONS.md)) and introduced `auto_trainer_daemon.py` for automated weekly retraining.
* **V7.5 - V7.6**: Added verbose Telegram monitoring modes and fixed pandas Copy-on-Write `ChainedAssignmentError` ([`CR-002`](file:///c:/cry_agent/v_4_AQ_AI/AlphaQuant_project_history/BUGS.md)) and uppercase `'1H'` resample string frequency regressions ([`CR-003`](file:///c:/cry_agent/v_4_AQ_AI/AlphaQuant_project_history/BUGS.md)).

### V8.0 – V8.2: The "Shotgun" Architecture Overhaul (Current Master)
* **Problem**: V7 filtering used strict primary signal filters (Trend, Breakout, Reversion) *before* passing samples to ML models, resulting in **Data Starvation** (<1% of candles labeled) and underperforming out-of-sample models.
* **V8.0 Shotgun Solution**: Re-architected pipeline to label **every single candle** with Triple Barrier outcomes (0=SHORT, 1=LONG, 2=HOLD/NO-TRADE), multiplying dataset size by >100x while treating primary signals as features.
* **V8.2 Fixes**: Fixed numpy float32 JSON serialization error in state saving, added model format compatibility checks during brain loading, and centralized system parameters in [`config.py`](file:///c:/cry_agent/v_4_AQ_AI/config.py).

---

## 3. System Architecture & Component Mapping

```mermaid
graph TD
    subgraph "Offline Batch Pipeline"
        A[data_ingestion.py] --> B[(MySQL Database / SQLite)];
        C[feature_generator_v7.py] --> B;
        D[label_generator_v6.py] --> B;
        E[model_training_v7.py] --> B;
        E --> F{{Asset Brain Models (.pkl)}};
        G[validation_suite_v8.py] --> B;
        G --> F;
    end

    subgraph "Live Async Trading Engine"
        H[main_v7.py] --> F;
        H --> I(Binance API / WebSocket);
        H <--> J[live_engine_state.json];
        H --> K(Telegram Notifications);
    end

    subgraph "Shared Core Infrastructure"
        L[feature_library.py];
        M[database_config.py];
        N[config.py];
    end

    C --> L;
    H --> L;
    A --> M;
    C --> M;
    D --> M;
    E --> M;
    G --> M;
```

### Core Subsystems & File Layout

| Subsystem | Key Files | Description & Responsibility |
| :--- | :--- | :--- |
| **Shared Core** | [`config.py`](file:///c:/cry_agent/v_4_AQ_AI/config.py)<br>[`feature_library.py`](file:///c:/cry_agent/v_4_AQ_AI/feature_library.py)<br>[`database_config.py`](file:///c:/cry_agent/v_4_AQ_AI/database_config.py) | Centralized system parameters (confidence thresholds, ATR multipliers), single source of truth for technical indicators & Z-scores, MySQL ORM connection engine. |
| **Data Ingestion** | [`data_ingestion.py`](file:///c:/cry_agent/v_4_AQ_AI/data_ingestion.py)<br>[`async_ingestion.py`](file:///c:/cry_agent/v_4_AQ_AI/async_ingestion.py) | Fetches historical OHLCV data, funding rates, and open interest from Binance Futures API into `market_data_1h`. |
| **Feature & Label Pipeline** | [`feature_generator_v7.py`](file:///c:/cry_agent/v_4_AQ_AI/feature_generator_v7.py)<br>[`label_generator_v6.py`](file:///c:/cry_agent/v_4_AQ_AI/label_generator_v6.py) | Computes price & statistical features, labels every candle via Triple Barrier Method, stores output in `feature_store`. |
| **Model Training & Validation** | [`model_training_v7.py`](file:///c:/cry_agent/v_4_AQ_AI/model_training_v7.py)<br>[`validation_suite_v8.py`](file:///c:/cry_agent/v_4_AQ_AI/validation_suite_v8.py)<br>[`run_full_pipeline_v8.py`](file:///c:/cry_agent/v_4_AQ_AI/run_full_pipeline_v8.py) | Trains multi-class XGBoost + LightGBM ensemble models with `CalibratedClassifierCV` (Isotonic), produces `.pkl` model brains and walk-forward reliability curves. |
| **Live Async Engine** | [`main_v7.py`](file:///c:/cry_agent/v_4_AQ_AI/main_v7.py)<br>[`live_engine_state.json`](file:///c:/cry_agent/v_4_AQ_AI/live_engine_state.json) | 24/7 live trading bot using `ccxt.pro` multiplexed WebSockets, managing real-time trade execution, ATR SL/TP, degradation locking, and state persistence. |
| **Continuous Learning Daemon** | [`auto_trainer_daemon.py`](file:///c:/cry_agent/v_4_AQ_AI/auto_trainer_daemon.py) | Background daemon executing weekly model retraining jobs every Sunday at 02:00 UTC. |
| **Project Documentation** | [`AlphaQuant_project_history/`](file:///c:/cry_agent/v_4_AQ_AI/AlphaQuant_project_history) | Contains 15 structured Markdown files detailing architecture, context, decisions, roadmap, standards, and bug trackers. |

---

## 4. Architectural Decision Records (ADR Summary)

* **ADR-001: Move to Ensemble Modeling**
  * *Decision*: Combine **XGBoost** and **LightGBM** predictions via simple probability averaging.
  * *Rationale*: Reduces single-model algorithmic bias/variance and improves out-of-sample prediction reliability.
* **ADR-002: Implement State Persistence via JSON**
  * *Decision*: Serialize active trades, penalty-boxed assets, and recent win/loss histories into [`live_engine_state.json`](file:///c:/cry_agent/v_4_AQ_AI/live_engine_state.json).
  * *Rationale*: Provides lightweight, zero-dependency recovery from bot crashes or server restarts, preventing trade orphaned states.
* **ADR-003: Externalize Secrets to Environment Variables**
  * *Decision*: Load API keys, database credentials, and Telegram tokens via `os.getenv()`.
  * *Rationale*: Enhances security by completely decoupling source code from production secrets.

---

## 5. Critical Bug Resolution Registry

| Bug ID | Severity | Root Cause | Fix Implementation | Fixed Version |
| :--- | :--- | :--- | :--- | :--- |
| **CR-001** | Critical | `label_generator` initialized labels with `NaN`, crashing model training with `ValueError: Input y_true contains NaN`. | Initialized labels as `0.0` (Loss/No-Trade) default. | V6.6 ([`label_generator_v5.py`](file:///c:/cry_agent/v_4_AQ_AI/label_generator_v5.py)) |
| **CR-002** | Critical | Pandas Copy-on-Write `ChainedAssignmentError` during `fillna()` in live engine. | Replaced `inplace=True` with explicit DataFrame assignment. | V7.6 ([`main_v7.py`](file:///c:/cry_agent/v_4_AQ_AI/main_v7.py)) |
| **CR-003** | Critical | Lowercase `'1h'` passed to `pandas.resample()`, breaking frequency string format. | Enforced uppercase `'1H'` frequency string standard. | V7.5 ([`main_v7.py`](file:///c:/cry_agent/v_4_AQ_AI/main_v7.py)) |
| **HI-001** | High | `ModuleNotFoundError` on production server due to outdated `requirements.txt`. | Updated `requirements.txt` with `ccxt`, `lightgbm`, `schedule`, `shap`. | V7.1 ([`requirements.txt`](file:///c:/cry_agent/v_4_AQ_AI/requirements.txt)) |
| **HI-002** | High | Zombie bot processes on server from multiple `screen -S` invocations. | Established operational procedure using `killall screen` and `screen -wipe`. | Deployment Guide |
| **JSON-01** | High | `TypeError: float32 not JSON serializable` during `save_state()`. | Added custom `NumpyEncoder` JSON serialization class in live engine. | V8.2 ([`main_v7.py`](file:///c:/cry_agent/v_4_AQ_AI/main_v7.py)) |

---

## 6. Comprehensive Telegram Notification Reference

Notifications are sent via Telegram Bot API using Markdown formatting:

1. **Trade Signal Executed**:
   ```markdown
   🧠 *[V8.2] SHOTGUN SIGNAL EXECUTED*
   • *Asset*: BTC/USDT | *Direction*: *LONG*
   • *Entry Price*: `$64,250.5000`
   • *Stop Loss (SL)*: `$63,800.2000` (-0.70%)
   • *Take Profit (TP)*: `$64,925.9500` (+1.05%)
   • *Position Size*: `$1,427.78` (Notional)
   • *Risk Amount*: `$10.00` | *R:R*: `1:1.5`
   • *AI Win Prob*: *61.45%*
   ```
2. **Trade Exit (TP/SL Hit)**:
   ```markdown
   🟢 🔔 *[V8.2] TRADE CLOSED*
   • *Asset*: ETH/USDT | *Direction*: SHORT
   • *Status*: *PROFIT* | *Net PnL*: *$+15.30*
   • *Entry Price*: $3,500.0000
   • *Exit Price*: $3,447.5000
   • *Take Profit (TP)*: $3,447.5000
   • *Stop Loss (SL)*: $3,535.0000
   ```
3. **Degradation Lock (24-Hour Isolation)**:
   ```markdown
   🛑 *DEGRADATION LOCK*: SOL/USDT isolated for 24 hours.
   ```
4. **Engine Lifecycle Status**:
   ```markdown
   🚀 *[AlphaQuant V8.2]*
   Serialization-Fixed Engine LIVE. Loaded 10/10 models.
   ```
5. **Auto-Trainer Retraining Status**:
   ```markdown
   🤖 *[V7.1 Auto-Train]*
   Starting weekly model retraining cycle...

   ✅ *[V7.1 Auto-Train]*
   Weekly model retraining cycle completed successfully.
   Duration: *14.25 minutes*. New AI brains are now live.
   ```

---

## 7. AI Assistant Engineering Rules

As defined in [`AI_RULES.md`](file:///c:/cry_agent/v_4_AQ_AI/AlphaQuant_project_history/AI_RULES.md):
1. **Zero-Trust Workflow**: Always read target files first before writing.
2. **Atomic Changes**: Implement focused, incremental edits rather than whole-file rewrites.
3. **Cross-File Impact Analysis**: Verify related files when modifying shared routines (e.g. [`feature_library.py`](file:///c:/cry_agent/v_4_AQ_AI/feature_library.py)).
4. **No Silent Failures**: Never use bare `except:` blocks; always log exceptions.
5. **Async Safety**: Do not use blocking I/O calls (`time.sleep`, synchronous `requests`) inside `async def` routines.