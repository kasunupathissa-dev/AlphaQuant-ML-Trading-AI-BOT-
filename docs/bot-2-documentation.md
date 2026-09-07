# Bot 2: SCALPER_HUNT (Live Scalper Engine)

## 1. Purpose & Objectives
**SCALPER_HUNT** is a high-frequency scalping variant of AlphaQuant designed to capture micro-momentum thrusts on 15m/sub-15m candles with rapid Take-Profit targets (0.2% - 0.5%) and high turnover.

---

## 2. Directory Structure & Key Files
```
c:\cry_agent\v_4_AQ_AI\scalper_hunt\
├── main_v7.py                  # Primary scalper execution script (1,453 lines)
├── config.py                   # Scalper configuration parameters
├── verify_api.py               # API credential connectivity checker
├── live_engine_state_scalper.json # Scalper runtime state file
└── trading_log_scalper.csv     # Scalper trade execution log
```

---

## 3. Entry Points & Runtime Lifecycle
* **Entry Command**: `python scalper_hunt/main_v7.py`
* **Systemd Service**: `aq-live-scalper.service`
* **Lifecycle**:
  1. Bootstraps environment variables (`USE_TESTNET`, `BINANCE_API_KEY`, `BINANCE_API_SECRET`).
  2. Loads pre-trained scalping ML models into memory.
  3. Establishes polling cycle across 6 selected high-beta scalping assets.
  4. Scans for rapid order flow momentum and EMA compression squeezes.
  5. Places immediate market entry with tight TP limit orders.

---

## 4. Supported Markets & Strategy Differences from Bot 1

| Parameter | Bot 1 (Main V8.2) | Bot 2 (SCALPER_HUNT) |
| :--- | :--- | :--- |
| **Monitored Assets** | 10 Assets (Multi-Market) | 6 High-Beta Assets (`SOL`, `SUI`, `HBAR`, `XRP`, `LINK`, `AVAX`) |
| **Take Profit Target** | $1.5 \times \text{ATR}$ (Swing Expansion) | $0.5 \times \text{ATR}$ (0.2% - 0.5% Scalp Target) |
| **Stop Loss Distance** | $1.0 \times \text{ATR}$ | $0.8 \times \text{ATR}$ (Tighter Stop) |
| **Max Hold Duration** | 24 Hours | 4 Hours (Aggressive Timeout Exit) |
| **Target Turnover** | 2-4 trades/day | 8-15 trades/day |

---

## 5. Historical Performance Record (Aug 17 – Aug 23, 2026)
* **Total Completed Trades**: 53
* **Wins**: 25 (47.17%)
* **Losses**: 28 (52.83%)
* **Net P&L**: **-$2.11 USD**
* **Profit Factor**: **0.62**
* **Average Win / Average Loss**: +$0.14 / -$0.20
* **Max Single Win / Max Single Loss**: +$0.27 / -$0.31
* **Asset Breakdown**:
  * `XRP/USDT`: **71.4% Win Rate** (7 trades, +$0.49 PnL)
  * `AVAX/USDT`: **66.7% Win Rate** (6 trades, +$0.12 PnL)
  * `BTC/USDT`: **54.5% Win Rate** (11 trades, -$0.35 PnL)
  * `SOL/USDT`: **33.3% Win Rate** (6 trades, -$0.72 PnL)
  * `DOT/USDT`: **25.0% Win Rate** (4 trades, -$0.42 PnL)

---

## 6. Root-Cause Analysis of Underperformance
1. **Exchange Fee Drag**: Scalping targets of 0.2% - 0.4% are heavily impacted by Binance taker fees (0.05% entry + 0.05% exit = 0.10% total fee, consuming 25% - 50% of gross trade profit).
2. **Spread & Wick Vulnerability**: Tight stop-losses ($0.8 \times \text{ATR}$) get triggered by random sub-minute wicks before the directional trend realizes.
3. **Negative Expectancy**: Average win ($+$0.14) is smaller than average loss ($-0.20$), resulting in an unfavorable asymmetric payoff structure.

---

## 7. Operational Recommendations
* **Maintain in Demo / Simulation Mode Only**: Do not allocate live capital to SCALPER_HUNT.
* **Repurpose as Microstructure Laboratory**: Use the fast execution hooks of SCALPER_HUNT to test limit-order maker execution (0% maker fee) and Level 2 order book absorption walls.
