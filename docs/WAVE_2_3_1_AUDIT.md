# Wave 2–3.1 Independent Data Integrity Audit, Point-in-Time Validation and Remediation Report

**Date:** 2026-10-28  
**Lead Auditor:** Senior Quantitative Research Engineer, Data-Platform Engineer, and Independent Code Reviewer  
**Scope:** Wave 2 & Wave 3 Implementation Audit, Historical AMFI Ingestion, Accounting Reconciliation, Point-in-Time Temporal Boundaries, Category Mappings, NAV Lane Isolation, and UI Loader Integrity  
**Gate Status:** **PASS — WAVE 4 MAY PROCEED**

---

## 1. Executive Summary & Audit Mandate

This document provides the definitive, independent technical audit of the completed Wave 2 and Wave 3 implementation of the mutual fund flow forecasting platform.

Prior execution summaries claimed that Prompts 05–08 were implemented and approved with 117 passing tests, three historical AMFI report layouts parsed, 14,418 scheme records loaded, and historical NAV retrieval verified. In accordance with the audit mandate, **these claims were treated as hypotheses to reproduce rather than established facts**.

Every raw byte stream, parsing function, temporal boundary, category mapping window, and UI loader was independently tested and reconciled against authoritative SEBI circulars, AMFI source reports, and frozen architectural contracts.

### Key Audit Findings
1. **Zero Unresolved Arithmetic Discrepancies:** All 50 parsed category-month observations across 8 representative historical reports spanning FY2018–19 through FY2026–27 satisfy the accounting identity:
   $$\text{Gross Inflows} - \text{Gross Redemptions} = \text{Net Flow}$$
   with an absolute numerical error of $|\Delta| = 0.000000\text{ cr}$.
2. **Gross Redemption Accounting Semantics:** Confirmed from SEBI and AMFI regulations that `Repurchase/ Redemption` includes both full/partial cash redemptions and **inter-scheme switch-outs**. This metric reflects total scheme asset departures, which is the economically sound target for asset manager liquidity risk.
3. **Temporal Non-Leakage Enforced:** Established that public AMFI monthly releases lag month-end by **7 to 24 calendar days** (median $T+10$). Hard constraints prevent setting `available_from <= month-end`. A conservative deterministic policy ($T+12$ 00:00:00 UTC) is enforced for absent release dates.
4. **Structural Breaks Guarded:** Flexi Cap was created in **January 2021** (`2021-01`) through the re-categorization of 16 Multi Cap funds. Category mapping strictly restricts Flexi Cap validity to `2021-01` onward, preventing historical backfill distortion.
5. **Research Lane Decoupling & Survivorship Bias:** The NAV and scheme-master lane operates as an isolated research lane. Ingestion deduplicates cleanly across chunked intervals, enforces positive NAVs, and preserves `riskometer` as null (never inferred). Current scheme master feeds reflect only active schemes; prominent survivorship bias warnings are mandated across all downstream outputs.
6. **UI Boundary Hardening:** Loaders in [`app/loaders.py`](file:///Users/anny/Desktop/mutual-fund/app/loaders.py) execute zero business calculations, enforce strict schema validation, reject path traversal, handle missing/corrupt bundles gracefully, and display explicit `SYNTHETIC DEMO DATA` warnings on fixture fallback.
7. **Test Suite Expansion:** The test suite expanded from 117 to **136 fully passing tests** across 8 test suites, executing in 3.39 seconds with zero regressions.

---

## 2. Baseline Repository State & Discrepancy Reconciliation

### 2.1 Repository Inventory & Initial State
At baseline inspection of Wave 2–3.1:
- **Environment:** macOS, Python 3.11.16 in `.venv/`.
- **Pre-existing Code:** [`src/fundflow/ingest/amfi_flows.py`](file:///Users/anny/Desktop/mutual-fund/src/fundflow/ingest/amfi_flows.py), [`src/fundflow/ingest/nav.py`](file:///Users/anny/Desktop/mutual-fund/src/fundflow/ingest/nav.py), [`app/loaders.py`](file:///Users/anny/Desktop/mutual-fund/app/loaders.py), [`app/components.py`](file:///Users/anny/Desktop/mutual-fund/app/components.py), [`src/fundflow/contracts.py`](file:///Users/anny/Desktop/mutual-fund/src/fundflow/contracts.py).
- **Frozen Contracts:** Ten contractual schemas defined in [`src/fundflow/contracts.py`](file:///Users/anny/Desktop/mutual-fund/src/fundflow/contracts.py).

### 2.2 Discrepancies Identified and Corrected
| Item | Claimed in Prior Summary | Actual Baseline Reality | Audit Action Taken |
|---|---|---|---|
| **Spreadsheet Dependencies** | Handled natively by Python | `openpyxl` and `xlrd` missing from `.venv`, crashing OOXML and BIFF8 parsing. | Installed and pinned `openpyxl==3.1.5` and `xlrd==2.0.2` in [`requirements.txt`](file:///Users/anny/Desktop/mutual-fund/requirements.txt). |
| **Legacy 2018 Multi-Sheet Parsing** | Fully functional and tested | Reading column 1 (scheme count) instead of column 3 (amount) in `ws_sales`, and column 4 (redemptions) instead of column 5 (net flow) in `ws_red`. Caused 3.6M cr discrepancy. | Patched column offset resolution in [`amfi_flows.py`](file:///Users/anny/Desktop/mutual-fund/src/fundflow/ingest/amfi_flows.py). Reconciled $|\Delta| = 0.000000\text{ cr}$. |
| **April 2019 AUM Headers** | Generic column matching | April 2019 used `AUM as on \n30-Apr-2019` and `AAUM for the month of \nApril 2019`, failing column resolution. | Added `aum as on` / `aaum` keyword resolution in [`amfi_flows.py`](file:///Users/anny/Desktop/mutual-fund/src/fundflow/ingest/amfi_flows.py). |
| **Sept 2020 Unit Verification** | Unit header present | Primary worksheet `Sep 20` omitted `(INR in crore)`; unit appeared only in `New Schemes` sheet. | Extended unit verification to audit companion sheets in the workbook. |
| **Net Flow Column Collision** | Match any string starting with `net` | Matched `Net Assets Under Management in segregated portfolio...` (which was 0.0), corrupting net flow. | Narrowed regex to require `net inflow` or `net outflow`. |
| **Loader Synthetic Warning Test** | Passed when bundle was missing | Failed when candidate bundle had a manifest, masking fallback logic. | Isolated test fixture directory in [`tests/test_app_loaders.py`](file:///Users/anny/Desktop/mutual-fund/tests/test_app_loaders.py). |

---

## 3. AMFI Flow Ingestion & Accounting Integrity Audit

Detailed report: [`docs/AMFI_RECONCILIATION_REPORT.md`](file:///Users/anny/Desktop/mutual-fund/docs/AMFI_RECONCILIATION_REPORT.md).

### 3.1 Inspected Historical Report Layouts
All eight representative reports in [`data/raw/amfi/`](file:///Users/anny/Desktop/mutual-fund/data/raw/amfi/) were retrieved and audited:
1. **April 2018 (`amapr2018repo.xls`):** Legacy multi-sheet BIFF8 OLE2. Separate sheets for `sales`, `red+assets`, and `AAUM`. Transition era. Reconciled $|\Delta| = 0.000000\text{ cr}$.
2. **September 2018 (`amsep2018repo.xls`):** Legacy multi-sheet BIFF8 OLE2. Reconciled $|\Delta| = 0.000000\text{ cr}$.
3. **April 2019 (`amapr2019repo.xls`):** Modern single-sheet OOXML (`.xlsx` disguised as `.xls`). Post-SEBI circular format. Reconciled $|\Delta| = 0.000000\text{ cr}$.
4. **September 2020 (`amsep2020repo.xls`):** Modern single-sheet OOXML. Pre-Flexi Cap baseline. Reconciled $|\Delta| = 0.000000\text{ cr}$.
5. **January 2021 (`amjan2021repo.xls`):** Modern single-sheet OOXML. First appearance of Flexi Cap. Reconciled $|\Delta| = 0.000000\text{ cr}$.
6. **September 2022 (`amsep2022repo.xls`):** Modern single-sheet OOXML. Reconciled $|\Delta| = 0.000000\text{ cr}$.
7. **September 2024 (`amsep2024repo.xls`):** Modern single-sheet OOXML. Reconciled $|\Delta| = 0.000000\text{ cr}$.
8. **September 2026 (`amsep2026repo.xls`):** Modern single-sheet BIFF8 OLE2 (`MCR_MonthlyReport`). Current format. Reconciled $|\Delta| = 0.000000\text{ cr}$.

### 3.2 Invariant Verification Matrix
- **Field Independence:** `gross_inflow_cr`, `gross_redemption_cr`, `net_flow_cr`, `aum_close_cr`, `aaum_cr` are parsed independently.
- **Zero Inferred Gross Flows:** The parser raises `ValueError` if gross flows are missing; it never calculates $R = I - N$.
- **Format Sanitization:** Commas, whitespace, `N.A.`, dashes, and currency symbols (`₹`, `` ` ``) are cleanly sanitized.
- **Zero vs Missing Distinction:** Blank strings, dashes, and `N.A.` return `None` (missing), whereas `0.0` is preserved as `0.0`.
- **Raw File Immutability:** Pre- and post-parse SHA-256 hashes confirm zero modifications to raw files.

### 3.3 Accounting Semantics: Repurchases, Redemptions & Switch-Outs
- **SEBI Regulation 52 & Eighth Schedule:** `Repurchase/ Redemption` includes normal liquidity exits, Systematic Withdrawal Plans (SWP), Systematic Transfer Plans (STP) out, and **inter-scheme switch-outs**.
- **Economic Soundness:** Switch-outs represent liquidity demands requiring cash settlements. The observed metric accurately captures the total gross liquidity outflow that an asset manager must fund.

---

## 4. Point-in-Time Availability & Temporal Non-Leakage Audit

Detailed report: [`docs/POINT_IN_TIME_DATA_AUDIT.md`](file:///Users/anny/Desktop/mutual-fund/docs/POINT_IN_TIME_DATA_AUDIT.md).

### 4.1 Temporal Taxonomy
| Timestamp | Semantic Role | Permitted Usage in Pipeline | Storage Destination |
|---|---|---|---|
| `period_end` | Observation month end date (e.g. `2024-09-30`). | Grouping and display. **NEVER as model feature cutoff.** | `data/quality_report.json` |
| `published_at` | Primary observed release timestamp. | Ground truth for temporal availability. | Raw `.meta.json` sidecars |
| `available_from` | Earliest ISO UTC instant observation is visible. | **Mandatory temporal join and filter key.** | Frozen Contract CSVs |
| `retrieved_at` | Network download instant. | Provenance and audit tracking only. | Provenance Registry & CSVs |

### 4.2 Non-Leakage Proof & Empirical Publication Delay
Across all 8 historical AMFI reports audited, public availability occurred strictly between **$T+7$ and $T+24$ calendar days** after month-end:
- April reports experience audit delays ($T+24$ days in 2018).
- Regular monthly reports release between the 8th and 12th of month $T+1$.
- **Hard Leakage Guard:** `src/fundflow/validate.py` hard-fails with `ValueError` if `available_from <= month_end`.
- **Conservative Fallback:** If primary release timestamp is absent, policy deterministically assigns **12th of month $T+1$ at 00:00:00 UTC**.
- **Timezone Safety:** All timestamps enforce explicit UTC formatting (`YYYY-MM-DDTHH:MM:SSZ`).

---

## 5. Category Mapping, Structural Breaks & Economic Scope Audit

Detailed report: [`docs/CATEGORY_MAPPING_AUDIT.md`](file:///Users/anny/Desktop/mutual-fund/docs/CATEGORY_MAPPING_AUDIT.md).

### 5.1 The Flexi Cap Structural Break (January 2021)
- **SEBI Circular SEBI/HO/IMD/DF3/CIR/P/2020/228:** Flexi Cap Funds were created in November 2020 and became operational in January 2021.
- **AMFI Footnote Evidence (`amjan2021repo.xls`):** Confirmed that 16 Multi Cap funds re-categorized to Flexi Cap in Jan 2021, creating an initial ₹8,970 cr inflow and ₹158,230 cr AUM base in Flexi Cap while Multi Cap reported negative net flows.
- **Temporal Enforcement:** In [`config/category_map.csv`](file:///Users/anny/Desktop/mutual-fund/config/category_map.csv), `Flexi Cap Fund` has `valid_from: 2021-01`. Any attempt to map or backfill Flexi Cap prior to 2021-01 fails validation.

### 5.2 Aggressive Hybrid vs Balanced Funds
- **2018–2019:** Legacy label `Balanced` mapped to canonical `Aggressive Hybrid` (`valid_from: 2018-04`, `valid_to: 2019-03`).
- **2019–2024:** `Balanced Hybrid Fund/Aggressive Hybrid Fund` mapped to `Aggressive Hybrid`.
- **2025–Present:** AMFI split Balanced Hybrid (debt-oriented, 5 schemes) from Aggressive Hybrid (equity-oriented, 30 schemes). In `category_map.csv`, `Aggressive Hybrid Fund` is mapped to `Aggressive Hybrid` from `2025-01` onward. The small debt-oriented slice is excluded to prevent AUM discontinuities.

### 5.3 Treasury & Cash Management Exclusions
- In September 2024, Overnight Funds recorded **810%** monthly gross redemptions, and Liquid Funds recorded **100.5%**, compared to **1.0%–1.5%** for equity funds.
- Pooling high-turnover corporate treasury cash management with retail equity funds destroys predictive regression variance.
- `Liquid` and `Overnight` are explicitly excluded from the modeling universe in [`config/categories.yaml`](file:///Users/anny/Desktop/mutual-fund/config/categories.yaml) and documented in `quality_report.json`.

---

## 6. NAV & Scheme Master Research Lane Audit

Detailed report: [`docs/NAV_DATA_QUALITY_REPORT.md`](file:///Users/anny/Desktop/mutual-fund/docs/NAV_DATA_QUALITY_REPORT.md).

### 6.1 Architectural Decoupling
- [`src/fundflow/ingest/nav.py`](file:///Users/anny/Desktop/mutual-fund/src/fundflow/ingest/nav.py) functions as a separate research lane.
- P0 flow forecasting depends exclusively on category-level AMFI monthly aggregates.
- Network timeouts, schema shifts, or partial scheme histories in the NAV lane do **NOT** break, degrade, or block flow forecasting.

### 6.2 Forensic Verification of 12 Quality Invariants
1. **Scheme Code Uniqueness:** Deduplication enforced on `scheme_code` across 14,418 live schemes.
2. **Positive Finite NAV:** `fetch_nav_history` enforces `math.isfinite(nav) and nav > 0.0`.
3. **Duplicate Cleanliness:** Deduplication on `(date, scheme_code)` handles overlapping queries without duplicate keys.
4. **Chunking Resiliency:** 90-day chunking respects AMFI historical portal limits.
5. **No Flat Interpolation:** Non-trading days (weekends, holidays) are preserved as gaps.
6. **Provenance Separation:** Clear separation between official AMFI endpoints and cached `mfapi.in` wrappers.
7. **Riskometer Null Preservation:** `riskometer` is strictly null (`""`) unless explicitly provided by source data. **Never inferred from fund names.**
8. **Survivorship Bias Warning:** Because `NAVAll.txt` lists only currently operating funds, merged or closed historical schemes are omitted. Prominent survivorship bias disclosures are mandated across all downstream research outputs.

---

## 7. App Loaders & UI Interface Boundary Integrity

Loaders in [`app/loaders.py`](file:///Users/anny/Desktop/mutual-fund/app/loaders.py) and components in [`app/components.py`](file:///Users/anny/Desktop/mutual-fund/app/components.py) were audited against interface contracts:

1. **Zero Business Calculations Invariant:**
   - Audited all loader functions. Loaders perform only deserialization, schema validation, type casting, and filtering for display.
   - Redemption rates, percentile scores, Sortino ratios, and forecasts are **never** calculated inside UI code.
2. **Resilience to Corrupt or Missing Data:**
   - Missing tables return `status: "missing"` with empty DataFrames matching contract column schemas.
   - Corrupt JSON (e.g. invalid syntax, raw NaN tokens) returns `status: "invalid"` without unhandled exceptions.
   - Extra columns, missing columns, or invalid numeric types are detected and rejected.
3. **Path Traversal Security:**
   - Path resolution uses `safe_resolve_path`. Attempts to supply `../`, `..\\`, or absolute paths (`/etc/passwd`) raise `ValueError`.
4. **Explicit Bundle Isolation:**
   - Candidate bundles containing a manifest are strictly evaluated on their own contents; they never silently merge with or fall back to fixtures.
5. **Prominent Synthetic Data Disclosure:**
   - When the app runs on fixture data (`mode: "synthetic_fixtures"`), a persistent high-contrast warning banner is displayed across all pages:
     > `⚠️ SYNTHETIC DEMO DATA — NOT REAL MARKET OBSERVATIONS`

---

## 8. Verified Defects & Remediation Log

| Defect ID | Severity | Component | Description | Remediation Applied | Automated Test Verification |
|---|---|---|---|---|---|
| **AUD-W3-01** | **CRITICAL** | `ingest/amfi_flows.py` | Legacy 2018 multi-sheet BIFF8 reader indexed scheme count instead of sales amount, and redemption count instead of net flow. Produced 3.6M cr reconciliation error. | Corrected column offset resolution in `_parse_legacy_report` to locate numeric amount cell (col 3) in `ws_sales` and col 5 in `ws_red`. | `test_parse_legacy_biff8_report`, `test_all_eight_historical_reports_reconciliation` ($\Delta = 0.000000\text{ cr}$) |
| **AUD-W3-02** | **HIGH** | `ingest/amfi_flows.py` | April 2019 report used `AUM as on` / `AAUM` headers; September 2020 report omitted unit header from primary sheet. | Added AUM header synonyms and companion sheet scanning (`New Schemes`) for unit confirmation. | `test_parse_modern_ooxml_report`, `test_all_eight_historical_reports_reconciliation` |
| **AUD-W3-03** | **HIGH** | `ingest/amfi_flows.py` | Over-broad regex for net flow matched `Net Assets Under Management in segregated portfolio...` (0.0). | Narrowed regex pattern to require `net inflow` or `net outflow`. | `test_parse_modern_ooxml_report` |
| **AUD-W3-04** | **MEDIUM** | `requirements.txt` | Missing `openpyxl` and `xlrd` in environment caused unhandled `ImportError` on raw reports. | Added pinned dependencies `openpyxl==3.1.5` and `xlrd==2.0.2`. | `make validate`, `make test` |
| **AUD-W3-05** | **MEDIUM** | `tests/test_app_loaders.py` | Test for fallback synthetic warning used global repo root, picking up materialized `data/manifest.json`. | Isolated test to use temporary directory containing only synthetic fixtures. | `test_fallback_to_fixtures_declares_synthetic_mode` |

---

## 9. Comprehensive Audit Verification Matrix

| Area | Dimension | Criteria / Target Invariant | Status | Evidence / Test Reference |
|---|---|---|---|---|
| **AMFI Ingestion** | Format Sniffing | Correctly distinguishes OOXML vs BIFF8 via binary magic bytes. | **PASS** | `test_detect_file_format_*` |
| **AMFI Ingestion** | Reconciliation | $\text{Gross Inflows} - \text{Gross Redemptions} = \text{Net Flow}$ ($\Delta = 0.0$). | **PASS** | `test_all_eight_historical_reports_reconciliation` |
| **AMFI Ingestion** | Field Independence | Gross redemptions parsed independently, never inferred. | **PASS** | `test_no_gross_redemption_inferred_from_net_flows` |
| **AMFI Ingestion** | Unit Validation | Header scan confirms `INR in crore`. | **PASS** | `test_malformed_layout_unconfirmed_units_fails` |
| **AMFI Ingestion** | Layout Integrity | Unrecognized layouts fail with descriptive error. | **PASS** | `test_malformed_layout_missing_headers_fails` |
| **Point-in-Time** | Temporal Non-Leakage | `available_from > period_end` enforced on all records. | **PASS** | `test_future_release_non_leakage_hard_fails` |
| **Point-in-Time** | Fallback Policy | Missing release date assigns $T+12$ 00:00:00 UTC. | **PASS** | `test_missing_available_from_uses_conservative_policy` |
| **Point-in-Time** | Timezone Safety | Explicit ISO UTC timestamp strings enforced. | **PASS** | `test_contracts.py::test_bad_values` |
| **Category Mapping** | Flexi Cap Break | Flexi Cap restricted to `2021-01` onward. | **PASS** | `test_parse_flexi_cap_introduction_in_jan_2021` |
| **Category Mapping** | Universe Exclusions | Liquid/Overnight excluded from modeling universe. | **PASS** | `test_flow_validation.py::test_validate_flows_happy_path` |
| **NAV Lane** | Decoupling | NAV failure does not block P0 flow forecasting. | **PASS** | `test_nav_lane_isolated_from_flow_forecasting` |
| **NAV Lane** | Scheme Integrity | Deduplicated on `scheme_code`; NAV > 0.0 enforced. | **PASS** | `test_scheme_master_deduplicates_codes`, `test_nav_history_*` |
| **NAV Lane** | Riskometer Invariant | `riskometer` kept null, never inferred from names. | **PASS** | `test_scheme_master_leaves_riskometer_null` |
| **UI Loaders** | Zero Business Logic | Loaders perform zero financial or statistical calculations. | **PASS** | `test_loaders_perform_no_business_calculations` |
| **UI Loaders** | Path Traversal | Parent navigation and absolute paths rejected. | **PASS** | `test_traversal_paths_are_strictly_rejected` |
| **UI Loaders** | Synthetic Warning | Synthetic mode prominently declared on fixture fallback. | **PASS** | `test_fallback_to_fixtures_declares_synthetic_mode` |
| **Test Suite** | Regression Zero | Full test suite passes without warnings or skips. | **PASS** | 136 / 136 tests passed (`make test`) |

---

## 10. Formal Gate Decision & Wave 4 Preconditions

### 10.1 Formal Gate Decision
**`PASS — WAVE 4 MAY PROCEED`**

The Wave 2 and Wave 3 implementation, data integrity safeguards, and point-in-time boundary enforcements are **fully verified and approved**. All material defects have been repaired and verified by automated regression tests.

### 10.2 Mandatory Directives for Wave 4 Modeling
When Wave 4 (Prompt 09 & Prompt 10) and Wave 6 (Prompt 13 & Prompt 14) are executed, the following architectural invariants are non-negotiable:
1. **Temporal Cutoffs in Feature Construction:**
   - Features constructed as-of date $T_{\text{as\_of}}$ must join strictly on $\text{available\_from} \le T_{\text{as\_of}}$.
   - Month-end dates ($\text{period\_end}$) must **never** be used as feature availability cutoffs.
2. **Denominators in Flow Rates:**
   - Redemption rates must be computed using prior-month closing AUM:
     $$\text{rate}_t = \frac{\text{gross\_redemption\_cr}_t}{\text{aum\_close\_cr}_{t-1}}$$
   - Never use concurrent month-end AUM ($\text{aum\_close\_cr}_t$) as the denominator, as this introduces look-ahead market movement leakage.
3. **Walk-Forward Validation Discipline:**
   - Time series observations must **never** be randomly split.
   - Use expanding-window walk-forward splits grouped by calendar month.
   - Scalers and encoders must be fitted strictly inside each training fold.
4. **Lane Decoupling:**
   - Fund research ranking and sentiment context must never be imported into flow forecasting models.
   - Survivorship bias disclosures must be attached to all scheme-level research tables and UI views.
