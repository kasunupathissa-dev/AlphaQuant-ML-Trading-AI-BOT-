# Open Questions & Architecture Decisions

## 1. Architectural Ambiguities for Leadership & Engineering Review

1. **Storage Unification Strategy**:
   * *Question*: Should flat-file CSV logging (`trading_log_*.csv`) be deprecated entirely in favor of TimescaleDB relational tables, or retained as a human-readable backup export?
   * *Recommendation*: Use TimescaleDB as the authoritative single source of truth, and generate CSV exports asynchronously via background export worker.
2. **Strategy Portfolio Weighting**:
   * *Question*: Should the 15m Shotgun Momentum strategy (Bot 1) and 1m Microstructure strategy (Bot 3) share the same global margin pool, or operate on partitioned sub-wallet allocations?
   * *Recommendation*: Partition margin allocations (e.g. 70% to 15m Swing Core, 30% to 1m Microstructure) to prevent high-frequency setups from consuming swing margin capacity.
3. **Dashboard Web Security**:
   * *Question*: Should the Web Dashboard (`dashboard_app.py`) be wrapped behind Nginx with OAuth2/OIDC, or basic HTTP authentication?
   * *Recommendation*: Deploy Nginx reverse proxy with SSL certificate and HTTP Basic Authentication.
