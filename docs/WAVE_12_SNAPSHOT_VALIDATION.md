# Wave 12 Snapshot Validation & Data Packaging Report

**Date:** 2026-10-29  
**Owner:** Agent A (Data Engineering & Offline Snapshot Architecture)  
**Scope:** Wave 12 Prompt 25 — Licence-Safe, Offline Demo Snapshots  
**Status:** **PASS — ALL INVARIANTS SATISFIED; 20 DEDICATED SNAPSHOT TESTS PASSED**

---

## 1. Executive Summary

Agent A implemented a reproducible, compact, licence-aware offline demo snapshot workflow under [`data/snapshots/`](file:///Users/anny/Desktop/mutual-fund/data/snapshots/) and CLI integration via `fundflow snapshot`:

1. **Licence Compliance & Exclusion of Restricted Datasets:**
   - In accordance with [`config/sources.yaml`](file:///Users/anny/Desktop/mutual-fund/config/sources.yaml), all restricted and unverified third-party sources (AMFI monthly flows, AMFI NAV, NSE India VIX, Nifty Indices, yfinance, and Prosus FinBERT weights) are **excluded** from public snapshot distribution.
   - The public demo snapshot contains **exclusively licence-permitted synthetic demo data** (`origin: synthetic`) and derived governance envelopes (`origin: derived`).
   - Every file carries an unambiguous machine-readable redistribution declaration (`redistribution: "permitted"`).
2. **Complete 10-Contract Offline Coverage:**
   - Packages all 10 frozen contract tables across `processed/` and `outputs/`, plus all 3 JSON artifact envelopes (`quality_report.json`, `source_metadata.json`, and `outputs/model_results.json`).
   - All 6 application pages render cleanly from the snapshot without live network access.
3. **Deterministic Manifest with SHA-256 Digests:**
   - Published [`data/snapshots/manifest.json`](file:///Users/anny/Desktop/mutual-fund/data/snapshots/manifest.json) includes schema version 1, ISO UTC timestamp, exact generation command, snapshot ID, sorted table lists, and per-artifact digests, sizes, and row counts.
4. **Transactional Publishing & Last-Good Preservation:**
   - Snapshots are staged in `.tmp_snapshot_<id>`, validated for hash integrity and contract conformity, and swapped atomically.
   - Verified that failures during staging or validation never corrupt or delete the existing last-known-good snapshot.

---

## 2. Command Execution Evidence

| Command Line | Working Directory | Exit Code | Execution Time | Output Summary |
|---|---|---|---|---|
| `make snapshot` | `/Users/anny/Desktop/mutual-fund` | 0 | 0.92s | Successfully staged, validated, and published snapshot to `data/snapshots/` |
| `.venv/bin/python -m fundflow.cli snapshot --verify` | `/Users/anny/Desktop/mutual-fund` | 0 | 0.45s | Independent verification of all 13 artifacts against `manifest.json` |
| `.venv/bin/python -m pytest -q tests/test_snapshots.py` | `/Users/anny/Desktop/mutual-fund` | 0 | 0.86s | **20 passed** (integrity, traversal rejection, transactional safety, offline UI) |
| `make test` | `/Users/anny/Desktop/mutual-fund` | 0 | 5.75s | **287 passed** across 19 test files (full suite) |

---

## 3. Snapshot Artifact Inventory & Integrity Manifest

Independent audit of artifacts declared in [`data/snapshots/manifest.json`](file:///Users/anny/Desktop/mutual-fund/data/snapshots/manifest.json):

| Relative Path | Byte Size | SHA-256 Digest | Rows | Origin | Redistribution Status |
|---|---|---|---|---|---|
| `outputs/alerts.csv` | 2,007 | `4c8d33ca233a7e446554b73108ce8a3d76e73cba5b66d54620f5c531398867a5` | 8 | `synthetic` | `permitted` |
| `outputs/model_results.json` | 553 | `cebaebc8a50616b6c00d879e6fcf82512f45ea2e0a2948cbb59ccb7b9f39088d` | N/A | `derived` | `permitted` |
| `outputs/predictions.csv` | 1,574 | `c41372b64a4b49e15998df9a175e11dd4f4340d16be902cf7f8dbccaa19277b0` | 8 | `synthetic` | `permitted` |
| `outputs/sentiment_agg.csv` | 102 | `001a18274d75fca92fceca47622dc3e7fa69956cc517f48e3cf247f1c1a96752` | 1 | `synthetic` | `permitted` |
| `outputs/sentiment_items.csv` | 494 | `b78e1b5268c1605ee7a8c3d9fb3a0c598075747656910629a3a936a9b40097a8` | 2 | `synthetic` | `permitted` |
| `outputs/shortlist.csv` | 428 | `9bfa487b32252cbe9b222cfdcf23bb89ffae78f0d96d9333902fbc89ca730a44` | 2 | `synthetic` | `permitted` |
| `processed/feature_matrix.csv` | 1,126 | `3d4fba73491e0fe252062b8c5f2b87ff04f6990390ea002a281e8ebc31ec1907` | 8 | `synthetic` | `permitted` |
| `processed/flows_category_month.csv` | 1,157 | `835a60a7e0d37e6f851509a244439cba91b05539ffb5e28a50f146a4d70b798f` | 8 | `synthetic` | `permitted` |
| `processed/market_month.csv` | 197 | `ba84ca6c382f6e91122a7f58ef56b9c9f2ae9bfa9da598b98471018698ca1bb6` | 1 | `synthetic` | `permitted` |
| `processed/nav_daily.csv` | 222 | `bdf5072051e9b28fe4112e2f3d2f2fa9eb0480bf13501a3cf8dff6e36d40d9d3` | 4 | `synthetic` | `permitted` |
| `processed/scheme_master.csv` | 275 | `6798c56fa7eaef85672d0295fc0981e9f0e1329cbf9bf6007ec18b8719f9fe4c` | 2 | `synthetic` | `permitted` |
| `quality_report.json` | 1,382 | `7fc13788ff3e36eec89eecb08f448b438aa677332c028a3014a68297fdb579e2` | N/A | `derived` | `permitted` |
| `source_metadata.json` | 11,712 | `1f3640be2e0ae97f0a1334966601ea257125e16ec57cbbd083b4b8a7f058098c` | N/A | `derived` | `permitted` |

* **Total Artifacts:** 13 files (10 CSV tables, 3 JSON artifact envelopes).
* **Hash Integrity:** 100% verified; zero digest mismatches.
* **Contract Compliance:** 100% of CSV tables validate against [`src/fundflow/contracts.py:COLUMNS`](file:///Users/anny/Desktop/mutual-fund/src/fundflow/contracts.py#L3).

---

## 4. Source Rights & Redistribution Audit

Based on [`config/sources.yaml`](file:///Users/anny/Desktop/mutual-fund/config/sources.yaml), every source is classified:

| Source ID | Source Name | Upstream Terms & Redistribution Status | Public Release Action & Evidence |
|---|---|---|---|
| `amfi_flows` | AMFI monthly flows | **Restricted:** Terms prohibit publication, derivative works, and redistribution. | **EXCLUDED** from public snapshot. Local files in `data/raw/` and `data/processed/` are gitignored. |
| `amfi_nav` | AMFI daily NAV | **Restricted:** Personal non-commercial site use only. | **EXCLUDED** from public snapshot. |
| `mfapi` | mfapi.in | **Unknown:** Unofficial wrapper; no redistribution rights verified. | **EXCLUDED** from public snapshot. |
| `nse_vix` | NSE India VIX | **Restricted:** Commercial data policy; automated access prohibited. | **EXCLUDED** from public snapshot. |
| `nifty_indices` | NSE Indices Nifty | **Restricted:** Terms prohibit redistribution and copying. | **EXCLUDED** from public snapshot. |
| `yfinance` | Yahoo Finance | **Restricted:** Upstream terms specify personal use only. | **EXCLUDED** from public snapshot. |
| `rbi_dbie` | RBI DBIE | **Unknown:** Redistribution permissions unverified. | **EXCLUDED** from public snapshot. |
| `rbi_rss` | RBI RSS | **Unknown:** Reuse rights unverified. | **EXCLUDED** from public snapshot. |
| `fed_rss` | Federal Reserve RSS | **Permitted with conditions:** US Gov Public Domain (with attribution). | Permitted with attribution. |
| `gdelt` | GDELT | **Permitted with conditions:** Permitted with citation. | Permitted with attribution. |
| `prosus_finbert` | ProsusAI/finbert | **Restricted:** CC-BY-NC-SA-4.0. Model weights excluded from repository. | **EXCLUDED** from repository. Lexical fallback active. |
| `synthetic_demo` | Synthetic Fixtures | **Permitted:** Created by project test generators. | **INCLUDED** in snapshot; explicitly tagged `origin: synthetic`. |

---

## 5. Transactional Rollback & Last-Good Safety Verification

Transactional publishing safety was verified through adversarial automated tests in [`tests/test_snapshots.py`](file:///Users/anny/Desktop/mutual-fund/tests/test_snapshots.py):
1. **Staging Isolation:** Files are staged into `.tmp_snapshot_<id>`, isolated from active snapshot paths.
2. **Pre-Publish Verification:** If verification fails during staging (e.g., checksum mismatch, missing file, or schema error), the staging folder is wiped and the active snapshot remains untouched.
3. **Atomic Swap:** Directory rename on POSIX platforms swaps staging to active in a single filesystem operation, with automatic rollback from backup if an error occurs.
4. **Fixture Directory Preservation:** Existing legacy unit test fixtures under `data/snapshots/fixtures/` are preserved during snapshot refreshes.

---

## 6. Offline UI Execution Evidence

Offline UI rendering was validated across all 6 Streamlit pages with `socket.create_connection` and `socket.socket.connect` hard-blocked via pytest monkeypatch:
* [`app/Home.py`](file:///Users/anny/Desktop/mutual-fund/app/Home.py) — **PASS**
* [`app/pages/1_Forecast_Lab.py`](file:///Users/anny/Desktop/mutual-fund/app/pages/1_Forecast_Lab.py) — **PASS**
* [`app/pages/2_Sentiment_Monitor.py`](file:///Users/anny/Desktop/mutual-fund/app/pages/2_Sentiment_Monitor.py) — **PASS**
* [`app/pages/3_Fund_Research.py`](file:///Users/anny/Desktop/mutual-fund/app/pages/3_Fund_Research.py) — **PASS**
* [`app/pages/4_Stress_Lab.py`](file:///Users/anny/Desktop/mutual-fund/app/pages/4_Stress_Lab.py) — **PASS**
* [`app/pages/5_Evidence_and_Limits.py`](file:///Users/anny/Desktop/mutual-fund/app/pages/5_Evidence_and_Limits.py) — **PASS**

Every page displays the mandatory `SYNTHETIC DEMO DATA` warning banner.

---

## 7. Deliverables & File Inventory

* **Implementation:** [`src/fundflow/snapshot.py`](file:///Users/anny/Desktop/mutual-fund/src/fundflow/snapshot.py)
* **CLI Integration:** [`src/fundflow/cli.py`](file:///Users/anny/Desktop/mutual-fund/src/fundflow/cli.py) (`fundflow snapshot --create` / `--verify`)
* **Build Target:** [`Makefile`](file:///Users/anny/Desktop/mutual-fund/Makefile) (`make snapshot`)
* **Manifest:** [`data/snapshots/manifest.json`](file:///Users/anny/Desktop/mutual-fund/data/snapshots/manifest.json)
* **Data Documentation:** [`data/README.md`](file:///Users/anny/Desktop/mutual-fund/data/README.md)
* **Dedicated Test Suite:** [`tests/test_snapshots.py`](file:///Users/anny/Desktop/mutual-fund/tests/test_snapshots.py) (20 tests)
* **Validation Report:** [`docs/WAVE_12_SNAPSHOT_VALIDATION.md`](file:///Users/anny/Desktop/mutual-fund/docs/WAVE_12_SNAPSHOT_VALIDATION.md) (This document)
