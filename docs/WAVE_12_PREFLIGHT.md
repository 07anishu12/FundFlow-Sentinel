# Wave 12 Pre-Flight Audit & Baseline Verification

**Date:** 2026-10-29  
**Lead Auditor / Integrator:** Senior Quantitative Research & Data Platform Lead  
**Scope:** Wave 12 — Offline Release & Clear Documentation (Prompts 25 & 26)  
**Baseline Wave 11 Status:** **PASS** (Confirmed via [`docs/WAVE_11_VALIDATION.md`](file:///Users/anny/Desktop/mutual-fund/docs/WAVE_11_VALIDATION.md))

---

## 1. Environment & Repository Baseline

* **Working Tree State:** Clean local workspace on branch `main` (untracked file set intact, no uncommitted merge conflicts).
* **Python Runtime:** Python `3.11.16` (`.venv/bin/python`)
* **Pytest Version:** `pytest 8.3.5`
* **Baseline Test Runs:**
  * `make validate`: **32 passed in 0.36s** (exit code 0)
  * `make test`: **267 passed in 6.95s** (exit code 0) across 18 test files
* **Frozen Contracts:** Confirmed 10 frozen contracts intact in [`src/fundflow/contracts.py`](file:///Users/anny/Desktop/mutual-fund/src/fundflow/contracts.py) with zero unauthorised schema mutations.

---

## 2. Empirical Data Sufficiency Audit

Inspection of current repository data files under `data/processed/` and `data/outputs/`:

| Dataset Path | Rows | Period Range | Categories / Assets | Empirical Sufficiency Status |
|---|---|---|---|---|
| [`data/processed/flows_category_month.csv`](file:///Users/anny/Desktop/mutual-fund/data/processed/flows_category_month.csv) | 8 | `2024-09` (1 month) | 8 categories | **1 month only** — cannot support 36M warm-up |
| [`data/processed/market_month.csv`](file:///Users/anny/Desktop/mutual-fund/data/processed/market_month.csv) | 61 | `2019-09` to `2024-09` | Macro/indices (61 months) | Sufficient market context; does not replace flow history |
| [`data/processed/feature_matrix.csv`](file:///Users/anny/Desktop/mutual-fund/data/processed/feature_matrix.csv) | 8 | `2024-09` (1 month) | 8 categories | Minimal 1-period feature matrix |
| [`data/outputs/predictions.csv`](file:///Users/anny/Desktop/mutual-fund/data/outputs/predictions.csv) | 8 | Target: `2024-09` | 8 categories | Inferred predictions; residual bands `insufficient_history` |
| [`data/outputs/alerts.csv`](file:///Users/anny/Desktop/mutual-fund/data/outputs/alerts.csv) | 8 | `2024-09` | 8 categories | Rule-evaluated alerts (1 Elevated, 7 Normal) |
| [`data/outputs/shortlist.csv`](file:///Users/anny/Desktop/mutual-fund/data/outputs/shortlist.csv) | 2 | As-of `2024-09-30` | 2 Direct-Growth schemes | Standalone NAV ranking shortlist |
| [`data/outputs/sentiment_agg.csv`](file:///Users/anny/Desktop/mutual-fund/data/outputs/sentiment_agg.csv) | 1 | `2024-09-30` | 1 daily aggregate | Context-only aggregate |

**Data Integrity Invariant:** Market history does not substitute for missing flow history. Walk-forward empirical residual bands, 24-month anomaly scores, and historical worst-case calibrations are honestly flagged as `insufficient_history` in empirical evaluation.

---

## 3. Source Licensing & Redistribution Ledger Audit

Inspection of [`config/sources.yaml`](file:///Users/anny/Desktop/mutual-fund/config/sources.yaml) determines what data may legally be bundled in a public offline release snapshot:

| Source Identifier | Source Name | Terms of Use / License Status | Redistribution Status | Public Release Action |
|---|---|---|---|---|
| `amfi_flows` | AMFI monthly flows | Personal non-commercial access only; no publication/redistribution | **Restricted** | **EXCLUDE raw/processed files from public snapshot** |
| `amfi_nav` | AMFI NAV | Personal non-commercial site use | **Restricted** | **EXCLUDE raw/processed files from public snapshot** |
| `mfapi` | mfapi.in | Unofficial wrapper; no redistribution grant verified | **Unknown** | **EXCLUDE from public snapshot** |
| `nse_vix` | NSE India VIX | Subject to NSE data agreement; automated collection prohibited | **Restricted** | **EXCLUDE from public snapshot** |
| `nifty_indices` | NSE Indices Nifty | Personal non-commercial use; redistribution prohibited | **Restricted** | **EXCLUDE from public snapshot** |
| `yfinance` | Yahoo Finance | Unofficial wrapper; upstream terms personal use only | **Restricted** | **EXCLUDE from public snapshot** |
| `rbi_dbie` | RBI DBIE | Download brochure only; redistribution unverified | **Unknown** | **EXCLUDE from public snapshot** |
| `rbi_rss` | RBI RSS | RSS feed subscription; redistribution unverified | **Unknown** | **EXCLUDE from public snapshot** |
| `fed_rss` | Federal Reserve RSS | US Gov Public Domain (with conditions on logos/third-party) | **Permitted with conditions** | Permitted with attribution |
| `gdelt` | GDELT | Commercial/academic/gov permitted with citation/link | **Permitted with conditions** | Permitted with attribution |
| `prosus_finbert` | ProsusAI/finbert | CC-BY-NC-SA-4.0 | **Restricted** | **EXCLUDE model weights from repository** |
| `finbert_tone` | yiyanghkust/finbert-tone | No explicit license grant found in model card | **Unknown** | **EXCLUDE from repository** |
| `vader` | VADER | MIT License | **Permitted with conditions** | Permitted with MIT notice |
| `synthetic_demo` | Synthetic Fixtures | Fully owned synthetic mock data generated by project | **Permitted** | **PERMITTED; labeled `origin: synthetic`** |

**Mandatory License Rule:** Any dataset classified as `restricted` or `unknown` must NOT be bundled in public snapshots under `data/snapshots/`. The public offline demo snapshot must contain exclusively licence-permitted synthetic demo data (`origin: synthetic`) and permitted derived metadata, with prominent UI warning banners (`SYNTHETIC DEMO DATA`).

---

## 4. Work Breakdown & Disjoint File Ownership

### Agent A (Prompt 25 — Snapshot Generation & Data Packaging):
* **Files Owned:**
  * `src/fundflow/snapshot.py` (Snapshot creation, verification, and transactional publishing)
  * `src/fundflow/cli.py` (Integration of `snapshot` subcommand)
  * `tests/test_snapshots.py` (Dedicated adversarial snapshot tests)
  * `data/snapshots/manifest.json` (Validated machine-readable manifest with provenance)
  * `data/README.md` (Data provenance, license decisions, excluded datasets, regeneration guide)
  * `docs/WAVE_12_SNAPSHOT_VALIDATION.md` (Agent A completion report)
* **Invariants Enforced:**
  * Transactional staging via temporary directory (`data/snapshots/.tmp_snapshot_<id>`).
  * Atomic directory replacement preserving last-known-good on failure.
  * SHA-256 and byte-size verification for every artifact.
  * Explicit `origin: "synthetic"`, `source_id: "synthetic:not-a-source"`, and `redistribution: "permitted"` for demo artifacts.
  * Rejection of path traversal, absolute paths, missing artifacts, and unpermitted data.

### Agent B (Prompt 26 — Repository-Accurate Documentation):
* **Files Owned:**
  * `README.md` (Project overview, feature map, tested setup, boundaries, quickstart)
  * `docs/USER_GUIDE.md` (Workflow guide, 6 page walkthroughs, labels, offline demo, troubleshooting)
  * `docs/ARCHITECTURE.md` (Complete system architecture, Mermaid data-flow diagram, module separation)
  * `docs/WAVE_12_DOCS_VALIDATION.md` (Agent B completion report)
* **Invariants Enforced:**
  * 100% adherence to actual implemented code and generated artifacts.
  * Accurate disclosure of 1-month flow data sufficiency vs 61-month market data.
  * Complete AST and import isolation of ranking from flow/forecasting/alert models.
  * Mandatory disclaimer: analytical decision support, non-investment advice, non-liquidity assurance.

### Integrator / Lead Auditor:
* **Files Owned:**
  * `docs/WAVE_12_PREFLIGHT.md` (This document)
  * `docs/WAVE_12_VALIDATION.md` (Authoritative final release gate report)
* **Responsibilities:**
  * Shared contract freeze preservation.
  * Independent verification of manifest SHA-256 digests and offline execution with hard-blocked sockets.
  * Validation of transactional rollback and last-good safety.
