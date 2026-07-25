# Architectural Decision Record (ADR)

This document records key architectural decisions made during the development of AlphaQuant.

---

### **ADR-001: Move to Ensemble Modeling**

-   **Date:** 2024-07-22
-   **Problem:** A single ML model (e.g., only XGBoost) can have specific, inherent biases or weaknesses. Over-reliance on one model architecture increases risk.
-   **Decision:** We will implement an ensemble of two different gradient-boosted models: **XGBoost** and **LightGBM**. The final prediction probability will be the simple average of the outputs from both models.
-   **Reason:** By combining two high-performing but distinct algorithms, we can reduce variance and create a more robust prediction that is less likely to be affected by the quirks of a single model. This is a standard institutional practice.
-   **Alternatives Considered:**
    1.  **Stacking:** A more complex ensembling method where a meta-model is trained on the outputs of the base models. Rejected as overly complex for the current project stage.
    2.  **Using a single, larger model:** Rejected as it does not provide the same robustness benefits as using multiple, diverse models.
-   **Trade-offs:** Increased training time and code complexity in exchange for higher prediction reliability.

---

### **ADR-002: Implement State Persistence via JSON**

-   **Date:** 2024-07-22
-   **Problem:** The live engine stored all its state (open trades, penalty-boxed assets) in-memory. A server restart or application crash would wipe this memory, leading to orphaned trades and the immediate trading of penalized assets. This was a critical production risk.
-   **Decision:** We will implement a `save_state()` and `load_state()` mechanism that serializes the critical state dictionaries to a `live_engine_state.json` file. `load_state()` is called on startup, and `save_state()` is called after any state change.
-   **Reason:** This provides a simple, file-based, and human-readable persistence layer that is sufficient for the current scale of the application and has no external dependencies.
-   **Alternatives Considered:**
    1.  **Redis:** A high-performance in-memory database. Rejected as it adds an extra service to manage and deploy, increasing operational complexity. It is noted as a future improvement.
    2.  **SQL Database:** Storing state in the main MySQL database. Rejected as it would mix transient application state with permanent historical data and could lead to performance issues.
-   **Trade-offs:** Potential for file corruption if the bot crashes during a write operation. Slower than Redis, but acceptable for the current frequency of state changes.

---

### **ADR-003: Externalize Secrets to Environment Variables**

-   **Date:** 2024-07-22
-   **Problem:** API keys and database passwords were hardcoded in Python source files, representing a critical security vulnerability.
-   **Decision:** All secrets will be removed from the code and loaded at runtime from system environment variables using `os.getenv()`.
-   **Reason:** This is the industry standard for managing secrets in production environments. It completely decouples the code from the credentials, allowing the code to be safely stored in a private Git repository without exposing sensitive information.
-   **Alternatives Considered:**
    1.  **Encrypted Config File:** Storing secrets in an encrypted file. Rejected due to the complexity of managing the decryption key.
    2.  **HashiCorp Vault / AWS Secrets Manager:** Dedicated secrets management services. Rejected as overly complex for the current single-server deployment but noted as a long-term goal.
-   **Trade-offs:** Requires a manual setup step on the server (`export VAR=value`) and careful management of the `~/.bashrc` file.
