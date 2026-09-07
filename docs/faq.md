# Frequently Asked Questions (FAQ)

## 1. Quantitative & Strategy Questions

### Q: Why did Bot 1 (AlphaQuant V8.2) achieve a 71.11% win rate while Bot 3 achieved 41.48%?
**A**: Bot 1 operates on a **15-minute timeframe**, where market trends have higher persistence and macro indicators (EMA 50/200, ADX) filter out sub-minute noise. Bot 3 was forward-tested on a **1-minute timeframe** using standard technical indicators, which suffer from high noise-to-signal ratios. To achieve high win rates on 1-minute timeframes, strategies must use **pure market microstructure** (order flow, CVD, liquidations) rather than retail technical indicators.

### Q: Does the platform promise or guarantee profits?
**A**: **No.** Quantitative trading involves market risk, volatility, and uncertainty. The platform is engineered strictly as a measurable research, signal generation, and risk-controlled paper-trading execution platform.

---

## 2. Technical & Operational Questions

### Q: How do I ensure no real money is ever traded?
**A**: Keep `USE_TESTNET=True` and `SIMULATION_MODE=True` in your `.env` file. In this mode, the Binance execution client executes orders entirely in simulated memory and skips all real order routing.

### Q: Where are the active trade logs stored?
**A**: Trade records are saved in `trading_log_v8.csv` (Main bot), `trading_log_scalper.csv` (Scalper bot), `trading_log_paper.csv` (Paper bot), and the `signal_rejections` PostgreSQL table.

### Q: What should I do if the Telegram bot stops sending messages?
**A**: Check service logs with `sudo journalctl -u aq-paper-quant.service -n 50 --no-pager` to verify if a network timeout occurred, and check if Telegram rate-limited your bot token.
