# Current Data Flow Architecture

## 1. End-to-End Data Ingestion & Execution Flow

This document details the real-time data flows across the system components, from exchange feeds to database persistence and telemetry.

---

## 2. Ingestion & Execution Sequence Diagram

```mermaid
sequenceDiagram
    autonumber
    participant BN as Binance Futures (WS & REST)
    participant COL as Async Collector (collector.py)
    participant REDIS as Redis Ring Buffer
    participant FEAT as Feature Engineering (feature_library.py)
    participant ML as ML Brain Classifier (*_brain.pkl)
    participant RISK as Risk Management Engine (risk_manager.py)
    participant SIM as Paper Execution / Binance Client
    participant TRACK as Paper Trade Tracker (paper_tracker.py)
    participant DB as PostgreSQL / TimescaleDB
    participant TG as Telegram Bot Gateway

    Note over BN,COL: Continuous 1m WebSocket Stream
    BN->>COL: kline message (closed = true)
    COL->>REDIS: RPUSH & LTRIM (Capped 500 bars)
    COL->>DB: INSERT into ohlcv_bars
    
    COL->>TRACK: update_positions(latest_candle)
    opt Active Position Hit TP or SL
        TRACK->>SIM: Mark Position Closed (PROFIT/LOSS)
        TRACK->>TG: Send Trade Closed Alert (PnL & Running Win Rate)
    end

    COL->>FEAT: generate_full_feature_vector(df_history)
    FEAT-->>COL: 12-indicator feature vector
    
    COL->>ML: predict_proba(feature_vector)
    ML-->>COL: Calibrated Win Probability (e.g. 71.67%)
    
    COL->>RISK: evaluate_order_proposal(symbol, direction, entry, atr, balance)
    
    alt Setup Passes Confidence Threshold & Risk Criteria
        RISK-->>COL: Approval (quantity, sl_price, tp_price)
        COL->>TRACK: record_entry(symbol, direction, entry, sl, tp, qty, prob)
        COL->>SIM: submit_bracket_trade(entry, sl, tp, qty)
        COL->>TG: Send Trade Executed Alert
    else Setup Fails Confidence or Risk Gate
        RISK-->>COL: Rejection (reason_code)
        COL->>DB: INSERT into signal_rejections (symbol, dir, prob, reason)
    end
```

---

## 3. Component Data Transformation Pipeline

| Stage | Input Data Structure | Output Data Structure | Latency Profile |
| :--- | :--- | :--- | :--- |
| **1. WebSocket Ingest** | Raw JSON Binance kline payload | Normalized Python dictionary | $< 5\text{ ms}$ |
| **2. Buffer Append** | Candlestick dict `[ts, o, h, l, c, v]` | Redis List (`candles:{symbol}`) | $< 2\text{ ms}$ |
| **3. Feature Extraction** | Pandas DataFrame (150 bars $\times 6$ cols) | 1D Feature Vector (12 floats) | $15 - 35\text{ ms}$ |
| **4. ML Inference** | 1D NumPy array (`1 x 12`) | Win Probability float ($0.0 - 100.0\%$) | $< 3\text{ ms}$ |
| **5. Risk Evaluation** | Candidate dict + Margin Balance | Sized Proposal dict or Rejection Code | $< 1\text{ ms}$ |
| **6. Paper Execution** | Approved Order Specs | Updated `trading_log_paper.csv` row | $< 5\text{ ms}$ |
| **7. Rejection Audit** | Rejection tuple | PostgreSQL `signal_rejections` row | $< 10\text{ ms}$ |
| **8. Telemetry Dispatch** | Formatted Markdown payload | Telegram Bot API HTTPS POST | $150 - 450\text{ ms}$ |

---

## 4. Periodic Background Data Flows

```mermaid
flowchart TD
    TIMER[30-Minute Timer] --> A[1. Monitor Rejected Signals Outcomes]
    TIMER --> B[2. Check Daily Drawdown Limit]
    TIMER --> C[3. Calibration Drift Audit]
    TIMER --> D[4. Compile Performance Summary]
    
    A --> A1[Fetch Current Prices -> Compare vs Rejection Entry/TP/SL]
    A1 --> A2[Update signal_rejections: outcome_status & missed_pnl]
    
    B --> B1[Get Balance -> Compare vs Peak Equity]
    B1 -->|Drawdown > 2.5%| B2[Activate Circuit Breaker Isolation]
    
    C --> C1[Query Last 30 Rejections -> Calculate Win Rate]
    C1 -->|Win Rate of Rejections > 60%| C2[Trigger Calibration Drift Alert]
    
    D --> D1[Query Paper Tracker Stats + Active Positions]
    D1 --> D2[Dispatch System Performance Report to Telegram]
```
