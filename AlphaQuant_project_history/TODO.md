# AlphaQuant TODO List

A checklist of tasks, technical debt, and research items.

### High Priority

-   [ ] **Re-architect Labeling:** Implement the "Shotgun" architecture by labeling every candle in `label_generator_v5.py`.
-   [ ] **Centralize Configuration:** Create a `config.py` file and migrate all hardcoded parameters (ATR, thresholds, model params) into it.
-   [ ] **Implement Unit Tests:** Create `tests/test_feature_library.py` and write `pytest` tests for all core calculation functions.

### Medium Priority

-   [ ] **Enhance Sentiment Features:** Add `_is_missing` flags for funding/OI data in `feature_generator_v6.py` and `main_v7.py`.
-   [ ] **Fix Validation Suite:** Refactor `validation_suite_v7.py` to use the exact same calibrated ensemble model as the production trainer.
-   [ ] **Improve Error Handling:** Implement specific `ccxt` exception handling (`RateLimitExceeded`, `NetworkError`) with retry logic in `main_v7.py`.

### Low Priority

-   [ ] **Structured Logging:** Replace all `print()` statements in `main_v7.py` with the `logging` module to write to a structured `bot.log` file.
-   [ ] **Atomic Model Swapping:** Modify `auto_trainer_daemon.py` to write new models to a temporary `.pkl_tmp` file and then perform an atomic `os.rename` to prevent race conditions.

### Technical Debt

-   [ ] The `main_v7.py` file is becoming too large and monolithic. Refactor the `AlphaQuantV7` class into smaller, more manageable components (e.g., `PositionManager`, `InferenceEngine`).
-   [ ] The reliance on `screen` for process management is not robust. Plan a migration to a proper service manager like `systemd`.

### Future Research

-   [ ] **Hyperparameter Optimization:** Investigate `Optuna` for tuning the XGBoost/LightGBM models.
-   [ ] **Backtesting Framework:** Evaluate `backtesting.py` and other libraries for building a faster strategy research environment.
-   [ ] **Alternative Data:** Research the integration of alternative data sources (e.g., social media sentiment, blockchain metrics).
