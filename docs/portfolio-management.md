# Portfolio Management & Exposure Modeling

## 1. Portfolio State & Exposure Architecture

The Portfolio Manager maintains the authoritative in-memory and persisted state of active positions, margin allocations, cash balances, and sector concentration limits:

```mermaid
graph TD
    subgraph Portfolio State
        BAL[Margin Balance: $1,000 USD]
        OPEN[Active Positions: 2 / Max 3]
        RISK[Total Risk at Risk: 2.0% / Max 3.0%]
    end
    
    subgraph Asset Exposures
        P1[SOL/USDT: LONG $45 Notional | Risk $10]
        P2[NEAR/USDT: SHORT $35 Notional | Risk $10]
    end
    
    BAL --> P1
    BAL --> P2
```

---

## 2. Mathematical Capital Allocation Rules

### A. Position Sizing via Fractional Kelly Criterion
To prevent catastrophic ruin while maximizing geometric growth, sizing uses a conservative half-Kelly fraction bounded by a 1.0% hard risk cap:
$$f^* = \frac{p(b + 1) - 1}{b} \times 0.5$$
$$\text{Allocated Risk \%} = \min\left(f^*, 0.01\right)$$
Where:
* $p$ = Calibrated ML Win Probability (e.g. $0.65$).
* $b$ = Risk-to-Reward Ratio (e.g. $1.5$).

### B. Correlation & Sector Concentration Ceilings
* **Single Asset Cap**: No single asset may consume $> 40\%$ of total available margin.
* **Correlated Exposure Cap**: Maximum 2 concurrent positions in high-beta Layer-1 assets (`SOL`, `NEAR`, `SUI`, `AVAX`).
* **Directional Net Exposure**: If net directional bias exceeds $+2$ LONGs, new LONG setups are throttled unless balanced by a SHORT hedge.
