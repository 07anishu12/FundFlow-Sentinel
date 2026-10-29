# FundFlow Sentinel — User Guide & Operational Manual

This guide describes the end-user workflow, page navigation, metric interpretation, offline demo operation, and troubleshooting procedures for FundFlow Sentinel.

---

## 1. Quick Launch & Operating Modes

FundFlow Sentinel runs locally using Streamlit. It can operate in two primary modes:
1. **Offline Demo Mode (Default):** Loads verified, licence-permitted synthetic demo snapshots from [`data/snapshots/`](file:///Users/anny/Desktop/mutual-fund/data/snapshots/) with zero external network dependencies.
2. **Local Refresh Mode:** Processes locally ingested empirical data through the deterministic CLI pipeline (`make run`) into `data/processed/` and `data/outputs/`.

### Launching the Application
```sh
# Ensure virtual environment is activated
source .venv/bin/activate

# Launch Streamlit Command Centre
make app
```
The browser will automatically open at `http://localhost:8501`.

---

## 2. Navigating the Application

The application comprises six dedicated pages organized in the sidebar:

### 1. Command Centre (`app/Home.py`)
* **Purpose:** Executive dashboard summarizing high-level mutual fund flow dynamics, active alerts, and system health.
* **Key Components:**
  * **Summary KPI Cards:** Top-level metrics tagged with origin (`OBSERVED`, `FORECAST`, `SCENARIO`), measurement period, and units.
  * **Central Forecast Overview:** Latest predicted category redemption rates vs baseline rates.
  * **Redemption Alert Ledger:** Active categories flagged for Elevated or Critical redemption pressure.
  * **Quality Banner:** Active data freshness and bundle origin status (`offline_snapshot`, `live`, or `synthetic`).

### 2. Forecast Lab (`app/pages/1_Forecast_Lab.py`)
* **Purpose:** Detailed quantitative inspection of category redemption forecasting models.
* **Key Components:**
  * **Forecast Comparison Table:** Category-by-category comparison between Persistence Baseline ($R_{t+1} = R_t$) and Pooled Ridge Regression ($R_{t+1} = \hat{R}$).
  * **Feature Contribution Breakdown:** Linear decomposition showing how market indicators (NIFTY return, VIX change) and lagged flow momentum contribute additively to the point forecast.
  * **Uncertainty Bounds:** Honest disclosure of residual bands. When empirical history is under 36 months, an `INSUFFICIENT_HISTORY` banner is displayed rather than fabricated intervals.

### 3. Sentiment Monitor (`app/pages/2_Sentiment_Monitor.py`)
* **Purpose:** Contextual news and tone tracking for mutual fund market narratives.
* **Key Components:**
  * **Topic Sentiment Summary:** Average polarity score ($-1.0$ to $+1.0$), negative tone share, and article volume.
  * **Item-Level Article Evidence:** Article headlines, publication timestamps, and lexical polarity classifications.
  * **Source Distinction Mandate:** Clear visual separation between local RSS headline feeds and historical GDELT tone datasets.
  * **Sufficiency Threshold:** Displays an `insufficient_data` notice if fewer than 30 articles are available for a period.

### 4. Fund Research (`app/pages/3_Fund_Research.py`)
* **Purpose:** Independent scheme-level performance research and shortlisting.
* **Architectural Boundary:** Completely isolated from flow, forecast, and alert modules. Evaluates funds solely on historical NAV performance.
* **Key Components:**
  * **Direct-Growth Universe:** Strictly filters for Direct Plan, Growth Option schemes with $\ge 750$ days of continuous NAV history ($\le 10$-day gap tolerance).
  * **5-Factor Composite Scoring:** 40% 3-year CAGR, 20% Annualized Volatility, 20% Max Drawdown (inverted), 10% Sortino Ratio, and 10% Rolling Return Consistency.
  * **Research Shortlist Table:** Percentile-ranked fund shortlist preserving source order.
  * **Regulatory Disclaimers:** Mandatory survivorship bias and non-investment advice disclosures.

### 5. Stress Lab (`app/pages/4_Stress_Lab.py`)
* **Purpose:** Capital-at-risk simulation and liquidity scenario analysis.
* **Key Components:**
  * **Scenario Selection:**
    - *Baseline Scenario:* Current point forecast.
    - *Historical Max Scenario:* Category worst-case historical redemption rate.
    - *Severe Shock Scenario:* User-adjustable stress shock (e.g. $+3.0\%$ to $+10.0\%$).
  * **Asset Capping Invariant:** Outflow estimates are mathematically capped at 100% of reference AUM. Negative rates and non-finite inputs are hard-rejected.
  * **Finance-Safe Narrative:** Clear prose explanation of incremental outflows without sensationalist language ("liquidity crisis", "run on the fund").

### 6. Evidence & Limitations (`app/pages/5_Evidence_and_Limits.py`)
* **Purpose:** Full transparency on empirical coverage, validation checks, source rights, and system boundaries.
* **Key Components:**
  * **Data Quality Audit Table:** Verification status of contract schemas, monetary units, category universes, and zero temporal leakage.
  * **Source Registry Table:** Upstream URLs, retrieval status, and redistribution permissions for all 13 project sources.
  * **Strict Redistribution Policy:** Explains why restricted third-party datasets (AMFI, NSE) are excluded from public snapshots.
  * **Model Limitations:** Records why empirical expanding-window backtests are marked `insufficient_history` when flow history is 1 month.

---

## 3. Interpreting Metric Tags & Status Labels

Every metric displayed in FundFlow Sentinel carries an explicit metadata card:

| Label | Meaning | Safe Interpretation |
|---|---|---|
| **`OBSERVED`** | Historical fact directly measured in raw or processed data. | Real empirical measurement for the indicated period. |
| **`FORECAST`** | Point estimate produced by a quantitative model. | Forward-looking expectation; subject to modeling error. |
| **`SCENARIO`** | Simulated stress assumption or scenario shock. | Hypothetical stress condition; not a predicted probability. |
| **`SYNTHETIC DEMO DATA`** | Invented mock records generated for interface testing. | Unconditionally displayed when using demo snapshots; not real funds or real AMFI flows. |
| **`INSUFFICIENT_HISTORY`** | Historical sample size is too short to compute a metric. | Honest omission; indicates that data cannot support credible statistical estimation. |

---

## 4. Running Offline vs Local Refresh

### Operating Completely Offline
FundFlow Sentinel is engineered to run with zero outbound network calls:
* Snapshots are read directly from local disk via [`app/loaders.py`](file:///Users/anny/Desktop/mutual-fund/app/loaders.py).
* All tests pass with network sockets blocked at the operating system level.
* No API keys, cloud tokens, or live internet connections are required.

### Executing a Local Pipeline Refresh
If you have retrieved local data and wish to execute the quantitative pipeline:
```sh
# Execute all pipeline stages end-to-end
make pipeline

# Or run individual stages
make build-data
make train
make alerts
make rank
```
If a stage fails, the pipeline immediately halts and preserves the last-known-good output files without corrupting previous outputs.

---

## 5. Troubleshooting & Diagnostics

### 1. "Dataset unavailable: not declared in the manifest"
* **Cause:** The requested table exists on disk but is omitted from `manifest.json`.
* **Fix:** Regenerate the snapshot using `make snapshot` or add the table name to `manifest.json["tables"]`.

### 2. "Stored data is older than the display freshness threshold"
* **Cause:** Artifact `generated_at` timestamp is older than the 45-day UI display threshold.
* **Fix:** This is an informational display warning. The data remains readable. To refresh, run `make snapshot` or run a local pipeline refresh.

### 3. Port Conflict on `8501`
* **Cause:** Another Streamlit application or process is using port 8501.
* **Fix:** Launch on a custom port:
  ```sh
  .venv/bin/python -m streamlit run app/Home.py --server.port 8502
  ```

### 4. Manifest Hash Mismatch during `fundflow snapshot --verify`
* **Cause:** A file in `data/snapshots/` was manually edited or corrupted.
* **Fix:** Rebuild the snapshot cleanly:
  ```sh
  make snapshot
  ```

---

## 6. Public Deployment & Hosting Operations Guide

### A. Streamlit Community Cloud (Public Demo Hosting)
FundFlow Sentinel is pre-configured for direct deployment to Streamlit Community Cloud:
* **Repository Entry Point:** `app/Home.py`
* **Python Runtime:** Select Python `3.11`.
* **Dependency File:** Point to `requirements.txt` (pinned dependencies install automatically).
* **Secrets Configuration:** Zero secrets or API keys are required. The public deployment loads the committed, licence-permitted offline demo snapshot from `data/snapshots/`.
* **Licensing Compliance:** Because `data/snapshots/` contains exclusively synthetic demo data (`origin: synthetic`), public hosting complies 100% with AMFI and NSE non-redistribution terms.

### B. Internal VPC / Local Workstation Hosting (With Real Empirical Data)
If operating FundFlow Sentinel on private enterprise infrastructure with proprietary ingested AMFI data:
1. **Redistribution Terms:** AMFI monthly reports and NSE indices are restricted to personal/internal non-commercial use. Do not expose real ingested raw reports to public internet endpoints without explicit third-party redistribution grants.
2. **Environment Variables:** Use `FUNDFLOW_FIXTURE_DIR` to select a private internal data directory if needed.
3. **Data Refresh Scheduling:** Category flows are published monthly by AMFI (typically around the 10th of each calendar month). Batch pipelines should execute on a monthly cron rather than high-frequency polling.
4. **Error Sanitization:** All pages execute within an error boundary that suppresses stack traces and internal filesystem paths, protecting server environments from information leakage.
