# Wave 4 Validation Record: Validated Flow Data & Market Context

**Date:** 2026-10-28  
**Environment:** Python 3.11.16 (`.venv`), macOS  
**Scope:** Parallel execution of Prompt 09 (Agent A: Flow validation & quality gate) and Prompt 10 (Agent B: Market ingestion & monthly features)  
**Status:** **PASSED & APPROVED BY LEAD (Wave 4 Gate Cleared)**  

---

## 1. Executive Summary

Wave 4 established the validated data layer and market context required for downstream modeling:

1. **Prompt 09 (Agent A — Flow Validation & Quality Gate):**
   - Implemented `src/fundflow/validate.py` providing `validate_flows(raw)` and `save_validated_flows()`.
   - Normalizes raw category names against the canonical `config/category_map.csv`.
   - Enforces strict non-leakage availability: any row where `available_from` is on or before period-end hard-fails with `ValueError`.
   - Implements a conservative fallback availability policy (12th of month $T+1$ at 00:00:00Z).
   - Detects gaps within each category and reports them explicitly in `quality_report.json`; never hides missing months through silent interpolation.
   - Hard-fails on duplicate keys `(month, category)`, absent gross redemptions, ambiguous units, or unmapped categories entering the modeling universe.
   - Implements snapshot preservation on failed refresh.
   - Covered by 10 unit tests in `tests/test_flow_validation.py`.

2. **Prompt 10 (Agent B — Market Ingestion & Monthly Features):**
   - Implemented `src/fundflow/ingest/market.py` aggregating daily Nifty 50 and India VIX observations into monthly indicators (`market_month.csv`).
   - Implements exact formulas:
     - `nifty_return`: Monthly return percentage points: $\frac{P_{\text{last}} - P_{\text{first}}}{P_{\text{first}}} \times 100$.
     - `nifty_drawdown_3m`: 3-month peak-to-trough percentage drawdown: $\frac{P_{\text{last}} - \max(P_{3\text{m}})}{\max(P_{3\text{m}})} \times 100$.
     - `vix_mean`: Monthly mean of closing India VIX.
     - `vix_change`: Monthly net change in closing India VIX.
     - `available_from`: Conservative cutoff at 1st of month $T+1$ at 00:00:00Z.
   - Enforces optional-feature policy: falls back to verified snapshots on network failure, never zero-fills missing features as a hidden shortcut, and records wrapper provenance (`yfinance (unofficial wrapper)`).
   - Covered by 6 unit tests in `tests/test_market.py`.

3. **Total Test Suite:**
   - 133 automated unit and contract tests passing (`make validate` and `make test`).

---

## 2. Ingestion & Validation Contracts Verification

| Dataset / Table | Module / Function | Output Path | Key Invariants Enforced |
|---|---|---|---|
| `flows_category_month` | `validate.validate_flows` | `data/processed/flows_category_month.csv` | Exactly one row per `(month, category)`; non-leakage `available_from > period_end`; gap tracking without interpolation; observed gross redemption requirement. |
| `quality_report` | `validate.save_validated_flows` | `data/quality_report.json` | Approved JSON envelope (version 1, source, generated_at, status, checks, coverage, exclusions, missingness, unmapped labels, source dates). |
| `market_month` | `market.fetch_and_build_market_month` | `data/processed/market_month.csv` | Monthly return, 3M drawdown, VIX mean/change; conservative $T+1$ cutoff; optional-feature snapshot fallback; no zero-fills. |

---

## 3. Empirical Ingestion Runs & Output Proofs

### 3.1 Flow Validation Run
- Input: Parsed AMFI reports across FY2018–19 to FY2026–27.
- Validation checks passed:
  - `schema_columns`: All 10 frozen columns present in exact order.
  - `units_inr_crore`: All monetary values confirmed finite INR crore.
  - `category_universe`: Active universe (`Large Cap`, `Mid Cap`, `Small Cap`, `Flexi Cap`, `Aggressive Hybrid`, `Corporate Bond`) validated.
  - `duplicate_keys`: Zero duplicate `(month, category)` keys.
  - `available_from_non_leakage`: All release dates strictly post-month-end.
  - `gross_redemption_observed`: All gross redemptions observed; zero inferred.
- Output files written:
  - `data/processed/flows_category_month.csv`
  - `data/quality_report.json`
  - `data/manifest.json`

### 3.2 Market Ingestion Run
- Ingested 61 monthly observations (5 years of daily history).
- Sample output rows:
  ```
  month,nifty_return,nifty_drawdown_3m,vix_mean,vix_change,available_from,source_name,retrieved_at
  2026-08,-2.8009,-2.8009,11.4833,-0.74,2026-09-01T00:00:00Z,yfinance (unofficial wrapper),2026-10-28T17:39:37Z
  2026-09,-5.9668,-8.6939,11.9890,2.00,2026-10-01T00:00:00Z,yfinance (unofficial wrapper),2026-10-28T17:39:37Z
  2026-10,1.2350,-8.3774,15.0758,1.785,2026-11-01T00:00:00Z,yfinance (unofficial wrapper),2026-10-28T17:39:37Z
  ```
- Output files written:
  - `data/processed/market_month.csv`
  - `data/snapshots/fixtures/market_month.csv`

---

## 4. Test Suite Summary

Executed command: `.venv/bin/pytest -q`
```
........................................................................ [ 54%]
.............................................................            [100%]
133 passed in 5.14s
```

Breakdown:
- `tests/test_flow_validation.py`: 10 passed (non-leakage, conservative availability, duplicate rejection, gap detection, unmapped universe hard-fail, snapshot fallback)
- `tests/test_market.py`: 6 passed (monthly aggregation, known-series math, conservative cutoff, snapshot fallback, no zero-fills)
- `tests/test_amfi_flows.py`: 15 passed (AMFI parser, format sniffing, modern/legacy layouts)
- `tests/test_nav_ingest.py`: 9 passed (scheme master, null riskometer, chunking, dedup, error isolation)
- `tests/test_contracts.py`: 32 passed (frozen schemas, value domains, config validations)
- `tests/test_registry.py`: 16 passed (provenance, ledger append, atomic replacement)
- `tests/test_app_loaders.py`: 28 passed (loader boundaries, typed loaders, freshness, safe paths)
- `tests/test_app_shell.py`: 17 passed (offline app execution, empty states, AST import checks)

Executed command: `make validate && make test`
```
.venv/bin/python -m pytest -q tests/test_contracts.py
................................                                         [100%]
32 passed in 0.20s
.venv/bin/python -m pytest -q
........................................................................ [ 54%]
.............................................................            [100%]
133 passed in 5.14s
```

---

## 5. Wave 4 Gate — Lead Decision

**APPROVAL GRANTED:**
1. **Row Counts & Period Coverage:** Processed flows and market indicators meet contract schemas and period boundaries.
2. **Units & Non-Leakage:** INR crore units confirmed; `available_from` strictly post-month-end in all records.
3. **Snapshot Fallback:** Failed refreshes preserve existing outputs; missing market series use snapshot fallback without zero-filling.
4. **Next Dependency:** Wave 5 (Feature engineering & baseline redemption rate calculations) may proceed.
