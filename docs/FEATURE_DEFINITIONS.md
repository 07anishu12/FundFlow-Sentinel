# FundFlow Feature Definitions & Target Rate Specification

**Specification Version:** 1.0.0  
**Owner:** Agent A (Quantitative Architecture)  
**Contract Authority:** [`src/fundflow/contracts.py:COLUMNS['feature_matrix']`](file:///Users/anny/Desktop/mutual-fund/src/fundflow/contracts.py#L26)  
**Implementation Modules:** [`src/fundflow/flows.py`](file:///Users/anny/Desktop/mutual-fund/src/fundflow/flows.py), [`src/fundflow/features.py`](file:///Users/anny/Desktop/mutual-fund/src/fundflow/features.py)  
**Verification Suite:** [`tests/test_features.py`](file:///Users/anny/Desktop/mutual-fund/tests/test_features.py)

---

## 1. Target Definition & Financial Semantics

### 1.1 Mathematical Formulation
For canonical category $c$ and target month $t$, the primary forecasting target is defined as:

$$\text{redemption\_rate\_pct}(c, t) = 100 \times \frac{\text{gross\_redemption\_cr}(c, t)}{\text{aum\_close\_cr}(c, t-1)}$$

* **Units:** Percentage points (e.g., $1.25$ represents $1.25\%$).
* **Opening AUM Proxy:** Indian mutual fund public disclosures (AMFI monthly reports) do not report exact opening day AUM. Prior-month closing AUM ($\text{aum\_close\_cr}(c, t-1)$) is explicitly defined as the proxy for opening AUM.
* **Accounting Meaning:** As verified in [`docs/AMFI_RECONCILIATION_REPORT.md`](file:///Users/anny/Desktop/mutual-fund/docs/AMFI_RECONCILIATION_REPORT.md), $\text{gross\_redemption\_cr}$ represents total scheme asset departures, encompassing regular redemptions, Systematic Withdrawal Plans (SWP), and inter-scheme switch-outs.

### 1.2 Denominator & Missingness Rules
1. **Zero Division Prohibition:** If prior-month closing AUM ($\text{aum\_close\_cr}(c, t-1)$) is zero, negative, missing, or non-finite, $\text{redemption\_rate\_pct}$ is set to `NaN`. Zero division is strictly prevented.
2. **Missing vs Zero Preservation:**
   - If gross redemptions are missing (`NaN`), the calculated rate is `NaN`.
   - If gross redemptions are genuinely $0.0\text{ cr}$ and denominator $> 0$, the calculated rate is $0.0\%$.
3. **Aggregation Before Ratio:** For multi-scheme or sub-category rows, monetary amounts ($\text{gross\_redemption\_cr}$, $\text{aum\_close\_cr}$) are aggregated before computing the ratio. Row-level rates are never averaged.

---

## 2. Feature Matrix Contract Catalog

The feature matrix matches the frozen 17-column contract:

| Column Name | Type | Unit | Formula / Source | Required History | Missing / Invalid Policy |
|---|---|---|---|---|---|
| `as_of` | String (ISO UTC) | Timestamp | Cutoff origin timestamp ($T_{\text{as\_of}}$) | Current decision time | Must be valid UTC with `Z` |
| `target_month` | String (YYYY-MM) | Calendar Month | Month being predicted ($t$) | $t$ | Must match `^\d{4}-(0[1-9]\|1[0-2])$` |
| `category` | String | Identifier | Canonical category name | Current | Must belong to active universe |
| `rate_lag0` | Float | Percentage points | $\text{rate}(c, t-1)$ | $t-1$ available by `as_of` | Exclude row if missing |
| `rate_lag1` | Float | Percentage points | $\text{rate}(c, t-2)$ | $t-2$ available by `as_of` | Exclude row if missing |
| `rate_lag2` | Float | Percentage points | $\text{rate}(c, t-3)$ | $t-3$ available by `as_of` | Exclude row if missing |
| `rate_lag11` | Float | Percentage points | $\text{rate}(c, t-12)$ | $t-12$ (seasonal lag) | Exclude row if missing |
| `roll_mean3` | Float | Percentage points | $\frac{1}{3} \sum_{i=0}^2 \text{rate\_lag}_i$ | 3 prior rates | Exclude row if missing |
| `roll_std3` | Float | Percentage points | Sample std of $\text{rate\_lag}_{0..2}$ | 3 prior rates | Defaults to 0.0 if identical |
| `delta1` | Float | Percentage points | $\text{rate\_lag0} - \text{rate\_lag1}$ | 2 prior rates | Exclude row if missing |
| `net_flow_rate_lag0`| Float | Percentage points | $100 \times \frac{\text{net\_flow}(c, t-1)}{\text{aum\_close}(c, t-2)}$ | $t-1, t-2$ | Exclude row if missing |
| `aum_growth_lag0` | Float | Percentage points | $100 \times \frac{\text{aum}(c, t-1) - \text{aum}(c, t-2)}{\text{aum}(c, t-2)}$ | $t-1, t-2$ | Exclude row if missing |
| `nifty_return_lag0`| Float | Percentage | Monthly Nifty 50 return ($t-1$) | `market_month` ($t-1$) | Exclude row if market unavailable |
| `nifty_drawdown_3m`| Float | Percentage | 3-month rolling Nifty drawdown | `market_month` ($t-1$) | Exclude row if market unavailable |
| `vix_mean_lag0` | Float | Volatility Index | India VIX average level ($t-1$) | `market_month` ($t-1$) | Exclude row if market unavailable |
| `vix_change_lag0` | Float | Index points | India VIX monthly change ($t-1$) | `market_month` ($t-1$) | Exclude row if market unavailable |
| `target_rate` | Float / Nullable | Percentage points | $\text{rate}(c, t)$ | Realized at $t+1$ | `NaN` / null during live inference |

---

## 3. Temporal Availability & Non-Leakage Invariants

1. **Strict Post-Period Cutoff:**
   Features for predicting target month $t$ are constructed as of decision timestamp $T_{\text{as\_of}}$. All input records must satisfy:
   $$\text{available\_from} \le T_{\text{as\_of}}$$
2. **Prior-Only Rolling Windows:**
   All rolling metrics (`roll_mean3`, `roll_std3`, `delta1`) utilize only prior observations ($t-1, t-2, t-3$). Centered rolling windows and target-observation inclusion are prohibited.
3. **Target / Feature Independence:**
   Neither target month flows, concurrent month-end AUM, nor future revisions are ever accessible to feature construction.
4. **Market Alignment:**
   Market features must be released before $T_{\text{as\_of}}$ (`market.available_from <= as_of`). If market data for month $t-1$ is delayed beyond $T_{\text{as\_of}}$, the row is excluded rather than zero-filled.
5. **Sentiment Isolation:**
   The primary historical feature matrix does not consume live sentiment or unverified sentiment feeds. The contract strictly restricts features to the 17 frozen columns.
