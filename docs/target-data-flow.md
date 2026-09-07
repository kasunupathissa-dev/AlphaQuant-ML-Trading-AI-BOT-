# Target Data Flow & Event Pipelines

## 1. Unified Event-Driven Data Flow

The target architecture operates on an **event-driven pipeline** where data flows sequentially through validation, calculation, strategy evaluation, risk verification, and simulated execution:

```mermaid
sequenceDiagram
    autonumber
    participant EX as Exchange (Binance Futures)
    participant INGEST as Data Ingestion Service
    participant BUS as Internal Event Bus (Asyncio Queue)
    participant FEAT as Feature Engine
    participant STRAT as Strategy Modules
    participant AGG as Signal Aggregator
    participant RISK as Risk Management Engine
    participant PORT as Portfolio State Manager
    participant EXEC as Paper Execution Adapter
    participant DB as TimescaleDB Persistence
    participant TG as Telegram Alert Gateway

    EX->>INGEST: Stream WebSocket Ticks & Closed Klines
    INGEST->>BUS: Publish Normalized MarketEvent
    BUS->>FEAT: Ingest MarketEvent -> Compute Features (CVD, ATR, Squeeze)
    FEAT->>STRAT: Dispatch FeatureSnapshot
    
    par Strategy Evaluation
        STRAT->>STRAT: Evaluate Shotgun Momentum Strategy
        STRAT->>STRAT: Evaluate Liquidation Cascade Strategy
        STRAT->>STRAT: Evaluate Mean Reversion Strategy
    end
    
    STRAT->>AGG: Submit Candidate Signal Objects
    AGG->>AGG: Arbitrate Conflicts, Filter Regime, Weight Evidence
    AGG->>RISK: Dispatch Aggregated Final Signal
    
    alt Signal Fails Risk Gate (Spread, Sizing, Exposure, Circuit Breaker)
        RISK->>DB: Log Rejection Audit (Candidate & Missed EV Tracking)
    else Signal Approved by Risk Gate
        RISK->>PORT: Request Sizing & Margin Allocation
        PORT-->>RISK: Approved Quantity & Bracket Parameters
        RISK->>EXEC: Submit Validated Order Bracket
        EXEC->>PORT: Register Open Position State
        EXEC->>DB: Persist Trade Record
        EXEC->>TG: Broadcast Signal Card & Trade Execution Alert
    end
```

---

## 2. Event Schemas & Domain Contracts

### A. `CandleEvent`
```json
{
  "event_type": "CANDLE_CLOSED",
  "exchange": "binance_futures",
  "symbol": "SOL/USDT",
  "timeframe": "1m",
  "timestamp": 1787736900000,
  "open": 96.35,
  "high": 96.42,
  "low": 96.31,
  "close": 96.38,
  "volume": 12450.2,
  "is_closed": true
}
```

### B. `MicrostructureEvent`
```json
{
  "event_type": "ORDER_FLOW_TICK",
  "exchange": "binance_futures",
  "symbol": "SOL/USDT",
  "timestamp": 1787736900500,
  "cvd_1m": 425000.0,
  "oi_change_1m": 12500.0,
  "liquidation_volume_usd": 85000.0,
  "liquidation_side": "SHORT",
  "bid_ask_spread_pct": 0.02
}
```
