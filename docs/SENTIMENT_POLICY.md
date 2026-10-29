# FundFlow Sentiment Policy & Context Specification

**Specification Version:** 1.0.0  
**Owner:** Agent B (Intelligence & External Context Architecture)  
**Contract Authority:** [`src/fundflow/contracts.py:COLUMNS['sentiment_items']`](file:///Users/anny/Desktop/mutual-fund/src/fundflow/contracts.py#L93), [`COLUMNS['sentiment_agg']`](file:///Users/anny/Desktop/mutual-fund/src/fundflow/contracts.py#L106)  
**Implementation Module:** [`src/fundflow/sentiment.py`](file:///Users/anny/Desktop/mutual-fund/src/fundflow/sentiment.py)  
**Verification Suite:** [`tests/test_sentiment.py`](file:///Users/anny/Desktop/mutual-fund/tests/test_sentiment.py)

---

## 1. Context-Only Scope & Architectural Boundary

1. **Non-Causal Context Invariant:**
   RSS sentiment is strictly an informational and contextual signal. It is **never** treated as an assumed causal driver of mutual fund redemption rates.
2. **Historical Model Isolation:**
   Live or recent RSS headlines must **never** be back-propagated or injected into historical walk-forward model training or feature matrices. A one-month lag does not establish historical point-in-time publication validity.
3. **Primary Pipeline Immunity:**
   The primary flow forecasting pipeline must remain 100% operational when sentiment feeds are absent, offline, stale, or marked `insufficient`.

---

## 2. Permitted Feeds & Ingestion Controls

RSS collection is strictly limited to the verified institutional allowlist:

| Source Identifier | Official Source Name | Feed Endpoint URL | Focus Area |
|---|---|---|---|
| `sebi_rss` | SEBI Press Releases | `https://www.sebi.gov.in/sebirss.xml` | Regulatory circulars & enforcement |
| `rbi_rss` | RBI Press Releases | `https://www.rbi.org.in/pressreleases_rss.xml` | Monetary policy & interest rates |
| `fe_mf_rss` | Financial Express MF | `https://www.financialexpress.com/market/mutual-funds/feed/` | Mutual fund trends & flows |
| `et_mf_rss` | Economic Times MF | `https://economictimes.indiatimes.com/mf/rssfeeds/default.cms` | Industry developments & SIP data |

### Data Minimization & Deduplication
- **URL Normalization:** Strips tracking parameters (`utm_*`, `ref`, `fbclid`, `gclid`) and trailing slashes.
- **Title / Summary Only:** Full article bodies are **never** scraped or stored.
- **Deterministic Deduplication:** Deduplication on normalized URL with a fallback hash on `(title, source_name)`.

---

## 3. Topic Tagging & Taxonomy (`TOPIC_MAP_V1`)

Articles are tagged using versioned keyword boundary matching:
- **`equity`**: Nifty, Sensex, equity, shares, stocks, small cap, mid cap, large cap, flexi cap, multicap.
- **`debt`**: Debt, bond, yield, gilt, fixed income, interest rate, RBI, repo, T-bill, commercial paper.
- **`regulatory`**: SEBI, AMFI, regulation, circular, compliance, mandate, penalty, disclosure.
- **`market`**: Inflow, outflow, redemption, AUM, SIP, mutual fund, AMC, portfolio.
- **`general`**: Deterministic fallback if no domain-specific keywords match. Stories are **never dropped**.

---

## 4. Pluggable Scoring & Model Governance

1. **Verified Offline Lexical Default (`lexical-finance-v1`):**
   - Uses an adapted Loughran-McDonald financial dictionary.
   - Computes score bounded in $[-1.0, +1.0]$.
   - Labels: `positive` (score $> +0.15$), `negative` (score $< -0.15$), and `neutral` (otherwise).
   - Zero external network dependencies.
2. **Transformer / FinBERT Preconditions:**
   - Any transformer model must verify model card, Apache 2.0/MIT licence, and confirmed local cache presence.
   - If unverified or uncached, the system falls back to `lexical-finance-v1` without network calls.
   - Lexical outputs must **never** be labeled as FinBERT.

---

## 5. Sufficiency & Alert Corroboration Rules

For alert corroboration:
- **Sufficiency Threshold:** Requires $\ge 30$ live articles within the preceding 14 calendar days.
- **Insufficient Coverage Policy:** If coverage $< 30$ articles, sentiment status is marked `insufficient`. Alert generation degrades gracefully and suppresses uncorroborated sentiment penalties.
