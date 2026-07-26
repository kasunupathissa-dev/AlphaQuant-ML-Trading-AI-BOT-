# Project Context

This document provides the high-level business and strategic context for the AlphaQuant project.

## Business Objective

To develop a fully autonomous, profitable quantitative trading system that can identify and capitalize on statistical arbitrage opportunities in the highly volatile cryptocurrency futures markets. The system must be robust, secure, and operate 24/7 with minimal human intervention.

## Current Version

**V7.6**

## Current Project Status

**Production Ready (for Live Paper Trading).**

The system has undergone a complete development and hardening cycle. All critical bugs related to state persistence, secrets management, and data integrity have been resolved. The offline pipeline and live engine are fully functional and architecturally aligned.

However, the latest validation run has revealed that the core trading strategy suffers from **Data Starvation**, leading to underperforming models. The system is mechanically sound but not yet consistently profitable.

## Current Architecture

The system uses a **Multi-Signal, Ensemble Architecture**. It first identifies one of three primary market conditions (Trend, Breakout, Reversion) and then deploys a specialized ensemble of XGBoost and LightGBM models to predict the outcome.

## AI Models Used

- **Primary Models:** XGBoost, LightGBM
- **Calibration:** Isotonic Regression via `CalibratedClassifierCV`
- **Explainability:** SHAP (SHapley Additive exPlanations)

## Trading Strategy Summary

The strategy is based on filtering the market for specific, high-quality setups (primary signals) and then using a meta-model (the ML ensemble) to decide whether to trade, based on a rich set of engineered features. This is a form of **meta-labeling**.

## Current Limitations

- **Data Starvation:** The primary signal filters are too restrictive, resulting in too few training examples for the ML models to learn effectively. This leads to poor out-of-sample performance as seen in the latest validation report.
- **Lack of Centralized Configuration:** Many critical parameters (ATR multipliers, model hyperparameters) are hardcoded across different files.
- **No Automated Backtesting Framework:** All validation is currently done via walk-forward analysis, which is slow.

## Current Priorities

1.  **Solve Data Starvation:** The highest priority is to re-architect the feature generation and labeling pipeline to a **"Shotgun" Architecture**, where every single candle is labeled and used for training. This will provide the models with significantly more data.
2.  **Centralize Configuration:** Implement a `config.py` or `config.ini` file to manage all strategic and model parameters in one place.

## Success Metrics

- **Primary Metric:** Positive PNL over a 30-day live paper-trading period.
- **Secondary Metrics:**
    - Walk-forward validation win rate > 55% on at least three asset-model pairs.
    - Sharpe Ratio > 1.0.
    - Max Drawdown < 20%.

## Long-Term Vision

To evolve AlphaQuant into a multi-strategy, multi-market portfolio of autonomous trading agents. The system will eventually incorporate hyperparameter optimization, automated feature discovery, and a robust backtesting engine to rapidly research and deploy new sources of alpha.
