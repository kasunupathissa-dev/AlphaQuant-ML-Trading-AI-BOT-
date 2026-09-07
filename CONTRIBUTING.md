# Contributing Guidelines

## 1. Development Standards

1. **Strict Type Annotations**: All new Python code must include complete PEP 484 type hints.
2. **Deterministic Risk Invariants**: No pull request may alter or bypass fail-closed risk checks without formal quantitative approval.
3. **No Hardcoded Secrets**: All configuration values must use environment variables loaded via `.env`.
4. **Test Coverage**: All new feature functions and strategy rules must be accompanied by unit tests in `tests/`.

---

## 2. Pull Request Workflow
1. Fork or branch from `main`.
2. Implement modular changes behind standard interfaces (`IStrategy`, `IRiskManager`, etc.).
3. Run test sanity suites: `pytest tests/`.
4. Submit PR with detailed commit rationale and risk impact summary.
