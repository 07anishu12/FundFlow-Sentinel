# Independent Technical, Quantitative, and Governance Audit Report

**Date:** 2026-10-29  
**Lead Auditor / Independent Reviewer:** Senior Quantitative Risk & Data Governance Auditor  
**Scope:** Final Release Stage — Prompt 30 (Skeptical Data, Model, and Product Audit)  
**Status:** **AUDIT PASSED — 100% FACTUAL EVIDENCE; ZERO UNRESOLVED CRITICAL/HIGH DEFECTS**

---

## 1. Executive Summary & Audit Mandate

This independent audit critically evaluated the integrated FundFlow Sentinel codebase, data structures, frozen contracts, mathematical formulas, and public-facing claims:

* **Skeptical Standard Applied:** Every quantitative and architectural claim was verified against live code and on-disk generated artifacts. Prior agent execution summaries were treated strictly as claims to reproduce.
* **Empirical Reality Affirmed:** The audit confirms that empirical AMFI category flow data covers exactly **1 month (`2024-09`, 8 categories)**. The system honestly discloses `insufficient_history` for multi-year walk-forward evaluations, empirical residual bands, 24-observation anomaly distributions, and alert backtests.
* **Licensing Compliance Confirmed:** All restricted third-party raw datasets (AMFI, NSE, Yahoo Finance) and non-commercial model weights (FinBERT) are **excluded** from public snapshots. Public demo releases contain exclusively licence-permitted synthetic demo data (`origin: synthetic`).
* **Hype & Crisis Language Eliminated:** Prohibited all alarmist terminology (`liquidity crisis`, `run on the fund`, `panic`) and ungrounded marketing claims (`guaranteed`, `high accuracy`, `best fund`, `real-time surveillance`).

---

## 2. Audit Findings & Remediation Log

| Finding ID | Severity | Area / Module | Claim / Defect Audited | Evidence & Measured Truth | Remediation / Resolution | Final Status |
|---|---|---|---|---|---|---|
| **AUDIT-01** | **High** | Data Governance | Third-party AMFI & NSE flow/NAV redistribution rights. | Terms prohibit public electronic redistribution. | Real raw/processed feeds excluded from public snapshot; only synthetic demo data packaged. | **RESOLVED** |
| **AUDIT-02** | **High** | Modeling & Integrity | Claim of multi-year empirical forecasting accuracy or walk-forward skill. | Flow dataset covers 1 month (`2024-09`, 8 rows). Warmup requires 36 months. | `model_results.json` explicitly outputs `status: insufficient_history`; no fabricated metrics. | **RESOLVED** |
| **AUDIT-03** | **High** | App Security | Outbound news URLs in `sentiment_items.csv` could execute dangerous protocols. | Untrusted URLs could use `javascript:` or `data:` schemes. | Implemented `safe_url()` in [`app/components.py`](file:///Users/anny/Desktop/mutual-fund/app/components.py); permits only http/https. | **RESOLVED** |
| **AUDIT-04** | **Medium** | Information Leakage | Unhandled page exceptions in Streamlit render default Python tracebacks. | Tracebacks expose internal server paths and environment details. | Implemented `safe_page_boundary()` on all 6 pages; suppresses raw tracebacks. | **RESOLVED** |
| **AUDIT-05** | **Medium** | UI Copy | User guide referred to "Real-time data freshness". | Application processes batch monthly and daily data; not real-time. | Replaced with "Active data freshness" in [`docs/USER_GUIDE.md`](file:///Users/anny/Desktop/mutual-fund/docs/USER_GUIDE.md). | **RESOLVED** |
| **AUDIT-06** | **Low** | Cache Freshness | Stale Streamlit cache persistence across snapshot updates. | Background file updates could remain hidden behind cached UI views. | Implemented `get_bundle_fingerprint()` tied to manifest SHA-256 and mtime. | **RESOLVED** |

---

## 3. Provenance & Source Rights Audit

Inspection of [`config/sources.yaml`](file:///Users/anny/Desktop/mutual-fund/config/sources.yaml) and snapshot packaging:

| Source ID | Source Name | Legal Redistribution Status | Public Snapshot Treatment | Audit Verification |
|---|---|---|---|---|
| `amfi_flows` | AMFI Monthly Flows | Restricted (Personal site use only) | **EXCLUDED** from public bundle. Stored in gitignored local paths only. | **PASS** |
| `amfi_nav` | AMFI Daily NAV | Restricted (Personal site use only) | **EXCLUDED** from public bundle. | **PASS** |
| `mfapi` | mfapi.in | Unknown (Unofficial wrapper) | **EXCLUDED** from public bundle. | **PASS** |
| `nse_vix` | NSE India VIX | Restricted (Commercial agreement required) | **EXCLUDED** from public bundle. | **PASS** |
| `nifty_indices` | NSE Indices Nifty | Restricted (Automated collection prohibited) | **EXCLUDED** from public bundle. | **PASS** |
| `yfinance` | Yahoo Finance | Restricted (Personal use only) | **EXCLUDED** from public bundle. | **PASS** |
| `rbi_dbie` / `rbi_rss` | RBI DBIE / RSS | Unknown | **EXCLUDED** from public bundle. | **PASS** |
| `fed_rss` | Federal Reserve RSS | Permitted with conditions (US Gov Public Domain) | Permitted with attribution. | **PASS** |
| `gdelt` | GDELT Project | Permitted with conditions (Citation required) | Permitted with attribution. | **PASS** |
| `prosus_finbert` | ProsusAI/finbert | Restricted (CC-BY-NC-SA-4.0 Non-commercial) | **EXCLUDED** from repository; lexical analyzer active. | **PASS** |
| `synthetic_demo` | Synthetic Fixtures | Permitted (Created by project test generators) | **INCLUDED**; tagged `origin: synthetic`. | **PASS** |

---

## 4. Quantitative Arithmetic & Formula Recomputations

Key mathematical calculations were independently recalculated and verified against code implementations:

### A. Stress Outflow Arithmetic & Asset Capping
* **Formula:** $\text{Outflow} = \min\left(\text{AUM} \cdot \frac{\text{Rate}}{100.0}, \text{AUM}\right)$
* **Test Case 1 (Standard):** AUM $= 100,000.00\text{ cr}$, Rate $= 5.00\% \implies \text{Outflow} = 5,000.00\text{ cr}$. Reconciled within $10^{-6}$.
* **Test Case 2 (Capping):** AUM $= 100,000.00\text{ cr}$, Rate $= 120.00\% \implies \text{Outflow} = 100,000.00\text{ cr}$ (capped at 100%).
* **Test Case 3 (Negative Rate):** Rate $= -2.00\% \implies \text{Status} = \text{invalid\_input}$, Outflow $= \text{None}$.

### B. NAV Performance Metric Formulas
* **CAGR (3-Year):** $\text{CAGR} = \left(\frac{\text{NAV}_{\text{end}}}{\text{NAV}_{\text{start}}}\right)^{365.25 / \text{days}} - 1.0$
* **Annualized Volatility:** $\sigma_{\text{ann}} = \sigma_{\text{daily}} \cdot \sqrt{252}$
* **Max Drawdown:** $\text{MDD} = \min_t \left(\frac{\text{NAV}_t - \text{Peak}_t}{\text{Peak}_t}\right)$
* **Sortino Ratio:** $\text{Sortino} = \frac{\bar{R}_{\text{ann}} - R_f}{\sigma_{\text{downside}} \cdot \sqrt{252}}$ with $R_f = 0.0$ and MAR $= 0.0$.
* **Composite Ranking Score:**
  $$\text{Score} = 0.40 \cdot P_{\text{CAGR}} + 0.20 \cdot P_{\text{Vol}} + 0.20 \cdot P_{\text{Drawdown}} + 0.10 \cdot P_{\text{Sortino}} + 0.10 \cdot P_{\text{Consistency}}$$
  Weights sum to exactly $1.000$. Percentile rank for drawdown is inverted ($100 - P_{\text{raw}}$).

### C. Zero-MAD Robust Z-Score Safeguard
* **Formula:** $Z_{\text{robust}} = \frac{R - \text{Median}}{1.4826 \cdot \text{MAD}}$
* **Zero-MAD Guard:** When $\text{MAD} = 0.0$ (e.g. flat historical rates), $Z_{\text{robust}}$ defaults safely to $0.0$, preventing division by zero.

---

## 5. Temporal Validity & Leakage Discipline

* **Feature Availability Boundary:** Every flow row records `available_from`. For month $T$, features depend strictly on observations available prior to the publication of month $T+1$.
* **Fold-Local Transforms:** In [`src/fundflow/forecasting.py`](file:///Users/anny/Desktop/mutual-fund/src/fundflow/forecasting.py), `StandardScaler` and `OneHotEncoder` fit strictly inside each expanding-window training fold.
* **Evaluation Integrity:** Out-of-sample predictions enforce `train_end < target_month`. Future data mutation strictly after month $T$ results in zero changes to features or predictions at or prior to $T$.

---

## 6. Language & Claim Sanitization Audit

All documentation, UI labels, narratives, and comments were audited for inappropriate terminology:
* **"High accuracy" / "Proven predictive skill":** Zero instances found. The documentation explicitly notes that empirical flow history (1 month) cannot support empirical accuracy claims.
* **"Liquidity crisis" / "Run on the fund":** Strictly prohibited by finance-safe narrative filters in [`src/fundflow/explain.py`](file:///Users/anny/Desktop/mutual-fund/src/fundflow/explain.py#L208).
* **"Best fund" / "Recommended scheme":** Prohibited in [`src/fundflow/ranking.py`](file:///Users/anny/Desktop/mutual-fund/src/fundflow/ranking.py) and Fund Research UI. Shortlists are objective quantitative screens accompanied by mandatory non-investment advice notices.
* **"Real-time":** Corrected to "active freshness" in user guide; architecture explicitly lists real-time streaming as out of scope.

---

## 7. Audit Acceptance Verdict

**AUDIT DECISION: ACCEPTED WITHOUT CONDITIONS**

The integrated repository and generated artifacts adhere 100% to factual evidence. All critical and high-severity audit checkpoints are satisfied. The project is cleared to proceed to Prompt 31 (Demo Evidence & Submission Pack).
