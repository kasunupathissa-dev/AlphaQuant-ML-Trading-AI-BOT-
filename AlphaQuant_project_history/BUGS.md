# AlphaQuant Bug Tracker

This document tracks major bugs, their root causes, and the version in which they were fixed.

---

### **Critical Bugs (Fixed)**

-   **Bug ID:** `CR-001`
    -   **Description:** `ValueError: Input y_true contains NaN.` The model training and validation scripts were crashing because they were being fed data with `NaN` values in the label columns.
    -   **Root Cause:** The `label_generator` was initialized with `NaN` values and failed to overwrite them for the first N candles due to the ATR calculation window.
    -   **Status:** **Fixed**
    -   **Workaround:** None.
    -   **Expected Fix Version:** **V6.6** (in `label_generator_v5.py`)

-   **Bug ID:** `CR-002`
    -   **Description:** `ChainedAssignmentError` in live engine. The `fillna` operation was failing due to modern `pandas` Copy-on-Write behavior.
    -   **Root Cause:** Using an `inplace=True` operation on a chained DataFrame selection.
    -   **Status:** **Fixed**
    -   **Workaround:** None.
    -   **Expected Fix Version:** **V7.6** (in `main_v7.py`)

-   **Bug ID:** `CR-003`
    -   **Description:** `Invalid frequency: 1H`. The live engine was crashing during feature generation due to a mismatch in the `pandas.resample()` frequency string.
    -   **Root Cause:** A regression where the live engine used `'1h'` (lowercase) while the training pipeline and `pandas` expect `'1H'` (uppercase).
    -   **Status:** **Fixed**
    -   **Workaround:** None.
    -   **Expected Fix Version:** **V7.5** (in `main_v7.py`)

---

### **High Priority Bugs (Fixed)**

-   **Bug ID:** `HI-001`
    -   **Description:** `ModuleNotFoundError` on the server for `lightgbm`, `schedule`, and `ccxt`.
    -   **Root Cause:** The `requirements.txt` file was not updated when new dependencies were added to the project.
    -   **Status:** **Fixed**
    -   **Workaround:** Manually `pip install` the missing packages on the server.
    -   **Expected Fix Version:** **V7.1** (in `requirements.txt`)

-   **Bug ID:** `HI-002`
    -   **Description:** Multiple "zombie" instances of the trading bot running simultaneously on the server.
    -   **Root Cause:** Repeatedly using `screen -S` to start the bot without first terminating the old session.
    -   **Status:** **Resolved** (Process issue, not a code bug).
    -   **Workaround:** Use `sudo killall -9 screen` and `screen -wipe` to ensure a clean environment before starting.
    -   **Expected Fix Version:** N/A (Operational procedure).

---

### **Known Issues (Low Priority)**

-   **Bug ID:** `LO-001`
    -   **Description:** The `auto_trainer_daemon.py` does not have a mechanism to prevent it from running if the live engine is currently in an open trade.
    -   **Root Cause:** The two services are completely independent and do not communicate.
    -   **Status:** **Open**
    -   **Workaround:** The live engine will re-adopt the trade after its state is reloaded, but there is a small window of unmanaged risk.
    -   **Expected Fix Version:** **Future** (Requires inter-process communication, e.g., via Redis).
