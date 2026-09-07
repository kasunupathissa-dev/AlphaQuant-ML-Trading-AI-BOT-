# High-Fidelity Paper Trading Simulation Engine

## 1. Paper Simulation Architecture

The `PaperExecutionAdapter` (`ai_quant_bot/execution/paper_tracker.py`) provides high-fidelity exchange simulation using the exact same signal generation, risk gates, and portfolio state logic as production trading, while executing exclusively in virtual memory and persistent storage.

```mermaid
graph TD
    SIGNAL[Approved Signal] --> PAPER[Paper Execution Adapter]
    PAPER --> SIM_POS[(Active Virtual Positions Table)]
    
    TICK[Live 1m Candle Stream] --> EVAL[Price Resolution Engine]
    SIM_POS --> EVAL
    
    EVAL -->|Candle High >= TP (Long)| PROFIT[Record PROFIT & Calculate Realized PnL]
    EVAL -->|Candle Low <= SL (Long)| LOSS[Record LOSS & Calculate Realized PnL]
    
    PROFIT --> CSV[(trading_log_paper.csv)]
    LOSS --> CSV
    PROFIT --> TG[Telegram Notification]
    LOSS --> TG
```

---

## 2. Realistic Simulation Modeling Rules

To prevent backtesting / paper-trading optimism, the simulation engine models:
1. **Taker Fee Friction**: Deducts standard Binance VIP0 taker fees ($0.05\%$ on entry $+ 0.05\%$ on exit $= 0.10\%$ total).
2. **Slippage Penalty**: Penalizes entries by $1.0\text{ tick}$ ($0.01\% - 0.03\%$) to simulate order book spread traversal.
3. **Execution Latency**: Delays fill timestamps by $150\text{ ms}$ relative to candle close event times.
4. **Zero Lookahead**: Position evaluation occurs strictly against future subsequent bars after the entry bar closes.
