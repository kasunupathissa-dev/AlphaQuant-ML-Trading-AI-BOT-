

# AlphaQuant V4.4: Institutional ML Trading Engine

AlphaQuant is a fully autonomous, asynchronous Machine Learning quantitative trading ecosystem designed for cryptocurrency perpetual futures. 

It utilizes a Dual-Model Meta-Labeling architecture, Platt-Scaled XGBoost classifiers, and continuous order book streaming to execute probability-driven, high-frequency trades.

## 🧠 Core Architecture

1. **Async Event-Driven Engine (`main_v4_institutional.py`)**
   - Zero-latency websocket streaming via `ccxt.pro`.
   - Simultaneous processing of 10 institutional assets.
   - Dynamic Target-Volatility Position Sizing.
   - Real-Time Degradation Locks (Asset Isolation).

2. **Continuous Learning Daemon (`auto_trainer_daemon.py`)**
   - Background cron-job that completely prevents Model Drift.
   - Weekly automated data ingestion, feature extraction, and XGBoost retraining.
   - Zero-downtime hot-swapping of Neural weights into the live async engine.

3. **High-Dimensional Feature Space (`feature_generator_v4.py`)**
   - Evaluates pure mathematical market structure.
   - Features include: Hurst Proxy (Choppiness Index), ADX, Volatility Z-Scores, Volume Anomalies, Bollinger Squeezes, and Institutional FVG Intensity.

4. **Dual-Model Meta-Labeling (`label_generator_v4.py` & `model_training.py`)**
   - Uses Marcos López de Prado's **Triple Barrier Method** for volatility-adjusted outcomes.
   - Trains separate `LONG` and `SHORT` AI models to solve directional class imbalance.
   - XGBoost probabilities are strictly calibrated using **Isotonic Regression (Platt Scaling)** to output True Empirical Probabilities.


   
