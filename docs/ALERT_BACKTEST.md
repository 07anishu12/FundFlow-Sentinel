# FundFlow Alert Rules Backtest & Performance Audit

**Date:** 2026-10-28  
**Lead Auditor / Modeling Architect:** Senior Quantitative Research Lead  
**Evaluation Status:** **BLOCKED / INSUFFICIENT_HISTORY ON REAL DATASET**

---

## 1. Backtesting Protocol & Evaluation Design

The platform backtesting protocol defines the evaluation of alert events chronologically:
1. **Decision Cutoff:** For each historical month $t$, alert rules are evaluated as of $T_{\text{as\_of}}(t)$.
2. **Prior-Only Thresholds:** Percentiles and robust Z-scores are computed strictly using observations with $\text{available\_from} \le T_{\text{as\_of}}(t)$.
3. **Event Ground Truth Definition:** A historical "High Outflow Event" is defined as a realized category gross redemption rate exceeding the historical 80th percentile computed from training data available up to that origin.
4. **Metrics Evaluated:**
   - Precision: $\frac{\text{True Alerts}}{\text{Total Alerts Fired}}$
   - Recall: $\frac{\text{True Alerts}}{\text{Total Historical Events}}$
   - False Alert Rate: $\frac{\text{False Alerts}}{\text{Total Normal Months}}$

---

## 2. Empirical Data Sufficiency Verdict

* **Inspected Dataset Coverage:** As documented in [`docs/WAVE_7_8_PREFLIGHT.md`](file:///Users/anny/Desktop/mutual-fund/docs/WAVE_7_8_PREFLIGHT.md), the real processed AMFI dataset ([`data/processed/flows_category_month.csv`](file:///Users/anny/Desktop/mutual-fund/data/processed/flows_category_month.csv)) currently contains only a **single month (`2024-09`)**.
* **Audit Determination:**
  - Backtesting cannot be performed on a single time slice.
  - An empirical backtest requires at least 24 to 36 months of continuous history.
  - Reporting metrics like $100\%$ precision or recall on an empty or 1-observation dataset constitutes statistical fabrication.
* **Status:** **BLOCKED / INSUFFICIENT_HISTORY**.
* **Precaution:** Synthetic test suites in [`tests/test_alerts.py`](file:///Users/anny/Desktop/mutual-fund/tests/test_alerts.py) verify rule boundary correctness and precedence logic, but do not substitute for empirical historical backtest performance.
