# Wave 12 Validation Report & Release Gate Approval

**Date:** 2026-10-29  
**Lead Auditor / Integrator:** Senior Quantitative Research & Data Platform Lead  
**Scope:** Wave 12 — Offline Release & Clear Documentation (Prompts 25 & 26)  
**Linked Pre-Flight & Agent Reports:**
* [`docs/WAVE_12_PREFLIGHT.md`](file:///Users/anny/Desktop/mutual-fund/docs/WAVE_12_PREFLIGHT.md)
* [`docs/WAVE_12_SNAPSHOT_VALIDATION.md`](file:///Users/anny/Desktop/mutual-fund/docs/WAVE_12_SNAPSHOT_VALIDATION.md) (Agent A)
* [`docs/WAVE_12_DOCS_VALIDATION.md`](file:///Users/anny/Desktop/mutual-fund/docs/WAVE_12_DOCS_VALIDATION.md) (Agent B)
* Prior Gate: [`docs/WAVE_11_VALIDATION.md`](file:///Users/anny/Desktop/mutual-fund/docs/WAVE_11_VALIDATION.md) (**PASS**)

**Release Decision:** **PASS FOR AN OFFLINE PUBLIC DEMO (WITH BOUNDED LIMITATIONS)**

---

## 1. Executive Summary & Verification Findings

Wave 12 successfully produced a licence-compliant, self-contained offline release bundle and comprehensive, repository-grounded documentation:

1. **Licence Compliance & Redistribution Enforcement:**
   - In adherence to [`config/sources.yaml`](file:///Users/anny/Desktop/mutual-fund/config/sources.yaml), all third-party sources whose redistribution rights are restricted or unverified (AMFI monthly flows, AMFI NAV, NSE India VIX, Nifty Indices, yfinance, and Prosus FinBERT model weights) are **strictly excluded** from public release bundles.
   - The public demo snapshot under [`data/snapshots/`](file:///Users/anny/Desktop/mutual-fund/data/snapshots/) contains **exclusively licence-permitted synthetic demo data** (`origin: synthetic`) and derived governance envelopes (`origin: derived`).
   - Every artifact declared in [`data/snapshots/manifest.json`](file:///Users/anny/Desktop/mutual-fund/data/snapshots/manifest.json) carries an explicit machine-readable `redistribution: "permitted"` classification.
2. **Snapshot Completeness & Integrity:**
   - All 10 frozen contract tables across `processed/` and `outputs/`, plus all 3 JSON artifact envelopes (`quality_report.json`, `source_metadata.json`, `outputs/model_results.json`), are packaged.
   - Independent verification recomputed SHA-256 digests and byte sizes for all 13 artifacts with **100% match** against `manifest.json`.
   - Contract schema checks confirmed that 100% of CSV tables validate against [`src/fundflow/contracts.py:COLUMNS`](file:///Users/anny/Desktop/mutual-fund/src/fundflow/contracts.py#L3).
3. **Transactional Publishing & Last-Good Safety:**
   - Snapshots are staged in `.tmp_snapshot_<id>`, validated for hash integrity and contract conformity, and swapped atomically.
   - Verified that failures during staging or validation never corrupt or delete the existing last-known-good snapshot.
4. **Complete Offline UI Execution:**
   - All 6 application pages were verified to render cleanly with network sockets disabled at the OS level (`socket.create_connection` and `socket.socket.connect` hard-blocked).
   - Every page displays the mandatory `SYNTHETIC DEMO DATA` warning banner.
5. **Documentation Truth & Alignment:**
   - Authoritative overhaul of [`README.md`](file:///Users/anny/Desktop/mutual-fund/README.md), creation of [`docs/USER_GUIDE.md`](file:///Users/anny/Desktop/mutual-fund/docs/USER_GUIDE.md), and publication of [`docs/ARCHITECTURE.md`](file:///Users/anny/Desktop/mutual-fund/docs/ARCHITECTURE.md) with a Mermaid data-flow diagram.
   - Every documented command was executed and verified. Every quantitative claim was reconciled against actual data files and code implementations.
   - Transparently disclosed that empirical flow history contains **1 month (`2024-09`, 8 categories)**, and that market indicators (61 months) do not substitute for flow history.

---

## 2. Command Execution Evidence

| Command Line | Working Directory | Exit Code | Tests Passed | Tests Failed | Execution Time | Environment Notes |
|---|---|---|---|---|---|---|
| `make validate` | `/Users/anny/Desktop/mutual-fund` | 0 | 32 | 0 | 0.20s | Contract schema validation |
| `make test` | `/Users/anny/Desktop/mutual-fund` | 0 | **287** | 0 | 7.11s | Full test suite across 19 test files (+20 snapshot tests) |
| `make snapshot` | `/Users/anny/Desktop/mutual-fund` | 0 | N/A | 0 | 0.92s | Staged, validated, and published `data/snapshots/` |
| `.venv/bin/python -m fundflow.cli snapshot --verify` | `/Users/anny/Desktop/mutual-fund` | 0 | N/A | 0 | 0.45s | Independent verification of all 13 artifacts |
| `.venv/bin/python -m fundflow.cli --offline all` | `/Users/anny/Desktop/mutual-fund` | 0 | N/A | 0 | 1.15s | Full pipeline execution in offline mode |
| `pytest tests/test_snapshots.py` | `/Users/anny/Desktop/mutual-fund` | 0 | 20 | 0 | 0.86s | Dedicated snapshot & offline tests |

* **Environment Details:**
  * Python: `3.11.16` (`.venv/bin/python`)
  * Pytest: `8.3.5`
  * Platform: `macOS-27.2-arm64` (Apple Silicon M-series)

---

## 3. Independent Manifest & Hash Verification

The Integrator independently audited all artifacts in [`data/snapshots/manifest.json`](file:///Users/anny/Desktop/mutual-fund/data/snapshots/manifest.json):

| Relative Path | Byte Size | SHA-256 Digest | Rows | Origin | Redistribution Status | Hash Match | Contract Validation |
|---|---|---|---|---|---|---|---|
| `outputs/alerts.csv` | 2,007 | `4c8d33ca233a7e446554b73108ce8a3d76e73cba5b66d54620f5c531398867a5` | 8 | `synthetic` | `permitted` | **MATCH** | **PASS** |
| `outputs/model_results.json` | 553 | `cebaebc8a50616b6c00d879e6fcf82512f45ea2e0a2948cbb59ccb7b9f39088d` | N/A | `derived` | `permitted` | **MATCH** | **PASS** |
| `outputs/predictions.csv` | 1,574 | `c41372b64a4b49e15998df9a175e11dd4f4340d16be902cf7f8dbccaa19277b0` | 8 | `synthetic` | `permitted` | **MATCH** | **PASS** |
| `outputs/sentiment_agg.csv` | 102 | `001a18274d75fca92fceca47622dc3e7fa69956cc517f48e3cf247f1c1a96752` | 1 | `synthetic` | `permitted` | **MATCH** | **PASS** |
| `outputs/sentiment_items.csv` | 494 | `b78e1b5268c1605ee7a8c3d9fb3a0c598075747656910629a3a936a9b40097a8` | 2 | `synthetic` | `permitted` | **MATCH** | **PASS** |
| `outputs/shortlist.csv` | 428 | `9bfa487b32252cbe9b222cfdcf23bb89ffae78f0d96d9333902fbc89ca730a44` | 2 | `synthetic` | `permitted` | **MATCH** | **PASS** |
| `processed/feature_matrix.csv` | 1,126 | `3d4fba73491e0fe252062b8c5f2b87ff04f6990390ea002a281e8ebc31ec1907` | 8 | `synthetic` | `permitted` | **MATCH** | **PASS** |
| `processed/flows_category_month.csv` | 1,157 | `835a60a7e0d37e6f851509a244439cba91b05539ffb5e28a50f146a4d70b798f` | 8 | `synthetic` | `permitted` | **MATCH** | **PASS** |
| `processed/market_month.csv` | 197 | `ba84ca6c382f6e91122a7f58ef56b9c9f2ae9bfa9da598b98471018698ca1bb6` | 1 | `synthetic` | `permitted` | **MATCH** | **PASS** |
| `processed/nav_daily.csv` | 222 | `bdf5072051e9b28fe4112e2f3d2f2fa9eb0480bf13501a3cf8dff6e36d40d9d3` | 4 | `synthetic` | `permitted` | **MATCH** | **PASS** |
| `processed/scheme_master.csv` | 275 | `6798c56fa7eaef85672d0295fc0981e9f0e1329cbf9bf6007ec18b8719f9fe4c` | 2 | `synthetic` | `permitted` | **MATCH** | **PASS** |
| `quality_report.json` | 1,382 | `7fc13788ff3e36eec89eecb08f448b438aa677332c028a3014a68297fdb579e2` | N/A | `derived` | `permitted` | **MATCH** | **PASS** |
| `source_metadata.json` | 11,712 | `1f3640be2e0ae97f0a1334966601ea257125e16ec57cbbd083b4b8a7f058098c` | N/A | `derived` | `permitted` | **MATCH** | **PASS** |

---

## 4. Source Rights & Redistribution Audit

| Source ID | Source Name | Upstream Terms & Permissions | Redistribution Status | Public Release Decision & Evidence |
|---|---|---|---|---|
| `amfi_flows` | AMFI monthly flows | Personal non-commercial site use only. Prohibits publication and redistribution. | **Restricted** | **EXCLUDED** from public snapshot. Local raw/processed files remain gitignored. |
| `amfi_nav` | AMFI daily NAV | Personal non-commercial site use only. | **Restricted** | **EXCLUDED** from public snapshot. |
| `mfapi` | mfapi.in | Unofficial wrapper; no redistribution grant verified. | **Unknown** | **EXCLUDED** from public snapshot. |
| `nse_vix` | NSE India VIX | Subject to NSE commercial data agreement; automated collection prohibited. | **Restricted** | **EXCLUDED** from public snapshot. |
| `nifty_indices` | NSE Indices Nifty | Personal non-commercial use; copying and redistribution prohibited. | **Restricted** | **EXCLUDED** from public snapshot. |
| `yfinance` | Yahoo Finance | Unofficial wrapper; upstream terms personal use only. | **Restricted** | **EXCLUDED** from public snapshot. |
| `rbi_dbie` | RBI DBIE | Download brochure only; redistribution unverified. | **Unknown** | **EXCLUDED** from public snapshot. |
| `rbi_rss` | RBI RSS | RSS feed subscription; redistribution rights unverified. | **Unknown** | **EXCLUDED** from public snapshot. |
| `fed_rss` | Federal Reserve RSS | US Government Public Domain (excluding third-party logos). | **Permitted with conditions** | Permitted with attribution. |
| `gdelt` | GDELT | Academic, commercial, and government use permitted with citation. | **Permitted with conditions** | Permitted with attribution. |
| `prosus_finbert` | ProsusAI/finbert | CC-BY-NC-SA-4.0 (Non-commercial only). Weights excluded from repository. | **Restricted** | **EXCLUDED** from repository. Lexical fallback active. |
| `synthetic_demo` | Synthetic Fixtures | Generated by FundFlow Sentinel test harnesses. | **Permitted** | **INCLUDED** in snapshot; tagged `origin: synthetic`. |

---

## 5. Offline UI Verification Across All Pages

All 6 application pages were verified to render offline with `socket.create_connection` and `socket.socket.connect` hard-blocked via pytest monkeypatch:

| Page Path | Verified Offline Invariants | Result |
|---|---|---|
| [`app/Home.py`](file:///Users/anny/Desktop/mutual-fund/app/Home.py) | Renders Command Centre; displays `SYNTHETIC DEMO DATA`; metrics tagged `OBSERVED`/`FORECAST`/`SCENARIO` | **PASS** |
| [`app/pages/1_Forecast_Lab.py`](file:///Users/anny/Desktop/mutual-fund/app/pages/1_Forecast_Lab.py) | Displays central forecast vs persistence baseline; honest `INSUFFICIENT_HISTORY` banner for empirical bands | **PASS** |
| [`app/pages/2_Sentiment_Monitor.py`](file:///Users/anny/Desktop/mutual-fund/app/pages/2_Sentiment_Monitor.py) | Displays aggregate sentiment; enforces Source Distinction Mandate (RSS vs GDELT); sufficiency notice | **PASS** |
| [`app/pages/3_Fund_Research.py`](file:///Users/anny/Desktop/mutual-fund/app/pages/3_Fund_Research.py) | Displays shortlist preserving source order; mandatory survivorship bias and non-investment advice disclaimers | **PASS** |
| [`app/pages/4_Stress_Lab.py`](file:///Users/anny/Desktop/mutual-fund/app/pages/4_Stress_Lab.py) | Displays reference AUM proxy; multi-scenario breakdown; $>100\%$ asset capping notice; finance-safe narrative | **PASS** |
| [`app/pages/5_Evidence_and_Limits.py`](file:///Users/anny/Desktop/mutual-fund/app/pages/5_Evidence_and_Limits.py) | Renders data quality checks, source registry table, strict redistribution policy warning, 4 system disclaimers | **PASS** |

---

## 6. Last-Known-Good Safety & Transactional Rollback

Verified that transactional publishing prevents corruption of the active snapshot:
* During snapshot generation, all files and the manifest are assembled in a temporary versioned folder (`.tmp_snapshot_<id>`).
* Independent self-verification checks all SHA-256 digests, byte sizes, relative paths, and frozen contracts.
* If staging or verification fails, the staging directory is cleaned up and the previous active snapshot remains intact.
* Automated regression test [`test_transactional_publish_preserves_last_good_on_failure`](file:///Users/anny/Desktop/mutual-fund/tests/test_snapshots.py#L225) confirmed that simulated failures leave the active snapshot 100% accessible and uncorrupted.

---

## 7. Inventory of Files Changed in Wave 12

### Implementation & Orchestration:
* [`src/fundflow/snapshot.py`](file:///Users/anny/Desktop/mutual-fund/src/fundflow/snapshot.py) (Snapshot generation, verification, and transactional publishing)
* [`src/fundflow/cli.py`](file:///Users/anny/Desktop/mutual-fund/src/fundflow/cli.py) (Added `snapshot` subcommand with `--create` and `--verify` options)
* [`Makefile`](file:///Users/anny/Desktop/mutual-fund/Makefile) (Added `snapshot` target)

### Data Bundles & Metadata:
* [`data/snapshots/manifest.json`](file:///Users/anny/Desktop/mutual-fund/data/snapshots/manifest.json) (Version 1 manifest with 13 artifacts)
* [`data/snapshots/processed/`](file:///Users/anny/Desktop/mutual-fund/data/snapshots/processed/) (5 frozen contract tables, synthetic demo)
* [`data/snapshots/outputs/`](file:///Users/anny/Desktop/mutual-fund/data/snapshots/outputs/) (5 frozen contract tables + `model_results.json`, synthetic demo)
* [`data/snapshots/quality_report.json`](file:///Users/anny/Desktop/mutual-fund/data/snapshots/quality_report.json) (Quality report envelope)
* [`data/snapshots/source_metadata.json`](file:///Users/anny/Desktop/mutual-fund/data/snapshots/source_metadata.json) (Source governance registry envelope)

### Tests:
* [`tests/test_snapshots.py`](file:///Users/anny/Desktop/mutual-fund/tests/test_snapshots.py) (20 dedicated snapshot and offline tests)

### Documentation:
* [`README.md`](file:///Users/anny/Desktop/mutual-fund/README.md) (Complete overhaul reflecting full 12 waves)
* [`data/README.md`](file:///Users/anny/Desktop/mutual-fund/data/README.md) (Data boundaries, licensing ledger, snapshot regeneration)
* [`docs/USER_GUIDE.md`](file:///Users/anny/Desktop/mutual-fund/docs/USER_GUIDE.md) (Comprehensive end-user and operational manual)
* [`docs/ARCHITECTURE.md`](file:///Users/anny/Desktop/mutual-fund/docs/ARCHITECTURE.md) (System architecture specification with Mermaid diagram)
* [`docs/WAVE_12_PREFLIGHT.md`](file:///Users/anny/Desktop/mutual-fund/docs/WAVE_12_PREFLIGHT.md) (Pre-flight audit report)
* [`docs/WAVE_12_SNAPSHOT_VALIDATION.md`](file:///Users/anny/Desktop/mutual-fund/docs/WAVE_12_SNAPSHOT_VALIDATION.md) (Agent A report)
* [`docs/WAVE_12_DOCS_VALIDATION.md`](file:///Users/anny/Desktop/mutual-fund/docs/WAVE_12_DOCS_VALIDATION.md) (Agent B report)
* [`docs/WAVE_12_VALIDATION.md`](file:///Users/anny/Desktop/mutual-fund/docs/WAVE_12_VALIDATION.md) (This authoritative gate report)

---

## 8. Final Release Gate Decision

**RELEASE DECISION: PASS FOR AN OFFLINE PUBLIC DEMO**

The FundFlow Sentinel repository satisfies all Wave 12 requirements:
1. **Clean Checkout Reproducibility:** A clean clone can install dependencies, pass all 287 automated tests, publish or verify the snapshot, and launch the offline demo app without network access.
2. **Strict Licensing Compliance:** No prohibited, unverified, or restricted data are included in public snapshots. All demo data are explicitly tagged synthetic with prominent UI banners.
3. **Transactional Safety:** Active snapshots survive refresh and staging failures without corruption.
4. **Factual Documentation:** System architecture, methodology, empirical limitations, and user guides describe current reality with zero unsupported performance or predictive claims.
