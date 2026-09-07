# Changelog

All notable changes to the **AlphaQuant Platform** are documented in this file.

---

## [Unreleased] - Target Modular Architecture
### Added
- Comprehensive 16-layer modular quantitative platform architecture.
- Formal JSON `SignalContract` schema with validation rules.
- Pure microstructure data ingestion hooks (`CVD`, `Liquidations`, `OI Velocity`).
- Standardized `IStrategy`, `IRiskManager`, `ISignalAggregator`, and `IExecutionAdapter` interfaces.
- 45+ professional implementation-level documentation files in `docs/`.

---

## [8.2.0] - 2026-08-26
### Fixed
- Fixed trade synchronization ordering in `PaperTradeTracker` to immediately persist closed trade outcomes (`PROFIT`/`LOSS`) to CSV.
- Resolved feature vector alignment in `FeatureEngineering` to supply calibrated ML brains with accurate live indicator vectors.
- Configured all live services (`aq-live-main`, `aq-live-scalper`, `aq-paper-quant`) to operate strictly in Demo / Simulation Mode.

### Added
- Auto-approval execution mode for paper trading simulation.
- Automated daily drawdown circuit breaker (2.5% threshold).
- Real-time rejection outcome and missed Expected Value (EV) database auditing.
