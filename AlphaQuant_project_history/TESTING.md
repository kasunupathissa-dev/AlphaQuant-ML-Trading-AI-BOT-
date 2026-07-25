# AlphaQuant Testing Strategy

This document outlines the multi-layered testing strategy for the AlphaQuant project, designed to ensure correctness, stability, and performance.

## Level 1: Unit Tests (TBD)

-   **Purpose:** To verify the correctness of individual, isolated functions.
-   **Framework:** `pytest`.
-   **Location:** `tests/` directory.
-   **Current Status:** **Not Implemented.** This is a high-priority technical debt item.
-   **Requirements:**
    -   All functions in `feature_library.py` must have corresponding unit tests.
    -   Tests should use static, pre-calculated data fixtures to validate outputs (e.g., verify that the `calculate_atr` function produces a known correct value for a given DataFrame).

## Level 2: Integration Tests (TBD)

-   **Purpose:** To verify that different components of the system work together correctly.
-   **Framework:** `pytest` with database fixtures.
-   **Current Status:** **Not Implemented.**
-   **Requirements:**
    -   **Pipeline Integration Test:** A test that runs the entire `run_full_pipeline_v7.py` on a small, mock dataset in a test database to ensure all stages can pass data to each other.
    -   **Live Engine Integration Test:** A test that simulates the `main_v7.py` engine's interaction with a mock exchange API and a test database.

## Level 3: Walk-Forward Validation (Implemented)

-   **Purpose:** To provide a robust, out-of-sample performance estimate of the ML models, simulating how they would perform in real trading.
-   **Framework:** Custom implementation using `sklearn.model_selection.TimeSeriesSplit`.
-   **Location:** `validation_suite_v7.py`.
-   **Current Status:** **Active.** This is currently our primary method for model validation.
-   **Limitations:** The current implementation in the validation suite does not perfectly mirror the production model architecture (it uses a basic model, not the full calibrated ensemble). This is a high-priority bug to be fixed.

## Level 4: Live Paper Trading (Active)

-   **Purpose:** To test the end-to-end system in a live market with zero financial risk.
-   **Framework:** The main `main_v7.py` engine with the `LIVE_TRADING_ENABLED` flag set to `False`.
-   **Current Status:** **Active.** This is the final gate before deploying with real capital.
-   **Requirements:** A new model must undergo at least one week of successful live paper trading without critical errors before being considered for a full production release.

## Future Testing Layers

-   **Backtesting Engine:** A dedicated framework to rapidly test new strategy ideas on historical data without retraining models. This is a high-priority item on the project roadmap.
-   **Performance & Load Testing:** Once the system becomes more complex, tests will be needed to measure CPU/memory usage under high load and identify performance bottlenecks.
