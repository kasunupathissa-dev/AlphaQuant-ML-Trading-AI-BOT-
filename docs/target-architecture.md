# Target Architecture Blueprint: Unified Quantitative Platform

## 1. 16-Layer Modular Platform Architecture

The target architecture is a decoupled, event-driven quantitative trading and signal platform structured across 16 formal architectural layers:

```mermaid
flowchart TD
    L1[1. Market Data Ingestion Layer<br/>CCXT Pro WebSockets & Order Flow Ingestion] --> L2[2. Data Validation Layer<br/>Timestamp, Gap & Monotonicity Verifier]
    L2 --> L3[3. Data Normalization Layer<br/>Asset Symbol, Scale & Decimal Normalizer]
    L3 --> L4[4. Feature & Indicator Engine<br/>Microstructure CVD, Liquidation & Volatility Math]
    
    L4 --> L5A[5A. Strategy: 15m Shotgun Momentum]
    L4 --> L5B[5B. Strategy: 1m Liquidation Cascade Hunter]
    L4 --> L5C[5C. Strategy: Statistical Mean Reversion]
    
    L5A --> L6[6. Signal Aggregator & Regime Arbiter]
    L5B --> L6
    L5C --> L6
    
    L6 --> L7[7. Deterministic Risk Engine<br/>Fail-Closed Risk & Circuit Breakers]
    
    L7 -->|Rejected Candidate| L11A[(Rejection Audit Table)]
    L7 -->|Approved Signal| L8[8. Portfolio & Position State Machine]
    
    L8 --> L9[9. Execution Simulation Layer<br/>Paper Trading Engine with Fee & Slippage Model]
    L8 -.->|Explicit Live Flag Only| L10[10. Exchange Execution Adapter<br/>Binance Futures CCXT Client]
    
    L9 --> L11[11. Persistence Layer<br/>TimescaleDB & Redis Ring Buffers]
    L9 --> L12[12. Notification Gateway<br/>Async Telegram Interactive Alerts]
    L9 --> L13[13. Observability & Telemetry<br/>Prometheus, Structured JSON Logs, Dashboard]
    
    L4 -.-> L14[14. Backtesting & Simulation Suite]
    L15[15. Configuration Subsystem<br/>Pydantic Models & .env Hierarchy] --> L7
    L16[16. Emergency Admin & Kill Switch] --> L7
    L16 --> L10
```

---

## 2. Layer Responsibilities & Boundaries

| Layer # | Layer Name | Responsibility & Boundary |
| :--- | :--- | :--- |
| **Layer 1** | **Market Data Ingestion** | Connects to Binance Futures WebSockets and REST feeds; streams raw tick trades, klines, liquidations, and depth. |
| **Layer 2** | **Data Validation** | Detects missing candles, out-of-sequence timestamps, price spikes, and stale data streams. |
| **Layer 3** | **Data Normalization** | Standardizes incoming data into immutable dataclass event structures (`CandleEvent`, `TickEvent`, `LiquidationEvent`). |
| **Layer 4** | **Feature & Indicator Engine** | Computes technical indicators and raw order flow metrics (CVD, OI velocity, ATR, ADX, Bollinger Squeeze). |
| **Layer 5** | **Strategy Modules** | Isolated strategy classes implementing the `Strategy` interface. Generates candidate `Signal` objects. |
| **Layer 6** | **Signal Aggregator** | Combines signals from multiple strategies, arbitrates conflicting directions, and weights by market regime. |
| **Layer 7** | **Deterministic Risk Engine** | Enforces fail-closed risk checks: maximum risk per trade, spread ceilings, position limits, and circuit breakers. |
| **Layer 8** | **Portfolio & Position State** | Maintains global portfolio state, cash balance, margin requirements, open positions, and unrealized PnL. |
| **Layer 9** | **Execution Simulation Layer** | Simulates realistic bracket order fills, slippage, taker fees, and latency in `PAPER_TRADING` mode. |
| **Layer 10** | **Exchange Execution Adapter** | Connects to live exchange endpoints. **Disabled by default**; requires manual live override. |
| **Layer 11** | **Persistence Layer** | Persists candlestick data, funding rates, trade executions, and rejection audits in TimescaleDB and Redis. |
| **Layer 12** | **Notification Gateway** | Dispatches interactive signal cards, execution receipts, and daily executive summaries to Telegram. |
| **Layer 13** | **Observability & Telemetry** | Exposes Prometheus metrics (`/metrics`), structured JSON application logs, and Web Dashboard APIs. |
| **Layer 14** | **Backtesting Suite** | Bias-free event-driven backtesting engine with walk-forward validation and parameter sensitivity testing. |
| **Layer 15** | **Configuration Subsystem** | Strongly-typed configuration schema validated via Pydantic with `.env` secrets injection. |
| **Layer 16** | **Kill Switch & Admin** | Emergency operator controls: immediate position closure, trading halt, and service isolation. |
