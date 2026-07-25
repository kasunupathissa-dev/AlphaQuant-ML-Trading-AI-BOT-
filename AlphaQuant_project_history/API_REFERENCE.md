# AlphaQuant API & Module Reference

A reference guide to the internal and external components of the AlphaQuant system.

## Internal Modules

-   **`main_v7.py`**: The primary application entry point. Contains the main `AlphaQuantV7` class, which orchestrates all live trading operations.
-   **`feature_library.py`**: A centralized, shared library for all data processing and feature calculation logic.
-   **`database_config.py`**: Provides a factory function `get_db_engine()` for creating a database connection.
-   **`run_full_pipeline_v7.py`**: Orchestrates the offline training and validation process.
-   **`auto_trainer_daemon.py`**: A background service that schedules and runs the offline pipeline.

## Core Classes & Functions

-   **`AlphaQuantV7` (in `main_v7.py`)**: The main class for the live engine.
    -   `.run()`: Starts the main asynchronous event loop.
    -   `.ml_inference_loop()`: The core 15-minute logic cycle for generating predictions.
    -   `.manage_active_trades()`: Manages the lifecycle of open positions.
    -   `.reconcile_open_positions()`: Recovers open trades on startup.
-   **`calculate_features_and_signals()` (in `feature_library.py`)**: The single source of truth for creating the feature set from a raw OHLCV DataFrame.

## Database Tables (MySQL)

-   **`market_data_1h`**:
    -   **Purpose:** Stores raw, validated 1-hour OHLCV data.
    -   **Columns:** `id`, `asset`, `timestamp`, `open`, `high`, `low`, `close`, `volume`.
    -   **Index:** `UNIQUE INDEX idx_asset_timestamp (asset, timestamp)`.
-   **`feature_store`**:
    -   **Purpose:** Stores the final, enriched feature vectors and their corresponding labels.
    -   **Columns:** `id`, `asset`, `timestamp`, `dist_ema_50`, `adx_14`, `funding_rate_zscore`, `primary_trend_long`, `target_label_long`, etc.

## Configuration & State Files

-   **`requirements.txt`**: A list of all Python package dependencies.
-   **`live_engine_state.json`**: A JSON file used to persist the live engine's state (`active_trades`, `asset_penalty_box`) across restarts.
-   **`.pkl` files**: Serialized Python objects containing the trained `scikit-learn` model pipelines (e.g., `BTC_USDT_brain.pkl`).

## External APIs

-   **`ccxt` / `ccxt.pro`**:
    -   **Purpose:** The primary interface for all interactions with the Binance exchange.
    -   **Usage:**
        -   `fetch_ohlcv()`: Used to get historical candle data.
        -   `watch_tickers()`: Used for the real-time WebSocket price stream.
        -   `fetch_funding_rate_history()` / `fetch_open_interest_history()`: Used for sentiment data.
-   **Telegram Bot API**:
    -   **Purpose:** Used for sending all real-time notifications and alerts.
    -   **Usage:** A simple `requests.post` call to the `https://api.telegram.org/bot<TOKEN>/sendMessage` endpoint.
