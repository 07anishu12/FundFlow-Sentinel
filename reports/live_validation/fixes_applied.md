# FundFlow Sentinel — Audit & Remediation Log (Fixes Applied)

**Branch:** `audit/live-validation-and-ui`  
**Base Commit:** `592e583191e760b730b0eb9a61e5e20b58b26a9b`  
**Audit Timestamp:** 2026-10-30T03:12:00Z  
**Test Suite Result:** 351 / 351 Passed (100.0%)  

---

## 1. Summary of Defects Identified and Resolved

| # | Component / Subsystem | Defect / Finding | Root Cause | File(s) Changed | Verification Evidence |
|---|---|---|---|---|---|
| 1 | **Visual QA & Screenshot Capture** | Chrome headless captured pre-rendered skeleton screens (~8-10 KB) showing "RUNNING..." spinner | Passing `--virtual-time-budget` to Chrome freezes the event loop for asynchronous I/O. As a result, Streamlit's localhost WebSocket connection never completed handshaking before Chrome took the screenshot and exited. | [`scripts/capture_live_validation_screenshots.py`](file:///Users/anny/Desktop/mutual-fund/scripts/capture_live_validation_screenshots.py) | Upgraded to Chrome DevTools Protocol (CDP) via Tornado WebSocket. Controls viewport dimensions (Desktop 1440x1100, Tablet 768x1024, Mobile 390x844), waits for Streamlit DOM completion, and captures 18 high-resolution screenshots (40KB - 122KB each). |
| 2 | **10-Fund Runtime Scheme Resolution** | Historical fund renamings by AMCs required alias mapping to resolve exact scheme codes | SEBI mutual fund categorisation mandates led AMCs to rename flagship schemes (e.g., ICICI Prudential Bluechip $\rightarrow$ Large Cap Fund [erstwhile Bluechip Fund], Kotak Emerging Equity $\rightarrow$ Mid Cap, SBI Bluechip $\rightarrow$ Large Cap, Mirae Asset Emerging Bluechip $\rightarrow$ Large & Midcap). Direct string matches failed. | [`scripts/validate_ten_schemes.py`](file:///Users/anny/Desktop/mutual-fund/scripts/validate_ten_schemes.py) | Verified all 10 funds against 14,441 records in live AMFI NAVAll feed. All 10 resolved to exact Direct Plan - Growth option scheme codes and ISINs. |
| 3 | **Historical NAV Ingestion & Gap Auditing** | Initial test cache contained only 6 days for 9 funds, preventing full 3-year ranking evaluation | Only Parag Parikh Flexi Cap (`122639`) possessed a cached continuous 3,300-day series. The remaining 9 funds had only 6 observations. | [`src/fundflow/ingest/nav.py`](file:///Users/anny/Desktop/mutual-fund/src/fundflow/ingest/nav.py), [`scripts/validate_ten_schemes.py`](file:///Users/anny/Desktop/mutual-fund/scripts/validate_ten_schemes.py) | Ingested full historical daily NAV series (3,181 to 3,411 daily observations per scheme, spanning 2021 to 2026). Verified positive, finite NAVs, monotonic chronological order, zero duplicate dates, and max calendar date gaps $\le 6$ days. |
| 4 | **Test Automation & Reporting** | Need for unified machine-readable JSON artifacts reflecting complete test suite status | Raw pytest CLI text output lacks machine-readable JSON structure required for automated CI verification and audit trails. | [`scripts/convert_junit_to_json.py`](file:///Users/anny/Desktop/mutual-fund/scripts/convert_junit_to_json.py) | Generated `reports/live_validation/test_results.json` mapping all 351 test cases, execution durations, and pass/fail statuses (100% pass rate). |
| 5 | **Programmatic UI Element Inspection** | Need for deterministic UI audit without relying solely on visual inspection | Visual screenshots cannot systematically audit underlying element counts, warning texts, and uncaught exceptions across all pages. | [`scripts/inspect_rendered_pages.py`](file:///Users/anny/Desktop/mutual-fund/scripts/inspect_rendered_pages.py) | Generated `reports/live_validation/ui_audit.md` using Streamlit `AppTest` runtime across all 6 pages. Verified zero exceptions and mandatory disclaimers. |

---

## 2. Before-and-After Test Results

### Before Audit & Remediation
* **Automated Tests:** 351 passing tests (existing baseline on `fix/final-verification-guardrails`).
* **Scheme Historical Validation:** Only 1 of 10 schemes (Parag Parikh Flexi Cap) had full 3Y history; 9 schemes had 6 observations (`Insufficient history`).
* **Screenshots:** Stale/premature headless Chrome screenshots (~8-10 KB) showing unrendered skeleton loaders.

### After Audit & Remediation
* **Automated Tests:** **351 / 351 Passed** (`make check` and `make test`).
* **Scheme Historical Validation:** **10 of 10 schemes validated** across live AMFI snapshot (2026-10-29 NAV date) and complete 3-year daily NAV history (3,181 to 3,411 observations per fund). All 10 schemes evaluated for 3Y CAGR, Volatility, Max Drawdown, Sortino ($R_f=6\%$), 1Y Consistency, and within-category Percentile Research Scores.
* **Screenshots:** 18 fully rendered, high-resolution screenshots generated via CDP across Desktop, Tablet, and Mobile viewports under `reports/live_validation/screenshots/`.
* **Exit Codes:** All test suites, contracts, and snapshot integrity verifications exited with code `0`.

---

## 3. Financial & Methodological Invariants Preserved

1. **Category vs Scheme Boundary:** NAV ranking metrics remain architecturally decoupled from category flow models (`test_ranking_import_isolation` verified). Scheme NAV research never attributes category flows or AUM to individual funds.
2. **Honest Data Provenance:** No synthetic observations were coerced into live labels; `N/A` is rendered for withheld metrics. Mode banners (`MODE: SYNTHETIC FIXTURE` / `MODE: OFFLINE SNAPSHOT` / `MODE: LIVE`) faithfully disclose dataset origin.
3. **No Unlicensed Redistribution:** Sources marked `restricted` or `disabled` in `config/sources.yaml` were not bypassed. Public snapshot bundles remain strictly licence-permitted synthetic demo data with explicit `synthetic:not-a-source` markers.
