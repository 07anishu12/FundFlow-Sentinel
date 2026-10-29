# FundFlow Sentinel — Five-Minute Technical Demonstration Runbook

This runbook outlines a structured, reproducible 5-minute technical demonstration of FundFlow Sentinel, guiding reviewers through the application's key capabilities, quantitative safeguards, and honest empirical limitations.

---

## 1. Quick Launch & Operating Environment

```sh
# 1. Activate virtual environment
source .venv/bin/activate

# 2. Run unified quality gate (validates compilation, contracts, snapshot, and 316 tests)
make check

# 3. Launch Streamlit Command Centre
make app
```
The browser will open to `http://localhost:8501`.

---

## 2. Five-Minute Demonstration Sequence

```
  ┌─────────────────────────────────────────────────────────────────────────────────┐
  │                           5-MINUTE DEMO SEQUENCE                                │
  │                                                                                 │
  │  [0:00] Step 1: Command Centre ─────── Executive Overview & Observed Flows      │
  │  [0:45] Step 2: Forecast Lab ───────── Central Forecast vs Persistence Baseline │
  │  [1:30] Step 3: Alert Sentinel ─────── 3-Tier Hierarchical Rules & Zero-MAD     │
  │  [2:15] Step 4: Sentiment Monitor ──── Contextual News & Source Distinction     │
  │  [3:00] Step 5: Stress Lab ─────────── 100% Capping & Finance-Safe Narrative    │
  │  [3:45] Step 6: Fund Research ──────── AST-Isolated NAV Composite Scoring      │
  │  [4:30] Step 7: Evidence & Limits ──── Transparency, Licenses & Disclaimers    │
  └─────────────────────────────────────────────────────────────────────────────────┘
```

---

### Step 1: Command Centre (`app/Home.py`)
* **Reviewer Action:** Open Home page. View category selector (default: "Large Cap"). Inspect KPI cards and alert summary.
* **Artifact / Metric Displayed:**
  * Closing AUM: `₹379,010.08 crore` (`OBSERVED`, Period: `2024-09`)
  * Gross Redemptions: `₹4,096.44 crore` (`OBSERVED`, Period: `2024-09`)
  * Forecast Redemption Rate: `1.09%` (`FORECAST`, Period: `2024-10`)
  * Alert Level: `Elevated` (`FORECAST`)
* **Defensible Takeaway:** Delivers a clear, unified executive overview uniting historical AMFI category flow metrics with quantitative next-period forecast rates and active redemption alerts.
* **Material Limitation Disclosed:** Historical flow data covers 1 month (September 2024); the demo snapshot displays licence-permitted synthetic test data tagged with the prominent `SYNTHETIC DEMO DATA` banner.

---

### Step 2: Forecast Lab (`app/pages/1_Forecast_Lab.py`)
* **Reviewer Action:** Navigate to Forecast Lab. Compare central walk-forward Ridge forecast against the persistence baseline. Inspect additive feature contributions.
* **Artifact / Metric Displayed:**
  * Ridge Point Forecast: `1.09%` vs Persistence Baseline: `1.12%`
  * Additive Linear Contributions: Base rate `1.00`, VIX mean `-0.05`, NIFTY return `+0.08` (reconciling exactly to point prediction within $10^{-4}$).
* **Defensible Takeaway:** Enforces strict temporal non-leakage: all scalers and transforms fit fold-locally, and models evaluate out-of-sample (`train_end < target_month`).
* **Material Limitation Disclosed:** Empirical P10/P90 residual uncertainty bands are withheld and labeled `INSUFFICIENT_HISTORY` because 1 month of historical flows cannot support statistical quantile estimation.

---

### Step 3: Redemption Alert Sentinel (`app/Home.py` / `alerts.csv`)
* **Reviewer Action:** Review alert ledger in Command Centre.
* **Artifact / Metric Displayed:**
  * Small Cap: `Critical` ($\ge 90\text{th}$ percentile and upward momentum $\ge 0.10$).
  * Large Cap & Mid Cap: `Elevated` ($\ge 75\text{th}$ percentile).
  * Corporate Bond: `Normal`.
* **Defensible Takeaway:** Hierarchical 3-tier rules with zero-MAD safeguards on robust Z-score calculation to eliminate false alarms during low-volatility regimes.
* **Material Limitation Disclosed:** Alert backtests and historical precision/recall statistics remain unavailable until multi-year flow datasets are ingested.

---

### Step 4: Sentiment Monitor (`app/pages/2_Sentiment_Monitor.py`)
* **Reviewer Action:** Navigate to Sentiment Monitor. Review topic sentiment metrics, sufficiency indicator, and recent headlines.
* **Artifact / Metric Displayed:**
  * Mean Polarity Score: `+0.15` (Scale $[-1.0, +1.0]$)
  * Negative Share: `12.0%`
  * Live Article Volume: `45 articles` (exceeds minimum 30-article sufficiency threshold).
  * Article Links: Validated via `safe_url()`; non-http schemes and mock markers are rendered as plain bold text without clickable hyperlinks.
* **Defensible Takeaway:** Strictly contextual media monitoring. The Source Distinction Mandate keeps immediate local RSS headlines separate from macro GDELT historical tone.
* **Material Limitation Disclosed:** Sentiment operates strictly as contextual intelligence; it does **not** drive fund ranking or quantitative flow forecasting.

---

### Step 5: Stress Lab (`app/pages/4_Stress_Lab.py`)
* **Reviewer Action:** Navigate to Stress Lab. Select Large Cap. Enter custom redemption shock of `8.0%`. Review multi-scenario table and finance-safe narrative.
* **Artifact / Metric Displayed:**
  * Base Outflow Proxy: `₹4,131.21 crore` (`SCENARIO`)
  * Custom Scenario Outflow: `₹30,320.81 crore` (`SCENARIO`)
  * Asset Capping Rule: Any scenario rate $>100.0\%$ triggers an explicit policy notice and caps outflows at 100% of reference AUM.
  * Objective Narrative: Summarizes incremental outflows without alarmist language ("liquidity crisis", "run on the fund", "panic").
* **Defensible Takeaway:** Pure deterministic gross redemption outflow arithmetic with mandatory asset capping and finance-safe institutional disclosures.
* **Material Limitation Disclosed:** Scenario shocks are user-defined hypothetical simulations, not predicted crisis probabilities.

---

### Step 6: Fund Research (`app/pages/3_Fund_Research.py`)
* **Reviewer Action:** Navigate to Fund Research. Review fund shortlist and multi-metric breakdown.
* **Artifact / Metric Displayed:**
  * Synthetic Bluechip Fund: Composite Research Score `81.4` (Direct Plan, Growth Option).
  * 3Y CAGR: `18.5%`, Volatility: `12.4%`, Inverted Max Drawdown: `-10.5%`, Sortino: `1.85`.
* **Defensible Takeaway:** AST-verified architectural isolation: fund research imports zero modules from forecasting, alerts, stress, or flow models. Evaluates funds strictly on 3-year risk-adjusted daily NAV performance.
* **Material Limitation Disclosed:** Survivorship bias in operational scheme feeds; past performance does not guarantee future returns. Strictly non-investment advice.

---

### Step 7: Evidence & Limitations (`app/pages/5_Evidence_and_Limits.py`)
* **Reviewer Action:** Navigate to Evidence and Limits. Review data quality checks, source registry table, and system disclaimers.
* **Artifact / Metric Displayed:**
  * Data Quality Status: `PASS` (6 contract checks verified).
  * Source Registry: 13 registered sources with explicit redistribution statuses.
  * Strict Redistribution Policy Warning: Explains why restricted third-party datasets (AMFI, NSE) are excluded from public snapshots.
* **Defensible Takeaway:** Full operational transparency. Clearly communicates system boundaries, licensing constraints, and quantitative limitations.
* **Material Limitation Disclosed:** Decision support only; not investment advice or emergency liquidity assurance.
