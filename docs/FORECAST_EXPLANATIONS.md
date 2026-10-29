# FundFlow Forecast Explanations & Empirical Uncertainty Bands

**Specification Version:** 1.0.0  
**Owner:** Agent A (Quantitative Architecture)  
**Implementation Module:** [`src/fundflow/explain.py`](file:///Users/anny/Desktop/mutual-fund/src/fundflow/explain.py)  
**Verification Suite:** [`tests/test_explain.py`](file:///Users/anny/Desktop/mutual-fund/tests/test_explain.py)  
**Current Empirical Status:** **BLOCKED / INSUFFICIENT_HISTORY on Real Dataset** (1 month of processed flows)

---

## 1. Linear Feature Decomposition & Non-Causal Semantics

### 1.1 Mathematical Formulation
For any out-of-sample redemption rate forecast $\hat{y}$ produced by the pooled Ridge model, the prediction is exactly decomposed into additive contributions:

$$\hat{y} = \beta_0 + \sum_{j=1}^{13} w_j \left( \frac{x_j - \mu_j}{\sigma_j} \right) + \sum_{k=1}^K v_k d_k$$

Where:
* $\beta_0$: Model intercept.
* $w_j$: Ridge coefficient for the $j$-th standardized numeric predictor.
* $z_j = \frac{x_j - \mu_j}{\sigma_j}$: Standardized feature value computed using training fold mean $\mu_j$ and scale $\sigma_j$.
* $\text{contrib}_j = w_j \cdot z_j$: Feature contribution in percentage points.
* $v_k \cdot d_k$: One-hot category effect for category $c$.

### 1.2 Reconciliation Invariant
The platform verifies exact linear reconciliation for every explained prediction:
$$\left| \hat{y} - \left( \beta_0 + \text{contrib}_{\text{category}} + \sum_{j=1}^{13} \text{contrib}_j \right) \right| \le 10^{-4}$$

If any feature value is missing or non-finite, the explainer returns `explanation_status: "unavailable"` with an explicit diagnostic reason rather than fabricated contributions.

### 1.3 Non-Causal Explanation Mandate
> **⚠️ NON-CAUSAL DISCLOSURE:**  
> Feature contributions describe the arithmetic mechanics of the fitted linear regression response. They represent statistical associations and linear weighting within the feature matrix, **NOT** structural economic causality or investor psychology drivers.

---

## 2. Empirical Residual Uncertainty Bands (P10 / P90)

### 2.1 Methodology
Rather than relying on unrealistic Gaussian homoskedasticity assumptions, the platform estimates prediction intervals empirically from historical out-of-sample walk-forward forecast errors:

$$e_i = y_{\text{actual}, i} - \hat{y}_{\text{pred}, i}$$

For a new forecast $\hat{y}$ made at decision origin $T_{\text{as\_of}}$:
1. **Eligible Residual Set ($\mathcal{E}_{T_{\text{as\_of}}}$):** Comprises exclusively out-of-sample forecast residuals from earlier origins whose actual realized targets were officially released before $T_{\text{as\_of}}$:
   $$\mathcal{E}_{T_{\text{as\_of}}} = \{ e_i \mid \text{as\_of}_i < T_{\text{as\_of}} \land \text{available\_from}(y_i) \le T_{\text{as\_of}} \}$$
2. **Empirical Quantiles:**
   $$\Delta_{\text{P10}} = \text{Quantile}_{0.10}(\mathcal{E}_{T_{\text{as\_of}}}), \quad \Delta_{\text{P90}} = \text{Quantile}_{0.90}(\mathcal{E}_{T_{\text{as\_of}}})$$
3. **Band Formulation:**
   $$\text{lower\_band} = \max(0.0, \hat{y} + \Delta_{\text{P10}}), \quad \text{upper\_band} = \hat{y} + \Delta_{\text{P90}}$$

### 2.2 Minimum History & Insufficient Evidence Policy
* **Minimum Residual Threshold:** Requires $N_{\text{residuals}} \ge 10$ prior out-of-sample residuals.
* **Insufficient History Fallback:** If $N_{\text{residuals}} < 10$, the engine returns:
  * `lower_band`: `None`
  * `upper_band`: `None`
  * `band_status`: `"insufficient_history"`
  * Zero-width or hard-coded fallback intervals are strictly prohibited.
* **Empirical Reality:** Because the real processed AMFI dataset currently contains only 1 month (`2024-09`), empirical walk-forward residual bands are classified as **BLOCKED / INSUFFICIENT_HISTORY** on the real data pipeline. The algorithm is verified via synthetic test suites.
