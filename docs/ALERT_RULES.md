# FundFlow Anomaly Evidence & Alert Rules Specification

**Specification Version:** 1.0.0  
**Owner:** Agent A (Quantitative Architecture)  
**Contract Authority:** [`src/fundflow/contracts.py:COLUMNS['alerts']`](file:///Users/anny/Desktop/mutual-fund/src/fundflow/contracts.py#L54)  
**Implementation Modules:** [`src/fundflow/anomaly.py`](file:///Users/anny/Desktop/mutual-fund/src/fundflow/anomaly.py), [`src/fundflow/alerts.py`](file:///Users/anny/Desktop/mutual-fund/src/fundflow/alerts.py)  
**Verification Suite:** [`tests/test_alerts.py`](file:///Users/anny/Desktop/mutual-fund/tests/test_alerts.py)

---

## 1. Alert Rule Hierarchy & Precedence

Alert evaluations strictly enforce deterministic hierarchical precedence:

```
                  ┌──────────────────────────────────────────────┐
                  │ Evaluate Forecast & Anomaly Evidence at as_of │
                  └──────────────────────┬───────────────────────┘
                                         │
                                         ▼
                 ┌────────────────────────────────────────────────┐
                 │  pct_forecast >= 90 AND                       │
                 │  (robust_z >= 2.0 OR momentum_3m >= 0.10) ?   │
                 └───────┬───────────────────────────────┬────────┘
                    YES  │                               │ NO
                         ▼                               ▼
                 ┌───────────────┐              ┌──────────────────┐
                 │ LEVEL:        │              │ pct_forecast >=  │
                 │   CRITICAL    │              │ 80 OR robust_z   │
                 └───────────────┘              │ >= 2.0 ?         │
                                                └────┬─────────┬───┘
                                                 YES │         │ NO
                                                     ▼         ▼
                                              ┌──────────┐ ┌────────┐
                                              │ LEVEL:   │ │ LEVEL: │
                                              │ ELEVATED │ │ NORMAL │
                                              └──────────┘ └────────┘
```

1. **`Critical` Precedence:**
   Fires when forecast percentile $\ge 90\%$ **and** either robust Z-score $\ge 2.0$ or 3-month momentum $\ge +10\%$. Critical unconditionally overrides Elevated.
2. **`Elevated`:**
   Fires when forecast percentile $\ge 80\%$ **or** robust Z-score $\ge 2.0$.
3. **`Normal`:**
   Default state when neither condition is met, or when data history is insufficient to evaluate anomalies.

---

## 2. Statistical Anomaly Evidence Formulations

All evidence metrics are strictly computed using **prior-only observations** available before the forecast decision cutoff $T_{\text{as\_of}}$:

### 2.1 Empirical Percentile Rank (`pct_forecast`)
$$\text{pct\_forecast} = 100 \times \frac{1}{N} \sum_{i=1}^N \mathbf{1}(R_i \le \hat{R}_{\text{pred}})$$
* Requires at least $6$ historical observations in the category.
* Represents where the predicted redemption rate sits relative to historical distributions.

### 2.2 Robust Z-Score (`robust_z`)
$$\text{robust\_z} = \frac{R_t - \text{median}_{24}}{1.4826 \times \text{MAD}_{24}}$$
* **$\text{MAD}_{24}$:** Median Absolute Deviation over the prior 24 eligible monthly observations.
* **Zero-MAD Safeguard:** If all observations in the window are identical ($\text{MAD} = 0$), the engine returns $0.0$ if $R_t == \text{median}$, or caps at $\pm 3.0$ rather than returning infinity.

### 2.3 3-Month Momentum (`momentum_3m`)
$$\text{momentum\_3m} = \frac{\bar{R}_{t-3..t-1}}{\bar{R}_{t-6..t-4}} - 1.0$$
* Compares the average redemption rate of the last 3 months against the preceding 3 months.
* Zero denominator check prevents division by zero.

---

## 3. Data Freshness & Sentiment Corroboration

1. **Data Freshness Days:**
   Computed as the elapsed calendar days between the latest observed flow month-end and decision cutoff $T_{\text{as\_of}}$.
2. **Sentiment Corroboration Invariant:**
   Live sentiment corroboration is only active if:
   - The last 14-day window contains $\ge 30$ live articles.
   - All items have verified `is_live == True`.
   - If historical reference sentiment distributions are missing, status is explicitly marked `unavailable`.
