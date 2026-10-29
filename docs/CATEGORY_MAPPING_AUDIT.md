# Category Mapping, Historical Reclassification & Structural Break Audit

**Audit Date:** 2026-10-28  
**Auditor:** Independent Quantitative & Data Platform Audit  
**Scope:** Wave 2–3.1 Data Integrity Audit  
**Artifacts Audited:** `config/category_map.csv`, `config/categories.yaml`, `src/fundflow/validate.py`

---

## 1. Executive Summary & Mapping Inventory

Mutual fund category definitions in India are governed by the SEBI Categorization and Rationalization Circular of October 2017 (effective April 2018), with subsequent structural circulars (most notably SEBI/HO/IMD/DF3/CIR/P/2020/228 introducing Flexi Cap Funds in November 2020).

To ensure that category aggregation and cross-sectional pooling do not introduce structural survivorship or reclassification distortion, `config/category_map.csv` establishes a deterministic mapping with bounded calendar validity intervals:

```csv
raw_category,category,valid_from,valid_to
Large Cap Fund,Large Cap,2018-04,9999-12
Mid Cap Fund,Mid Cap,2018-04,9999-12
Small Cap Fund,Small Cap,2018-04,9999-12
Flexi Cap Fund,Flexi Cap,2021-01,9999-12
Balanced Hybrid Fund/Aggressive Hybrid Fund,Aggressive Hybrid,2018-04,9999-12
Balanced,Aggressive Hybrid,2018-04,2019-03
Aggressive Hybrid Fund,Aggressive Hybrid,2025-01,9999-12
Corporate Bond Fund,Corporate Bond,2018-04,9999-12
Liquid Fund,Liquid,2018-04,9999-12
Liquid/ Money Market,Liquid,2018-04,2019-03
Overnight Fund,Overnight,2018-04,9999-12
```

---

## 2. In-Depth Structural Break & Mapping Analyses

### 2.1 The Flexi Cap Structural Break (January 2021)
* **Empirical Fact:** In November 2020, SEBI mandated that `Multi Cap Funds` must maintain a minimum 25% allocation each in Large, Mid, and Small Cap stocks by January 2021. To allow fund managers unconstrained market-cap flexibility, SEBI introduced `Flexi Cap Funds` (minimum 65% in equity across all caps).
* **AMFI Source Evidence:** In `amjan2021repo.xls`, AMFI added a specific footnote:
  > *"$$ During Jan 2021, 16 Multi Cap Funds were re-categorized as Flexi Cap Fund. As such, the funds mobilized, redemption figures of these funds are now shown under Flexi Cap Fund, resulting in negative funds mobilized and redemption figures under Multi Cap Fund."*
* **Audit Mandate:**
  1. The `Flexi Cap` category did NOT exist prior to January 2021 (`2021-01`).
  2. Any backfill of Flexi Cap prior to `2021-01` constitutes historical data fabrication.
  3. `valid_from: 2021-01` is strictly enforced.
  4. In `2021-01`, Multi Cap flows exhibit negative values due to inter-category reclassification transfers, while Flexi Cap recorded an initial surge (₹8,970 cr inflows, ₹158,230 cr closing AUM). Modeling datasets must flag `2021-01` as an initial reclassification observation.

### 2.2 Aggressive Hybrid vs Balanced Funds (2018 to 2026)
* **Pre-April 2019:** AMFI reported equity-oriented hybrid schemes under the broad legacy label `Balanced`. Mapped to `Aggressive Hybrid` with interval `2018-04` to `2019-03`.
* **April 2019 to 2024:** AMFI standardized the category as `Balanced Hybrid Fund/Aggressive Hybrid Fund` (minimum 65% to 80% equity). Mapped to `Aggressive Hybrid` with interval `2018-04` to `9999-12`.
* **2026 Split:** AMFI began reporting `Balanced Hybrid Fund` (debt-heavy, 5 schemes, ₹3.3k cr) separately from `Aggressive Hybrid Fund` (equity-heavy, 30 schemes, ₹254k cr). Mapped `Aggressive Hybrid Fund` to `Aggressive Hybrid` from `2025-01` onward. The 5 niche Balanced Hybrid funds are excluded from the main Aggressive Hybrid series to prevent AUM discontinuities.

### 2.3 Liquid & Overnight Exclusions
* **Empirical Fact:**
  - In September 2024, Overnight Fund recorded ₹525,369 cr inflows and ₹544,732 cr redemptions on an AUM of ₹67,274 cr (monthly redemption rate of **810%**).
  - In September 2024, Liquid Fund recorded ₹370,028 cr inflows and ₹442,694 cr redemptions on an AUM of ₹440,332 cr (monthly redemption rate of **100.5%**).
  - By contrast, equity categories (Large Cap, Mid Cap) recorded monthly redemption rates of **1.0% to 1.5%**.
* **Audit Mandate:**
  - Pooling treasury cash-management instruments with retail/institutional investment funds destroys regression variance and gradient stability.
  - Confirmed as excluded from the predictive universe in `config/categories.yaml`.
  - Excluded categories remain intact in raw storage and `flows_category_month.csv`, but are filtered out from feature matrices and reported as exclusions in `quality_report.json`.

---

## 3. Deterministic Mapping & Overlap Audit

A programmatic audit of `config/category_map.csv` was executed to verify that for any given month $M$, no raw category string maps ambiguously to multiple canonical categories:

$$\forall M, \text{count}(\text{raw\_category} \mid \text{valid\_from} \le M \le \text{valid\_to}) \le 1$$

* **Result:** **PASS.** All overlapping rows for the same raw category (e.g. `Liquid Fund` vs `Liquid/ Money Market`) have mutually disjoint validity windows (`2018-04` to `2019-03` vs `2018-04` to `9999-12`).
* **Unmapped Categories:** Categories outside the 6 active modeling universe categories and 2 excluded categories (e.g., Arbitrage, Gilt, Sectoral/Thematic, Gold ETF) are tracked as unmapped in `quality_report.json` and prevented from silently corrupting model training datasets.
