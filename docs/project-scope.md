# Project Scope & Operational Boundaries

## 1. Project Overview

The **AlphaQuant Quantitative Platform** is an algorithmic signal generation, market data ingestion, and risk-managed execution framework built for cryptocurrency derivatives markets.

The primary system objective is to provide a reliable, modular, and measurable environment for research, backtesting, forward-testing, and simulated execution of quantitative strategies across liquid cryptocurrency perpetual contracts.

---

## 2. In-Scope Deliverables & Capabilities

### Market Data Ingestion
* Ingestion of live OHLCV candlestick data (1m and 15m timeframes) via Binance Futures WebSockets and REST fallback endpoints.
* Real-time tracking of funding rates, open interest (OI), and liquidation events via CCXT Pro and Binance WebSocket streams.
* Pruned circular memory buffers utilizing Redis lists (`LPUSH` / `LTRIM`) to maintain bounded operational memory footprints.

### Feature Engineering & Modeling
* Quantitative feature calculations: Wilder's ADX, Average True Range (ATR), Bollinger Band Width / Squeeze ratios, Relative Volume (RVOL), Cumulative Volume Delta (CVD) proxies, Choppiness Index, and MACD Histogram.
* Pre-trained Machine Learning inference utilizing scikit-learn, XGBoost, and isotonic calibration models (`ManualCalibratedClassifier`).

### Strategy & Signal Generation
* Multi-timeframe trend-following momentum models.
* Statistical mean-reversion models detecting extreme price-distribution anomalies ($Z$-score $\ge \pm 3.0$).
* High-probability signal generation with predefined Entry, Take-Profit (TP), and Stop-Loss (SL) targets.

### Risk Controls & Portfolio Safety
* Maximum percentage risk per trade constraint (default: 1.0% of margin equity).
* Minimum Risk-to-Reward Ratio (RRR) enforcement (minimum 1:1.5).
* Portfolio concentration ceilings (maximum 3 concurrent open trade brackets).
* Spread anomaly rejection (maximum 0.15% bid-ask spread threshold).
* Dynamic daily loss drawdown circuit breakers (2.5% daily drawdown threshold triggering 24h trading isolation).
* Stale data watchdog monitoring WebSocket heartbeat liveness (120-second threshold).

### Execution Modes
* **Mode 1: `SIGNAL_ONLY`**: Generates and broadcasts structured signal cards to Telegram without initiating order submissions.
* **Mode 2: `PAPER_TRADING`** (Default): Simulates order placements, slippage, and position lifecycles in memory and logs outcomes to persistent storage (`trading_log_paper.csv`).
* **Mode 3: `LIVE_TRADING`** (Disabled by Default): Automated or semi-automated execution on live exchange endpoints. Requires explicit, manual operator authorization.

### Telemetry, Storage, & Dashboards
* PostgreSQL / TimescaleDB persistence for historical candlestick bars, funding rate history, and rejected signal audits.
* Real-time Telegram alerting with interactive confirmation gates and periodic performance summaries.
* Multi-bot performance web dashboard hosted via a lightweight Python HTTP server (`dashboard_app.py`).

---

## 3. Supported Markets & Instruments

The platform exclusively targets high-liquidity cryptocurrency perpetual contracts settled in USDT (USDⓈ-M Futures on Binance):

| Asset Symbol | Base Asset | Quote Asset | Contract Type | Default Risk Allocation |
| :--- | :--- | :--- | :--- | :--- |
| `SOL/USDT` | Solana | USDT | Linear Perpetual | $1.0\times$ (Standard) |
| `NEAR/USDT` | NEAR Protocol | USDT | Linear Perpetual | $0.75\times$ (Conservative) |
| `SUI/USDT` | Sui | USDT | Linear Perpetual | $1.0\times$ (Standard) |
| `HBAR/USDT` | Hedera | USDT | Linear Perpetual | $1.0\times$ (Standard) |
| `XRP/USDT` | XRP | USDT | Linear Perpetual | $1.25\times$ (Aggressive) |
| `LINK/USDT` | Chainlink | USDT | Linear Perpetual | $1.0\times$ (Standard) |
| `AVAX/USDT` | Avalanche | USDT | Linear Perpetual | $1.25\times$ (Aggressive) |
| `DOGE/USDT` | Dogecoin | USDT | Linear Perpetual | $1.0\times$ (Standard) |
| `DOT/USDT` | Polkadot | USDT | Linear Perpetual | $0.75\times$ (Conservative) |

> [!NOTE]
> `BTC/USDT` and `ETH/USDT` are tracked for macroeconomic regime identification and correlation analysis, but are omitted from primary active trade execution to protect small wallet margin safety.

---

## 4. Explicit Non-Goals & Out-of-Scope Items

* **No High-Frequency Market Making (HMM)**: The system is not designed for sub-millisecond co-located order book market-making.
* **No Unhedged Grid / Martingale Trading**: The system strictly forbids doubling down on losing positions or using unhedged averaging grids.
* **No Guaranteed Wealth or Profit Promises**: The system makes no representations regarding guaranteed returns. All trading involves capital risk.
* **No Multi-Exchange Arbitrage**: The current scope is focused on single-venue directional execution on Binance Futures. Cross-exchange latency arbitrage is out of scope.
* **No Automated Fund Withdrawals**: API integration is strictly forbidden from requesting or possessing withdrawal permissions.
