# AlphaQuant V4.0: True ML Engine Architecture

This is the development directory for the next-generation Machine Learning trading agent.

## Core Directives for V4.0
1. **Decoupled Architecture**: Data ingestion must be separated from inference.
2. **Local Database Storage**: All market data and calculated features must be saved locally (SQLite/PostgreSQL) to enable model training.
3. **Machine Learning Core**: Transition from Heuristic Rules (if/else) to Probabilistic ML (XGBoost/LightGBM).
4. **Vectorized Backtesting**: The logic must be executable against historical datasets without requiring live API connections.
5. **Async I/O**: Shift from synchronous REST calls to `asyncio` for high-frequency data ingestion.

## Development Roadmap
- [ ] **Stage 1**: Database schema & Asynchronous data ingestion engine.
- [ ] **Stage 2**: Feature Store creation (Standardizing EMAs, FVGs, Volatility into ML-readable arrays).
- [ ] **Stage 3**: Backtesting Harness (Offline validation).
- [ ] **Stage 4**: Model Training (XGBoost logic).
- [ ] **Stage 5**: Live Inference & Execution."# AlphaQuant-ML-Trading-AI-BOT-" 
