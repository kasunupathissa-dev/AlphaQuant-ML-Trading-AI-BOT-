# AlphaQuant Quantitative Trading Platform: Documentation Index

Welcome to the technical documentation library for the **AlphaQuant Quantitative Trading and Signal Platform**.

This documentation suite provides an implementation-level audit of the three cryptocurrency trading-signal systems in this repository, evaluates their architectures and historical performance, details their operational characteristics, identifies security and financial risks, and provides a target modular architecture for a unified, risk-controlled signal generation and paper-trading platform.

---

## 📑 Documentation Structure & Sitemap

### 1. Executive & Project Governance
* [Executive Summary](file:///c:/cry_agent/v_4_AQ_AI/docs/executive-summary.md): High-level system appraisal, performance summary, risk review, and key priorities.
* [Project Scope](file:///c:/cry_agent/v_4_AQ_AI/docs/project-scope.md): Operational boundaries, supported asset classes, operational modes, and explicit non-goals.
* [Glossary & Quantitative Taxonomy](file:///c:/cry_agent/v_4_AQ_AI/docs/glossary.md): Definitions of quantitative finance, machine learning, and systems engineering terminology.

### 2. Legacy Systems Audit & Comparative Analysis
* [Current System Overview](file:///c:/cry_agent/v_4_AQ_AI/docs/current-system-overview.md): Macro architectural layout of all three co-existing bot implementations.
* [Bot 1: AlphaQuant V8.2 (Main Engine)](file:///c:/cry_agent/v_4_AQ_AI/docs/bot-1-documentation.md): Deep-dive audit of `main_v7.py` (15m multi-asset momentum & reversion engine).
* [Bot 2: SCALPER_HUNT Engine](file:///c:/cry_agent/v_4_AQ_AI/docs/bot-2-documentation.md): Deep-dive audit of `scalper_hunt/main_v7.py` (high-frequency fast-scan variant).
* [Bot 3: AlphaQuant Paper Quant Engine](file:///c:/cry_agent/v_4_AQ_AI/docs/bot-3-documentation.md): Deep-dive audit of `ai_quant_bot/` (1m async WebSocket real-time paper trading engine).
* [Comparative Systems Analysis](file:///c:/cry_agent/v_4_AQ_AI/docs/bot-comparison.md): Feature matrix, data ingestion, risk controls, and execution strategy comparison.

### 3. Current State Architecture & Engineering Reviews
* [Current Data Flows](file:///c:/cry_agent/v_4_AQ_AI/docs/current-data-flow.md): Sequence diagrams, WebSocket loops, and Redis buffer pipelines.
* [Current API Documentation](file:///c:/cry_agent/v_4_AQ_AI/docs/current-api-documentation.md): REST endpoints, WebSocket feeds, Telegram gateway, and Dashboard HTTP routes.
* [Current Database Documentation](file:///c:/cry_agent/v_4_AQ_AI/docs/current-database-documentation.md): PostgreSQL / TimescaleDB and Redis schemas, table constraints, and indexing.
* [Current Configuration Matrix](file:///c:/cry_agent/v_4_AQ_AI/docs/current-configuration.md): Environment variables, `config.py`, `assets.yaml`, and threshold matrices.
* [Current Deployment Architecture](file:///c:/cry_agent/v_4_AQ_AI/docs/current-deployment.md): Systemd unit services, process trees, environment isolation, and Linux hosting layout.
* [Current Security Audit](file:///c:/cry_agent/v_4_AQ_AI/docs/current-security-review.md): STRIDE threat modeling, credential exposures, and access control audit.
* [Current Risk Management Review](file:///c:/cry_agent/v_4_AQ_AI/docs/current-risk-review.md): Mathematical risk limits, slippage bounds, drawdown caps, and circuit breaker audits.

### 4. Target Unified Architecture & Design
* [Target Architecture Blueprint](file:///c:/cry_agent/v_4_AQ_AI/docs/target-architecture.md): 16-layer decoupled modular platform architecture.
* [Target Data Flow Pipelines](file:///c:/cry_agent/v_4_AQ_AI/docs/target-data-flow.md): Unified event-driven data ingestion, normalization, and feature generation flow.
* [Target Component Design](file:///c:/cry_agent/v_4_AQ_AI/docs/target-component-design.md): Interfaces, dependency injection patterns, and domain contracts.
* [Signal Contract Specification](file:///c:/cry_agent/v_4_AQ_AI/docs/signal-contract.md): Formal JSON signal schema, field specifications, and validation rules.
* [Signal Generation Engine](file:///c:/cry_agent/v_4_AQ_AI/docs/signal-generation.md): Candidate generation, validation criteria, and expiration lifecycles.
* [Strategy Modules Specification](file:///c:/cry_agent/v_4_AQ_AI/docs/strategy-documentation.md): Mathematical models for Momentum, Mean Reversion, and Order-Flow Microstructure.
* [Signal Aggregation & Arbitration](file:///c:/cry_agent/v_4_AQ_AI/docs/signal-aggregation.md): Conflict resolution, weighted voting, and regime-based arbitration models.

### 5. Risk, Portfolio, & Execution Engines
* [Deterministic Risk Management](file:///c:/cry_agent/v_4_AQ_AI/docs/risk-management.md): Fail-closed risk gates, exposure ceilings, and dynamic volatility filters.
* [Portfolio Management](file:///c:/cry_agent/v_4_AQ_AI/docs/portfolio-management.md): Kelly sizing, correlation caps, and margin allocation rules.
* [Order Execution Engine](file:///c:/cry_agent/v_4_AQ_AI/docs/order-execution.md): Bracket orders, OCO execution, slippage models, and order lifecycle states.
* [High-Fidelity Paper Trading](file:///c:/cry_agent/v_4_AQ_AI/docs/paper-trading.md): Slippage, latency, fee simulation, and order state machine.
* [Exchange Integration Protocols](file:///c:/cry_agent/v_4_AQ_AI/docs/exchange-integration.md): CCXT unified adapter, Binance Futures protocols, rate-limiting, and error handling.

### 6. Validation, Backtesting, & Quality Assurance
* [Backtesting Framework](file:///c:/cry_agent/v_4_AQ_AI/docs/backtesting.md): Bias-free event-driven backtesting, fee modeling, and metrics calculation.
* [Validation Methodology](file:///c:/cry_agent/v_4_AQ_AI/docs/validation-methodology.md): Walk-forward optimization, calibration drift testing, and out-of-sample audits.
* [Testing Strategy](file:///c:/cry_agent/v_4_AQ_AI/docs/testing-strategy.md): Unit, integration, property-based, chaos, and regression testing specifications.
* [Security Architecture](file:///c:/cry_agent/v_4_AQ_AI/docs/security-architecture.md): Secrets management, network isolation, and principle of least privilege.

### 7. Observability, Operations, & Runbooks
* [Observability Architecture](file:///c:/cry_agent/v_4_AQ_AI/docs/observability.md): Metrics, structured logging, tracing, and dashboard instrumentation.
* [Alerting & Notification Policy](file:///c:/cry_agent/v_4_AQ_AI/docs/alerting.md): Telegram notifications, incident escalations, and rate-limiting policies.
* [Failure Recovery Protocols](file:///c:/cry_agent/v_4_AQ_AI/docs/failure-recovery.md): Crash recovery, state reconstruction, and database reconciliation.
* [Deployment Guide](file:///c:/cry_agent/v_4_AQ_AI/docs/deployment-guide.md): Installation, systemd configuration, and environment bootstrapping.
* [Operations Runbook](file:///c:/cry_agent/v_4_AQ_AI/docs/operations-runbook.md): Standard Operating Procedures (SOPs), emergency kill switch, and key rotations.
* [Troubleshooting Guide](file:///c:/cry_agent/v_4_AQ_AI/docs/troubleshooting.md): Diagnosis and remediation of common operational and data anomalies.
* [Frequently Asked Questions (FAQ)](file:///c:/cry_agent/v_4_AQ_AI/docs/faq.md): Technical and operational FAQ.

### 8. Project Roadmaps & Audit Reports
* [Engineering Roadmap](file:///c:/cry_agent/v_4_AQ_AI/docs/roadmap.md): 5-phase migration plan to the unified target architecture.
* [Open Questions & Trade-offs](file:///c:/cry_agent/v_4_AQ_AI/docs/open-questions.md): Architecture ambiguities and design trade-offs.
* [Assumptions](file:///c:/cry_agent/v_4_AQ_AI/docs/assumptions.md): Underlying system, network, and market assumptions.
* [Known Limitations](file:///c:/cry_agent/v_4_AQ_AI/docs/known-limitations.md): Technical debt, scaling bottlenecks, and known constraints.
* [Final Review Checklist](file:///c:/cry_agent/v_4_AQ_AI/docs/final-review-checklist.md): Pre-production verification and governance checklist.
* [Final Review Report](file:///c:/cry_agent/v_4_AQ_AI/docs/final-review-report.md): Summary of architectural findings and readiness assessment.

---

## 🛡️ Core Operating Principle: Strict Risk Control & Zero Live Exposure

The platform is designed with a strict default operating posture:
1. **Default Mode**: `SIGNAL_ONLY` or `PAPER_TRADING`.
2. **Live Execution Policy**: All live real-money order routing is disabled by default. Live execution can only be activated by an explicit operator action with validated risk bounds.
3. **No Profit Guarantees**: This system is a quantitative research and signal platform. It makes no promises of profit or guaranteed returns.
