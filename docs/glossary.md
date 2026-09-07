# Glossary & Quantitative Taxonomy

This document establishes standard quantitative, technical, and operational definitions used across the AlphaQuant documentation and codebase.

---

## 1. Quantitative Finance & Trading Terms

### Average True Range (ATR)
A technical volatility indicator introduced by J. Welles Wilder measuring the market volatility of an asset by decomposing the entire range of an asset price for a given period.
$$\text{TR} = \max\left[(\text{High} - \text{Low}), |\text{High} - \text{Close}_{\text{prev}}|, |\text{Low} - \text{Close}_{\text{prev}}|\right]$$
$$\text{ATR}_{t} = \frac{\text{ATR}_{t-1} \times (n - 1) + \text{TR}_t}{n}$$

### Bollinger Band Width & Squeeze
A volatility metric measuring the percentage spread between upper and lower Bollinger Bands relative to the middle simple moving average (SMA). A "squeeze" occurs when band width drops below a rolling 10th percentile threshold, signaling volatility compression prior to expansion.

### Choppiness Index (CI)
An indicator designed to determine if the market is choppy (trading sideways) or trending. Values above 55.0 indicate consolidating/choppy markets, while values below 45.0 signal directional trending regimes.
$$\text{CI} = 100 \times \frac{\log_{10}\left(\frac{\sum_{i=1}^{n} \text{TR}_i}{\max(\text{High}_n) - \min(\text{Low}_n)}\right)}{\log_{10}(n)}$$

### Cumulative Volume Delta (CVD)
The cumulative running sum of the difference between buying and selling volume over a series of bars. Provides insight into whether aggressive market buyers or aggressive market sellers are dominating order flow.

### Expected Value (EV)
The theoretical statistical expectation of a trading setup based on win probability ($p$), reward magnitude ($R$), and loss magnitude ($L$):
$$\text{EV} = (p \times R) - ((1 - p) \times L)$$

### Funding Rate
Periodic payments exchanged between long and short traders in perpetual futures contracts to keep contract prices aligned with the underlying spot index price.

### Liquidation Cascade
A rapid sequence of forced liquidations triggered when leveraged market participants hit maintenance margin limits, causing market orders to cascade and often resulting in temporary price exhaustion wicks.

### Open Interest (OI)
The total number of outstanding derivative contracts (long and short) that have not been settled. Rising price with rising OI signifies aggressive new capital; rising price with falling OI signifies short-covering.

### Profit Factor
The ratio of gross profits to gross losses over a given trading sample:
$$\text{Profit Factor} = \frac{\sum \text{Profits}}{\sum |\text{Losses}|}$$

### Risk-to-Reward Ratio (RRR)
The ratio of potential profit (distance from entry to take-profit) compared to potential loss (distance from entry to stop-loss):
$$\text{RRR} = \frac{|\text{Take Profit} - \text{Entry}|}{|\text{Stop Loss} - \text{Entry}|}$$

### Slippage
The difference between the expected execution price of an order and the actual price at which the order is filled on the exchange order book.

---

## 2. Machine Learning & Statistical Terms

### Calibration Drift
A statistical state where an ML model's predicted win probabilities diverge significantly from actual realized outcomes over a rolling evaluation window (e.g., predicted 50% but realized 70% win rate).

### Feature Engineering
The process of transforming raw market feeds (OHLCV, tick trades, order book depth) into normalized numerical vectors suitable for statistical inference.

### Isotonic Regression
A non-parametric calibration technique used to map raw model output scores into well-calibrated, monotonic empirical probabilities.

### Lookahead Bias
A critical error in quantitative backtesting where information from the future is inadvertently used to generate historical signals, creating artificially inflated backtest performance.

### Overfitting / Curve Fitting
The production of an analysis that corresponds too closely or exactly to a particular historical dataset, failing to predict future out-of-sample data accurately.

### $Z$-Score Normalization
The statistical measurement of a value's relationship to the mean of a group of values, measured in terms of standard deviations:
$$Z = \frac{x - \mu}{\sigma}$$

---

## 3. System & Engineering Terms

### Bracket Order
A compound order structure consisting of an initial market/limit entry order paired with simultaneous Stop-Loss and Take-Profit limit/market orders.

### Circuit Breaker
An automated risk control mechanism that halts trading operations when predefined adverse thresholds (e.g., maximum daily drawdown) are breached.

### Dead Man's Switch / Watchdog
A background monitor that continuously checks system liveness and data feed freshness, triggering automated restarts or alerting if no updates are recorded within a timeout period.

### Fail-Closed
A software design principle ensuring that if an error, exception, or timeout occurs, the system defaults to a safe, non-trading state rather than proceeding with unverified assumptions.

### Idempotency
A property of an operation whereby it can be applied multiple times without changing the result beyond the initial application (e.g., executing the same trade signal twice must not open two positions).

### OCO (One-Cancels-the-Other)
A pair of conditional orders where the execution of one automatically cancels the other (used to link Stop-Loss and Take-Profit orders).

### Redis Ring Buffer
An in-memory fixed-capacity queue implemented using Redis lists (`RPUSH` and `LTRIM`) to maintain a sliding window of historical bars with $O(1)$ append time.
