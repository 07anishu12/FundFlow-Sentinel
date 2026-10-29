# Wave 2 Validation Record: AMFI Inspection & Loader Hardening

**Date:** 2026-10-28  
**Environment:** Python 3.11.16 (`.venv`), macOS  
**Scope:** Parallel execution of Prompt 05 (Agent A) and Prompt 06 (Agent B)  
**Status:** **PASSED & APPROVED BY LEAD**  

---

## 1. Executive Summary

Wave 2 ran Prompt 05 and Prompt 06 in parallel to establish empirical data grounding before any ingestion parsers are built, while hardening the application loader boundary to guarantee safe, offline UI execution.

1. **Prompt 05 (Agent A):** Inspected 8 representative official AMFI monthly flow reports across FY2018–19 through FY2026–27 using binary stream inspection (`scripts/inspect_amfi_reports.py`), verified findings in `notebooks/00_source_inspection.ipynb`, and documented the complete layout specification and field mapping in `docs/AMFI_FIELD_INSPECTION.md`.
2. **Prompt 06 (Agent B):** Implemented typed loaders in `app/loaders.py`, presentation helpers in `app/components.py`, and comprehensive contract tests in `tests/test_app_loaders.py` (28 new unit tests, bringing total test suite to 93 tests, all passing).
3. **Wave 2 Gate (Lead Approval):** The Lead has reviewed and approved the AMFI field map, category validity map, and UI loader output contracts. Forecasting on assumed columns remains strictly prohibited.

---

## 2. Prompt 05 — AMFI Inspection & Target Availability Verification

### 2.1 Key Findings & Evidence

| Requirement | Finding | Evidence & Invariant |
|---|---|---|
| **Bulk Report Granularity** | **Category-level ONLY** | Bulk public reports (`amsep2024repo.xls`, `amsep2026repo.xls`, etc.) list SEBI category aggregates. Scheme names do NOT appear with flow series. The architectural assumption of category-month modeling is verified. Scheme-level flows cannot be claimed from bulk reports. |
| **Gross Redemption Field** | `Repurchase/ Redemption for the month of <Month Year> (INR in crore)` | Distinct from net flow. Exactly represents gross outflows. |
| **Net Inflow Identity** | `Net Inflow (+ve)/Outflow (-ve)` | Arithmetic identity verified: $\text{Net Flow} = \text{Funds Mobilized} - \text{Repurchase/Redemption}$. |
| **Switch-Out Treatment** | **Included in Repurchase/Redemption** | Under SEBI/AMFI mutual fund accounting, inter-scheme switch-outs are registered as redemptions from the source scheme and funds mobilized into the destination scheme. |
| **Liquid/Overnight Churn** | **Excluded from Main Model** | Corporate treasury cash churn produces monthly redemptions exceeding 800% of AUM (e.g. ₹5.44 lakh cr in Overnight in Sep 2024). Pooling these with equity/hybrid (1%–4% redemptions) distorts cross-sectional scaling. Documented as excluded in `config/categories.yaml`. |
| **Publication Lag (`available_from`)** | **~8th to 12th of Following Month ($T+1$)** | HTTP `Last-Modified` headers and in-sheet `Released on DD-Mon-YYYY` prove reports are released 8 to 12 days after month-end (up to 24 days for April reports). Availability date rule must strictly use verified publication dates. Assuming month-end ($T$) availability constitutes fatal look-ahead bias. |
| **File Format Evolution** | **Format Drift (BIFF8 ↔ OOXML)** | 2018: BIFF8 (`.xls` OLE2); 2019–2024: OOXML (`.xlsx` disguised as `.xls`); 2025–2026: BIFF8 (`.xls` OLE2). Parsers must inspect magic bytes and branch dynamically. |
| **Structural Break: Flexi Cap** | **Introduced January 2021 (`2021-01`)** | In Jan 2021, 16 Multi Cap funds were reclassified to Flexi Cap, causing artificial negative flows in Multi Cap and initiating the Flexi Cap series. Flexi Cap history begins at `2021-01`. |

### 2.2 Approved `category_map.csv`
Entries populated and approved with historical validity date windows:
```csv
raw_category,category,valid_from,valid_to
Large Cap Fund,Large Cap,2018-04,9999-12
Mid Cap Fund,Mid Cap,2018-04,9999-12
Small Cap Fund,Small Cap,2018-04,9999-12
Flexi Cap Fund,Flexi Cap,2021-01,9999-12
Balanced Hybrid Fund/Aggressive Hybrid Fund,Aggressive Hybrid,2018-04,9999-12
Corporate Bond Fund,Corporate Bond,2018-04,9999-12
Liquid Fund,Liquid,2018-04,9999-12
Overnight Fund,Overnight,2018-04,9999-12
```

---

## 3. Prompt 06 — Loader Boundary & Page Contracts Hardening

### 3.1 Architecture & Invariants

1. **Strict Offline Operation:** Loaders execute zero network requests. Verified by test socket blocking fixtures and AST import inspections.
2. **Safe Rooted Paths:** All path accesses are resolved against `DATA_ROOT`. Any relative path attempting parent traversal (`..`) or absolute path resolution is strictly rejected.
3. **Zero Business Calculations in UI:** Loaders only validate, typecast, and filter data. They never compute redemption rates, baselines, z-scores, rankings, or forecasts.
4. **Resilient Failure Handling:**
   - Missing tables / artifacts $\rightarrow$ `status="missing"`, empty typed DataFrame / `None` payload, clear message without crashing.
   - 0-byte or header-only files $\rightarrow$ `status="empty"`, empty typed DataFrame with frozen columns.
   - Corrupt JSON / extra or missing CSV columns / invalid non-numeric floats / NaNs $\rightarrow$ `status="invalid"`, data withheld.
5. **Freshness Tracking & Metadata:**
   - Injectable clock (`now`) and configurable threshold (`stale_days`, default 45 days).
   - Returns structured `Metadata(mode, source, last_period, generated_at, freshness)`.
   - Prominent `SYNTHETIC DEMO DATA` warning displayed on any fallback to synthetic fixtures.

### 3.2 Test Verification Matrix

| Test Category | Test Cases in `test_app_loaders.py` | Result |
|---|---|---|
| **Network Boundary** | `test_loaders_make_no_network_requests` | PASSED |
| **Missing Files** | `test_missing_table_csv_returns_missing_status`, `test_missing_artifact_json_returns_missing_status`, `test_undeclared_table_returns_missing_status`, `test_undeclared_artifact_returns_missing_status`, `test_missing_manifest_returns_missing_status` | PASSED |
| **Empty Files** | `test_zero_byte_csv_returns_empty_status`, `test_header_only_csv_returns_empty_status` | PASSED |
| **Malformed Files** | `test_csv_with_missing_columns_is_invalid`, `test_csv_with_extra_columns_is_invalid`, `test_csv_with_invalid_numeric_values_is_invalid`, `test_corrupt_json_artifact_is_invalid`, `test_json_artifact_with_nan_is_invalid`, `test_json_artifact_with_missing_payload_contract_is_invalid`, `test_quality_metadata_contract_validation`, `test_source_metadata_contract_validation` | PASSED |
| **Freshness & Stale Data** | `test_fresh_data_below_threshold`, `test_stale_data_above_threshold`, `test_configurable_stale_threshold` | PASSED |
| **Valid Snapshot & Typing** | `test_valid_snapshot_loads_all_columns_and_types`, `test_typed_helper_loaders` | PASSED |
| **Safe Paths & Bundles** | `test_traversal_paths_are_strictly_rejected`, `test_absolute_paths_are_strictly_rejected`, `test_unknown_bundle_is_rejected`, `test_explicit_bundle_selection_never_falls_back`, `test_malformed_manifest_in_candidate_bundle_is_not_replaced_by_fixtures`, `test_fallback_to_fixtures_declares_synthetic_mode` | PASSED |
| **Boundary Separation** | `test_loaders_perform_no_business_calculations` | PASSED |

---

## 4. Test Suite Summary

Executed command: `.venv/bin/pytest -q`
```
........................................................................ [ 77%]
.....................                                                    [100%]
93 passed in 0.45s
```
Breakdown:
- `tests/test_contracts.py`: 32 passed (frozen schema contracts, value domain checks, config validations)
- `tests/test_registry.py`: 16 passed (hash generation, append/roundtrip, atomic writes, permission tracking)
- `tests/test_app_shell.py`: 17 passed (offline page rendering, empty state handling, AST import checks)
- `tests/test_app_loaders.py`: 28 passed (loader boundaries, typed loaders, freshness, error handling)

Executed command: `make validate && make test`
```
32 passed in 0.36s (make validate)
93 passed in 0.45s (make test)
```

---

## 5. Wave 2 Gate — Lead Decision

**APPROVAL GRANTED:**
1. **AMFI Field Map & Specification:** Approved as specified in `docs/AMFI_FIELD_INSPECTION.md`. The design assumption of category-month modeling is confirmed. Format sniffing (magic bytes) and publication lag timestamping are mandated for Wave 3 parser implementation.
2. **Category Map:** Approved and populated in `config/category_map.csv`. `Liquid` and `Overnight` exclusions confirmed in `config/categories.yaml`.
3. **UI Loader Output Contracts:** Approved as implemented in `app/loaders.py` and `app/components.py`. All interface contracts and safety boundaries are strictly enforced.

**Next Wave Dependency:**
Wave 3 data ingestion (`ingest/amfi_flows.py`, `validate.py`, `market.py`) may proceed using the approved field mapping and layout spec. Forecasting on assumed columns remains strictly prohibited.
