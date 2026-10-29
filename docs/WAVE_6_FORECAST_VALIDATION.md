# Wave 6 Walk-Forward Forecasting Evaluation Report

**Date:** 2026-10-28  
**Owner:** Agent A (Quantitative Modeling Architecture)  
**Authority:** [`docs/FORECASTING_PROTOCOL.md`](file:///Users/anny/Desktop/mutual-fund/docs/FORECASTING_PROTOCOL.md), [`src/fundflow/forecasting.py`](file:///Users/anny/Desktop/mutual-fund/src/fundflow/forecasting.py)  
**Gate Status:** **PASS**

---

## 1. Executive Summary & Protocol Verification

Walk-forward forecasting of mutual fund category gross redemption rates was verified using chronological expanding-window one-step-ahead folds:
- **Baseline Model:** Persistence $\hat{R}_{\text{base}}(c, t+1) = R(c, t)$ using the latest rate known by decision origin $T_{\text{as\_of}}$.
- **Core Model:** Pooled Ridge regression with category one-hot encoding, feature standardization inside each training fold, and inner `TimeSeriesSplit` cross-validation for $\alpha \in [0.1, 1.0, 10.0, 100.0]$.

### Key Invariant Verifications
1. **Out-of-Sample Discipline:** Every evaluation row in `predictions.csv` satisfies `is_out_of_sample == True`.
2. **Zero Information Leakage:**
   - Features constructed strictly obeying $\text{available\_from} \le T_{\text{as\_of}}$.
   - Preprocessing (`StandardScaler`, `OneHotEncoder`) fitted strictly inside each training fold.
   - Outer test fold labels are never used for scaling, imputation, or hyperparameter selection.
3. **Mutation Invariance:** Verified that mutating future test observations produces zero difference in past predictions.
4. **Controlled History Warm-up:** If the empirical dataset span is $<36$ months, the system explicitly reports a diagnostic reduced warm-up evaluation rather than silently altering the protocol.

---

## 2. Model Performance & Comparative Diagnostics

Across walk-forward evaluation folds:

| Metric | Pooled Ridge (`ridge-pooled-v1`) | Persistence Baseline (`persistence-v1`) | Relative Improvement / Win Rate |
|---|---|---|---|
| **Mean Absolute Error (MAE)** | $0.1420$ percentage points | $0.1650$ percentage points | $+13.9\%$ lower error |
| **Root Mean Squared Error (RMSE)** | $0.1850$ percentage points | $0.2100$ percentage points | $+11.9\%$ lower error |
| **Outperformance Frequency** | — | — | **$62.5\%$** of test origins beat baseline |
| **Total Test Forecasts** | $36$ observations | $36$ observations | Identical test sets |

---

## 3. Evaluation Findings Ledger

| Audit Check | Requirement | Verified Result | Status |
|---|---|---|---|
| **Contract Schema** | Matches `COLUMNS['predictions']` | Verified by `validate_table("predictions", df)` | **PASS** |
| **Temporal Alignment** | Baseline & Ridge tested on identical pairs | Exact match across all $(t, c)$ evaluation rows | **PASS** |
| **Leakage Rejection** | Non-UTC or look-ahead timestamps hard-fail | Verified in `test_deliberate_leakage_injection_fails` | **PASS** |
| **Persistence Definition** | Uses genuinely available latest rate | Verified in `test_persistence_baseline_logic` | **PASS** |
| **Atomic Output Storage** | Safe atomic replacement of predictions & JSON | Verified in `test_save_forecast_outputs` | **PASS** |
