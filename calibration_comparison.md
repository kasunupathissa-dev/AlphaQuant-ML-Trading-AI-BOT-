# AlphaQuant: Backtest vs. Live Calibration Comparison

Generated at: 2026-07-30 09:16:12.236320

This report compares the out-of-sample backtest calibration curves with real live trade log calibration curves.

## Asset: BTC/USDT
* **Backtest (OOS) Brier Score:** `0.2064` (Sample size: 3444)
* **Live Trades Brier Score:** `0.2404` (Sample size: 7)


| Probability Bin | OOS N | OOS Pred | OOS True (95% CI) | Live N | Live Pred | Live True (95% CI) | Delta / Evaluation |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| 50%-55% | 353 | 52.4% | 42.5% (37%-48%) | 0 | - | - | - |
| 55%-60% | 316 | 57.3% | 46.2% (41%-52%) | 0 | - | - | - |
| 60%-65% | 320 | 62.3% | 52.2% (47%-58%) | 2 | 61.3% | 100.0% (34%-100%) | 🔍 Outperforming Live (Underconfident) |
| 65%-70% | 199 | 67.4% | 59.8% (53%-66%) | 0 | - | - | - |
| 70%-75% | 154 | 72.7% | 68.2% (60%-75%) | 0 | - | - | - |
| 75%-80% | 85 | 77.5% | 72.9% (63%-81%) | 2 | 77.4% | 50.0% (9%-91%) | ⚠️ Underperforming Live (Overconfident) |
| 80%+ | 170 | 87.1% | 86.5% (81%-91%) | 3 | 82.3% | 66.7% (21%-94%) | ⚠️ Underperforming Live (Overconfident) |

---

## Asset: ETH/USDT
* **Backtest (OOS) Brier Score:** `0.2031` (Sample size: 3444)
* **Live Trades Brier Score:** `0.3135` (Sample size: 10)


| Probability Bin | OOS N | OOS Pred | OOS True (95% CI) | Live N | Live Pred | Live True (95% CI) | Delta / Evaluation |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| 50%-55% | 289 | 52.4% | 44.3% (39%-50%) | 0 | - | - | - |
| 55%-60% | 324 | 57.4% | 43.5% (38%-49%) | 2 | 55.5% | 50.0% (9%-91%) | 🔍 Outperforming Live (Underconfident) |
| 60%-65% | 245 | 62.4% | 50.6% (44%-57%) | 1 | 63.4% | 0.0% (0%-79%) | ⚠️ Underperforming Live (Overconfident) |
| 65%-70% | 217 | 67.6% | 61.8% (55%-68%) | 3 | 69.4% | 0.0% (0%-56%) | ⚠️ Underperforming Live (Overconfident) |
| 70%-75% | 122 | 72.4% | 65.6% (57%-73%) | 0 | - | - | - |
| 75%-80% | 94 | 77.1% | 73.4% (64%-81%) | 3 | 77.3% | 66.7% (21%-94%) | ✅ Match (Stable Calibration) |
| 80%+ | 229 | 87.4% | 86.5% (81%-90%) | 1 | 81.9% | 100.0% (21%-100%) | 🔍 Outperforming Live (Underconfident) |

---

## Asset: SOL/USDT
* **Backtest (OOS) Brier Score:** `0.2058` (Sample size: 3444)
* **Live Trades Brier Score:** `0.2469` (Sample size: 11)


| Probability Bin | OOS N | OOS Pred | OOS True (95% CI) | Live N | Live Pred | Live True (95% CI) | Delta / Evaluation |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| 50%-55% | 467 | 52.6% | 37.5% (33%-42%) | 0 | - | - | - |
| 55%-60% | 338 | 57.7% | 46.7% (41%-52%) | 2 | 58.1% | 100.0% (34%-100%) | 🔍 Outperforming Live (Underconfident) |
| 60%-65% | 307 | 62.5% | 53.1% (48%-59%) | 2 | 63.2% | 100.0% (34%-100%) | 🔍 Outperforming Live (Underconfident) |
| 65%-70% | 228 | 67.4% | 59.6% (53%-66%) | 2 | 67.1% | 0.0% (0%-66%) | ⚠️ Underperforming Live (Overconfident) |
| 70%-75% | 123 | 72.2% | 74.0% (66%-81%) | 2 | 71.7% | 0.0% (0%-66%) | ⚠️ Underperforming Live (Overconfident) |
| 75%-80% | 86 | 77.3% | 69.8% (59%-78%) | 3 | 76.6% | 100.0% (44%-100%) | 🔍 Outperforming Live (Underconfident) |
| 80%+ | 170 | 86.0% | 85.3% (79%-90%) | 0 | - | - | - |

---

## Asset: BNB/USDT
* **Backtest (OOS) Brier Score:** `0.2160` (Sample size: 3444)
* **Live Trades Brier Score:** `0.2807` (Sample size: 16)


| Probability Bin | OOS N | OOS Pred | OOS True (95% CI) | Live N | Live Pred | Live True (95% CI) | Delta / Evaluation |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| 50%-55% | 394 | 52.5% | 43.7% (39%-49%) | 0 | - | - | - |
| 55%-60% | 371 | 57.4% | 50.9% (46%-56%) | 0 | - | - | - |
| 60%-65% | 363 | 62.5% | 56.5% (51%-61%) | 6 | 62.0% | 50.0% (19%-81%) | ⚠️ Underperforming Live (Overconfident) |
| 65%-70% | 270 | 67.5% | 58.5% (53%-64%) | 3 | 67.8% | 66.7% (21%-94%) | 🔍 Outperforming Live (Underconfident) |
| 70%-75% | 160 | 72.3% | 63.1% (55%-70%) | 2 | 71.7% | 100.0% (34%-100%) | 🔍 Outperforming Live (Underconfident) |
| 75%-80% | 88 | 77.5% | 65.9% (56%-75%) | 2 | 79.8% | 50.0% (9%-91%) | ⚠️ Underperforming Live (Overconfident) |
| 80%+ | 86 | 86.5% | 82.6% (73%-89%) | 3 | 82.9% | 33.3% (6%-79%) | ⚠️ Underperforming Live (Overconfident) |

---

## Asset: ADA/USDT
* **Backtest (OOS) Brier Score:** `0.2083` (Sample size: 3444)
* **Live Trades Brier Score:** `0.1636` (Sample size: 10)


| Probability Bin | OOS N | OOS Pred | OOS True (95% CI) | Live N | Live Pred | Live True (95% CI) | Delta / Evaluation |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| 50%-55% | 356 | 52.6% | 38.8% (34%-44%) | 0 | - | - | - |
| 55%-60% | 290 | 57.5% | 49.0% (43%-55%) | 1 | 55.1% | 0.0% (0%-79%) | ⚠️ Underperforming Live (Overconfident) |
| 60%-65% | 295 | 62.4% | 50.2% (44%-56%) | 1 | 62.0% | 0.0% (0%-79%) | ⚠️ Underperforming Live (Overconfident) |
| 65%-70% | 213 | 67.4% | 61.5% (55%-68%) | 3 | 67.6% | 66.7% (21%-94%) | ✅ Match (Stable Calibration) |
| 70%-75% | 156 | 72.3% | 66.0% (58%-73%) | 3 | 70.7% | 100.0% (44%-100%) | 🔍 Outperforming Live (Underconfident) |
| 75%-80% | 96 | 77.3% | 71.9% (62%-80%) | 0 | - | - | - |
| 80%+ | 179 | 86.3% | 76.5% (70%-82%) | 2 | 82.5% | 100.0% (34%-100%) | 🔍 Outperforming Live (Underconfident) |

---

## Asset: XRP/USDT
* **Backtest (OOS) Brier Score:** `0.2089` (Sample size: 3444)
* **Live Trades Brier Score:** `0.1893` (Sample size: 7)


| Probability Bin | OOS N | OOS Pred | OOS True (95% CI) | Live N | Live Pred | Live True (95% CI) | Delta / Evaluation |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| 50%-55% | 374 | 52.2% | 35.0% (30%-40%) | 0 | - | - | - |
| 55%-60% | 329 | 57.4% | 45.9% (41%-51%) | 1 | 58.7% | 100.0% (21%-100%) | 🔍 Outperforming Live (Underconfident) |
| 60%-65% | 240 | 62.3% | 60.8% (55%-67%) | 2 | 62.5% | 100.0% (34%-100%) | 🔍 Outperforming Live (Underconfident) |
| 65%-70% | 230 | 67.5% | 57.4% (51%-64%) | 1 | 67.8% | 100.0% (21%-100%) | 🔍 Outperforming Live (Underconfident) |
| 70%-75% | 126 | 72.4% | 58.7% (50%-67%) | 0 | - | - | - |
| 75%-80% | 88 | 77.3% | 70.5% (60%-79%) | 1 | 75.6% | 100.0% (21%-100%) | 🔍 Outperforming Live (Underconfident) |
| 80%+ | 151 | 86.6% | 80.1% (73%-86%) | 2 | 81.1% | 50.0% (9%-91%) | ⚠️ Underperforming Live (Overconfident) |

---

## Asset: LINK/USDT
* **Backtest (OOS) Brier Score:** `0.2087` (Sample size: 3444)
* **Live Trades Brier Score:** `0.0968` (Sample size: 6)


| Probability Bin | OOS N | OOS Pred | OOS True (95% CI) | Live N | Live Pred | Live True (95% CI) | Delta / Evaluation |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| 50%-55% | 432 | 52.4% | 40.7% (36%-45%) | 0 | - | - | - |
| 55%-60% | 408 | 57.4% | 48.8% (44%-54%) | 1 | 55.2% | 100.0% (21%-100%) | 🔍 Outperforming Live (Underconfident) |
| 60%-65% | 266 | 62.3% | 52.6% (47%-59%) | 1 | 62.6% | 100.0% (21%-100%) | 🔍 Outperforming Live (Underconfident) |
| 65%-70% | 184 | 67.2% | 59.8% (53%-67%) | 0 | - | - | - |
| 70%-75% | 123 | 72.1% | 69.1% (60%-77%) | 1 | 72.1% | 100.0% (21%-100%) | 🔍 Outperforming Live (Underconfident) |
| 75%-80% | 83 | 77.0% | 68.7% (58%-78%) | 3 | 76.7% | 100.0% (44%-100%) | 🔍 Outperforming Live (Underconfident) |
| 80%+ | 92 | 87.9% | 92.4% (85%-96%) | 0 | - | - | - |

---

## Asset: AVAX/USDT
* **Backtest (OOS) Brier Score:** `0.2044` (Sample size: 3444)
* **Live Trades Brier Score:** `0.2806` (Sample size: 10)


| Probability Bin | OOS N | OOS Pred | OOS True (95% CI) | Live N | Live Pred | Live True (95% CI) | Delta / Evaluation |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| 50%-55% | 349 | 52.4% | 37.2% (32%-42%) | 0 | - | - | - |
| 55%-60% | 348 | 57.5% | 47.7% (43%-53%) | 1 | 58.4% | 100.0% (21%-100%) | 🔍 Outperforming Live (Underconfident) |
| 60%-65% | 310 | 62.6% | 55.2% (50%-61%) | 3 | 62.0% | 0.0% (0%-56%) | ⚠️ Underperforming Live (Overconfident) |
| 65%-70% | 238 | 67.3% | 55.5% (49%-62%) | 2 | 69.2% | 100.0% (34%-100%) | 🔍 Outperforming Live (Underconfident) |
| 70%-75% | 192 | 72.3% | 67.7% (61%-74%) | 3 | 72.0% | 66.7% (21%-94%) | ✅ Match (Stable Calibration) |
| 75%-80% | 104 | 76.9% | 76.9% (68%-84%) | 1 | 79.7% | 0.0% (0%-79%) | ⚠️ Underperforming Live (Overconfident) |
| 80%+ | 107 | 85.9% | 83.2% (75%-89%) | 0 | - | - | - |

---

## Asset: DOGE/USDT
* **Backtest (OOS) Brier Score:** `0.2055` (Sample size: 3445)
* **Live Trades Brier Score:** `0.2076` (Sample size: 9)


| Probability Bin | OOS N | OOS Pred | OOS True (95% CI) | Live N | Live Pred | Live True (95% CI) | Delta / Evaluation |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| 50%-55% | 470 | 52.4% | 39.1% (35%-44%) | 0 | - | - | - |
| 55%-60% | 404 | 57.5% | 41.8% (37%-47%) | 2 | 55.5% | 100.0% (34%-100%) | 🔍 Outperforming Live (Underconfident) |
| 60%-65% | 264 | 62.3% | 56.8% (51%-63%) | 2 | 62.0% | 100.0% (34%-100%) | 🔍 Outperforming Live (Underconfident) |
| 65%-70% | 169 | 67.2% | 62.7% (55%-70%) | 4 | 67.4% | 50.0% (15%-85%) | ⚠️ Underperforming Live (Overconfident) |
| 70%-75% | 151 | 72.7% | 64.2% (56%-71%) | 0 | - | - | - |
| 75%-80% | 92 | 77.0% | 71.7% (62%-80%) | 1 | 75.8% | 100.0% (21%-100%) | 🔍 Outperforming Live (Underconfident) |
| 80%+ | 154 | 86.4% | 85.7% (79%-90%) | 0 | - | - | - |

---

## Asset: DOT/USDT
* **Backtest (OOS) Brier Score:** `0.2071` (Sample size: 3445)
* **Live Trades Brier Score:** `0.3465` (Sample size: 14)


| Probability Bin | OOS N | OOS Pred | OOS True (95% CI) | Live N | Live Pred | Live True (95% CI) | Delta / Evaluation |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| 50%-55% | 374 | 52.5% | 34.2% (30%-39%) | 0 | - | - | - |
| 55%-60% | 355 | 57.5% | 49.0% (44%-54%) | 1 | 58.6% | 100.0% (21%-100%) | 🔍 Outperforming Live (Underconfident) |
| 60%-65% | 289 | 62.3% | 52.6% (47%-58%) | 3 | 61.7% | 100.0% (44%-100%) | 🔍 Outperforming Live (Underconfident) |
| 65%-70% | 215 | 67.4% | 61.4% (55%-68%) | 4 | 67.9% | 0.0% (0%-49%) | ⚠️ Underperforming Live (Overconfident) |
| 70%-75% | 137 | 72.0% | 65.0% (57%-72%) | 1 | 72.6% | 0.0% (0%-79%) | ⚠️ Underperforming Live (Overconfident) |
| 75%-80% | 89 | 77.3% | 73.0% (63%-81%) | 4 | 77.4% | 25.0% (5%-70%) | ⚠️ Underperforming Live (Overconfident) |
| 80%+ | 141 | 86.1% | 81.6% (74%-87%) | 1 | 82.2% | 100.0% (21%-100%) | 🔍 Outperforming Live (Underconfident) |

---
