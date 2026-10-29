# FundFlow NAV Metrics & Fund Research Ranking Methodology

**Specification Version:** 1.0.0  
**Owner:** Agent B (Intelligence & Fund Research Architecture)  
**Contract Authority:** [`src/fundflow/contracts.py:COLUMNS['shortlist']`](file:///Users/anny/Desktop/mutual-fund/src/fundflow/contracts.py#L78)  
**Implementation Modules:** [`src/fundflow/nav_metrics.py`](file:///Users/anny/Desktop/mutual-fund/src/fundflow/nav_metrics.py), [`src/fundflow/ranking.py`](file:///Users/anny/Desktop/mutual-fund/src/fundflow/ranking.py)  
**Verification Suite:** [`tests/test_ranking.py`](file:///Users/anny/Desktop/mutual-fund/tests/test_ranking.py)

---

## 1. Architectural Boundary & Research Lane Decoupling

1. **Strict Decoupling Invariant:**
   Fund ranking and NAV research metrics are **architecturally and runtime-isolated** from the flow forecasting and alert lanes.
   - Ranking code **never** imports, consumes, or depends on `fundflow.flows`, `fundflow.forecasting`, `fundflow.features`, `fundflow.validate`, or `alerts`.
   - Verified programmatically via AST import boundary analysis in [`tests/test_ranking.py:test_ranking_import_isolation`](file:///Users/anny/Desktop/mutual-fund/tests/test_ranking.py#L27).
2. **Context-Only Flow Display:**
   Flow conditions and category forecasts may be displayed as separate contextual metadata in the UI, but are **strictly excluded** from the fund research score.

---

## 2. Eligibility Filtering & Rejection Ledger

Every scheme in the scheme master is audited against explicit quantitative criteria before entering the ranking universe. Excluded schemes are recorded in an auditable rejection ledger:

| Invariant | Criterion | Operational Definition | Rejection Reason |
|---|---|---|---|
| **Plan Type** | Direct Plan | `plan_type.str.title() == "Direct"` | `Non-direct plan` |
| **Option Type** | Growth Option | `option_type.str.title() == "Growth"` | `Non-growth option` |
| **History Length** | $\ge 3$ Years | $\ge 750$ daily trading observations | `Insufficient history (< 750 days)` |
| **NAV Gaps** | No material gaps | Maximum calendar day gap $\le 10$ days | `Material unexplained NAV gap` |
| **NAV Numerics** | Positive & Finite | All values $> 0.0$ and finite | `Invalid or non-positive NAV values` |

*Note: Scheme attributes (`plan_type`, `option_type`, `riskometer`) are never inferred from ambiguous scheme names.*

---

## 3. Mathematical Formulation of Historical NAV Metrics

All metrics are calculated on clean, business-day NAV series without linear interpolation over weekends or exchange closures:

### 3.1 3-Year CAGR (`cagr_3y`)
$$\text{cagr\_3y} = 100 \times \left( \left(\frac{\text{NAV}_T}{\text{NAV}_0}\right)^{1 / \text{Years}} - 1 \right)$$
where $\text{Years} = \frac{N_{\text{days}}}{252}$.

### 3.2 Annualized Volatility (`vol`)
$$\text{vol} = 100 \times \sqrt{252} \times \sqrt{\frac{1}{N-1} \sum_{t=1}^N (r_t - \bar{r})^2}$$
where $r_t = \frac{\text{NAV}_t - \text{NAV}_{t-1}}{\text{NAV}_{t-1}}$.

### 3.3 Maximum Drawdown (`max_drawdown`)
$$\text{max\_drawdown} = 100 \times \max_{t \in [1, T]} \left( \frac{\text{Peak}_t - \text{NAV}_t}{\text{Peak}_t} \right)$$
Reported as a positive percentage (e.g. $14.50\%$).

### 3.4 Sortino Ratio (`sortino`)
$$\text{sortino} = \frac{\text{cagr\_3y}/100 - R_f}{\sigma_{\text{downside}} \times \sqrt{252}}$$
* $R_f = 6.00\%$ (RBI Repo Rate baseline).
* Downside deviation $\sigma_{\text{downside}} = \sqrt{\frac{1}{N} \sum_{t=1}^N \min(r_t - R_{f,\text{daily}}, 0)^2}$.

### 3.5 Rolling 1-Year Consistency (`consistency`)
Fraction of rolling 252-trading-day windows with positive nominal return:
$$\text{consistency} = \frac{1}{T - 252} \sum_{t=252}^T \mathbf{1}\left( \frac{\text{NAV}_t}{\text{NAV}_{t-252}} - 1 > 0 \right)$$

---

## 4. Within-Category Percentile Scoring

Schemes are evaluated relative to peers within the identical SEBI category:

$$\text{research\_score} = 0.30 P_{\text{return}} + 0.25 P_{\text{consistency}} + 0.25 P_{\text{drawdown}} + 0.20 P_{\text{risk\_adj}}$$

* **Percentile Direction:**
  - $P_{\text{return}}$: Higher CAGR $\rightarrow$ Higher score.
  - $P_{\text{consistency}}$: Higher consistency $\rightarrow$ Higher score.
  - $P_{\text{drawdown}}$: **Inverted.** Lower peak-to-trough decline $\rightarrow$ Higher score ($100 - \text{percentile}$).
  - $P_{\text{risk\_adj}}$: Higher Sortino $\rightarrow$ Higher score.
* **Deterministic Tie-Breaking:** Average rank percentile method.
* **Weights Normalization:** $0.30 + 0.25 + 0.25 + 0.20 = 1.00$.

---

## 5. Weight Sensitivity Analysis

To ensure ranking robustness, the system executes an automated sensitivity test perturbing each weight by $\pm 10$ percentage points ($\pm 0.10$):
1. Weights are non-negatively clipped and renormalized: $\sum w_i' = 1.0$.
2. The platform computes Spearman rank correlation ($\rho$) against the base ranking and top-5 scheme overlap fraction.
3. Typical stability threshold: $\rho \ge 0.90$ and top-5 overlap $\ge 80\%$.

---

## 6. Survivorship Bias & Regulatory Disclosures

> **⚠️ MANDATORY RESEARCH DISCLOSURE:**
> Current scheme master feeds sourced from AMFI (`NAVAll.txt`) list only currently operational mutual fund schemes. Schemes that were merged, liquidated, or wound up over the historical observation window are absent from the universe. Historical return metrics on surviving schemes alone will overstate category average performance. These scores represent transparent quantitative filtering, not forward return guarantees or investment advice.
