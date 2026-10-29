# AMFI Monthly Flow Report Field & Layout Inspection

**Document Version:** 1.0  
**Inspection Date:** 2026-10-28  
**Inspector / Owner:** Agent A (Data & Ingestion Lead)  
**Target Span:** FY2018–19 through FY2026–27  
**Companion Artifacts:** `scripts/inspect_amfi_reports.py`, `notebooks/00_source_inspection.ipynb`, `docs/amfi_inspection_evidence.json`

---

## 1. Executive Summary & Verification Outcomes

Prior to implementing ingestion parsers in Wave 3, this inspection empirically examines representative official AMFI monthly flow reports published on `portal.amfiindia.com` across an 8-year span.

| Verification Item | Finding / Status | Evidence & Impact |
|---|---|---|
| **Bulk Report Granularity** | **Category-level ONLY** | Bulk public reports list SEBI category aggregates; column titled `Scheme Name` or `Scheme Category` contains category names. Individual fund schemes are NOT reported with flow series. The design assumption of category-month modeling is verified. Scheme-level flows cannot be claimed from bulk reports. |
| **Gross Redemption Field** | `Repurchase/ Redemption for the month of <Month Year> (INR in crore)` | Distinct from net flow. Exactly represents total gross outflow. |
| **Net Inflow Identity** | `Net Inflow (+ve)/Outflow (-ve)` | Arithmetic identity verified: $\text{Net Flow} = \text{Funds Mobilized} - \text{Repurchase/Redemption}$. |
| **Switch-Out Treatment** | **Included in Repurchase/Redemption** | Under SEBI/AMFI mutual fund accounting standards, inter-scheme switch-outs are registered as redemptions from the source fund; switch-ins are registered as funds mobilized into the destination fund. |
| **Liquid/Overnight Exclusion** | **Excluded from Predictive Model** | High-frequency corporate treasury churn produces monthly redemptions exceeding 800% of AUM (e.g. ₹5.44 lakh cr in Overnight in Sep 2024). Pooling these with equity/hybrid (1%–4% redemptions) distorts cross-sectional scaling. Excluded by default in `config/categories.yaml`. |
| **Publication Lag (`available_from`)** | **~8th to 12th of Following Month ($T+1$)** | Primary evidence: HTTP `Last-Modified` headers and in-sheet `Released on DD-Mon-YYYY` text prove reports are released 8 to 12 days after month-end (up to 24 days for April reports). Availability date rule must strictly use verified publication dates. Assuming month-end ($T$) availability constitutes fatal look-ahead bias. |
| **File Format Evolution** | **Format Drift (BIFF8 ↔ OOXML)** | 2018: BIFF8 (`.xls` OLE2); 2019–2024: OOXML (`.xlsx` disguised as `.xls`); 2025–2026: BIFF8 (`.xls` OLE2). Parsers must inspect magic bytes and branch dynamically. |
| **Structural Break: Flexi Cap** | **Introduced January 2021 (`2021-01`)** | In Jan 2021, 16 Multi Cap funds were reclassified to Flexi Cap, causing artificial negative flows in Multi Cap and initiating the Flexi Cap series. Flexi Cap history begins at `2021-01`. |

---

## 2. Representative Report Inspection Evidence (FY2018–19 to FY2026–27)

Eight representative official reports across the entire intended history were downloaded and parsed using binary stream inspection (`scripts/inspect_amfi_reports.py`).

### 2.1 Inspection Evidence Ledger

```
+-----------+----------------------+--------------------+--------------------+---------------------------+--------------+
| Period    | Format               | HTTP Last-Modified | In-Sheet Release   | Sheet Names               | Units        |
+-----------+----------------------+--------------------+--------------------+---------------------------+--------------+
| 2018-04   | BIFF8 (.xls)         | 2018-05-24 09:18   | Released 07.05.2018| a+s+r, sales, red+assets  | INR in crore |
| 2018-09   | BIFF8 (.xls)         | 2018-10-11 06:17   | Released 08.10.2018| a+s+r, sales, red+assets  | INR in crore |
| 2019-04   | OOXML (.xlsx as .xls)| 2019-06-10 09:51   | Released 09-May-19 | Apr 2019, New Schemes     | INR in crore |
| 2020-09   | OOXML (.xlsx as .xls)| 2020-10-08 07:34   | Released 08-Oct-20 | Sep 20, New Schemes       | INR in crore |
| 2021-01   | OOXML (.xlsx as .xls)| 2021-02-09 07:33   | Released 09-Feb-21 | Jan 21, New Schemes       | INR in crore |
| 2022-09   | OOXML (.xlsx as .xls)| 2022-10-10 08:25   | Released 10-Oct-22 | Sep 22, New Schemes       | INR in crore |
| 2024-09   | OOXML (.xlsx as .xls)| 2024-10-10 08:57   | Released 10-Oct-24 | Sep 24, New Schemes       | INR in crore |
| 2026-09   | BIFF8 (.xls)         | 2026-10-12 06:10   | Header evidence    | MCR_MonthlyReport, NSR    | INR in crore |
+-----------+----------------------+--------------------+--------------------+---------------------------+--------------+
```

### 2.2 Deep Dive into Individual Reports

#### A. September 2024 Report (`amsep2024repo.xls`)
- **URL:** `https://portal.amfiindia.com/spages/amsep2024repo.xls`
- **File Type:** OOXML SpreadsheetML (`PK\x03\x04` ZIP archive) disguised with `.xls` extension.
- **HTTP Headers:** `Content-Length: 44831`, `Content-Type: application/vnd.ms-excel`, `Last-Modified: Thu, 10 Oct 2024 08:57:53 GMT`.
- **Sheet Names:** `['Sep 24', 'New Schemes']`.
- **In-File Release Text:** Row 90 contains `Released on 10-Oct-2024`.
- **Units:** Column headers state `(INR in crore)`.
- **Header Row (Row 3):**
  - `Col A (A3):` `Sr `
  - `Col B (B3):` `Scheme Name ` *(Note: Contains category labels)*
  - `Col C (C3):` `No. of Schemes as on September 30, 2024`
  - `Col D (D3):` `No. of Folios as on September 30, 2024`
  - `Col E (E3):` `Funds Mobilized for the month of September 2024 (INR in crore)`
  - `Col F (F3):` `Repurchase/ Redemption for the month of September 2024 (INR in crore)`
  - `Col G (G3):` `Net Inflow (+ve)/Outflow (-ve) for the month of September 2024 (INR in crore)`
  - `Col H (H3):` `Net Assets Under Management as on September 30, 2024 (INR in crore)`
  - `Col I (I3):` `Average Net Assets Under Management for the month September 2024 (INR in crore)`
- **Sample Category Rows:**
  - `Large Cap Fund` (Row 26): Schemes=32, Folios=14,891,416, Mobilized=5,865.86 cr, Repurchase=4,096.44 cr, Net Flow=1,769.42 cr, Closing AUM=379,010.08 cr, AAUM=374,132.40 cr.
  - `Mid Cap Fund` (Row 28): Schemes=29, Mobilized=7,671.57 cr, Repurchase=4,541.14 cr, Net Flow=3,130.42 cr, Closing AUM=397,009.72 cr.
  - `Flexi Cap Fund` (Row 35): Schemes=39, Mobilized=7,705.86 cr, Repurchase=4,491.29 cr, Net Flow=3,214.57 cr, Closing AUM=444,375.43 cr.
  - `Balanced Hybrid Fund/Aggressive Hybrid Fund` (Row 40): Schemes=31, Mobilized=2,893.14 cr, Repurchase=2,376.95 cr, Net Flow=516.19 cr, Closing AUM=229,296.60 cr.
  - `Corporate Bond Fund` (Row 16): Schemes=21, Mobilized=8,766.16 cr, Repurchase=3,727.09 cr, Net Flow=5,039.07 cr, Closing AUM=162,570.27 cr.
  - `Overnight Fund` (Row 6): Schemes=35, Mobilized=525,369.60 cr, Repurchase=544,732.24 cr, Net Flow=-19,362.65 cr, Closing AUM=67,274.59 cr. *(Redemption exceeds 800% of AUM)*.

#### B. September 2026 Report (`amsep2026repo.xls`)
- **URL:** `https://portal.amfiindia.com/spages/amsep2026repo.xls`
- **File Type:** BIFF8 OLE2 Compound Document (`\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1`).
- **HTTP Headers:** `Content-Length: 110080`, `Last-Modified: Mon, 12 Oct 2026 06:10:10 GMT`.
- **Sheet Names:** `['MCR_MonthlyReport', 'NSR']` (MCR = Monthly Category Report; NSR = New Scheme Report).
- **Units:** `(INR in crore)`.
- **Headers & Categories:** Matches the modern consolidated schema; column headers specify `(INR in crore)`.

#### C. January 2021 Report (`amjan2021repo.xls`) — Structural Break Evidence
- **URL:** `https://portal.amfiindia.com/spages/amjan2021repo.xls`
- **File Type:** OOXML SpreadsheetML (`PK\x03\x04`).
- **Release Evidence:** `Released on 09-Feb-2021` (HTTP Last-Modified: 09 Feb 2021 07:33:12 GMT).
- **Sheet Names:** `['Jan 21', 'New Schemes']`.
- **Critical Structural Event:** First appearance of `Flexi Cap Fund` in AMFI monthly statistics.
- **AMFI Footnote in Report:**  
  > *\"$$ During Jan 2021, 16 Multi Cap Funds were re-categorized as Flexi Cap Fund. As such, the funds mobilized, redemption figures of these funds are now shown under Flexi Cap Fund, resulting in negative funds mobilized and redemption figures under Multi Cap Fund.\"*
- **Implication:** The `Flexi Cap` category did not exist prior to January 2021. Any data backfill prior to `2021-01` must treat Flexi Cap as non-existent (not zero flows). Multi Cap data in `2021-01` contains a distortion artifact due to fund migration.

#### D. September 2018 Report (`amsep2018repo.xls`) — Early SEBI Categorization Layout
- **URL:** `https://portal.amfiindia.com/spages/amsep2018repo.xls`
- **File Type:** BIFF8 OLE2 Compound Document.
- **Release Evidence:** `Released on 08.10.2018` (HTTP Last-Modified: 11 Oct 2018 06:17:57 GMT).
- **Sheet Names:** `['a+s+r', 'sales', 'red+assets', 'AAUM']`.
- **Layout Structure:** Flows were published across multiple sheets:
  - `sales`: Gross funds mobilized per category and sector.
  - `red+assets`: Gross redemptions and closing AUM per category.
  - `AAUM`: Average assets under management.
- **Implication:** Parser must support multi-sheet joining for reports prior to April 2019.

---

## 3. Detailed Field Map & Contract Correspondence

The AMFI reporting columns map directly to the frozen CSV contract `flows_category_month`:

| Target Contract Column | AMFI Source Field in Sheet | Data Type | Notes / Processing |
|---|---|---|---|
| `month` | Derived from report title / sheet name | `YYYY-MM` | e.g., "Monthly Report for September 2024" $\rightarrow$ `2024-09`. |
| `category` | Column B (`Scheme Name` / `Scheme Category`) | `str` | Normalized via `category_map.csv`. |
| `gross_inflow_cr` | `Funds Mobilized for the month of...` | `float` (cr) | Gross inflows including switch-ins and NFOs. |
| `gross_redemption_cr` | `Repurchase/ Redemption for the month of...` | `float` (cr) | **Primary Target:** Gross outflows including switch-outs. |
| `net_flow_cr` | `Net Inflow (+ve)/Outflow (-ve)...` | `float` (cr) | Difference: `gross_inflow_cr - gross_redemption_cr`. |
| `aum_close_cr` | `Net Assets Under Management as on...` | `float` (cr) | Month-end closing AUM. |
| `aaum_cr` | `Average Net Assets Under Management...` | `float` (cr) | Average monthly AUM. |
| `available_from` | Verified release timestamp | `ISO UTC` | Release timestamp from HTTP header or sheet text (e.g., `2024-10-10T08:57:53Z`). |
| `source_url` | Report download URL | `str` | Exact official AMFI report URL. |
| `retrieved_at` | Acquisition timestamp | `ISO UTC` | Timestamp when raw bytes were downloaded. |

---

## 4. Proposed `category_map.csv`

To handle category labeling conventions and structural breaks across history, the following entries are proposed for `config/category_map.csv`:

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

### Excluded Categories
- **`Liquid Fund` (`Liquid`)** and **`Overnight Fund` (`Overnight`)**: Documented in `config/categories.yaml` as excluded. As established in Section 2, monthly churn in these funds reflects short-term corporate treasury cash balancing, producing redemption rates often exceeding 100%–800% of AUM. Including them in pooled regression models would corrupt gradient and scale estimations for equity/hybrid categories.

---

## 5. Parser Architecture Specification (For Wave 3 Ingestion)

When implementing `src/fundflow/ingest/amfi_flows.py` in Wave 3, the parser must follow these exact invariants:

1. **Format Sniffing (No Blind Extensions):**
   - Inspect initial 8 bytes before delegating to an engine:
     - If bytes start with `50 4B 03 04` (`PK\x03\x04`), parse as OOXML (`openpyxl` or internal XML extractor).
     - If bytes start with `D0 CF 11 E0 A1 B1 1A E1`, parse as BIFF8 OLE2 (`xlrd` or binary record extractor).
   - Reject any file that matches neither magic signature.
2. **Layout Adapter Selection:**
   - **Modern Layout (2019-04 to present):**
     - Target sheet: Search for sheet name matching `<Month> <YY>` (e.g., `Sep 24`, `Jan 21`) or `MCR_MonthlyReport`.
     - Header row: Scan first 10 rows for row containing both `Funds Mobilized` and `Repurchase/ Redemption`.
     - Extract columns by keyword matching: `Scheme` $\rightarrow$ category, `Mobilized` $\rightarrow$ inflow, `Repurchase` $\rightarrow$ redemption, `Net Inflow` $\rightarrow$ net flow, `Net Assets` $\rightarrow$ AUM.
   - **Legacy Multi-Sheet Layout (2018-04 to 2019-03):**
     - Target sheets: `sales` and `red+assets`. Join on category label.
3. **Fail Loudly on Layout Drift:**
   - If header keywords are not found within the first 15 rows of the main sheet, raise `ValueError("Unknown AMFI report layout; header keywords missing")`.
   - Never substitute default or zero values for missing flow columns.
4. **Release Timestamp Attachment:**
   - Extract `Released on <Date>` from footer rows if present, or fallback to the archived HTTP `Last-Modified` timestamp.
   - Under no circumstances assign month-end ($T$) to `available_from`.
