# Underlying System Assumptions

## 1. Environmental & Market Assumptions

1. **Exchange Liquidity**: Assumes Binance USDⓈ-M Futures contracts for selected top-tier assets (`SOL`, `NEAR`, `AVAX`, `XRP`, `DOGE`) maintain adequate order book depth to absorb $10\text{ - }50\text{ USD}$ testlot sizes with $< 0.03\%$ slippage.
2. **Network Liveness**: Assumes outbound HTTPS and WSS latency between the host server (`187.127.125.221`) and Binance API gateways remains $< 350\text{ ms}$ under normal network conditions.
3. **UTC Clock Synchronization**: Assumes host server system clock is synchronized via NTP (`systemd-timesyncd`), guaranteeing $< 100\text{ ms}$ clock skew against exchange timestamps.
4. **Execution Posture**: Assumes live real-money execution remains strictly disabled unless explicitly authorized by an authorized operator.
