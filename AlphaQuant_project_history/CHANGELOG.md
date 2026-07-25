# Changelog

All notable changes to the AlphaQuant project will be documented in this file.

## [7.6] - 2024-07-22

### Bug Fixes

-   **[CRITICAL]** Permanently fixed the `ChainedAssignmentError` in `main_v7.py` by replacing `inplace=True` with explicit DataFrame assignment, adhering to modern pandas standards.
-   **[CRITICAL]** Permanently fixed the `Invalid frequency: 1H` regression in `main_v7.py` by ensuring the `pandas.resample()` function always uses the correct uppercase `'1H'` frequency string.

## [7.5] - 2024-07-22

### New Features

-   **Verbose Monitoring Mode:** The live engine now sends comprehensive real-time status updates to Telegram, including the start/end of each inference cycle and details on all analyzed signals, even those not traded.
-   **Accelerated Debug Cycle:** Added a 3-minute inference timer to `main_v7.py` to allow for faster local testing and validation.

### Bug Fixes

-   **[CRITICAL]** Fixed a `feature_names mismatch` error in the live engine by ensuring the `ml_inference_loop` correctly fetches and integrates sentiment features (`funding_rate_zscore`, `oi_zscore`) before making predictions.

## [6.9] - 2024-07-22

### Bug Fixes

-   **[HIGH]** Hardened the Telegram notification function to provide clear, actionable error messages for common failures like incorrect tokens (`401/404`) or invalid chat IDs (`400`).
-   **[MEDIUM]** Fixed a recurring `IndentationError` in `main_v6.py` caused by an incomplete function body during previous refactoring.

## [6.8] - 2024-07-22

### Performance Improvements

-   **WebSocket Hardening:** Rearchitected the live engine's `watch_ticker_stream` to use a single, multiplexed WebSocket connection (`watch_tickers`) for all assets. This dramatically reduces network overhead and permanently resolves the `ping-pong keepalive` timeout errors.

## [6.6] - 2024-07-22

### Bug Fixes

-   **[CRITICAL]** Permanently fixed the `AssertionError: NaN values found in LONG labels!` in `label_generator_v5.py`. The logic was changed to a "default to zero" approach, initializing all labels as `0.0` (Loss) instead of `NaN`, which prevents data corruption from the start.

## [6.5] - 2024-07-22

### New Features

-   **State Persistence:** Implemented a critical state persistence mechanism in `main_v6.py`. The bot now saves its state (penalty box, recent results, open trades) to `live_engine_state.json` and reloads it on startup, enabling graceful recovery from crashes.
-   **Secrets Management:** All hardcoded secrets (DB passwords, API tokens) were removed from the codebase and are now securely loaded from environment variables.
-   **Code Centralization:** Refactored all feature calculation logic into a single, shared `feature_library.py` to eliminate code duplication and ensure consistency between training and live execution.

### Known Issues

-   The initial implementation of state persistence did not correctly reconcile open positions with the exchange on startup. This was fixed in later versions.
