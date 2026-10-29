# FundFlow Sentinel Data Boundary & Snapshot Registry

This directory contains data structures, offline release snapshots, and source governance configurations for FundFlow Sentinel.

---

## 1. Directory Structure & Bundle Hierarchy

```
data/
├── README.md                      # This document
├── manifest.json                  # Root development bundle manifest
├── quality_report.json            # Empirical data quality audit report
├── raw/                           # Raw downloaded source reports (immutable, gitignored)
├── processed/                     # Leakage-safe, validated tables (gitignored)
│   ├── flows_category_month.csv   # Empirical category flow history (September 2024, 8 rows)
│   ├── market_month.csv           # Macro/index indicators (61 months)
│   └── feature_matrix.csv         # Modeling feature matrix
├── outputs/                       # Generated pipeline outputs (gitignored)
│   ├── predictions.csv            # Central point forecasts
│   ├── alerts.csv                 # Hierarchical alert evaluations
│   ├── shortlist.csv              # NAV-only fund research shortlist
│   ├── sentiment_agg.csv          # Aggregate sentiment tone
│   ├── sentiment_items.csv        # Item-level sentiment records
│   ├── model_results.json         # Model evaluation metrics & limitations
│   └── run_report.json            # Deterministic CLI run telemetry
└── snapshots/                     # Licence-permitted offline release bundles (committed)
    ├── manifest.json              # Version 1 snapshot manifest with provenance & digests
    ├── quality_report.json        # Snapshot data quality envelope
    ├── source_metadata.json       # Snapshot source governance registry envelope
    ├── processed/                 # Frozen processed contract tables (synthetic demo)
    │   ├── feature_matrix.csv
    │   ├── flows_category_month.csv
    │   ├── market_month.csv
    │   ├── nav_daily.csv
    │   └── scheme_master.csv
    ├── outputs/                   # Frozen output contract tables (synthetic demo)
    │   ├── alerts.csv
    │   ├── model_results.json
    │   ├── predictions.csv
    │   ├── sentiment_agg.csv
    │   ├── sentiment_items.csv
    │   └── shortlist.csv
    └── fixtures/                  # Flat legacy synthetic fixtures for unit tests
```

---

## 2. Redistribution Licensing & Source Governance

In accordance with [`config/sources.yaml`](../config/sources.yaml) and the project's data governance policy, public release snapshots contain **exclusively licence-permitted synthetic demo data** (`origin: synthetic`) and permitted derived metadata (`origin: derived`).

### Source Rights Ledger & Public Snapshot Decisions

| Source ID | Source Name | Data Type | Upstream License / Terms | Redistribution Status | Public Snapshot Action |
|---|---|---|---|---|---|
| `amfi_flows` | AMFI Monthly Flows | Category Flows | AMFI Terms of Use: Personal non-commercial site use only. Prohibits publication and redistribution. | **Restricted** | **EXCLUDED** from public snapshot. Local raw/processed files remain gitignored. |
| `amfi_nav` | AMFI NAV Daily | Daily NAV | AMFI Terms of Use: Personal non-commercial site use only. | **Restricted** | **EXCLUDED** from public snapshot. |
| `mfapi` | mfapi.in | Daily NAV | Unofficial wrapper; no redistribution grant verified. | **Unknown** | **EXCLUDED** from public snapshot. |
| `nse_vix` | NSE India VIX | Market Volatility | NSE Data Policy: Subject to commercial agreement; scraping prohibited. | **Restricted** | **EXCLUDED** from public snapshot. |
| `nifty_indices` | NSE Indices Nifty | Benchmark Indices | Terms prohibit automated collection and redistribution. | **Restricted** | **EXCLUDED** from public snapshot. |
| `yfinance` | Yahoo Finance | Market Data | Upstream Yahoo Terms: Personal non-commercial use only. | **Restricted** | **EXCLUDED** from public snapshot. |
| `rbi_dbie` | RBI DBIE | Macro Data | Download brochure only; redistribution unverified. | **Unknown** | **EXCLUDED** from public snapshot. |
| `rbi_rss` | RBI RSS | News Headlines | Subscription permitted; redistribution rights unverified. | **Unknown** | **EXCLUDED** from public snapshot. |
| `fed_rss` | Federal Reserve RSS | Global Macro Headlines | US Government Public Domain (excluding third-party logos). | **Permitted with conditions** | Permitted with attribution. |
| `gdelt` | GDELT Project | Historical Tone | Academic, commercial, and government use permitted with citation. | **Permitted with conditions** | Permitted with attribution. |
| `prosus_finbert` | ProsusAI/finbert | Transformer Weights | CC-BY-NC-SA-4.0: Non-commercial only; weights excluded. | **Restricted** | **EXCLUDED** from repository. Lexical fallback active. |
| `finbert_tone` | yiyanghkust/finbert | Transformer Weights | No explicit license grant found on model card. | **Unknown** | **EXCLUDED** from repository. |
| `vader` | VADER Lexicon | Sentiment Lexicon | MIT License. | **Permitted with conditions** | Permitted with MIT notice. |
| `synthetic_demo` | Synthetic Fixtures | All 10 Contracts | Generated by FundFlow Sentinel test harnesses. | **Permitted** | **INCLUDED** in public snapshot; tagged `origin: synthetic`. |

---

## 3. Origin Labels & Machine-Readable Provenance

Every artifact declared in `data/snapshots/manifest.json` carries an explicit `origin` and `redistribution` classification:
* **`origin: "synthetic"`**: Synthetic test observations generated for interface demonstration. These contain mock rates, flows, and scheme parameters. The UI unconditionally displays a visible `SYNTHETIC DEMO DATA` warning banner.
* **`origin: "derived"`**: Governance metadata envelopes (such as `quality_report.json` and `source_metadata.json`) derived from repository configurations and pipeline execution telemetry.
* **`origin: "real"`**: Real empirical observations. Strictly restricted from public snapshot redistribution; stored in gitignored local development directories only (`data/raw/`, `data/processed/`).

---

## 4. Empirical Data Reality & Sufficiency

Local real data processing is subject to empirical sufficiency bounds:
* **Category Flows:** `data/processed/flows_category_month.csv` contains **8 records covering 1 month (`2024-09`)**.
* **Market Data:** `data/processed/market_month.csv` contains **61 monthly records (`2019-09` to `2024-09`)**.
* **Sufficiency Impact:** Longer market history does **not** substitute for missing flow history. Walk-forward expanding-window forecasting, empirical residual bands, 24-observation robust anomaly scores, and alert backtests require multi-year flow history. In the empirical pipeline, these remain explicitly flagged as `insufficient_history` / unavailable rather than simulated or fabricated.

---

## 5. Snapshot Generation & Verification Commands

### Generate and Publish Offline Snapshot
```sh
# Using Make
make snapshot

# Using CLI directly
.venv/bin/python -m fundflow.cli snapshot --create

# Using module entrypoint
PYTHONPATH=src .venv/bin/python -m fundflow.snapshot
```

### Verify Existing Snapshot Integrity
```sh
# Verify snapshot manifest, digests, byte sizes, and schemas
.venv/bin/python -m fundflow.cli snapshot --verify

# Verbose verification reporting
.venv/bin/python -m fundflow.cli -v snapshot --verify
```

### Transactional Publishing Safety
Snapshot publication executes transactionally:
1. All artifacts and the manifest are staged into a temporary folder (`.tmp_snapshot_<id>`).
2. Self-verification validates all SHA-256 digests, byte sizes, relative paths, and table contracts.
3. If staging or verification fails at any point, the temporary staging folder is cleaned up and the previous snapshot remains uncorrupted.
4. On POSIX platforms, the staging folder is swapped atomically into place.
