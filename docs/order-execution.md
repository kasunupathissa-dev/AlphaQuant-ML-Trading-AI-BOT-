# Order Execution & Bracket Lifecycle

## 1. Bracket Order Execution Protocol

All trades are submitted as **atomic compound bracket structures** consisting of:
1. **Entry Order**: Market or Limit order at the entry target price.
2. **Stop-Loss Protection Order**: `STOP_MARKET` order placed immediately upon entry confirmation.
3. **Take-Profit Target Order**: `TAKE_PROFIT_MARKET` or Limit order linked via One-Cancels-the-Other (OCO) logic.

```mermaid
stateDiagram-v2
    [*] --> CREATED: Signal Approved by Risk Engine
    CREATED --> SUBMITTING: Transmitted to Execution Adapter
    SUBMITTING --> ACTIVE: Entry Filled on Exchange / Simulator
    
    state ACTIVE {
        [*] --> MONITORING
        MONITORING --> TP_TRIGGERED: Price Hits Take-Profit
        MONITORING --> SL_TRIGGERED: Price Hits Stop-Loss
        MONITORING --> TIMEOUT_EXIT: Max Hold Time Exceeded
    }
    
    TP_TRIGGERED --> CLOSED: Cancel SL & Record Profit PnL
    SL_TRIGGERED --> CLOSED: Cancel TP & Record Loss PnL
    TIMEOUT_EXIT --> CLOSED: Market Close Position
    
    CLOSED --> [*]
```

---

## 2. Order Execution State Machine States

* `CREATED`: Order object initialized and validated in memory.
* `SUBMITTING`: Order payload sent to exchange or paper engine.
* `ACTIVE`: Position open with verified stop-loss and take-profit orders in place.
* `CLOSED`: Position completely resolved with realized PnL recorded in database and CSV logs.
* `RECONCILING`: State mismatch detected between local state and exchange; halts execution until verified.
