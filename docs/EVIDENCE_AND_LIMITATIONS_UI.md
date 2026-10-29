# Evidence & Limitations UI Specification

**Specification Version:** 1.0.0  
**Owner:** Agent B (Intelligence & User Interface Architecture)  
**Page Path:** [`app/pages/5_Evidence_and_Limits.py`](file:///Users/anny/Desktop/mutual-fund/app/pages/5_Evidence_and_Limits.py)  
**Component Module:** [`app/components.py:evidence_and_limits`](file:///Users/anny/Desktop/mutual-fund/app/components.py#L295)  
**Verification Suite:** [`tests/test_ui_pages.py:test_evidence_and_limits_smoke`](file:///Users/anny/Desktop/mutual-fund/tests/test_ui_pages.py)  
**Operational Mode:** **OFFLINE-FIRST / AUDIT-GRADE PROVENANCE**

---

## 1. Page Purpose & Architectural Boundary

1. **Complete Provenance & Quality Transparency:**
   The Evidence and Limitations page acts as the central auditing cockpit for FundFlow Sentinel. It surfaces raw dataset provenance, data pipeline validation findings, model diagnostics, license restrictions, and structural system boundaries.
2. **Read-Only Inspection:**
   The UI performs no evaluation, inference, or score calculation. It reads certified local artifacts via [`app/loaders.py`](file:///Users/anny/Desktop/mutual-fund/app/loaders.py):
   * Quality report via `load_quality_metadata()`
   * Source registry via `config/sources.yaml`
   * Model results via `load_model_results()`
   * Table statuses via `load_table()`

---

## 2. Key Interface Sections & Display Rules

### 2.1 Data Quality Audit Status
* **Overall Gate Status:** Displays system quality gate verdict (`PASS` / `FAIL`).
* **Automated Checks Ledger:** Tabular rendering of verified pipeline assertions:
  * Schema columns and types
  * Finite INR crore monetary units
  * Universe category validation
  * Duplicate `(month, category)` key checks
  * Non-leakage availability boundary verification (`available_from > month_end`)
  * Observed gross redemption enforcement (zero inferred values)
* **Sample Coverage:** Observation window (`start_month` to `end_month`), total records, and excluded categories (`Liquid`, `Overnight`).

### 2.2 Official Source Registry & Redistribution Ledger
* **Registered Sources Table:**
  * Source ID & Name (`amfi_flows`, `amfi_nav`, `mfapi`, `nse_vix`, `nifty_indices`, `gdelt`)
  * Data Type & Frequency
  * Status (`official`, `restricted`, `unverified`)
  * Redistribution Status (`restricted`, `unknown`)
  * Permitted Use terms
* **Mandatory Redistribution Notice:**
  > `⚠️ STRICT REDISTRIBUTION POLICY: Personal and non-commercial access only. Public distribution of commercial index feeds or bulk historical reports requires explicit third-party permissions. Live network access is never required by this application.`

### 2.3 Model Validation & Documented Limitations
* **Model Execution Status:** Displays payload status (`evaluated`, `inferred_only`, `empty`).
* **Evaluation Metrics:** If multi-period walk-forward testing is supported, renders out-of-sample MAE and RMSE metrics for Ridge vs Persistence baseline.
* **Insufficient Sample Notice:** In the event of single-period flow history, displays:
  `Walk-forward evaluation metrics are unavailable: current sample history (1 month) is insufficient for expanding-window evaluation.`
* **Limitations Ledger:** Bulleted display of explicit model constraints recorded in `model_results.json`.

### 2.4 Frozen Contract Table Availability
Audits the availability and provenance of all 10 frozen contracts:
1. `flows_category_month`
2. `market_month`
3. `feature_matrix`
4. `predictions`
5. `alerts`
6. `nav_daily`
7. `scheme_master`
8. `shortlist`
9. `sentiment_items`
10. `sentiment_agg`

Each table reports: Contract Name, Status (`ok`, `missing`, `empty`, `invalid`, `stale`), Row Count, Bundle Mode (`synthetic`, `offline_snapshot`, `live`), Source, and Freshness.

### 2.5 Mandatory Research & Regulatory Notices
Displays 4 binding architectural disclaimers:
1. **Flow Data History Limitation:** 1-month AMFI flow history constraint (`INSUFFICIENT_HISTORY`).
2. **Survivorship Bias:** Operational scheme master limitations.
3. **Architectural Lane Isolation:** Strict independence between fund research ranking and flow forecasting/sentiment.
4. **Not Investment Advice:** Objective quantitative research nature of all outputs.

---

## 3. Offline & Empty States

* **Network Isolation:** Hard-blocked in test environment (`tests/test_ui_pages.py`).
* **Graceful Missing Handling:** Handled cleanly with empty-state messages if JSON artifacts or tables are absent.
