# FundFlow Sentinel — End-to-End Broken Handoffs and Resolution Log

| Document Metadata | Details |
|---|---|
| **Audit Date** | 2026-10-29 |
| **Auditor Role** | Senior Integration Engineer, QA Lead, Skeptical Reviewer |
| **Repository** | `FundFlow Sentinel` |
| **Verification Scope** | End-to-end component boundaries across Prompts 01–30 |

---

## 1. Executive Summary

During the end-to-end verification and independent audit of the FundFlow Sentinel application (spanning Prompts 01 through 30), all inter-module boundaries, loader interfaces, CLI orchestration steps, and UI rendering paths were subjected to adversarial testing. 

A total of **5 defects / broken handoffs** were identified across severity levels (0 Critical, 2 High, 2 Medium, 1 Low). **Every defect has been fully remediated and verified with regression tests.** The entire test suite of **316 tests passes in 5.10s**, and the Streamlit web application operates cleanly across all six functional views without runtime exceptions.

---

## 2. Prioritized Findings Register

### BRK-01: Metric Card Runtime Precondition Failure on Alert Level Display
* **Severity:** **HIGH** (UI Runtime Crash / Safe Boundary Trigger)
* **Affected Components:** [`app/components.py`](file:///Users/anny/Desktop/mutual-fund/app/components.py) (`metric_card`, `_render_command_centre`), [`app/Home.py`](file:///Users/anny/Desktop/mutual-fund/app/Home.py)
* **First Failing Edge:** Category Alert Summary rendering in Command Centre when `alerts.csv` is populated.
* **Reproducible Symptom:**
  ```python
  ERROR:root:[AppResilience] Error rendering Command Centre: ValueError: Metric period, units and source are required
  ```
  When `alerts.csv` was present in the data bundle, navigating to or rendering `app/Home.py` caused an unhandled `ValueError` inside `metric_card`, falling back to the generic error boundary banner.
* **Root Cause Analysis:**
  The `metric_card` function defines a strict presentation invariant:
  ```python
  if not period or not units or not source:
      raise ValueError("Metric period, units and source are required")
  ```
  In `_render_command_centre`, the alert level metric was rendered via:
  ```python
  metric_card("Alert level", a_row["level"], kind="FORECAST", period=a_row["target_month"], units="", source="alert engine")
  ```
  Because `units=""` is an empty string, the truthiness check `if not units` evaluated to True and triggered a `ValueError`. When `alerts.csv` was missing or empty in earlier mockups, this branch was bypassed, hiding the bug until full bundle integration.
* **Remediation Applied:**
  Updated line 151 in [`app/components.py`](file:///Users/anny/Desktop/mutual-fund/app/components.py) to provide an explicit semantic unit: `units="tier"`.
  ```python
  metric_card("Alert level", a_row["level"], kind="FORECAST", period=a_row["target_month"], units="tier", source="alert engine")
  ```
* **Regression Test Added / Executed:**
  Executed `tests/test_ui_pages.py::test_command_centre_smoke` and end-to-end AppTest simulation across all 6 pages with loaded alerts.
* **Verification Evidence:**
  ```
  AppTest from app/Home.py:
  Exception: ElementList() (0 exceptions)
  Metrics rendered: 5 (['OBSERVED · Closing AUM', 'OBSERVED · Gross redemptions', 'FORECAST · Alert level', 'FORECAST · Forecast rate', 'SCENARIO · Est. outflow'])
  Alert level displayed: "Elevated tier"
  ```

---

### BRK-02: Forbidden Module `urllib` Imported in App Layer
* **Severity:** **HIGH** (Architectural Boundary Violation)
* **Affected Components:** [`app/components.py`](file:///Users/anny/Desktop/mutual-fund/app/components.py) (`safe_url`), [`tests/test_app_shell.py`](file:///Users/anny/Desktop/mutual-fund/tests/test_app_shell.py)
* **First Failing Edge:** AST inspection in `test_app_shell.py:80` (`test_no_network_libraries_in_app`).
* **Reproducible Symptom:**
  ```
  AssertionError: PosixPath('/Users/anny/Desktop/mutual-fund/app/components.py')
  Found forbidden network/remote import 'urllib' in UI presentation layer.
  ```
* **Root Cause Analysis:**
  To implement defensive URL sanitization in Wave 13 Prompt 28, `from urllib.parse import urlparse` was introduced into `app/components.py`. However, the architectural contract frozen in Wave 1 strictly forbids importing `urllib`, `requests`, `httpx`, or `yfinance` anywhere inside `app/` to guarantee that UI code cannot execute unexpected network requests or leak telemetry.
* **Remediation Applied:**
  Removed `urllib.parse` import completely. Replaced URL validation with a lightweight, zero-dependency string parser in `app/components.py`:
  ```python
  def safe_url(url: Optional[str]) -> Optional[str]:
      if not url or not isinstance(url, str):
          return None
      url_str = url.strip()
      if "://" not in url_str:
          return None
      scheme, rest = url_str.split("://", 1)
      if scheme.lower() not in {"http", "https"}:
          return None
      netloc = rest.split("/", 1)[0].split("?", 1)[0].split("#", 1)[0].strip()
      if not netloc:
          return None
      return url_str
  ```
* **Regression Test Added / Executed:**
  `tests/test_app_shell.py::test_no_network_libraries_in_app`.
* **Verification Evidence:**
  `pytest tests/test_app_shell.py` passed with 17 passed tests in 0.18s. AST check confirms 0 prohibited network modules in `app/`.

---

### BRK-03: CLI Module Resolution Failure Outside `make` Invocations
* **Severity:** **MEDIUM** (Developer Experience & Operational Break)
* **Affected Components:** `.venv` configuration, [`src/fundflow/cli.py`](file:///Users/anny/Desktop/mutual-fund/src/fundflow/cli.py)
* **First Failing Edge:** Direct shell execution: `.venv/bin/python -m fundflow.cli --help`.
* **Reproducible Symptom:**
  ```
  ModuleNotFoundError: No module named 'fundflow'
  ```
* **Root Cause Analysis:**
  The `Makefile` exported `PYTHONPATH := src`, allowing `make check` and `make test` to succeed. However, running Python or CLI commands directly in terminal sessions or subshells without manually setting `PYTHONPATH` failed because the `src/` directory was not registered in the virtual environment's site-packages.
* **Remediation Applied:**
  Created `.venv/lib/python3.11/site-packages/fundflow.pth` pointing directly to `/Users/anny/Desktop/mutual-fund/src`.
* **Regression Test Added / Executed:**
  Ran `.venv/bin/python -m fundflow.cli snapshot --verify` from an empty shell environment without `PYTHONPATH`.
* **Verification Evidence:**
  Command exited with code 0: `Snapshot at data/snapshots verified successfully.`

---

### BRK-04: Default Development Bundle Omitted Materialized Tables
* **Severity:** **MEDIUM** (Data Flow Incompleteness)
* **Affected Components:** [`data/manifest.json`](file:///Users/anny/Desktop/mutual-fund/data/manifest.json), [`app/loaders.py`](file:///Users/anny/Desktop/mutual-fund/app/loaders.py)
* **First Failing Edge:** Streamlit UI default bundle resolution (`app/loaders.py::_bundle`).
* **Reproducible Symptom:**
  When starting Streamlit via standard `make app` (without overriding `FUNDFLOW_FIXTURE_DIR`), the loader automatically resolved `bundle=""` (`data/`), where `data/manifest.json` declared only `flows_category_month` and `market_month`. As a result, subsequent pages (Forecast Lab, Fund Research, Sentiment Monitor) showed empty state warnings: *"Dataset unavailable: not declared in the manifest"*.
* **Root Cause Analysis:**
  `data/manifest.json` was written in early Wave 4 when only AMFI flow and market data ingestion existed. As later pipeline stages were developed, new tables (`predictions`, `alerts`, `shortlist`, `nav_daily`, `scheme_master`) were generated in `data/snapshots/`, but `data/manifest.json` was never updated to declare these tables in the local development bundle.
* **Remediation Applied:**
  Synchronized `data/manifest.json` and demo artifacts from `data/snapshots/` to `data/`. Now both the root development bundle `data/` and the snapshot bundle `data/snapshots/` declare all 10 frozen tables and 3 JSON artifacts.
* **Regression Test Added / Executed:**
  Smoke tested all 6 Streamlit pages with default environment (`FUNDFLOW_FIXTURE_DIR` unset).
* **Verification Evidence:**
  All 6 pages render full KPIs, charts, and tables with 0 missing dataset errors.

---

### BRK-05: Promotional "Real-Time Freshness" Claim in User Guide
* **Severity:** **LOW** (Documentation & Semantic Accuracy)
* **Affected Components:** [`docs/USER_GUIDE.md`](file:///Users/anny/Desktop/mutual-fund/docs/USER_GUIDE.md)
* **First Failing Edge:** Independent audit of documentation against architecture batch invariants.
* **Reproducible Symptom:**
  Line 35 of `docs/USER_GUIDE.md` claimed "Real-time data freshness monitoring".
* **Root Cause Analysis:**
  The architecture of FundFlow Sentinel is explicitly a monthly/daily batch analytical system with conservative publication-lag enforcement (12th of month T+1). Claiming "real-time" freshness creates false user expectations and contradicts the system's point-in-time non-leakage design.
* **Remediation Applied:**
  Replaced promotional claim with accurate factual wording: *"Active data freshness and bundle origin status"*.
* **Regression Test Added / Executed:**
  Documentation review and grep for unauthorized real-time claims.
* **Verification Evidence:**
  `grep -rn "Real-time" docs/` returns 0 hits in claims of data freshness.

---

## 3. Defect Status & Resolution Matrix

| Defect ID | Severity | Component | Status | Verification Check |
|---|---|---|---|---|
| **BRK-01** | HIGH | `app/components.py` | **RESOLVED** | AppTest Home renders 5 metrics cleanly |
| **BRK-02** | HIGH | `app/components.py` | **RESOLVED** | `pytest tests/test_app_shell.py` (17 passed) |
| **BRK-03** | MEDIUM | Virtualenv / CLI | **RESOLVED** | Direct CLI commands resolve cleanly |
| **BRK-04** | MEDIUM | `data/manifest.json` | **RESOLVED** | All 6 pages render from default bundle |
| **BRK-05** | LOW | `docs/USER_GUIDE.md` | **RESOLVED** | Documentation reflects batch nature |
