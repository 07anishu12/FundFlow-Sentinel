# GDELT Historical Model Comparison Protocol & Pre-Registration

**Date:** 2026-10-28  
**Lead Auditor / Modeling Architect:** Senior Quantitative Research Lead  
**Evaluation Status:** **NOT TESTED / INSUFFICIENT_HISTORY ON REAL DATASET**

---

## 1. Predeclared Evaluation Protocol

To avoid publication bias and data snooping, any future proposal to incorporate GDELT macro news tone into category-level redemption forecasting must adhere to the following protocol:

1. **Paired Out-of-Sample Design:**
   - Model A (Baseline): Pooled Ridge with 13 core financial & market features.
   - Model B (Candidate): Pooled Ridge with 13 core features + `gdelt_mean_tone_lag0`.
   - Both models must be evaluated on **identical out-of-sample forecast origins**, identical expanding-window folds, and identical target labels.
2. **Predeclared Improvement Threshold:**
   Model B must demonstrate:
   - Out-of-sample MAE reduction $\ge 5.0\%$ across all categories.
   - Lower MAE in $\ge 60\%$ of test calendar months.
   - Stability across categories without degrading any single category by $>10\%$.
3. **In-Fold Standardization:**
   If GDELT tone is included, its scaler must be fitted exclusively inside each training fold.

---

## 2. Empirical Feasibility Audit

* **Current Reality:** As established in [`docs/WAVE_7_8_PREFLIGHT.md`](file:///Users/anny/Desktop/mutual-fund/docs/WAVE_7_8_PREFLIGHT.md), the real processed AMFI dataset currently contains only 1 month (`2024-09`).
* **Audit Verdict:** A walk-forward comparison cannot be executed on empirical data at this time.
* **Prohibition:** In-sample correlations, synthetic dataset comparisons, or partial time spans must **never** be cited as evidence of GDELT predictive outperformance.
* **Lead Recommendation:** GDELT tone remains excluded from the primary feature matrix.
