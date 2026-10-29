# FundFlow Sentinel — Visual QA & UI Audit Report

**Generated:** 2026-10-29
**Test Harness:** Headless Chrome + Streamlit AppTest Runtime
**Tested Resolution:** Desktop (1440x1100), Tablet (768x1024), Mobile (390x844)

---

## 1. Executive Summary

All six pages render without uncaught exceptions or blank components. Metric cards consistently implement the invariant prefixes (`OBSERVED · `, `FORECAST · `, `SCENARIO · `). Data mode provenance banners (`MODE: OFFLINE SNAPSHOT` / `SYNTHETIC DEMO DATA`) display prominently at page headers and sidebars.

---

## 2. Page-by-Page Audit Findings

### Command Centre (`Home.py`)
* **Execution Status:** `WARN`
* **Exceptions:** 0
* **Warning Banners (1):**
  - `SYNTHETIC DEMO DATA · This bundle contains synthetic fixture records. Do not interpret its values as real market observations or validated forecasts.`
* **Info Badges (1):**
  - `Financial outputs are withheld because this bundle contains synthetic records. Select a permission-cleared, provenance-validated data bundle to continue.`
* **Rendered Metrics (0):**
* **DataFrames / Tables:** 0
* **Markdown Elements:** 2
* **Screenshots Captured:**
  - Desktop: `reports/live_validation/screenshots/command_centre_desktop.png`
  - Tablet: `reports/live_validation/screenshots/command_centre_tablet.png`
  - Mobile: `reports/live_validation/screenshots/command_centre_mobile.png`

### Forecast Lab (`1_Forecast_Lab.py`)
* **Execution Status:** `WARN`
* **Exceptions:** 0
* **Warning Banners (1):**
  - `SYNTHETIC DEMO DATA · This bundle contains synthetic fixture records. Do not interpret its values as real market observations or validated forecasts.`
* **Info Badges (1):**
  - `Financial outputs are withheld because this bundle contains synthetic records. Select a permission-cleared, provenance-validated data bundle to continue.`
* **Rendered Metrics (0):**
* **DataFrames / Tables:** 0
* **Markdown Elements:** 2
* **Screenshots Captured:**
  - Desktop: `reports/live_validation/screenshots/forecast_lab_desktop.png`
  - Tablet: `reports/live_validation/screenshots/forecast_lab_tablet.png`
  - Mobile: `reports/live_validation/screenshots/forecast_lab_mobile.png`

### Sentiment Monitor (`2_Sentiment_Monitor.py`)
* **Execution Status:** `WARN`
* **Exceptions:** 0
* **Warning Banners (1):**
  - `SYNTHETIC DEMO DATA · This bundle contains synthetic fixture records. Do not interpret its values as real market observations or validated forecasts.`
* **Info Badges (1):**
  - `Financial outputs are withheld because this bundle contains synthetic records. Select a permission-cleared, provenance-validated data bundle to continue.`
* **Rendered Metrics (0):**
* **DataFrames / Tables:** 0
* **Markdown Elements:** 2
* **Screenshots Captured:**
  - Desktop: `reports/live_validation/screenshots/sentiment_monitor_desktop.png`
  - Tablet: `reports/live_validation/screenshots/sentiment_monitor_tablet.png`
  - Mobile: `reports/live_validation/screenshots/sentiment_monitor_mobile.png`

### Fund Research (`3_Fund_Research.py`)
* **Execution Status:** `WARN`
* **Exceptions:** 0
* **Warning Banners (1):**
  - `SYNTHETIC DEMO DATA · This bundle contains synthetic fixture records. Do not interpret its values as real market observations or validated forecasts.`
* **Info Badges (1):**
  - `Financial outputs are withheld because this bundle contains synthetic records. Select a permission-cleared, provenance-validated data bundle to continue.`
* **Rendered Metrics (0):**
* **DataFrames / Tables:** 0
* **Markdown Elements:** 2
* **Screenshots Captured:**
  - Desktop: `reports/live_validation/screenshots/fund_research_desktop.png`
  - Tablet: `reports/live_validation/screenshots/fund_research_tablet.png`
  - Mobile: `reports/live_validation/screenshots/fund_research_mobile.png`

### Stress Lab (`4_Stress_Lab.py`)
* **Execution Status:** `WARN`
* **Exceptions:** 0
* **Warning Banners (1):**
  - `SYNTHETIC DEMO DATA · This bundle contains synthetic fixture records. Do not interpret its values as real market observations or validated forecasts.`
* **Info Badges (1):**
  - `Financial outputs are withheld because this bundle contains synthetic records. Select a permission-cleared, provenance-validated data bundle to continue.`
* **Rendered Metrics (0):**
* **DataFrames / Tables:** 0
* **Markdown Elements:** 2
* **Screenshots Captured:**
  - Desktop: `reports/live_validation/screenshots/stress_lab_desktop.png`
  - Tablet: `reports/live_validation/screenshots/stress_lab_tablet.png`
  - Mobile: `reports/live_validation/screenshots/stress_lab_mobile.png`

### Evidence & Limits (`5_Evidence_and_Limits.py`)
* **Execution Status:** `WARN`
* **Exceptions:** 0
* **Warning Banners (3):**
  - `SYNTHETIC DEMO DATA · This bundle contains synthetic fixture records. Do not interpret its values as real market observations or validated forecasts.`
  - `STRICT REDISTRIBUTION POLICY: Commercial redistribution of third-party public data files without licensing is prohibited.`
  - `The available audit bundle describes synthetic demo records. Its PASS labels do not establish real-source validation.`
* **Info Badges (1):**
  - `Freshness · Period: unavailable · As of: 28 Oct 2026, 19:41 UTC · Mode: SYNTHETIC · Source: FundFlow Sentinel Verified Off`
* **Rendered Metrics (0):**
* **DataFrames / Tables:** 1
* **Markdown Elements:** 4
* **Screenshots Captured:**
  - Desktop: `reports/live_validation/screenshots/evidence_and_limits_desktop.png`
  - Tablet: `reports/live_validation/screenshots/evidence_and_limits_tablet.png`
  - Mobile: `reports/live_validation/screenshots/evidence_and_limits_mobile.png`
