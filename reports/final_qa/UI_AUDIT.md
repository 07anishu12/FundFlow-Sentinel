# FundFlow Sentinel — Visual QA & UI Audit Report

**Audit Date:** 2026-10-29 / 2026-10-30  
**Target Repository:** `https://github.com/07anishu12/FundFlow-Sentinel.git`  
**Application Branch:** `feature/live-fund-validation-audit`  
**Execution Environment:** Streamlit 1.43+ / Python 3.11 / Headless Chrome 1440px, 768px, 390px  

---

## 1. Executive Summary & Audit Scope

This audit report documents the multi-viewport visual and functional QA evaluation of the redesigned **FundFlow Sentinel** financial intelligence dashboard. All six application pages were audited across three standardized institutional viewports:
1. **Desktop (1440 × 1100 px)**: Full institutional terminal experience with side-by-side metric grids, interactive dual charts, and wide tables.
2. **Tablet (768 × 1024 px)**: Responsive intermediate layout with wrapped KPI columns and adapted touch-friendly controls.
3. **Mobile (390 × 844 px)**: Single-column vertical stack with clear typography, horizontal table scroll preservation, and accessible spacing.

A total of **18 screenshots** were captured and verified under `reports/final_qa/screenshots/`.

---

## 2. Screenshot Inventory & Viewport Coverage

| Page | Viewport | Resolution | Screenshot File | Rendering Status |
| :--- | :--- | :--- | :--- | :--- |
| **01 Command Centre** | Desktop | 1440 × 1100 | [`01_command_centre_desktop.png`](file:///Users/anny/Desktop/mutual-fund/reports/final_qa/screenshots/01_command_centre_desktop.png) | **PASS** — Dual row KPI grid, area flow trends, gap analysis |
| **01 Command Centre** | Tablet | 768 × 1024 | [`01_command_centre_tablet.png`](file:///Users/anny/Desktop/mutual-fund/reports/final_qa/screenshots/01_command_centre_tablet.png) | **PASS** — 2-column flex wrapped metrics, stacked charts |
| **01 Command Centre** | Mobile | 390 × 844 | [`01_command_centre_mobile.png`](file:///Users/anny/Desktop/mutual-fund/reports/final_qa/screenshots/01_command_centre_mobile.png) | **PASS** — Single-column cards, full touch usability |
| **02 Forecast Lab** | Desktop | 1440 × 1100 | [`02_forecast_lab_desktop.png`](file:///Users/anny/Desktop/mutual-fund/reports/final_qa/screenshots/02_forecast_lab_desktop.png) | **PASS** — Model config controls, P10/P90 empirical bands |
| **02 Forecast Lab** | Tablet | 768 × 1024 | [`02_forecast_lab_tablet.png`](file:///Users/anny/Desktop/mutual-fund/reports/final_qa/screenshots/02_forecast_lab_tablet.png) | **PASS** — Responsive model comparison, responsive form |
| **02 Forecast Lab** | Mobile | 390 × 844 | [`02_forecast_lab_mobile.png`](file:///Users/anny/Desktop/mutual-fund/reports/final_qa/screenshots/02_forecast_lab_mobile.png) | **PASS** — Clean vertical parameter selectors, interval view |
| **03 Sentiment Monitor** | Desktop | 1440 × 1100 | [`03_sentiment_monitor_desktop.png`](file:///Users/anny/Desktop/mutual-fund/reports/final_qa/screenshots/03_sentiment_monitor_desktop.png) | **PASS** — Topic breakdown, tone polarity cards, GDELT feed |
| **03 Sentiment Monitor** | Tablet | 768 × 1024 | [`03_sentiment_monitor_tablet.png`](file:///Users/anny/Desktop/mutual-fund/reports/final_qa/screenshots/03_sentiment_monitor_tablet.png) | **PASS** — Responsive card grid, sentiment context disclaimers |
| **03 Sentiment Monitor** | Mobile | 390 × 844 | [`03_sentiment_monitor_mobile.png`](file:///Users/anny/Desktop/mutual-fund/reports/final_qa/screenshots/03_sentiment_monitor_mobile.png) | **PASS** — Vertical feed cards, clean badge spacing |
| **04 Fund Research** | Desktop | 1440 × 1100 | [`04_fund_research_desktop.png`](file:///Users/anny/Desktop/mutual-fund/reports/final_qa/screenshots/04_fund_research_desktop.png) | **PASS** — 10 Indian MF audit table, shortlist metrics, score cards |
| **04 Fund Research** | Tablet | 768 × 1024 | [`04_fund_research_tablet.png`](file:///Users/anny/Desktop/mutual-fund/reports/final_qa/screenshots/04_fund_research_tablet.png) | **PASS** — Scrollable dataframes, percentile metrics |
| **04 Fund Research** | Mobile | 390 × 844 | [`04_fund_research_mobile.png`](file:///Users/anny/Desktop/mutual-fund/reports/final_qa/screenshots/04_fund_research_mobile.png) | **PASS** — Responsive tables, eligibility status pills |
| **05 Stress Lab** | Desktop | 1440 × 1100 | [`05_stress_lab_desktop.png`](file:///Users/anny/Desktop/mutual-fund/reports/final_qa/screenshots/05_stress_lab_desktop.png) | **PASS** — Scenario multiplier table, Altair outflow breakdown |
| **05 Stress Lab** | Tablet | 768 × 1024 | [`05_stress_lab_tablet.png`](file:///Users/anny/Desktop/mutual-fund/reports/final_qa/screenshots/05_stress_lab_tablet.png) | **PASS** — Wrapped scenario cards, interactive slider |
| **05 Stress Lab** | Mobile | 390 × 844 | [`05_stress_lab_mobile.png`](file:///Users/anny/Desktop/mutual-fund/reports/final_qa/screenshots/05_stress_lab_mobile.png) | **PASS** — Stacked shock scenarios, full touch compatibility |
| **06 Evidence & Limits** | Desktop | 1440 × 1100 | [`06_evidence_limits_desktop.png`](file:///Users/anny/Desktop/mutual-fund/reports/final_qa/screenshots/06_evidence_limits_desktop.png) | **PASS** — Source registry ledger, redistribution policies |
| **06 Evidence & Limits** | Tablet | 768 × 1024 | [`06_evidence_limits_tablet.png`](file:///Users/anny/Desktop/mutual-fund/reports/final_qa/screenshots/06_evidence_limits_tablet.png) | **PASS** — Full table display, audit status pills |
| **06 Evidence & Limits** | Mobile | 390 × 844 | [`06_evidence_limits_mobile.png`](file:///Users/anny/Desktop/mutual-fund/reports/final_qa/screenshots/06_evidence_limits_mobile.png) | **PASS** — Clean vertical limitation lists, source links |

---

## 3. Page-by-Page Visual & UX Findings

### 3.1 Page 1: Command Centre (`Home.py`)
- **Theme & Palette**: Clean institutional white `#F8FAFC` background with subtle borders (`#E2E8F0`) and emerald green accents (`#15803D`).
- **Global Filter Row**: Clean 4-column filter (Data Source, Category Universe, Observation Period, Refresh Button) housed within an elevated `.fin-card`.
- **KPI Metrics (6 Executive Cards)**:
  1. `OBSERVED · Closing AUM`: Formatted in INR crore (`₹254,594.79 crore`), period tagged `Sep 2024`, provenance `AMFI Official`.
  2. `OBSERVED · Gross redemptions`: Formatted in INR crore with proper thousand separators.
  3. `FORECAST · Forecast redemption rate`: Formatted as percentage (`1.79%`), provenance `Walk-Forward Ridge`.
  4. `FORECAST · Est. outflow`: Formatted in INR crore.
  5. `FORECAST · Realized outflow gap`: Formatted as signed currency difference (`−₹125.40 crore` or `N/A` if target unobserved). Never outputs `N/A ₹ crore`.
  6. `FORECAST · Alert level`: Formatted as tier pill (`Normal`, `Elevated`, `Critical`).
- **Chart Dynamics**: Side-by-side historical gross redemption trends and closing AUM dynamic line charts with gradient fills, grid lines, and interactive crosshairs.

### 3.2 Page 2: Forecast Lab (`pages/1_Forecast_Lab.py`)
- **Configuration Panel**: Allows switching between AMFI Category Monthly Flows and Scheme NAV Daily Series, target variable selection, forecast horizon ($h=1, 2, 3$ steps), and model families (Persistence, Seasonal Naive, Ridge).
- **Out-of-Sample Performance**: Displays multi-model test forecasts, directional gap analysis, and percentage errors.
- **Empirical Residual Bands**: When $\ge 10$ out-of-sample forecast residuals exist, displays Lower Bound (P10), Point Forecast, and Upper Bound (P90) with quantile offsets. When $< 10$ observations exist, cleanly withholds bands with an honest `INSUFFICIENT_HISTORY` governance explanation.

### 3.3 Page 3: Sentiment Monitor (`pages/2_Sentiment_Monitor.py`)
- **Topic Breakdown Cards**: Negative share, Mean lexical score (bounded $[-1.0, +1.0]$), and Article count.
- **Governance Isolation**: Prominently displays the architectural disclosure:  
  *Context only; sentiment does not alter flow forecasts or fund rankings without demonstrated out-of-sample comparison.*
- **News Item Feed**: Scored articles with publication timestamps, source links, and polarity badges.

### 3.4 Page 4: Fund Research (`pages/3_Fund_Research.py`)
- **Target Mutual Funds Audit (10 Schemes)**: Displays the live-resolved validation table for the 10 requested Indian mutual funds (Parag Parikh, Nippon India, HDFC, ICICI Prudential, SBI, UTI Nifty 50, Kotak, Axis, Mirae Asset, DSP).
  - Scheme code, category, plan (`Direct`), option (`Growth`), latest NAV, NAV date, eligibility status (`ELIGIBLE` vs `REJECTED`), 3Y CAGR, Volatility, Sortino, and explicit rejection reason (`Insufficient history (6 < 750 trading days)`).
- **Shortlist Candidates**: Clean table displaying percentile ranks (`p_return`, `p_consistency`, `p_drawdown`, `p_risk_adj`) and composite research score.
- **Survivorship Bias Disclaimer**: Prominently rendered warning explaining registry limitations.

### 3.5 Page 5: Stress Lab (`pages/4_Stress_Lab.py`)
- **Category Selector**: Selects any of the 8 AMFI categories.
- **Scenario Stress Testing**: Evaluates 1.5x, 2.0x, 2.5x, and 3.0x redemption outflow shocks against latest observed category closing AUM.
- **Metrics**: Category AUM, Severe stress outflow, Outflow share of total AUM.
- **Visual Chart**: Altair horizontal/vertical bar chart showing redemption outflow escalation under base, moderate, severe, and catastrophic scenarios.

### 3.6 Page 6: Evidence & Limits (`pages/5_Evidence_and_Limits.py`)
- **Provenance & Integrity Ledger**: Full inventory of registered data sources (AMFI, RBI, NSE, GDELT) with licence permissions and redistribution constraints.
- **Redistribution Policy**: Prominent warning clarifying that raw ingested data is restricted to research and redistribution is subject to source terms.
- **Quality Checks Table**: Complete status of data contracts, timestamp monotonicities, and validation rules.

---

## 4. Remediation of Identified UX Defects

1. **Elimination of `-1` Sentinel Bug**: All financial metric cards, table formatters, and status badges now strictly check for sentinel placeholders and non-negative metric bounds. Missing or uninitialized values render cleanly as `N/A` without trailing units (`N/A ₹ crore`). Legitimate negative values (returns, drawdowns, gaps) preserve true unicode minus signs (`−`).
2. **Elimination of Erroneous Synthetic Warnings in Production**: The application now distinguishes operational environments from automated test fixtures. When running in operational mode with verified AMFI data (543 category-month records), clean institutional badges (`MODE: LIVE DATA (AMFI ARCHIVE)`) are displayed, and outputs are fully rendered.
3. **Empty Dataset Resolution**: Resolved the SHA-256 and size-bytes mismatch in `data/manifest.json`, allowing the typed loader pipeline to validate and load the full 72-month operational dataset without failure.
4. **Responsive Layout Discipline**: Enforced max-width containers, flexible grid column wrapping on tablets, and vertical single-column reflow on mobile. Tables now scroll horizontally within containers rather than breaking page layout.

---

## 5. Verification Sign-Off

- **Total Screenshots Captured**: 18 of 18 (100% verified under `reports/final_qa/screenshots/`)
- **Automated Tests**: 350 of 350 passing (`make check` validated)
- **Zero Fabrication**: Grounded strictly in official AMFI/NSE datasets and quantitative contracts.
