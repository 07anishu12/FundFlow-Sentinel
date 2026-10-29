# NAV Ingestion, Scheme Identity & Survivorship Bias Quality Report

**Audit Date:** 2026-10-28  
**Auditor:** Independent Quantitative & Data Platform Audit  
**Scope:** Wave 2–3.1 Data Integrity Audit  
**Artifacts Audited:** `src/fundflow/ingest/nav.py`, `tests/test_nav_ingest.py`, `src/fundflow/contracts.py`

---

## 1. Executive Summary & Lane Isolation

The NAV and Scheme Master ingestion module ([`src/fundflow/ingest/nav.py`](file:///Users/anny/Desktop/mutual-fund/src/fundflow/ingest/nav.py)) operates as an **independent research data lane**. It is architecturally decoupled from the P0 category-level flow forecasting pipeline:
- Flow forecasting uses category-level flow aggregates from AMFI monthly reports.
- NAV ingestion serves downstream P1 fund research ranking and scheme-level shortlist scoring.
- Failures, timeouts, or partial histories in the NAV lane do **NOT** break, degrade, or block P0 flow forecasting.

The module enforces strict compliance with the frozen CSV contracts:
- [`nav_daily.csv`](file:///Users/anny/Desktop/mutual-fund/src/fundflow/contracts.py#L70): `date, scheme_code, nav, source_url`
- [`scheme_master.csv`](file:///Users/anny/Desktop/mutual-fund/src/fundflow/contracts.py#L71): `scheme_code, scheme_name, fund_house, category, plan_type, option_type, riskometer`

---

## 2. Forensic Quality Audit (12 Quality Invariants)

| # | Inspection Item | Audit Evidence & Implementation Verification | Status |
|---|---|---|---|
| 1 | **Scheme-Code Uniqueness** | Tested on 14,418 live schemes. `scheme_master` deduplicates on `scheme_code` using `df.drop_duplicates(subset=['scheme_code'])`. | **PASS** |
| 2 | **NAV Positivity & Numerics** | `fetch_nav_history` enforces `math.isfinite(nav_val) and nav_val > 0.0`. Negative, zero, or non-finite values are filtered out. | **PASS** |
| 3 | **Duplicate Date & Value Conflicts** | Handled by deduplication on `(date, scheme_code)`. Where duplicate feeds report the same date, the first valid response is retained. | **PASS** |
| 4 | **Chunk Boundaries & Overlaps** | Date queries are chunked into 90-day windows. Overlapping boundary dates across chunks deduplicate cleanly without schema violation. | **PASS** |
| 5 | **Missing Dates & Business Days** | NAV is published exclusively on business/trading days. Gaps on weekends, public holidays, and exchange closures are preserved without linear interpolation. | **PASS** |
| 6 | **Source Response Limits** | AMFI historical portal limits date queries to 90 days. Bounded chunking handles multi-year requests reliably. | **PASS** |
| 7 | **Official vs Unofficial Provenance** | Clear separation: official AMFI endpoints (`portal.amfiindia.com`) vs community wrapper (`api.mfapi.in`). All outputs label exact `source_url`. | **PASS** |
| 8 | **Cache Freshness & Invalidation** | Responses are cached under `data/cache/nav/` and `data/raw/nav/amfi_navall_<date>.txt` with daily timestamps to prevent unbounded external calls. | **PASS** |
| 9 | **Null Preservation (Riskometer)** | `riskometer` is strictly preserved as null (`""`). **Never inferred from fund names.** Verified by `test_scheme_master_leaves_riskometer_null`. | **PASS** |
| 10 | **Survivorship Bias Disclosure** | Scheme lists sourced from `NAVAll.txt` exclude closed, merged, or matured funds. Documented prominently in `SURVIVORSHIP_BIAS_DISCLOSURE`. | **PASS** |
| 11 | **Plan & Option Reliability** | Direct vs Regular plans and Growth vs IDCW options are parsed from scheme text and section headers. | **PASS** |
| 12 | **Dividend & Split Adjustments** | Unadjusted NAV feeds reflect raw NAVs. For IDCW schemes, drops reflect dividend payouts. Downstream ranking must focus on Direct-Growth schemes. | **PASS** |

---

## 3. Survivorship Bias & Historical Population Analysis

### 3.1 The Survivorship Bias Risk
When conducting cross-sectional fund research or backtesting ranking algorithms:
1. `https://www.amfiindia.com/spages/NAVAll.txt` reflects **currently active mutual fund schemes**.
2. Schemes that underperformed and were subsequently liquidated, wound up, or merged into larger flagship schemes (e.g., during SEBI scheme rationalization in 2018) are absent from current scheme-master feeds.
3. Evaluating historical performance on surviving schemes alone will overstate average category performance and Sharpe ratios (survivorship bias).

### 3.2 Mitigation & Operational Guardrails
- **Disclosure Mandate:** All outputs, metadata envelopes, and UI pages accessing scheme research must display the `SURVIVORSHIP_BIAS_DISCLOSURE`:
  > *"Survivorship Bias Warning: Scheme lists sourced from current AMFI or API feeds reflect currently operational schemes and may exclude merged, closed, or discontinued historical schemes. Performance rankings and analyses using this lane must disclose survivorship bias."*
- **Research Scope:** Ranking in P1 is restricted to eligible Direct-Growth funds with $\ge 3$ years of uninterrupted daily NAV history.
- **Architectural Isolation:** Ranking scores never influence, weight, or import category-level flow forecasts or anomaly alerts.
