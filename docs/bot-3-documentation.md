# Bot 3: AlphaQuant Paper Quant Engine (`ai_quant_bot`)

## 1. Purpose & Objectives
**AlphaQuant Paper Quant** is a modern, asynchronous, layered quantitative platform designed to ingest real-time 1-minute market data via CCXT Pro WebSockets, calculate quantitative features in bounded Redis memory buffers, evaluate machine learning models, and execute simulated paper trading with zero live financial exposure.

---

## 2. Directory Structure & Key Files
```
c:\cry_agent\v_4_AQ_AI\ai_quant_bot\
├── main.py                     # Main async orchestrator (427 lines)
├── config/
│   ├── config.py               # Global environment & parameter definitions
│   └── assets.yaml             # Asset-specific threshold & risk matrix
├── data/
│   ├── collector.py            # Async CCXT Pro WebSocket data stream ingestion
│   ├── database.py             # SQLAlchemy Asyncpg TimescaleDB ORM schema
│   ├── redis_buffer.py         # Redis-backed fixed-length ring buffer (500 bars)
│   └── maintenance.py          # Periodic database vacuum & cleanup worker
├── execution/
│   ├── binance_client.py       # CCXT Binance Futures client with simulation mode
│   ├── circuit_breaker.py      # Automated daily loss drawdown circuit breaker
│   ├── paper_tracker.py        # Persistent paper trade manager & win rate analyzer
│   └── risk_manager.py         # Sizing, RRR, and portfolio exposure engine
├── features/
│   ├── feature_library.py      # Aligned 12-feature calculation engine
│   └── label_generator.py      # Triple-barrier labeling generator
├── models/
│   ├── calibrator.py           # Probability calibration module
│   └── train_pipeline.py       # TimeSeriesSplit ML training pipeline
├── monitoring/
│   ├── rejection_audit.py      # Hypothetical P&L tracking of filtered signals
│   ├── telegram_notifier.py    # Async Telegram notification gateway
│   └── watchdog.py             # Stale data feed liveness monitor (120s timeout)
└── validation_suite.py         # 5-point pre-flight production sanity suite
```

---

## 3. Entry Points & Runtime Lifecycle
* **Entry Command**: `python ai_quant_bot/main.py`
* **Systemd Service**: `aq-paper-quant.service`
* **Lifecycle Flow**:
  1. Executes 5-point production sanity suite (Binance API connectivity, ML models presence, ADX math sanity, Telegram connectivity, Database read/write permissions).
  2. Initializes PostgreSQL schema (`ohlcv_bars`, `funding_rates`, `signal_rejections`).
  3. Pre-warms Redis sliding buffers with 150 historical bars per asset via REST.
  4. Launches concurrent async WebSocket listeners (`_watch_ohlcv_stream`) across all 9 target assets.
  5. Upon every closed 1-minute candle:
     - Appends candle to Redis buffer (`RPUSH` / `LTRIM 500`).
     - Updates active paper positions for Take-Profit / Stop-Loss resolution (`paper_tracker.update_positions`).
     - Computes quantitative feature vector (`FeatureEngineering.generate_full_feature_vector`).
     - Computes ML win probability via pickled `ManualCalibratedClassifier`.
     - Validates confidence threshold (`assets.yaml`) and risk rules (`risk_manager.py`).
     - If approved: Auto-executes virtual bracket order, logs entry to `trading_log_paper.csv`, and sends Telegram alert.
     - If rejected: Logs candidate to `signal_rejections` database table for missed EV tracking.
  6. Background periodic loop executes every 30 minutes to audit missed EV, check calibration drift, and publish Telegram performance reports.

---

## 4. Feature Pipeline & Model Compatibility
Bot 3's `FeatureEngineering` module produces the exact 12 features required by the pre-trained brain classifiers:
* `dist_ema_50`, `dist_ema_200`, `atr_pct`, `volume_zscore`, `adx_14`, `bb_width`, `funding_rate_zscore`, `oi_zscore`, `rsi_14`, `macd_hist`, `supertrend_direction`, `chop_index`.

---

## 5. Forward-Testing Performance Record (Aug 24 – Aug 26, 2026)
* **Total Completed Simulated Trades**: 135 (285 pending resolution)
* **Wins**: 56 (41.48%)
* **Losses**: 79 (58.52%)
* **Net P&L**: **+$0.11 USD** (Flat breakeven)
* **Profit Factor**: **1.03**
* **Average Win / Average Loss**: +$0.06 / -$0.04
* **Asset Breakdown**:
  * `SOL/USDT`: **46.2% Win Rate** (26 trades, +$0.16 PnL)
  * `DOGE/USDT`: **43.5% Win Rate** (62 trades, +$0.15 PnL)
  * `AVAX/USDT`: **40.0% Win Rate** (10 trades, +$0.05 PnL)
  * `NEAR/USDT`: **38.2% Win Rate** (34 trades, -$0.11 PnL)

---

## 6. Key Quantitative Insights & Next Evolution
* **Insight**: Ingesting 1-minute candles with standard technical indicators yields a ~41.5% win rate because sub-minute noise creates frequent false breakout signals.
* **Evolution**: Transition Bot 3 from technical indicators to **Pure Market Microstructure** by integrating `async_ingestion.py` (Cumulative Volume Delta, aggressive market order flow, tick liquidation bursts, and Level 2 order book imbalances).
