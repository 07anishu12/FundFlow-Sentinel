# GDELT Global Tone Policy & Source Specification

**Specification Version:** 1.0.0  
**Owner:** Agent B (Intelligence & External Data Architecture)  
**Implementation Module:** [`src/fundflow/ingest/gdelt.py`](file:///Users/anny/Desktop/mutual-fund/src/fundflow/ingest/gdelt.py)  
**Verification Suite:** [`tests/test_gdelt.py`](file:///Users/anny/Desktop/mutual-fund/tests/test_gdelt.py)  
**Operational Status:** **OPTIONAL RESEARCH LANE (OFFLINE FIXTURE AUDITED)**

---

## 1. Source Definition & News Tone Semantics

1. **Broad Macro News Tone Proxy:**
   GDELT (Global Database of Events, Language, and Tone) Doc API Tone measures the emotional charge of global web news mentioning target entities (e.g., India, RBI, SEBI, mutual funds).
   - Scale: Typically bounded between $-10.0$ and $+10.0$ (percentage of positive vs negative words in the article).
   - Semantics: It represents broad English-language media tone, **NOT** institutional mutual fund investor flows or retail redemption intent.
   - Prohibited Claim: GDELT tone must **never** be labeled as FinBERT or a calibrated probability.
2. **Distinct Zero vs Missing State:**
   A tone of `0.0` represents neutral media sentiment. Missing or unavailable data must be explicitly represented as `NaN` or `None`, never converted to `0.0`.

---

## 2. Ingestion Controls & Query Specification

* **Endpoint:** `https://api.gdeltproject.org/api/v2/doc/doc`
* **Query Template:** `(India OR "Reserve Bank of India" OR SEBI OR "mutual fund" OR "stock market") tone<-1`
* **Rate Limits & Polite Access:** Retrieval is bounded with a 10-second timeout and polite retry handling.
* **Offline Mandate:** Unit tests and offline UI rendering **never** require external network access. All tests utilize local JSON fixtures.

---

## 3. Point-in-Time Monthly Aggregation

For any observation month $M$:
* **Aggregation:** $\text{mean\_tone} = \frac{1}{N} \sum_{i=1}^N \text{tone}_i$.
* **Temporal Cutoff:** $\text{available\_from} = \text{YYYY-(MM+1)-01T00:00:00Z}$.
* Observation month $M$ cannot be used as an input feature for decision timestamps prior to the 1st of month $M+1$.

---

## 4. Lane Decoupling & Failure Modes

* GDELT tone operates as an **independent, optional research lane**.
* The primary flow forecasting pipeline ([`src/fundflow/forecasting.py`](file:///Users/anny/Desktop/mutual-fund/src/fundflow/forecasting.py)) remains 100% operational when GDELT feeds are missing, unconfigured, stale, or malformed.
* Under the frozen 17-column feature matrix contract ([`src/fundflow/contracts.py`](file:///Users/anny/Desktop/mutual-fund/src/fundflow/contracts.py#L26)), GDELT features are strictly excluded from the production feature matrix.
