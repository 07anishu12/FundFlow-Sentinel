# FundFlow Stress Methodology & Scenario Analysis Specification

**Specification Version:** 1.0.0  
**Owner:** Agent A (Quantitative Architecture)  
**Contract Authority:** [`docs/INTERFACES.md:17-18`](file:///Users/anny/Desktop/mutual-fund/docs/INTERFACES.md#L17)  
**Implementation Module:** [`src/fundflow/stress.py`](file:///Users/anny/Desktop/mutual-fund/src/fundflow/stress.py)  
**Verification Suite:** [`tests/test_stress.py`](file:///Users/anny/Desktop/mutual-fund/tests/test_stress.py)  
**Empirical Data Status:** **CALIBRATIONS MARKED INSUFFICIENT_HISTORY ON REAL DATASET** (1 month of processed flows)

---

## 1. Pure Deterministic Stress Outflow Arithmetic

### 1.1 Mathematical Formulation
The primary stress arithmetic calculates estimated category gross redemption outflow:

$$\text{estimated\_outflow\_cr} = \text{aum\_cr} \times \frac{\text{effective\_rate\_pct}}{100.0}$$

* **Units:** All monetary values are expressed in **₹ crore**. Rates are in **percentage points** ($2.50$ means $2.50\%$).
* **Deterministic Precision:** Rounded to 2 decimal places ($0.01\text{ cr}$).

### 1.2 Rate Bounds, Rejections & Capping Rules
1. **Nonnegative Rates:**
   Gross redemption rates must be $\ge 0.0\%$. Negative rates are strictly rejected with status `invalid_input`. The engine **never** outputs negative gross redemptions.
2. **Above-100% Rate Capping:**
   Redemptions cannot exceed the fund's total assets. Rates $> 100.0\%$ are **explicitly capped at 100.0%** with status `capped_at_100` and documented in metadata:
   $$\text{effective\_rate\_pct} = \min(\text{rate\_pct}, 100.0)$$
   Silent clamping without status disclosure is prohibited.
3. **Reference AUM Validation:**
   AUM must be finite and $\ge 0.0$. Negative, missing, or non-finite AUM returns `invalid_input` with `estimated_outflow_cr = None`.

---

## 2. Reference AUM Proxy Definition & Governance

1. **Proxy Semantics:**
   In public Indian mutual fund disclosures, closing AUM of the prior month is the authoritative publicly available size metric. It is explicitly labeled **"reference AUM proxy"**, not current intraday liquid assets.
2. **Observation Period Metadata:**
   Every scenario calculation tags the observation month (e.g. `2024-09`) and availability timestamp ($T_{\text{as\_of}}$).
3. **Stale / Missing AUM Policy:**
   If closing AUM is missing, zero, or unavailable by $T_{\text{as\_of}}$, all scenario numeric outflows return `None` with status `unavailable`.

---

## 3. Multi-Scenario Table Construction

The function [`scenario_table`](file:///Users/anny/Desktop/mutual-fund/src/fundflow/stress.py#L82) constructs comparative scenario rows:

| Scenario Name | Type | Rate Assumption | Outflow Formula | Incremental Outflow | Status Conditions |
|---|---|---|---|---|---|
| **Base Forecast** | `baseline` | Point forecast $\hat{R}_t$ | $\text{AUM} \times \hat{R}_t / 100$ | $0.0\text{ cr}$ (base) | `valid` if forecast & AUM exist |
| **Lower Bound (P10)** | `empirical_bound` | Empirical P10 residual bound | $\text{AUM} \times R_{\text{P10}} / 100$ | $\text{Outflow}_{\text{P10}} - \text{Outflow}_{\text{base}}$ | `insufficient_history` if $N < 10$ |
| **Upper Bound (P90)** | `empirical_bound` | Empirical P90 residual bound | $\text{AUM} \times R_{\text{P90}} / 100$ | $\text{Outflow}_{\text{P90}} - \text{Outflow}_{\text{base}}$ | `insufficient_history` if $N < 10$ |
| **Moderate Stress (1.25x)** | `multiplier_stress`| $1.25 \times \hat{R}_t$ | $\text{AUM} \times 1.25\hat{R}_t / 100$ | $\text{Outflow}_{\text{1.25x}} - \text{Outflow}_{\text{base}}$ | `valid` if base is valid |
| **Severe Stress (1.50x)** | `multiplier_stress`| $1.50 \times \hat{R}_t$ | $\text{AUM} \times 1.50\hat{R}_t / 100$ | $\text{Outflow}_{\text{1.50x}} - \text{Outflow}_{\text{base}}$ | `valid` if base is valid |
| **Historical Maximum** | `historical_max` | $\max_{i}(R_i)$ over $\ge 24$ mo | $\text{AUM} \times R_{\max} / 100$ | $\text{Outflow}_{\max} - \text{Outflow}_{\text{base}}$ | `insufficient_history` if $N < 24$ |
| **Custom Scenario** | `custom` | User rate $R_{\text{custom}}$ | $\text{AUM} \times R_{\text{custom}} / 100$ | $\text{Outflow}_{\text{custom}} - \text{Outflow}_{\text{base}}$ | `valid` if $0 \le R \le 100$ |

### 3.1 Incremental Outflow Reconciliation
$$\text{incremental\_outflow\_cr} = \text{estimated\_outflow\_cr} - \text{base\_outflow\_cr}$$
* If the Base Forecast is unavailable, incremental outflows for all scenarios evaluate strictly to `None` / `NaN`.
* The sum of base outflow plus incremental outflow strictly reconciles to the scenario estimated outflow.

---

## 4. Empirical Sample Adequacy & Insufficient History Rules

* **Historical Worst-Case Rate:**
  Calibrating an empirical historical maximum rate requires at least $24$ continuous monthly observations.
  Because the real processed dataset contains only **1 month (`2024-09`)**, describing the observed September 2024 rate as a historical worst-case is statistically invalid.
  The engine marks Historical Maximum as `status: "insufficient_history"` on the empirical pipeline.
* **Empirical Residual Bounds:**
  Require $N \ge 10$ prior out-of-sample forecast residuals. Marked `status: "insufficient_history"`.
