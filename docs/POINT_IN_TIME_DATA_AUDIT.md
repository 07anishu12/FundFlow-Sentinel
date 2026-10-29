# Point-in-Time Data Availability & Temporal Non-Leakage Audit

**Audit Date:** 2026-10-28  
**Auditor:** Independent Quantitative & Data Platform Audit  
**Scope:** Wave 2–3.1 Data Integrity Audit  
**Artifacts Audited:** `src/fundflow/validate.py`, `src/fundflow/ingest/amfi_flows.py`, `src/fundflow/contracts.py`, `docs/AMFI_FIELD_INSPECTION.md`

---

## 1. Temporal Foundations & Semantics

In quantitative time-series forecasting, look-ahead bias occurs whenever information timestamped after a simulation cutoff $t$ is utilized to generate a prediction for $t+1$. 

To prevent look-ahead bias across the ingestion, feature-engineering, and modeling lanes, four distinct temporal concepts are audited and enforced:

| Field | Definition & Semantic Boundary | Permitted Usage | Storage Layer |
|---|---|---|---|
| `period_end` | Last calendar day of the observation month (e.g., `2024-09-30`). | Grouping and calendar indexing only. **NEVER permitted as a forecast availability cutoff.** | Metadata & Quality Report (`period_end`) |
| `published_at` | Actual observed release timestamp from primary source evidence (HTTP `Last-Modified` or in-sheet release stamp). | Primary evidence for availability boundary. | Metadata sidecar (`.meta.json`) & Quality Report |
| `available_from` | Earliest ISO UTC instant at which the observation is legally and point-in-time visible to the model. | **Mandatory join and filter key for feature engineering.** | Frozen Contract CSV (`flows_category_month`, `market_month`) |
| `retrieved_at` | Instant when byte stream was downloaded from the network into local raw storage. | Provenance, auditability, and cache invalidation only. | Frozen Contract CSV & Provenance Ledger |

---

## 2. Invariants & Proof of Non-Leakage

### Invariant PIT-01: Strict Post-Period-End Publication Boundary
* **Rule:** For every flow observation with period $M$ (`YYYY-MM`), `available_from` must satisfy:
  $$\text{date}(\text{available\_from}) > \text{period\_end}(M)$$
* **Evidence:** In all 8 inspected AMFI reports, the release date occurred between 7 and 24 calendar days following month-end:
  - `2018-04`: Released on `2018-05-07` ($T+7$ days, HTTP modified `2018-05-24` $T+24$ days)
  - `2018-09`: Released on `2018-10-08` ($T+8$ days, HTTP modified `2018-10-11` $T+11$ days)
  - `2019-04`: Released on `2019-05-09` ($T+9$ days)
  - `2020-09`: Released on `2020-10-08` ($T+8$ days)
  - `2021-01`: Released on `2021-02-09` ($T+9$ days)
  - `2022-09`: Released on `2022-10-10` ($T+10$ days)
  - `2024-09`: Released on `2024-10-10` ($T+10$ days)
  - `2026-09`: HTTP Last-Modified `2026-10-12` ($T+12$ days)
* **Enforcement:** `src/fundflow/validate.py` executes a hard check:
  ```python
  if avail_date <= month_end:
      raise ValueError("Fatal look-ahead bias: available_from is on or before month-end")
  ```
  Any attempt to set `available_from` to month-end or an intra-month date immediately terminates processing.

### Invariant PIT-02: Documented Conservative Fallback Policy
* **Rule:** If primary release-date evidence is absent, the system must not assume month-end or guess an arbitrary date.
* **Policy:** A deterministic conservative fallback is assigned: **12th of month $T+1$ at 00:00:00 UTC** (`YYYY-(MM+1)-12T00:00:00Z`).
* **Justification:** Across 8 years of empirical evidence, no regular monthly AMFI report was released later than the 12th of the following month (except April reports, which carry extended audit delays). Setting $T+12$ guarantees that historical training data will not back-propagate unreleased numbers into earlier trading decisions.

### Invariant PIT-03: Timezone Safety
* **Rule:** All availability and retrieval timestamps must be explicit ISO 8601 UTC strings terminating in `Z` or `+00:00`.
* **Enforcement:** `contracts.py` and `validate.py` parse with `datetime.fromisoformat` and reject any naive or non-UTC offset with `ValueError`.

---

## 3. Automated Temporal Stress Tests

To guarantee point-in-time safety, automated regression tests in `tests/test_flow_validation.py` deliberately attempt to inject future information:

1. `test_future_release_non_leakage_hard_fails`: Passes observation with `available_from = 2024-09-30T23:59:59Z`. Fails with `Fatal look-ahead bias`.
2. `test_intra_month_availability_hard_fails`: Passes observation with `available_from = 2024-09-15T00:00:00Z`. Fails with `Fatal look-ahead bias`.
3. `test_missing_available_from_uses_conservative_policy`: Passes empty string. Validates that `2024-10-12T00:00:00Z` is automatically and transparently attached.
4. `test_market_following_month_cutoff`: Verifies that monthly market aggregations assign `YYYY-(MM+1)-01T00:00:00Z` to prevent same-month close leakage.

---

## 4. Modeling Boundary Mandate for Wave 4

When Wave 4 feature engineering builds the training matrix:
1. When generating features as-of date $T_{\text{as\_of}}$, rows where $\text{available\_from} > T_{\text{as\_of}}$ must be strictly masked.
2. In expanding-window walk-forward splits, fold $k$'s training window for target month $M$ may only contain labels and features whose $\text{available\_from} \le \text{as\_of}(M)$.
3. Walk-forward backtests must use calendar group splits rather than unconstrained cross-validation.
