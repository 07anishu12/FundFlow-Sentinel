# FundFlow Sentinel — Visual QA & Interface Inspection Report

## Overview
Visual quality assurance was conducted across all six application pages using automated Google Chrome headless screenshot capture and Streamlit AppTest programmatic verification. The inspection validates layout stability, responsive reflow, white-theme design tokens, financial data formatting, and interaction behaviors.

---

## 1. Viewports & Test Environments

| Viewport | Dimensions | Target Platform | Test Status |
|---|---|---|---|
| **Desktop** | `1440 × 1100` | Standard workstation / institutional monitor | **Pass** (No overflow, max-width 1440px enforced) |
| **Tablet** | `768 × 1024` | iPad / tablet portrait | **Pass** (KPI cards wrap into 2 columns, charts scale) |
| **Mobile** | `390 × 844` | iPhone 14/15 mobile screen | **Pass** (Stacked single-column layout, touch hit areas >= 42px) |

---

## 2. Page-by-Page Visual Inspection

### 1. Command Centre (`app/Home.py`)
* **Header & Status Panel**: Clean `#FFFFFF` elevated card with `#E4E7EC` border. Displays data mode (`SYNTHETIC DEMO` / `OFFLINE DEMO` / `LIVE`), observation month, forecast as-of date, target period, and working "🔄 Refresh Data" button.
* **Global Selectors**: 4-column aligned filter row on desktop (Data Source, Category Universe, Observation Period, Refresh action). Reflows to 2 columns on tablet and stacked on mobile.
* **6 Executive Metric Cards**:
  - `OBSERVED · Closing AUM`: Cleanly formatted in `₹ crore` (e.g. `₹254,594.79 crore`), tabular numerals.
  - `OBSERVED · Gross redemptions`: Formatted in `₹ crore`.
  - `FORECAST · Forecast redemption rate`: Percentage with 2 decimals.
  - `FORECAST · Est. outflow`: Estimated outflow in `₹ crore`.
  - `FORECAST · Realized outflow gap`: Signed error ($Actual - Forecast$) in `₹ crore` with absolute gap and percentage error captions. Unobserved future targets honestly report `N/A`.
  - `FORECAST · Alert level`: Semantic pill badge (`Normal` in emerald, `Elevated` in amber, `Critical` in red).
* **Category Dynamics Charts**: Two high-contrast Altair area charts (`#15803D` for redemptions, `#175CD3` for AUM) with light gridlines (`#F2F4F7`) and dark-slate hover tooltips.
* **Category Overview Table**: Sortable, formatted columns with no horizontal scrollbar at 1440px desktop.

### 2. Forecast Lab (`app/pages/1_Forecast_Lab.py`)
* **User-Defined Forecast Configuration**:
  - Dropdowns for Dataset, Forecast Target, Category/Scheme, Horizon, Models (Persistence, Seasonal Naive, Ridge), and Evaluation Method.
  - "Run Forecast Comparison" primary action button (`#15803D`).
* **Output Metric Strip**: Separate cards for each model's point forecast.
* **Model Comparison Table**: Out-of-sample MAE, RMSE, Baseline Comparison, and OOS counts cleanly tabulated.
* **Empirical Uncertainty Bands**: Governance policy notice displayed prominently (`INSUFFICIENT_HISTORY` transparent disclosure).

### 3. Sentiment Monitor (`app/pages/2_Sentiment_Monitor.py`)
* **Headline Intelligence**: White cards with score pills (`SCORE: +0.45` in green, `SCORE: -0.32` in red), publication timestamps, and safe outbound links.
* **Source Distinction**: Clear callout distinguishing immediate RSS media tone from broad GDELT macro tone.

### 4. Fund Research (`app/pages/3_Fund_Research.py`)
* **Regulatory Banner**: Prominent disclosure highlighting `Survivorship Bias` in active AMFI scheme registries.
* **Fund Shortlist Table**: Clean 5-factor percentile ranking columns (`p_return`, `p_consistency`, `p_drawdown`, `p_risk_adj`, `eligible`).

### 5. Stress Lab (`app/pages/4_Stress_Lab.py`)
* **Scenario Sensitivity Chart**: Clean `#15803D` bar chart comparing 7 stress scenarios against reference category AUM.
* **Assumptions Table**: Full description of multipliers and capped outflows (strict 100% ceiling).
* **Tail Risk Warning**: Discloses diagnostic state under `INSUFFICIENT_HISTORY`.

### 6. Evidence & Limitations (`app/pages/5_Evidence_and_Limits.py`)
* **Redistribution Policy**: Amber banner disclosing strict non-redistribution boundaries for third-party public data.
* **Data Quality Checks**: Table showing all structural and mathematical contract tests.

---

## 3. Screenshot Evidence Index

The following headless browser captures were generated and verified:

* `reports/screenshots/home_desktop.png` (Desktop 1440px layout)
* `reports/screenshots/home_rendered.png` (Fully loaded web-socket rendered dashboard)
* `reports/screenshots/command_centre_desktop.png`
* `reports/screenshots/command_centre_tablet.png`
* `reports/screenshots/command_centre_mobile.png`
* `reports/screenshots/forecast_lab_desktop.png`
* `reports/screenshots/forecast_lab_tablet.png`
* `reports/screenshots/forecast_lab_mobile.png`
* `reports/screenshots/sentiment_monitor_desktop.png`
* `reports/screenshots/fund_research_desktop.png`
* `reports/screenshots/stress_lab_desktop.png`
* `reports/screenshots/evidence_limits_desktop.png`
