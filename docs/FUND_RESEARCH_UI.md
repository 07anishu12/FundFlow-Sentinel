# Fund Research UI Specification

**Specification Version:** 1.0.0  
**Owner:** Agent B (Intelligence & User Interface Architecture)  
**Page Path:** [`app/pages/3_Fund_Research.py`](file:///Users/anny/Desktop/mutual-fund/app/pages/3_Fund_Research.py)  
**Component Module:** [`app/components.py:fund_research`](file:///Users/anny/Desktop/mutual-fund/app/components.py#L152)  
**Verification Suite:** [`tests/test_ui_pages.py:test_fund_research_smoke`](file:///Users/anny/Desktop/mutual-fund/tests/test_ui_pages.py#L59)  
**Operational Mode:** **OFFLINE-FIRST / SNAPSHOT COMPLIANT**

---

## 1. Page Purpose & Architectural Isolation

1. **Independent Research Lane:**
   The Fund Research interface allows transparent exploration of quantitative scheme rankings based exclusively on historical daily NAV performance.
2. **Zero Inflow / Forecast Contamination:**
   Category flow forecasts, stress multipliers, and anomaly alerts **never** influence or weight the fund research scores.
3. **Preservation of Canonical Order:**
   The UI consumes the validated ranking artifact ([`outputs/shortlist.csv`](file:///Users/anny/Desktop/mutual-fund/src/fundflow/contracts.py#L78)) directly. Category filters preserve the deterministic rank order established by [`src/fundflow/ranking.py`](file:///Users/anny/Desktop/mutual-fund/src/fundflow/ranking.py). Scores are **never recalculated or re-ranked** inside the UI.

---

## 2. Key Interface Sections & Display Rules

### 2.1 Scheme Research Metrics
* **Composite Research Score:** Percentile-weighted score $[0, 100]$:
  $$\text{research\_score} = 0.30 P_{\text{return}} + 0.25 P_{\text{consistency}} + 0.25 P_{\text{drawdown}} + 0.20 P_{\text{risk\_adj}}$$
* **3Y CAGR:** Displayed as an `OBSERVED` metric card with `%` units.
* **Maximum Drawdown:** Displayed as an `OBSERVED` metric card with `%` units (lower drawdown achieved higher percentile rank).
* **Scheme Metadata:** Scheme code, canonical name, and verified daily history duration ($\ge 3$ years).

### 2.2 Shortlist Data Table
Displays eligible Direct-Growth funds in order of research score:
* `scheme_code`, `scheme_name`, `category`, `cagr_3y`, `vol`, `max_drawdown`, `sortino`, `consistency`, `research_score`.

### 2.3 Mandatory Disclosures & Disclaimers
> **⚠️ MANDATORY RESEARCH DISCLOSURES:**  
> 1. **Survivorship Bias:** Scheme lists sourced from current AMFI feeds reflect operational schemes only. Discontinued, merged, or liquidating historical funds are omitted.  
> 2. **Not Investment Advice:** Research scores represent objective quantitative filtering across historical CAGR, volatility, drawdown, and Sortino ratio. Past performance is not a guarantee of future returns.

---

## 3. Offline & Empty State Behavior

* **Empty Shortlist:** If no schemes qualify in a category or `shortlist.csv` is absent, an informative message states: *"Shortlist records unavailable in current bundle."*
* **Network Independence:** Fully runnable without network access; verified by automated Streamlit `AppTest` suites.
