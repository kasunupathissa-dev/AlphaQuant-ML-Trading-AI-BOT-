# AlphaQuant Project Roadmap

This document outlines the development priorities for the AlphaQuant project.

## Completed (V7.6)

-   [✓] **Architecture:** Implement Multi-Signal, Ensemble AI Core.
-   [✓] **Data Pipeline:** Build robust data ingestion and feature generation pipeline.
-   [✓] **Validation:** Create a Walk-Forward Validation and Reliability Curve suite.
-   [✓] **Production Hardening:**
    -   [✓] Implement State Persistence for penalty box and open trades.
    -   [✓] Externalize all secrets to environment variables.
    -   [✓] Refactor feature logic into a shared library.
    -   [✓] Harden WebSocket connections to prevent timeout errors.
-   [✓] **Debugging:** Implement a verbose, real-time monitoring mode via Telegram.

## In Progress

-   *No active development tasks. Current phase is deployment and observation.*

## Next Version (V8.0) - The "Shotgun" Release

*   **Priority 1 (Critical):** **Solve Data Starvation.**
    -   **Task:** Re-architect the labeling pipeline. Instead of only labeling "primary signal" candles, label **every single candle** with its Triple Barrier outcome.
    -   **Reason:** This will increase the size of our training dataset by over 100x, giving the ML models enough data to find more subtle and robust patterns. The "primary signal" flags will be kept as features for the model to use.

*   **Priority 2 (High):** **Implement Centralized Configuration.**
    -   **Task:** Create a `config.py` file.
    -   **Task:** Move all hardcoded strategic parameters (ATR multipliers, time limits, risk amounts) and model hyperparameters into this file.
    -   **Reason:** This is a critical step for maintainability and enables systematic optimization.

## Future Ideas

-   **Hyperparameter Optimization (Project 3):**
    -   Integrate `Optuna` or `Hyperopt` into the training pipeline to automatically find the best hyperparameters for the XGBoost and LightGBM models.
-   **Automated Feature Engineering:**
    -   Use libraries like `featuretools` to automatically discover new, potentially more predictive features.
-   **Advanced Risk Management:**
    -   Implement a portfolio-level risk manager that can adjust position sizes based on overall market volatility or correlated positions.
-   **Robust Backtesting Engine:**
    -   Build a dedicated backtesting framework (e.g., using `backtesting.py` or a custom solution) to allow for much faster strategy research and iteration than the current walk-forward validation.

## Long-Term Goals

-   Evolve AlphaQuant into a multi-strategy, multi-market portfolio of autonomous trading agents.
-   Develop a web-based dashboard for real-time monitoring of PNL, open positions, and system health.
-   Achieve a consistently positive return with a Sharpe Ratio > 1.5 over a 6-month period.
