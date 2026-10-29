# Sentiment Monitor UI Specification

**Specification Version:** 1.0.0  
**Owner:** Agent B (Intelligence & User Interface Architecture)  
**Page Path:** [`app/pages/2_Sentiment_Monitor.py`](file:///Users/anny/Desktop/mutual-fund/app/pages/2_Sentiment_Monitor.py)  
**Component Module:** [`app/components.py:sentiment_monitor`](file:///Users/anny/Desktop/mutual-fund/app/components.py#L120)  
**Verification Suite:** [`tests/test_ui_pages.py:test_sentiment_monitor_smoke`](file:///Users/anny/Desktop/mutual-fund/tests/test_ui_pages.py#L48)  
**Operational Mode:** **OFFLINE-FIRST / SNAPSHOT COMPLIANT**

---

## 1. Page Purpose & Architectural Boundary

1. **Context-Only Information Boundary:**
   The Sentiment Monitor provides high-level informational context regarding news tone and regulatory circulars. Sentiment is **never** used to adjust model forecasts or recalculate fund scores in the UI.
2. **Loader-Only Data Path:**
   All metrics and articles are loaded strictly via [`app/loaders.py`](file:///Users/anny/Desktop/mutual-fund/app/loaders.py) (`load_table("sentiment_agg")`, `load_table("sentiment_items")`). The UI executes zero NLP classifiers, scraping commands, or network calls.

---

## 2. Key Interface Sections & Display Rules

### 2.1 Aggregate Sentiment Metrics
* **Negative Share:** Displayed as an `OBSERVED` metric card with percentage/fraction units.
* **Mean Score:** Scored on a $[-1.0, +1.0]$ lexical scale.
* **Article Count:** Total articles contributing to the aggregate period.
* **Live vs Snapshot Badge:** Clear status badge distinguishing live materialized feeds from static snapshots.

### 2.2 Source Distinction Mandate (RSS vs GDELT)
> **Mandatory UI Note:**  
> **RSS Headline Sentiment:** Reflects immediate domestic Indian mutual fund headlines via lexical scoring.  
> **GDELT Global Tone:** Measures broad global news tone mentioning Indian macroeconomic and financial entities.  
> *These measurements have different coverage, scales, and frequencies, and are strictly presented separately.*

### 2.3 Sufficiency & Alert Corroboration State
* **Sufficiency Threshold:** Requires $\ge 30$ live articles in the preceding 14-day window.
* **Insufficient Warning:** If $< 30$ live articles are present, the page prominently displays:
  `⚠️ Coverage Insufficient for Corroboration: Fewer than 30 live articles observed in monitoring window.`

### 2.4 Headline Feed & Provenance
* Displays article title, publisher/source, publication timestamp, and topic tags.
* Titles render as secure, clickable links using normalized canonical URLs. Full article text is never stored or rendered.

---

## 3. Offline & Failure States

* **Missing Files:** Displays explicit informative empty states without raising unhandled Streamlit exceptions.
* **Offline Smoke Test:** Verified with network sockets hard-blocked (`tests/test_ui_pages.py`).
