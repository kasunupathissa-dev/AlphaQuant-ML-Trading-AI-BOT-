# Known Limitations & Technical Debt

## 1. Known Architectural Limitations

1. **Indicator Lag on Sub-5m Charts**: Standard momentum indicators (RSI, Moving Averages, MACD) on 1m candles produce frequent whipsaws and false breakouts due to sub-minute market noise (demonstrated by Bot 3's 41.48% win rate).
2. **Monolithic Script Coupling**: `main_v7.py` and `scalper_hunt/main_v7.py` couple data fetching, indicator math, ML inference, and Telegram alerting inside 1,450-line procedural files.
3. **Synchronous Blocking REST Calls**: Legacy scripts execute blocking `requests.post` and CCXT REST calls inside async loops, introducing intermittent loop latency.
4. **Unauthenticated HTTP Dashboard**: `dashboard_app.py` exposes port 8080 without default TLS encryption or access authentication.
