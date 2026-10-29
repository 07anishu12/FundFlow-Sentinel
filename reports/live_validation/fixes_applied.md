# FundFlow Sentinel — Audit & Remediation Log (Fixes Applied)

**Branch:** `feature/live-fund-validation-audit`  
**Base Commit:** `daaabd6ec2d5006d74cc514c982e5cd24a26bfb7`  
**Validation Date:** 2026-10-29 / 2026-10-30  
**Test Suite Result:** 346 / 346 Passed (100%)

---

## 1. Summary of Defects Identified and Resolved

| # | Component / Subsystem | Defect / Finding | Root Cause | File(s) Changed | Verification Evidence |
|---|---|---|---|---|---|
| 1 | **UI Header & Shell** | Missing `SYNTHETIC DEMO DATA` warning banner on fixture fallback environments | In `page_header()`, the `except Exception:` block defaulted `synthetic = False`, causing missing-file tests to emit `DATA SOURCE UNVERIFIED` rather than the mandatory `SYNTHETIC DEMO DATA` warning. | [`app/components.py`](file:///Users/anny/Desktop/mutual-fund/app/components.py#L132) | `tests/test_app_shell.py::test_missing_optional_files_render` (6/6 passed) |
| 2 | **Data Ingestion & Resolution** | Scheme name renamings in official AMFI feed (`(erstwhile Bluechip Fund)`) | SEBI mutual fund rationalization rules led AMCs to rename historical flagships (e.g. ICICI Bluechip $\rightarrow$ Large Cap, Kotak Emerging Equity $\rightarrow$ Mid Cap, Mirae Asset Emerging Bluechip $\rightarrow$ Large & Midcap). Exact-match lookups failed to match official AMFI lines. | [`scripts/validate_ten_schemes.py`](file:///Users/anny/Desktop/mutual-fund/scripts/validate_ten_schemes.py) | Dynamic alias and ISIN resolution verified against 14,441 live AMFI schemes. |
| 3 | **Historical NAV Sufficiency** | 9 of 10 schemes lacked 3-year continuous daily history for ranking | Only Parag Parikh Flexi Cap (`122639`) possessed a cached 3,300-day continuous NAV history. The remaining 9 schemes only had a 5-day sample from Jan 2024 and 1 latest snapshot day. | [`scripts/validate_ten_schemes.py`](file:///Users/anny/Desktop/mutual-fund/scripts/validate_ten_schemes.py), [`src/fundflow/ranking.py`](file:///Users/anny/Desktop/mutual-fund/src/fundflow/ranking.py) | Ranking gate correctly rejected all 9 schemes with explicit auditable reason `Insufficient history (6 < 750 trading days)`. No fabricated metrics were created. |
| 4 | **Visual QA & Screenshots** | Incomplete multi-device screenshot evidence | Prior screenshot script only captured desktop views for 4 pages and tablet/mobile for 2 pages. | [`scripts/capture_live_validation_screenshots.py`](file:///Users/anny/Desktop/mutual-fund/scripts/capture_live_validation_screenshots.py) | 18 full-resolution screenshots generated across 6 pages $\times$ 3 viewports in `reports/live_validation/screenshots/`. |
| 5 | **Automated UI Audit** | Lack of machine-verifiable element inspection | Screenshots alone do not prove absence of silent runtime exceptions or evaluate AppTest warning strings. | [`scripts/inspect_rendered_pages.py`](file:///Users/anny/Desktop/mutual-fund/scripts/inspect_rendered_pages.py) | Produced [`reports/live_validation/ui_audit.md`](file:///Users/anny/Desktop/mutual-fund/reports/live_validation/ui_audit.md), confirming 0 uncaught exceptions across all 6 pages. |

---

## 2. Before-and-After Test Results

### Before Remediation
* `pytest tests/test_app_shell.py`: 6 Failed (`test_missing_optional_files_render` across Home, Forecast Lab, Sentiment Monitor, Fund Research, Stress Lab, Evidence & Limits), 11 Passed.
* Total Passing: 338 / 344 tests.

### After Remediation
* `pytest tests/test_app_shell.py`: 17 / 17 Passed.
* Total Passing: **346 / 346 Passed** in 11.17s.
* `make check` passed with zero errors or warnings.

---

## 3. Financial & Methodological Invariants Preserved

1. **Category vs Scheme Isolation:** NAV ranking metrics are strictly isolated from category flow models (`test_ranking_import_isolation` verified).
2. **Honest Data Provenance:** No synthetic observations were coerced into live labels; `N/A` is rendered for withheld metrics.
3. **No Unlicensed Scraping:** Sources marked `restricted` or `disabled` in `config/sources.yaml` were not bypassed.
