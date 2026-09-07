# Pre-Production Final Review Checklist

## 1. Governance & Operational Verification Checklist

- [x] **Zero Live Risk Verified**: All bots are confirmed in `USE_TESTNET=True` or `SIMULATION_MODE=True`.
- [x] **No Leaked Secrets**: All documentation and example files use sanitized, placeholder values.
- [x] **Exact Codebase Alignment**: All documented file paths, class names, functions, and services correspond to active code.
- [x] **Mermaid Diagram Syntax**: All diagrams verified and renderable.
- [x] **Mathematical Integrity**: ATR sizing, risk percentages, and RRR formulas verified.
- [x] **Database Schemas Documented**: PostgreSQL `ohlcv_bars`, `funding_rates`, and `signal_rejections` tables documented.
- [x] **Fail-Closed Risk Verified**: Sizing rejects on missing balances, wide spreads, and circuit breaker limits.
- [x] **Emergency Kill Switch Documented**: Step-by-step shell commands for immediate service shutdown verified.
