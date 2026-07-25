# AlphaQuant Feature Registry

This document lists all major implemented features in the AlphaQuant V7 system.

---

### **Feature: Multi-Signal Architecture**

-   **Purpose:** To apply different AI models based on the prevailing market structure, rather than using a one-size-fits-all approach.
-   **Current Status:** Implemented & Active.
-   **Dependencies:** `feature_library.py` (for signal generation).
-   **Future Improvements:** Add more signal types (e.g., volatility contraction/expansion, candlestick patterns).
-   **Known Limitations:** The current signal definitions are too restrictive, leading to data starvation.

---

### **Feature: Ensemble Modeling**

-   **Purpose:** To improve prediction accuracy and robustness by combining the outputs of two different ML models (XGBoost and LightGBM).
-   **Current Status:** Implemented & Active.
-   **Dependencies:** `xgboost`, `lightgbm`, `scikit-learn`.
-   **Future Improvements:** Experiment with different model architectures (e.g., TabNet, Neural Networks) and different ensembling techniques (e.g., weighted averaging, stacking).
-   **Known Limitations:** The ensemble adds computational overhead to the training process.

---

### **Feature: State Persistence**

-   **Purpose:** To allow the live engine to recover gracefully from a crash or restart without losing its memory of open trades or risk-management state.
-   **Current Status:** Implemented & Active.
-   **Dependencies:** `json`, `os`.
-   **Future Improvements:** Migrate from a simple JSON file to a more robust, high-performance key-value store like Redis for better scalability and to prevent file corruption issues.
-   **Known Limitations:** The current implementation does not fully reconcile open positions with the exchange if the state file is lost; it only logs a warning.

---

### **Feature: Degradation Lock (Penalty Box)**

-   **Purpose:** An automated circuit breaker to protect capital by automatically disabling trading on an asset after a set number of consecutive losses.
-   **Current Status:** Implemented & Active.
-   **Dependencies:** `State Persistence` feature.
-   **Future Improvements:** Make the number of losses and the penalty duration configurable.
-   **Known Limitations:** The logic is simple (2 consecutive losses) and could be improved with more sophisticated performance analysis.

---

### **Feature: Secure Secrets Management**

-   **Purpose:** To remove all sensitive credentials (API keys, passwords) from the source code, adhering to security best practices.
-   **Current Status:** Implemented & Active.
-   **Dependencies:** `os` (`os.getenv`).
-   **Future Improvements:** Integrate with a dedicated secrets management service like HashiCorp Vault or AWS Secrets Manager for institutional-grade security.
-   **Known Limitations:** Relies on the user correctly setting environment variables on the host machine.

---

### **Feature: Verbose Debug & Monitoring Mode**

-   **Purpose:** To provide a high-frequency stream of real-time status updates to Telegram for close monitoring of the bot's internal state and decision-making process.
-   **Current Status:** Implemented & Active.
-   **Dependencies:** `Telegram API`.
-   **Future Improvements:** Create a `config` flag to easily toggle this mode on or off without a code change.
-   **Known Limitations:** Can be very noisy and lead to alert fatigue if left on permanently in a stable production environment.
