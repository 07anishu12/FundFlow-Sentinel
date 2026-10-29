# Wave 3 Validation Record: Independent Data Feeds (AMFI Flows & NAV)

**Date:** 2026-10-28  
**Environment:** Python 3.11.16 (`.venv`), macOS  
**Scope:** Parallel execution of Prompt 07 (Agent A: AMFI monthly flow ingestion) and Prompt 08 (Agent B: NAV and Scheme Master ingestion)  
**Status:** **PASSED & APPROVED BY LEAD (Wave 3 Gate Cleared)**  

---

## 1. Executive Summary

Wave 3 implemented production-grade data ingestion feeds grounded in the empirical inspection findings from Wave 2:

1. **Prompt 07 (Agent A — AMFI Monthly Flow Ingestion):**
   - Implemented `src/fundflow/ingest/amfi_flows.py` featuring bounded polite downloading, SHA-256 hash registration, format sniffing (OOXML vs BIFF8), and layout-specific parsing adapters.
   - Supports Modern single-sheet layout (OOXML/BIFF8, 2019-04 to present) and Legacy multi-sheet layout (`sales` + `red+assets`, 2018-04 to 2019-03).
   - Strictly enforces that raw files remain untouched under `data/raw/amfi/`.
   - Never infers gross redemption from net flows.
   - Enforces units confirmation (INR in crore) and evidence-backed non-leakage publication availability (`available_from`).
   - Covered by 15 tests in `tests/test_amfi_flows.py`.

2. **Prompt 08 (Agent B — NAV & Scheme Master Ingestion):**
   - Implemented `src/fundflow/ingest/nav.py` as an isolated research data lane.
   - Parses official AMFI scheme master (`NAVAll.txt`) without inferring `riskometer` values from scheme names (left null as per contract).
   - Formulates daily NAV queries across chunked date windows (<=90 days) and deduplicates overlaps across chunk boundaries.
   - Supports both official AMFI endpoints and labelled, cached unofficial wrapper (`mfapi.in`).
   - Documents survivorship bias in returned metadata.
   - Degrades gracefully on network/upstream failures without breaking P0 flow forecasting.
   - Covered by 9 tests in `tests/test_nav_ingest.py`.

3. **Total Test Suite:**
   - 117 automated unit and contract tests passing in 3.3s (`make validate` and `make test`).

---

## 2. Ingestion Contracts Verification

Feed outputs conform strictly to frozen contracts in `src/fundflow/contracts.py`:

| Dataset / Table | Ingest Function | Columns Verified | Key Invariants Enforced |
|---|---|---|---|
| `flows_category_month` | `amfi_flows.parse_report` | `month, category, gross_inflow_cr, gross_redemption_cr, net_flow_cr, aum_close_cr, aaum_cr, available_from, source_url, retrieved_at` | Format sniffing; untampered source bytes; unit confirmation; non-leakage `available_from`; zero gross redemption inference; exact arithmetic verification. |
| `nav_daily` | `nav.fetch_nav_history` | `date, scheme_code, nav, source_url` | 90-day chunked windows; overlap deduplication; positive finite NAV; wrapper provenance labelling (`mfapi.in` vs `AMFI`). |
| `scheme_master` | `nav.fetch_scheme_master` | `scheme_code, scheme_name, fund_house, category, plan_type, option_type, riskometer` | Null `riskometer` (no name inference); deduplicated `scheme_code`; survivorship bias disclosure attached to metadata. |

---

## 3. Empirical Ingestion Runs & Output Proofs

### 3.1 Real AMFI Flow Report Ingestion (Prompt 07)
The following official AMFI reports were retrieved and parsed into `flows_category_month`:

1. **September 2024 Report (`amsep2024repo.xls` - Modern OOXML):**
   - Source URL: `https://portal.amfiindia.com/spages/amsep2024repo.xls`
   - SHA-256: `46c6a1fdebe4aa81dcf84e6f6b9f5259f15fd9f7cf9778ea14e06ba209dc26d0`
   - Release Evidence: In-sheet `Released on 10-Oct-2024` $\rightarrow$ `available_from: 2024-10-10T00:00:00Z`
   - Mapped Categories: Overnight, Liquid, Corporate Bond, Large Cap, Mid Cap, Small Cap, Flexi Cap, Aggressive Hybrid
   - Sample Extracted Row (`Large Cap`):
     - `gross_inflow_cr`: ₹5,865.86 cr
     - `gross_redemption_cr`: ₹4,096.44 cr
     - `net_flow_cr`: ₹1,769.42 cr
     - `aum_close_cr`: ₹379,010.08 cr
     - `aaum_cr`: ₹374,132.40 cr

2. **September 2026 Report (`amsep2026repo.xls` - Modern BIFF8):**
   - Source URL: `https://portal.amfiindia.com/spages/amsep2026repo.xls`
   - SHA-256: `b1daaaf1a8c71260c10e9056272bebf7f3367559ac66d5ad5d6d0ec8a9f09967`
   - Release Evidence: HTTP Last-Modified `2026-10-12T06:10:10Z` $\rightarrow$ `available_from: 2026-10-12T06:10:10Z`
   - Sample Extracted Row (`Large Cap`):
     - `gross_inflow_cr`: ₹5,087.85 cr
     - `gross_redemption_cr`: ₹4,228.38 cr
     - `net_flow_cr`: ₹859.47 cr
     - `aum_close_cr`: ₹390,384.40 cr

3. **September 2018 Report (`amsep2018repo.xls` - Legacy Multi-Sheet BIFF8):**
   - Source URL: `https://portal.amfiindia.com/spages/amsep2018repo.xls`
   - SHA-256: `b43158e5e02a820cd13d65cf30e0d2a9a17e1f78d3ca80d960e3f6054c119c9b`
   - Sheets joined: `sales`, `red+assets`
   - Extracted `Liquid` category: `gross_inflow_cr: ₹1,627,150.00`, `gross_redemption_cr: ₹1,838,200.00`, `net_flow_cr: -₹211,050.00`, `aum_close_cr: ₹394,774.00`.

### 3.2 Real NAV & Scheme Master Ingestion (Prompt 08)
1. **Scheme Master (`NAVAll.txt`):**
   - Parsed 14,418 live schemes from official AMFI feed.
   - Exact schema validated with 0 null constraint violations.
   - All `riskometer` fields kept null (`""`).
2. **NAV History (`mfapi.in` wrapper & AMFI historical):**
   - Successfully retrieved, parsed, and cached daily series.
   - Chunked requests deduplicated on `(date, scheme_code)` without duplicates.

---

## 4. Test Suite Summary

Executed command: `.venv/bin/pytest -q`
```
........................................................................ [ 61%]
.............................................                            [100%]
117 passed in 3.32s
```

Breakdown:
- `tests/test_amfi_flows.py`: 15 passed (format detection, modern/legacy layout parsing, malformed handling, no gross inference, hash immutability)
- `tests/test_nav_ingest.py`: 9 passed (scheme master parsing, null riskometer, survivorship disclosure, date chunking, overlap dedup, graceful failure)
- `tests/test_contracts.py`: 32 passed (frozen schema contracts, value domain checks, config validations)
- `tests/test_registry.py`: 16 passed (provenance, ledger append, atomic replacement)
- `tests/test_app_loaders.py`: 28 passed (loader boundaries, typed loaders, freshness, safe paths)
- `tests/test_app_shell.py`: 17 passed (offline app execution, empty states, AST import checks)

Executed command: `make validate && make test`
```
.venv/bin/python -m pytest -q tests/test_contracts.py
................................                                         [100%]
32 passed in 0.19s
.venv/bin/python -m pytest -q
........................................................................ [ 61%]
.............................................                            [100%]
117 passed in 3.32s
```

---

## 5. Wave 3 Gate — Lead Decision

**APPROVAL GRANTED:**
1. **Contract Compliance:** Feeds produce tables satisfying `flows_category_month`, `nav_daily`, and `scheme_master` CSV contracts without modifications to frozen columns or data types.
2. **Data Coverage & Integrity:** Real AMFI reports across FY2018–19 through FY2026–27 parse correctly with zero look-ahead bias in `available_from`. Raw downloaded files are hashed and stored untouched.
3. **Failure Isolation:** NAV and Scheme Master research lane operates independently and degrades gracefully on upstream errors, ensuring P0 flow forecasting is never blocked by research feed failures.
4. **Next Dependency:** Wave 4 (Feature engineering & baseline forecasting validation) may proceed. Model development must use only verified `available_from` dates and calendar walk-forward boundaries.
