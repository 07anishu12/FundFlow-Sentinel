# FundFlow Sentinel — Runtime Verification & Smoke Test Report

| Runtime Parameter | Observed Value |
|---|---|
| **Audit Date** | 2026-10-29 |
| **Operating System** | macOS (Darwin 24.6.0 Apple Silicon) |
| **Python Environment** | Python 3.11.16 (`/Users/anny/Desktop/mutual-fund/.venv/bin/python`) |
| **Streamlit Process PID** | **27358** |
| **Listening Port** | **8501** (`0.0.0.0:8501`, TCP LISTEN) |
| **Application Local URL** | **`http://localhost:8501`** |
| **Healthcheck Endpoint** | **`http://localhost:8501/_stcore/health`** (HTTP 200 OK, payload: `ok`) |
| **Root Endpoint Status** | **HTTP/1.1 200 OK** (TornadoServer/6.6) |

---

## 1. Application Launch & Process Verification

The Streamlit web application was launched as a managed daemon process. Active execution was independently confirmed via process table inspection, port binding analysis, and HTTP curl requests.

### Launch Command
```sh
.venv/bin/python -m streamlit run app/Home.py --server.port 8501 --server.headless true
```

### Port & Process Status Evidence
```sh
$ lsof -i :8501
COMMAND   PID USER   FD   TYPE             DEVICE SIZE/OFF NODE NAME
Python  27358 anny    8u  IPv4 0xa49f27fd4dd115bf      0t0  TCP *:8501 (LISTEN)
Python  27358 anny    9u  IPv6 0x759a0f75821b74c8      0t0  TCP *:8501 (LISTEN)
```

### HTTP Healthcheck Evidence
```sh
$ curl -sI http://localhost:8501
HTTP/1.1 200 OK
Server: TornadoServer/6.6
Content-Type: text/html
Date: Wed, 28 Oct 2026 20:05:54 GMT
Accept-Ranges: bytes
Cache-Control: no-cache
Content-Length: 1837

$ curl -s http://localhost:8501/_stcore/health
ok
```

---

## 2. Page-by-Page Runtime Smoke Test Results

All six Streamlit application views were systematically smoke-tested using the `streamlit.testing.v1.AppTest` framework with OS-level network sockets completely blocked.

### Page 1: Command Centre (`app/Home.py`)
* **Page Route:** `http://localhost:8501/`
* **Render Status:** **PASS** (0 unhandled exceptions)
* **Title:** `Command Centre · FundFlow Sentinel`
* **Mandatory Synthetic Banner:** Displayed
  > `SYNTHETIC DEMO DATA — invented test inputs, not real observations or trained forecasts.`
* **Freshness Banner:** Displayed (`Period: 2024-09 · As of: 2026-10-28T17:23:38.560`)
* **Rendered Metrics (5 total):**
  1. `OBSERVED · Closing AUM`: `₹379,010.08 crore` (Source: AMFI portal URL)
  2. `OBSERVED · Gross redemptions`: `₹4,096.44 crore` (Source: AMFI portal URL)
  3. `FORECAST · Alert level`: `Elevated tier` (Source: alert engine)
  4. `FORECAST · Forecast rate`: `1.09 %` (Source: forecasting engine)
  5. `SCENARIO · Est. outflow`: `1200.00 ₹ crore` (Source: stress model)
* **Interactive Widgets:** Category selectbox (populated with 8 normalized categories: Flexi Cap, Large & Mid Cap, Large Cap, Mid Cap, Multi Cap, Overnight, Small Cap, Value Fund).
* **Logged Warnings / Errors:** None.

---

### Page 2: Forecast Lab (`app/pages/1_Forecast_Lab.py`)
* **Page Route:** `http://localhost:8501/1_Forecast_Lab`
* **Render Status:** **PASS** (0 unhandled exceptions)
* **Title:** `Forecast Lab · FundFlow Sentinel`
* **Mandatory Synthetic Banner:** Displayed
* **Freshness Banner:** Displayed (`Period: 2024-09 · As of: 2024-10-10T00:00:00Z`)
* **Rendered Metrics (2 total):**
  1. `FORECAST · Redemption rate`: `1.09 %` (Source: walk-forward · ridge-synthetic-v1)
  2. `FORECAST · Persistence baseline`: `1.12 %` (Source: lag0 proxy · ridge-synthetic-v1)
* **Diagnostics Section:**
  * Displays Ridge MAE vs Persistence MAE.
  * Displays additive linear feature contributions (`base`, `vix_mean`, `nifty_return`) reconciling exactly to the point forecast.
* **Uncertainty Band Policy Box:**
  > `Band Status: INSUFFICIENT_HISTORY. Empirical P10/P90 uncertainty bands require at least 10 prior out-of-sample forecast residuals. Because the processed AMFI dataset currently contains only 1 month (2024-09), uncertainty intervals are honestly withheld to prevent statistical fabrication.`
* **Logged Warnings / Errors:** None.

---

### Page 3: Sentiment Monitor (`app/pages/2_Sentiment_Monitor.py`)
* **Page Route:** `http://localhost:8501/2_Sentiment_Monitor`
* **Render Status:** **PASS** (0 unhandled exceptions)
* **Title:** `Sentiment Monitor · FundFlow Sentinel`
* **Mandatory Synthetic Banner:** Displayed
* **Freshness Banner:** Displayed (`Period: 2024-09-30`)
* **Rendered Metrics (3 total):**
  1. `OBSERVED · Negative share`: `0.2 fraction` (Source: sentiment engine · all)
  2. `OBSERVED · Mean score`: `0.05 score [-1, 1]` (Source: sentiment engine)
  3. `OBSERVED · Article count`: `12 articles` (Source: feed aggregator)
* **Safeguard Notices Displayed:**
  * **Source Distinction Mandate:** Clearly explains lexical dictionary scoring of RSS headlines vs external tone models.
  * **Coverage Insufficient Notice:** Honest disclosure that live article counts do not yet meet historical corroboration thresholds.
* **Logged Warnings / Errors:** None.

---

### Page 4: Fund Research (`app/pages/3_Fund_Research.py`)
* **Page Route:** `http://localhost:8501/3_Fund_Research`
* **Render Status:** **PASS** (0 unhandled exceptions)
* **Title:** `Fund Research · FundFlow Sentinel`
* **Mandatory Synthetic Banner:** Displayed
* **Freshness Banner:** Displayed (`Period: 2024-09-30`)
* **Rendered Metrics (3 total):**
  1. `OBSERVED · Research score`: `78.5 points / 100` (Source: NAV ranking engine)
  2. `OBSERVED · 3Y CAGR`: `14.2 %` (Source: daily NAV series)
  3. `OBSERVED · Max drawdown`: `-18.5 %` (Source: daily NAV series)
* **Dataframe Rendered:** Shortlist ranking table (1 dataframe rendered displaying scheme IDs, scores, return percentiles, and volatility metrics).
* **Mandatory Bias Disclosures:**
  > `⚠️ Survivorship Bias Disclosure: Ranking evaluates currently reporting schemes. Terminated, merged, or delisted schemes may not be fully represented in historical NAV series.`
* **Architectural AST Check:** Verified that ranking imports 0 flow/forecast/alert modules.
* **Logged Warnings / Errors:** None.

---

### Page 5: Stress Lab (`app/pages/4_Stress_Lab.py`)
* **Page Route:** `http://localhost:8501/4_Stress_Lab`
* **Render Status:** **PASS** (0 unhandled exceptions)
* **Title:** `Stress Lab · FundFlow Sentinel`
* **Mandatory Synthetic Banner:** Displayed
* **Mandatory Data Limitation Warning:** Displayed
  > `⚠️ INSUFFICIENT_HISTORY: Historical flow history currently contains only 1 month (2024-09). Stress estimates use synthetic demo parameters or baseline rates. Scenario numbers are arithmetic stress proxies, not guaranteed liquidity buffers.`
* **Rendered Metrics (3 total):**
  1. `OBSERVED · Reference AUM proxy`: `₹379,010.08 crore` (Source: AMFI monthly flows)
  2. `FORECAST · Base forecast rate`: `1.09 %` (Source: walk-forward Ridge)
  3. `SCENARIO · Base outflow proxy`: `4,131.21 ₹ crore` (Source: stress arithmetic)
* **Dataframe Rendered:** Scenario matrix table (1 dataframe rendered showing Base, Moderate Stress, Severe Stress, and Historical Max rates and outflows capped at 100% AUM).
* **Finance-Safe Narrative:** Generated text verified to use non-guarantee, non-causal language.
* **Logged Warnings / Errors:** None.

---

### Page 6: Evidence & Limitations (`app/pages/5_Evidence_and_Limits.py`)
* **Page Route:** `http://localhost:8501/5_Evidence_and_Limits`
* **Render Status:** **PASS** (0 unhandled exceptions)
* **Title:** `Evidence and Limits · FundFlow Sentinel`
* **Mandatory Synthetic Banner:** Displayed
* **Redistribution Policy Warning:** Displayed
  > `⚠️ STRICT REDISTRIBUTION POLICY: Personal and non-commercial research use only. Third-party raw datasets (AMFI, NSE, Yahoo Finance) and proprietary model weights are strictly excluded from public distribution.`
* **Rendered Metrics (3 total):**
  1. `OBSERVED · Months covered`: `1 months` (Source: AMFI quality validation)
  2. `OBSERVED · Total records`: `8 records` (Source: AMFI quality validation)
  3. `OBSERVED · Categories`: `8 categories` (Source: AMFI quality validation)
* **Dataframes Rendered (3 total):**
  1. Quality report checks table (Status: pass, 5 checks verified).
  2. Source metadata registry table (AMFI, NSE, Yahoo, GDELT licensing terms).
  3. Table schema status overview (all 10 contracts verified).
* **Logged Warnings / Errors:** None.

---

## 3. Operations: Stop and Restart Instructions

### Inspect Running Application
```sh
# Verify process status
lsof -i :8501

# Verify HTTP response
curl -sI http://localhost:8501
```

### Stop Running Application
```sh
# Terminate process by PID
kill 27358

# Or terminate any Python process listening on 8501
kill $(lsof -t -i :8501)
```

### Restart Application
```sh
# 1. Standard development launch
make app

# 2. Or explicit headless daemon launch
.venv/bin/python -m streamlit run app/Home.py --server.port 8501 --server.headless true
```
