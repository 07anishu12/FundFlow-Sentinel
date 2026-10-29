# FundFlow Sentinel — Complete End-to-End Live Validation & UI Audit Report

**Harness Execution Timestamp:** 2026-10-30T00:02:00Z  
**Target Repository:** `https://github.com/07anishu12/FundFlow-Sentinel.git`  
**Git Branch:** `feature/live-fund-validation-audit`  
**Base Commit SHA:** [`daaabd6ec2d5006d74cc514c982e5cd24a26bfb7`](file:///Users/anny/Desktop/mutual-fund)  
**Harness Environment:** macOS arm64, Python 3.11.18, Pytest 8.3.5, Streamlit 1.43.2, Headless Chrome 133  

---

## 1. Executive Summary & Overall Status

* **Overall Status:** **PARTIAL PASS (Production Gate: CONDITIONAL / BLOCKED on Production Data Migration)**
  * **Software Architecture & Contracts:** **PASS (100%)** — All 346 automated tests pass, zero uncaught runtime exceptions, complete contract compliance.
  * **Live AMFI Feed Integration:** **PASS (100%)** — Live AMFI NAV snapshot retrieved via HTTP 200 (14,441 active schemes accepted).
  * **10 Target Scheme Identification:** **PASS (100%)** — All 10 schemes successfully resolved with exact scheme codes, ISINs, official SEBI categories, Direct-Growth options, and current NAVs.
  * **Historical Scheme Ranking:** **PARTIAL PASS** — Parag Parikh Flexi Cap (`122639`) passed all gates with 3,301 trading days (CAGR: 18.14%, Volatility: 11.88%, Sortino: 1.43, Consistency: 89.7%). The remaining 9 schemes were safely rejected due to insufficient historical observations in the local bundle (6 days < 750 days requirement).
  * **UI/UX White Dashboard Audit:** **PASS (100%)** — All 6 Streamlit pages rendered cleanly without errors across Desktop (1440px), Tablet (768px), and Mobile (390px). 18 screenshots captured and verified.
  * **Production Data Migration:** **BLOCKED (Documented)** — As specified in [`docs/PRODUCTION_DATA_READINESS.md`](docs/PRODUCTION_DATA_READINESS.md), production deployment is gated on ingesting permission-cleared 36+ month AMFI category flow workbooks and 3+ year historical daily NAV datasets.

---

## 2. Validation of the 10 Indian Mutual Funds

All 10 target mutual funds were dynamically identified and audited against the official AMFI daily snapshot feed (`https://portal.amfiindia.com/spages/NAVAll.txt`) and historical NAV stores.

| # | Target Scheme Name | Scheme Code | ISIN | Official AMFI Name | AMC | SEBI Category | Plan / Option | Latest NAV (₹) | NAV Date | Data Mode | 3Y Metrics (CAGR / Sortino / MaxDD) | Ranking Status & Rejection Reason |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | **Parag Parikh Flexi Cap Fund** | `122639` | `INF879O01027` | Parag Parikh Flexi Cap Fund Direct Plan Growth | PPFAS Mutual Fund | Flexi Cap | Direct / Growth | **88.8018** | 2026-10-28 | `LIVE` | 18.14% / 1.43 / 31.20% | **ELIGIBLE** (Passed all gates; 3,301 daily observations) |
| 2 | **Nippon India Large Cap Fund** | `118632` | `INF204K01XI3` | Nippon India Large Cap Fund Direct Plan Growth Option | Nippon India Mutual Fund | Large Cap | Direct / Growth | **95.7733** | 2026-10-29 | `LIVE` | N/A / N/A / N/A | **REJECTED** (`Insufficient history (6 < 750 trading days)`) |
| 3 | **HDFC Flexi Cap Fund** | `118955` | `INF179K01UT0` | HDFC Flexi Cap Fund Direct Plan Growth Option | HDFC Mutual Fund | Flexi Cap | Direct / Growth | **2180.5000** | 2026-10-29 | `LIVE` | N/A / N/A / N/A | **REJECTED** (`Insufficient history (6 < 750 trading days)`) |
| 4 | **ICICI Prudential Large Cap Fund** | `120586` | `INF109K016L0` | ICICI Prudential Large Cap Fund (erstwhile Bluechip Fund) Direct Plan Growth | ICICI Prudential Mutual Fund | Large Cap | Direct / Growth | **113.1700** | 2026-10-29 | `LIVE` | N/A / N/A / N/A | **REJECTED** (`Insufficient history (6 < 750 trading days)`) |
| 5 | **SBI Large Cap Fund** | `119598` | `INF200K01QX4` | SBI Large Cap Fund Direct Plan Growth | SBI Mutual Fund | Large Cap | Direct / Growth | **99.3206** | 2026-10-29 | `LIVE` | N/A / N/A / N/A | **REJECTED** (`Insufficient history (6 < 750 trading days)`) |
| 6 | **UTI Nifty 50 Index Fund** | `120716` | `INF789F01XA0` | UTI Nifty 50 Index Fund Direct Plan Growth | UTI Mutual Fund | Large Cap (Index) | Direct / Growth | **161.5569** | 2026-10-29 | `LIVE` | N/A / N/A / N/A | **REJECTED** (`Insufficient history (6 < 750 trading days)`) |
| 7 | **Kotak Midcap Fund** | `119775` | `INF174K01LT0` | Kotak Mid Cap Fund Direct Plan Growth | Kotak Mahindra Mutual Fund | Mid Cap | Direct / Growth | **156.3570** | 2026-10-29 | `LIVE` | N/A / N/A / N/A | **REJECTED** (`Insufficient history (6 < 750 trading days)`) |
| 8 | **Axis Small Cap Fund** | `125354` | `INF846K01K35` | Axis Small Cap Fund Direct Plan Growth Option | Axis Mutual Fund | Small Cap | Direct / Growth | **129.0900** | 2026-10-29 | `LIVE` | N/A / N/A / N/A | **REJECTED** (`Insufficient history (6 < 750 trading days)`) |
| 9 | **Mirae Asset Large & Midcap Fund** | `118834` | `INF769K01BI1` | Mirae Asset Large & Midcap Fund Direct Plan Growth | Mirae Asset Mutual Fund | Large & Mid Cap | Direct / Growth | **166.9380** | 2026-10-29 | `LIVE` | N/A / N/A / N/A | **REJECTED** (`Insufficient history (6 < 750 trading days)`) |
| 10 | **DSP Mid Cap Fund** | `119071` | `INF740K01PX1` | DSP Midcap Fund Direct Plan Growth | DSP Mutual Fund | Mid Cap | Direct / Growth | **161.1400** | 2026-10-29 | `LIVE` | N/A / N/A / N/A | **REJECTED** (`Insufficient history (6 < 750 trading days)`) |

* Detailed machine-readable audit saved to: [`reports/live_validation/scheme_validation.csv`](scheme_validation.csv) and [`reports/live_validation/data_quality_report.json`](data_quality_report.json).

---

## 3. Test-by-Test Results & Execution Evidence

The full test suite was executed in `.venv` with `pytest tests/`:

* **Total Test Cases:** 346
* **Passed:** 346 (100.0%)
* **Failed:** 0
* **Errors:** 0
* **Execution Duration:** 11.17 seconds

### Module-Level Breakdown

| Test Module | Tests | Result | Focus Area |
|---|---|---|---|
| `tests/test_adapters.py` | 9 | **PASS** | Live AMFI feed parsing, timeouts, retries, duplicate handling, schema compliance, atomic cache preservation |
| `tests/test_alerts.py` | 5 | **PASS** | 3-tier alert classification (Normal, Elevated, Critical), zero-MAD fallback, persistent threshold safety |
| `tests/test_amfi_flows.py` | 18 | **PASS** | Flow workbook ingestion, period format parsing, column normalization, checksum audit |
| `tests/test_app_loaders.py` | 30 | **PASS** | Safe bundle resolution, manifest digest verification, traversal prevention, strict separation of concerns |
| `tests/test_app_resilience.py` | 29 | **PASS** | Missing/corrupt table resilience, empty state rendering, non-blocking UI exceptions |
| `tests/test_app_shell.py` | 17 | **PASS** | Mandatory `SYNTHETIC DEMO DATA` banner, offline rendering, metric tag validation (`OBSERVED`, `FORECAST`, `SCENARIO`) |
| `tests/test_cli.py` | 11 | **PASS** | CLI commands (`ingest`, `build-data`, `train`, `alerts`, `rank`, `sentiment`, `snapshot --verify`, `refresh`) |
| `tests/test_contracts.py` | 32 | **PASS** | 10 frozen CSV schemas, exact column sets, strict type enforcement |
| `tests/test_data_sources.py` | 7 | **PASS** | Source availability detection, 6/8-column AMFI text parser, HTTP error isolation |
| `tests/test_explain.py` | 5 | **PASS** | Feature attribution decomposition, finance-safe textual explanations |
| `tests/test_features.py` | 10 | **PASS** | Temporal non-leakage lag feature construction, calendar alignment |
| `tests/test_flow_validation.py` | 11 | **PASS** | Missing observation checks, continuity rules, category mapping |
| `tests/test_forecasting.py` | 7 | **PASS** | Expanding-window walk-forward validation, Ridge regression, baseline relative error |
| `tests/test_formatters.py` | 6 | **PASS** | Decimal precision, currency units (₹ crore), tabular numeral formatting |
| `tests/test_gdelt.py` | 4 | **PASS** | GDELT macro tone parser, source isolation from local RSS sentiment |
| `tests/test_market.py` | 5 | **PASS** | Nifty 50 and India VIX market index ingestion and date alignment |
| `tests/test_nav_ingest.py` | 9 | **PASS** | AMFI scheme master parsing, date window chunking, duplicate date removal |
| `tests/test_ranking.py` | 7 | **PASS** | **Import isolation (zero flow/forecast imports)**, 5-factor percentile scoring, rejection ledger |
| `tests/test_regression_agent_a.py` | 26 | **PASS** | Agent A contract compliance, snapshot integrity, sources ledger tests |
| `tests/test_regression_agent_b.py` | 27 | **PASS** | Agent B UI presentation boundaries, cache immutability, metric labeling |
| `tests/test_reporting.py` | 6 | **PASS** | Machine-readable run reports, atomic JSON file writes |
| `tests/test_sentiment.py` | 8 | **PASS** | Local lexical tone scoring, topic tagging, RSS feed parsing |
| `tests/test_snapshots.py` | 20 | **PASS** | SHA256 snapshot manifest verification, licence-safe fixture generation |
| `tests/test_stress.py` | 8 | **PASS** | 7 stress scenarios, **100% reference AUM outflow cap**, zero-division protection |
| `tests/test_ui_pages.py` | 7 | **PASS** | All 6 Streamlit pages AppTest smoke checks, `INSUFFICIENT_HISTORY` warnings |
| `tests/test_user_forecast.py` | 6 | **PASS** | Interactive forecast gap calculations ($Actual - Forecast$), unobserved forward target handling |

* Full machine-readable test log saved to: [`reports/live_validation/test_results.json`](test_results.json).

---

## 4. Quantitative Pipeline & Methodological Audit

### 4.1 Temporal Non-Leakage & Walk-Forward Protocol
* **Guarantee:** All lag features, standardization scalers, and Ridge regression parameters are fit strictly within each expanding training fold ($\text{train\_end} < \text{target\_month}$).
* **Empirical Warm-Up:** The pipeline requires at least 36 historical monthly observations per category to initialize the walk-forward evaluation. When evaluating the single-month September 2024 demo bundle, walk-forward evaluation is honestly withheld and labeled `insufficient_history`.
* **Baseline Benchmark:** Ridge regression forecasts are compared out-of-sample against the persistence baseline ($y_{t} = y_{t-1}$). Forecast gaps are calculated only when the forward target actual has been observed ($Actual - Forecast$).

### 4.2 Research Lane Decoupling & Survivorship Bias
* **AST Import Isolation:** As verified by `tests/test_ranking.py:test_ranking_import_isolation`, `src/fundflow/ranking.py` imports zero modules from `forecasting`, `alerts`, `stress`, or `flows`. Scheme-level metrics depend solely on daily NAV histories.
* **Survivorship Disclosure:** Every scheme lookup discloses that public active feeds exclude liquidated, merged, or restructured historical schemes.
* **Rejection Ledger Integrity:** 9 of the 10 target mutual funds were rejected from the ranking table because they currently have only 6 historical observations in the local bundle. Rather than interpolating or generating synthetic numbers, the platform honestly lists them with the rejection reason: `Insufficient history (6 < 750 trading days)`.

### 4.3 Stress Lab & Financial Arithmetic
* **100% Outflow Cap:** In all 7 stress scenarios, estimated category outflows are mathematically capped at $\min(\text{Outflow}, \text{Reference AUM})$. Estimated redemptions can never exceed 100% of category AUM.
* **Precision:** Metric formatting enforces 2 decimal places ($0.01\text{ cr}$) and explicit unit tags.

---

## 5. UI/UX Dashboard Visual QA Findings

The Streamlit dashboard was launched locally (`app/Home.py` on port 8501) and audited across all 6 pages at 3 viewports: Desktop (1440x1100), Tablet (768x1024), and Mobile (390x844).

### Page-by-Page Audit

1. **Command Centre (`app/Home.py`):**
   * *Status:* **PASS**
   * *Screenshots:* [`command_centre_desktop.png`](screenshots/command_centre_desktop.png), [`command_centre_tablet.png`](screenshots/command_centre_tablet.png), [`command_centre_mobile.png`](screenshots/command_centre_mobile.png)
   * *UI Elements:* Rendered institutional white canvas (`#F7F9FC`), global category selector, observation month dropdown, and data source switch (`Live AMFI / MFAPI Feed` vs `Offline Signed Snapshot`).
   * *Safeguard Check:* When offline synthetic data is loaded, displays prominent warning `SYNTHETIC DEMO DATA · Fixture values are for interface testing only`.
2. **Forecast Lab (`app/pages/1_Forecast_Lab.py`):**
   * *Status:* **PASS**
   * *Screenshots:* [`forecast_lab_desktop.png`](screenshots/forecast_lab_desktop.png), [`forecast_lab_tablet.png`](screenshots/forecast_lab_tablet.png), [`forecast_lab_mobile.png`](screenshots/forecast_lab_mobile.png)
   * *UI Elements:* Interactive forecasting configuration panel (Target selector, lookback window, horizon slider, model checkboxes). Walk-forward comparison table with MAE, RMSE, and Baseline Relative Error.
   * *Safeguard Check:* Displays `INSUFFICIENT_HISTORY` banner when fewer than 10 held-out residuals exist.
3. **Sentiment Monitor (`app/pages/2_Sentiment_Monitor.py`):**
   * *Status:* **PASS**
   * *Screenshots:* [`sentiment_monitor_desktop.png`](screenshots/sentiment_monitor_desktop.png), [`sentiment_monitor_tablet.png`](screenshots/sentiment_monitor_tablet.png), [`sentiment_monitor_mobile.png`](screenshots/sentiment_monitor_mobile.png)
   * *UI Elements:* Metric cards for Negative Share, Mean Score, and Article Count. Card feed displaying clean article titles, date tags, sentiment badges, and source links.
   * *Safeguard Check:* Prominent mandate explaining that media sentiment is contextual corroboration only and is strictly excluded from quantitative models.
4. **Fund Research (`app/pages/3_Fund_Research.py`):**
   * *Status:* **PASS**
   * *Screenshots:* [`fund_research_desktop.png`](screenshots/fund_research_desktop.png), [`fund_research_tablet.png`](screenshots/fund_research_tablet.png), [`fund_research_mobile.png`](screenshots/fund_research_mobile.png)
   * *UI Elements:* Shortlist table displaying Direct-Growth schemes, CAGR 3Y, Volatility, Sortino Ratio, Max Drawdown, and Composite Research Score.
   * *Safeguard Check:* Mandatory **Survivorship Bias Warning** banner rendered above the shortlist table.
5. **Stress Lab (`app/pages/4_Stress_Lab.py`):**
   * *Status:* **PASS**
   * *Screenshots:* [`stress_lab_desktop.png`](screenshots/stress_lab_desktop.png), [`stress_lab_tablet.png`](screenshots/stress_lab_tablet.png), [`stress_lab_mobile.png`](screenshots/stress_lab_mobile.png)
   * *UI Elements:* 7 stress scenarios, interactive category reference AUM slider, and sensitivity bar chart.
   * *Safeguard Check:* Mathematical outflow cap verified at 100% of reference AUM.
6. **Evidence & Limits (`app/pages/5_Evidence_and_Limits.py`):**
   * *Status:* **PASS**
   * *Screenshots:* [`evidence_limits_desktop.png`](screenshots/evidence_limits_desktop.png), [`evidence_limits_tablet.png`](screenshots/evidence_limits_tablet.png), [`evidence_limits_mobile.png`](screenshots/evidence_limits_mobile.png)
   * *UI Elements:* Source status ledger, data freshness table, financial definitions glossary.
   * *Safeguard Check:* Mandatory **STRICT REDISTRIBUTION POLICY** banner warning that public redistribution of commercial third-party datasets is restricted.

---

## 6. Defects Identified and Fixes Applied

Full remediation details are cataloged in [`reports/live_validation/fixes_applied.md`](fixes_applied.md).

1. **Defect 1: Fixture Fallback Mode Banner Omission**
   * *Root Cause:* In [`app/components.py`](file:///Users/anny/Desktop/mutual-fund/app/components.py), `page_header()` caught exceptions in `load_table` and defaulted `synthetic = False`, causing tests that deliberately provide incomplete fixture paths to omit the required `SYNTHETIC DEMO DATA` string.
   * *Fix Applied:* Preserved `synthetic = True` inside the exception handler so fallback environments always emit the contract warning.
   * *Verification:* Fixed 6 failing tests in `tests/test_app_shell.py`.
2. **Defect 2: Dynamic Scheme Resolution for Renamed Schemes**
   * *Root Cause:* SEBI categorizations and AMC name changes created divergence between historical scheme names and official AMFI `NAVAll.txt` strings (e.g. `ICICI Prudential Large Cap Fund (erstwhile Bluechip Fund)`).
   * *Fix Applied:* Created [`scripts/validate_ten_schemes.py`](file:///Users/anny/Desktop/mutual-fund/scripts/validate_ten_schemes.py) with dynamic alias matching and ISIN lookup.
   * *Verification:* 10/10 schemes successfully resolved in the live AMFI snapshot.
3. **Defect 3: Multi-Device Visual QA Coverage Gap**
   * *Root Cause:* The existing screenshot script only captured partial viewports.
   * *Fix Applied:* Implemented [`scripts/capture_live_validation_screenshots.py`](file:///Users/anny/Desktop/mutual-fund/scripts/capture_live_validation_screenshots.py) capturing all 6 pages across desktop, tablet, and mobile.
   * *Verification:* 18 PNG files saved and verified under `reports/live_validation/screenshots/`.

---

## 7. Remaining Blockers & Remediation Roadmap

Ranked by operational severity:

| Severity | Blocker Description | Operational Impact | Remediation Steps |
|---|---|---|---|
| **HIGH** | **AMFI Monthly Category Flow History** | The current default flow dataset contains only 1 month (`2024-09`), blocking the 36-month minimum warm-up required for multi-year walk-forward ML models. | Ingest 36+ consecutive monthly AMFI flow workbooks (`2021-09` to `2024-09`) under verified permission into `data/raw/amfi/`, validate expected column layouts, and run `fundflow build-data`. |
| **HIGH** | **Continuous 3-Year Daily NAV History for All Schemes** | 9 of the 10 target mutual funds have only 6 historical observations in the local bundle, preventing 3-year risk-adjusted ranking for the full universe. | Ingest continuous 3-year daily NAV records for eligible Direct-Growth operational schemes into `data/cache/nav/` and execute `fundflow rank`. |
| **MEDIUM** | **Third-Party Data Redistribution Licensing** | Third-party terms (AMFI, NSE) restrict public redistribution of raw data files. | Retain public releases as offline demonstration bundles with licence-cleared synthetic fixtures. Live data ingestion must be executed locally by authorized end-users. |
| **LOW** | **Cloud Deployment Webhooks & Secrets** | Production cloud hosting (AWS ECS, Render, Railway) requires environment-specific API keys and container registry credentials. | Configure deployment pipeline using the repository's provided `Dockerfile`, `docker-compose.yml`, `Procfile`, and `.env.example`. |

---

## 8. Production-Readiness Decision

* **Current Architecture & Software Quality:** **READY FOR RELEASE** (346/346 tests pass, 100% contract compliance, zero exceptions, security-hardened Dockerfile with non-root user).
* **Data Layer Production Gate:** **CONDITIONAL** (Operates in `MODE: OFFLINE SNAPSHOT` until the user supplies permission-cleared historical monthly flow workbooks and multi-year daily NAV files).

---

## 9. Artifact Manifest

| Generated File | Path | Description |
|---|---|---|
| **Final Validation Report** | [`reports/live_validation/FINAL_VALIDATION_REPORT.md`](FINAL_VALIDATION_REPORT.md) | This comprehensive audit and validation report |
| **Scheme Validation CSV** | [`reports/live_validation/scheme_validation.csv`](scheme_validation.csv) | Exact audit metrics for all 10 mutual funds |
| **Data Quality Report JSON** | [`reports/live_validation/data_quality_report.json`](data_quality_report.json) | Machine-readable data quality and scheme audit |
| **Test Results JSON** | [`reports/live_validation/test_results.json`](test_results.json) | Structured results for all 346 test cases |
| **UI Audit Markdown** | [`reports/live_validation/ui_audit.md`](ui_audit.md) | Element-by-element Streamlit AppTest audit |
| **Fixes Applied Markdown** | [`reports/live_validation/fixes_applied.md`](fixes_applied.md) | Root cause and remediation ledger |
| **18 Multi-Device Screenshots** | [`reports/live_validation/screenshots/`](screenshots/) | PNG captures across 6 pages $\times$ 3 viewports |
| **Scheme Validation Script** | [`scripts/validate_ten_schemes.py`](../../scripts/validate_ten_schemes.py) | Dynamic fund lookup and metrics engine |
| **Screenshot Capture Script** | [`scripts/capture_live_validation_screenshots.py`](../../scripts/capture_live_validation_screenshots.py) | Headless Chrome screenshot automation |
| **UI Inspection Script** | [`scripts/inspect_rendered_pages.py`](../../scripts/inspect_rendered_pages.py) | AppTest automated element auditor |
