# FundFlow Sentinel

**FundFlow Sentinel** is a quantitative decision-support platform for Indian mutual funds. It combines category-level net flow forecasting, hierarchical redemption alerting, portfolio stress-testing scenarios, and independent NAV-based fund research into a local-first, offline-capable application.

The application adheres to strict quantitative integrity, temporal non-leakage guarantees, source governance licensing, and clear separation between macro category flows and scheme-level fund research.

---

## 1. Core Feature Map

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                                 FUNDFLOW SENTINEL                                     │
├──────────────────────────┬────────────────────────────┬────────────────────────────────┤
│ Category Flow Sentinel   │ Scenario Stress Lab        │ Independent Fund Research     │
│ • Persistence baseline   │ • Reference AUM proxy      │ • NAV-only metrics (3Y daily)  │
│ • Ridge walk-forward     │ • 3 stress scenarios       │ • Direct-Growth plan filter    │
│ • 3-tier alert engine    │ • Outflow cap at 100%      │ • Composite 5-factor scoring   │
│ • Zero-MAD safeguards    │ • Finance-safe narrative   │ • Zero flow/model imports      │
├──────────────────────────┼────────────────────────────┼────────────────────────────────┤
│ Sentiment Context        │ Local-First Presentation   │ Governance & Verification      │
│ • Lexical sentiment      │ • Command Centre & 5 Labs  │ • 10 frozen CSV contracts      │
│ • Source distinction     │ • Offline demo snapshots   │ • Transactional atomic CLI     │
│ • Context-only policy    │ • Tagged metric cards      │ • Strict redistribution policy │
└──────────────────────────┴────────────────────────────┴────────────────────────────────┘
```

* **Command Centre (`app/Home.py`):** Executive overview of category flows, baseline vs model forecasts, active alert summaries, market context indicators, and system quality status.
* **Forecast Lab (`app/pages/1_Forecast_Lab.py`):** Central walk-forward category redemption rate forecasts vs persistence baseline, feature contribution decomposition, and empirical residual band tracking.
* **Sentiment Monitor (`app/pages/2_Sentiment_Monitor.py`):** Topic tone distribution and item-level article evidence with strict distinction between local RSS headlines and historical GDELT tone. Context-only lane.
* **Fund Research (`app/pages/3_Fund_Research.py`):** Scheme-level fund shortlist ranked by composite 3-year risk-adjusted NAV performance. Completely isolated from flow, forecast, and alert modules.
* **Stress Lab (`app/pages/4_Stress_Lab.py`):** Interactive asset-at-risk simulation applying historical max, baseline forecast, and scenario shocks against category AUM proxies, with asset outflows capped strictly at 100%.
* **Evidence & Limitations (`app/pages/5_Evidence_and_Limits.py`):** Transparent disclosure of empirical data coverage, quality checks, source licensing terms, and core research disclaimers.

---

## 2. Quick-Start (Clean Setup Path)

### Tested Environment
* **Platform:** macOS Apple Silicon (arm64) / POSIX Linux
* **Python Runtime:** Python `3.11` (tested on `3.11.16`)
* **Package Manager:** `pip` with direct pinned requirements in [`requirements.txt`](requirements.txt)

### Installation & Launch
```sh
# 1. Create and activate Python 3.11 virtual environment
python3.11 -m venv .venv
source .venv/bin/activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Validate frozen contracts and run full test suite (287 tests)
make validate
make test

# 4. Generate or verify offline demo snapshot
make snapshot

# 5. Launch the Streamlit application
make app
```
The application opens locally in your browser at `http://localhost:8501`.

---

## 3. CLI Pipeline & Offline Orchestration

FundFlow Sentinel includes a deterministic CLI orchestrator with transactional atomic writes and last-known-good preservation:

```sh
# Run full pipeline end-to-end in offline mode
.venv/bin/python -m fundflow.cli --offline all

# Run individual pipeline stages
.venv/bin/python -m fundflow.cli build-data    # Feature matrix generation
.venv/bin/python -m fundflow.cli train         # Walk-forward model fitting
.venv/bin/python -m fundflow.cli alerts        # Hierarchical alert evaluation
.venv/bin/python -m fundflow.cli sentiment     # RSS sentiment aggregation
.venv/bin/python -m fundflow.cli rank          # Independent NAV fund ranking

# Create and verify licence-permitted offline demo snapshots
.venv/bin/python -m fundflow.cli snapshot --create
.venv/bin/python -m fundflow.cli snapshot --verify
```

Execution telemetry and SHA-256 file digests are atomically recorded in `data/outputs/run_report.json`.

---

## 4. Empirical Data Reality & Sufficiency

FundFlow Sentinel enforces honest empirical disclosures:

* **Category Flows:** The processed empirical AMFI flow dataset ([`data/processed/flows_category_month.csv`](data/processed/flows_category_month.csv)) contains **8 records covering 1 month (`2024-09`)** across 8 categories (`Large Cap`, `Flexi Cap`, `Mid Cap`, `Small Cap`, `Corporate Bond`, `Aggressive Hybrid`, `Liquid`, `Overnight`).
* **Market Indicators:** Market indicators ([`data/processed/market_month.csv`](data/processed/market_month.csv)) cover **61 monthly records (`2019-09` to `2024-09`)**.
* **Sufficiency Impact:** Longer market history does **not** substitute for missing flow history. Walk-forward expanding-window validation (requiring a 36-month warm-up), multi-year empirical residual bands, 24-month robust anomaly scores, and alert backtests are **withheld and labeled `insufficient_history`** in empirical runs.
* **Offline Demo Data:** Public releases bundle licence-permitted synthetic demo data ([`data/snapshots/`](data/snapshots/)) clearly tagged `origin: synthetic` and `source: synthetic:not-a-source`, with prominent UI `SYNTHETIC DEMO DATA` warning banners.

---

## 5. Architectural & Research Invariants

1. **Temporal Non-Leakage:** All features, scalers, and transforms fit strictly inside training folds. Point forecasts evaluate out-of-sample (`train_end < target_month`). Observations after month $T$ cannot alter features or forecasts at or prior to $T$.
2. **Ranking & Presentation Isolation:** Fund research ranking ([`src/fundflow/ranking.py`](src/fundflow/ranking.py)) imports zero modules from forecasting, alerts, stress, or flows. The UI presentation layer ([`app/`](app/)) executes no machine learning inference or ranking computations.
3. **Finance-Safe Arithmetic:** Outflows reconcile exactly to point estimates ($0.01\text{ cr}$ precision) and are mathematically capped at 100% of reference AUM.
4. **Source Governance & Redistribution:** Raw and processed third-party data subject to restrictive terms (AMFI, NSE, Yahoo Finance) are excluded from public snapshots. Model weights requiring non-commercial licenses (FinBERT) are excluded in favor of a verified local lexical classifier.

---

## 6. Disclaimers & Regulatory Notices

> **⚠️ MANDATORY NOTICES:**
> 1. **Decision Support Only:** FundFlow Sentinel provides quantitative analytical decision support. It does not provide investment advice, trading recommendations, or financial solicitations.
> 2. **Not a Liquidity Guarantee:** Macro category-level redemption forecasts do not represent scheme-level cash requirements, run risks, or emergency liquidity guarantees.
> 3. **Survivorship Bias:** Historical scheme master lists reflect active operational schemes only. Liquidated, merged, or restructured schemes are excluded from public NAV daily feeds.
> 4. **No Predictive Guarantee:** Past performance and quantitative models do not guarantee future returns or redemption outcomes.

---

## 7. Project Documentation Index

* **[User Guide](docs/USER_GUIDE.md):** Comprehensive workflow guide, page navigation, label definitions, and troubleshooting.
* **[Architecture Document](docs/ARCHITECTURE.md):** Implemented system architecture, data-flow diagrams, and module boundaries.
* **[Data Boundary & Snapshot Registry](data/README.md):** Data schemas, licensing audit, and snapshot commands.
* **[Frozen Interface Specifications](docs/INTERFACES.md):** Frozen CSV contract columns and function signatures.
* **[Source Registry Ledger](config/sources.yaml):** Formal rights, terms URLs, and redistribution status for all 13 data sources.
* **[Wave 11 Test Hardening Validation](docs/WAVE_11_VALIDATION.md):** Verification of 267 adversarial regression tests.
* **[Wave 12 Snapshot Validation](docs/WAVE_12_SNAPSHOT_VALIDATION.md):** Agent A snapshot integrity and offline release report.
* **[Wave 12 Documentation Validation](docs/WAVE_12_DOCS_VALIDATION.md):** Agent B documentation verification and claim reconciliation.
* **[Production Deployment Runbook](docs/DEPLOYMENT.md):** Docker, Docker Compose, PaaS, health monitoring, and atomic rollback instructions.
