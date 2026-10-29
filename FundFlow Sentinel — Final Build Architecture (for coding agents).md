# FundFlow Sentinel — Final Build Architecture

A hand-off spec for coding agents. Free and open-source data and tools only. Everything here is a design, not a claim that anything is built or measured.

---

## 1. Verdict on your blueprint

The blueprint is strong on honesty rules (no leakage, baseline first, no fake metrics). It has **real gaps** that will break the build if agents follow it literally. Fix these first.

| # | Gap | Why it matters | Fix in this architecture |
| --- | --- | --- | --- |
| G1 | **Flows are modelled at scheme level, but AMFI's public monthly report is category-level** (funds mobilised, repurchase/redemption, net inflow, AUM, average AUM per SEBI category). Scheme-level gross flows are not in the free bulk data as far as I know. | `monthly_flows.scheme_code` cannot be filled. Flow stability per scheme is impossible. | Flows are **category-month only**. Agent A must inspect real files first and report available fields before anything else is built. |
| G2 | **Flow-stability (20% of ranking) is identical for every fund in a category.** | A constant adds nothing to ranking. | Remove it from the score. Show category flow context beside the shortlist as information only. Replace with a Sortino-style risk-adjusted component. |
| G3 | **Publication lag ignored.** Month-end AUM and flows are published around the 8th–10th of the next month. | A forecast "as of 30 Sept" would use data not yet public. This is hidden leakage. | Add `available_from` date per flow row. Forecast as-of date = release date, not month end. Features only use rows with `available_from <= as_of`. |
| G4 | **"Redemption" in AMFI data includes switch-outs.** Liquid, overnight and money-market categories show enormous churn. | Rates can be hundreds of percent of AUM and dominate pooled models. | Default universe = equity + hybrid + a few debt categories. Liquid/overnight excluded by config, documented. |
| G5 | **Category names changed (SEBI recategorisation, Oct 2017) and report layouts drift.** | Parser breaks across years; series have structural breaks. | Start history from FY2018-19 onward. Maintain `category_map.csv`. Parser has per-layout adapters and fails loudly. |
| G6 | **Small sample.** \~80–90 months per category at best, 3–6 categories, correlated. | A 10% "high-pressure" label gives only a handful of test events. | Report alert metrics with event counts and the caveat. Use Ridge and persistence only. Gradient boosting is an optional appendix, off by default. |
| G7 | **No free historical news.** Live RSS headlines cannot validate sentiment as a predictor. | Your own blueprint flags this but offers no path. | Two lanes: **live lane** (RSS + FinBERT-class classifier, context only) and **history lane** (GDELT free tone time series, monthly, back to \~2017) for a genuine with/without-sentiment backtest. |
| G8 | **Fragile free sources.** NSE blocks scrapers; AMFI pages are dynamic; AMFI NAV history is 90 days per request. | Demo day failure. | **Committed data snapshots.** App runs offline from `data/snapshots/`. Live refresh is a bonus button, never a dependency. |
| G9 | **"Critical" alert rule is undefined.** | Agents will invent thresholds. | Exact rule spec in Section 6. |
| G10 | **No forecast uncertainty.** | Stress lab then has only arbitrary multipliers. | Empirical error band from walk-forward residuals (P10/P90) plus a "worst historical month" scenario. |
| G11 | **Model licences unverified.** Your document cites a non-commercial licence for FinBERT weights. | Legal risk if shown as commercial. | Licence register (Section 9). Agent C checks the model card at build time and records it. Lexicon fallback (VADER/Loughran-McDonald) always available. |
| G12 | **Survivorship bias in NAV data.** Current NAV files list only live schemes. | Shortlist looks better than reality. | Disclose on the Fund Research screen. Do not claim otherwise. |
| G13 | **No explanation mechanism for the model.** | "Explainable alerts" otherwise means text templates. | Ridge contributions = coefficient × standardised feature value, stored per forecast. |

---

## 2. Locked MVP scope

**P0 (must ship):** category flow ingestion → validated dataset → redemption rate → persistence baseline + Ridge → walk-forward backtest → alerts with evidence → stress lab → Streamlit command centre + forecast lab → tests + README.

**P1:** live headline sentiment (context only), fund shortlist.

**P2:** GDELT history lane + sentiment backtest, macro features, prediction intervals polish, deploy.

**Default universe (config, editable):** Large Cap, Mid Cap, Small Cap, Flexi Cap, Aggressive Hybrid, Corporate Bond. Pick exactly the names that appear in the AMFI file; the mapping file decides.

**One-sentence product:** "For each fund category, we forecast next month's gross redemption rate, compare it with a naive baseline, flag unusual pressure with stated reasons, and let an analyst stress the rupee outflow — with a separate, transparent fund research shortlist."

---

## 3. System architecture

```
 SOURCES (free)                                   
 AMFI monthly xls | AMFI/mfapi NAV | Nifty+VIX | RSS + GDELT | RBI (P2)
        |               |               |            |
        v               v               v            v
 [1 INGEST] ---- writes data/raw/<source>/<retrieved_at>/ + source_registry.csv
        |
        v
 [2 VALIDATE / STANDARDISE] ---- quality_report.json (hard fail on schema break)
        |
        v
 [3 SHARED DATASETS]  flows_category_month | market_month | nav_daily | scheme_master | headlines
        |                    |                  |                  |
        v                    v                  v                  v
 [4a FLOW FEATURES]    [4b MARKET FEATURES]   [4c NAV METRICS]   [4d SENTIMENT]
        \_______ feature_matrix ______/             |                  |
                     |                              |                  |
                     v                              |                  |
   [5 FORECAST ENGINE: persistence, Ridge] --> predictions + contributions
                     |                              |                  |
   [5b ANOMALY: percentile + robust z]               |                  |
                     v                              v                  v
   [6 DECISION LAYER: alerts, stress scenarios]  [7 RANKING]      sentiment_agg
                     \______________________  ______|__________________/
                                            v
                          [8 STREAMLIT APP: reads parquet/csv only]
                                            v
                          [9 REPORT EXPORT: model_results.json + evidence pack]
```

**Isolation rules (enforced by import tests):**

- `ranking` imports only `nav`, `scheme_master`. Never forecasts or alerts.
- `sentiment` output is read by `alerts` only as display evidence unless the P2 backtest shows improvement.
- The app imports nothing from `forecasting` internals; it reads output files and calls `stress.py` and `explain.py`.

---

## 4. Data flow, stage by stage

| Stage | Input | Process | Output file (in `data/`) | Gate |
| --- | --- | --- | --- | --- |
| 1 Ingest | URLs in `config/sources.yaml` | Download with retries, polite delay, store untouched | `raw/amfi/YYYY-MM.xls`, `raw/nav/*.json`, `raw/market/*.csv`, `raw/news/*.jsonl`; `source_registry.csv` | Every file has url, retrieved\_at, sha256 |
| 2 Validate | raw files | Per-layout parser, unit to ₹ crore, category map, dedupe | `processed/flows_category_month.csv`, `quality_report.json` | No duplicate (month, category); no missing months inside range; units asserted |
| 3 Market | Nifty, VIX daily | Monthly aggregate | `processed/market_month.csv` | Month index aligned to flows |
| 4a Features | flows + market | Lags, rolling stats, `available_from` filter | `processed/feature_matrix.csv` | Leakage test passes |
| 5 Forecast | feature matrix | Expanding-window walk-forward, min 36 months training | `outputs/predictions.csv`, `outputs/model_results.json` | Out-of-sample only |
| 5b Anomaly | rate history | Percentile and robust z using data up to as-of | `outputs/anomaly_scores.csv` | Thresholds fit on past only |
| 6 Alerts | predictions + anomaly + sentiment\_agg | Rule engine | `outputs/alerts.csv` | Every alert has reasons + freshness |
| 6 Stress | forecast rate, AUM, scenario | Arithmetic | in-memory / `outputs/stress_default.csv` | Reconciliation test |
| 7 Ranking | nav\_daily, scheme\_master | Eligibility, metrics, percentile score | `outputs/shortlist.csv` | Weights + exclusions saved |
| 4d Sentiment | headlines | Dedupe, classify, aggregate | `outputs/sentiment_items.csv`, `outputs/sentiment_agg.csv` | `is_live` flag on every row |
| 8 App | `outputs/*` | Render | n/a | Every number labelled observed / forecast / scenario |

**Folder `data/snapshots/`** holds a committed copy of the last good `processed/` and `outputs/` so the demo works with zero network.

---

## 5. Data contracts (column-exact)

All money in ₹ crore. All months as `YYYY-MM` (period end). All timestamps UTC ISO.

**flows\_category\_month.csv** `month, category, gross_inflow_cr, gross_redemption_cr, net_flow_cr, aum_close_cr, aaum_cr, available_from, source_url, retrieved_at`

**market\_month.csv** `month, nifty_return, nifty_drawdown_3m, vix_mean, vix_change, available_from, source_name, retrieved_at`

**feature\_matrix.csv** (one row per category-month, features known at `as_of`) `as_of, target_month, category, rate_lag0, rate_lag1, rate_lag2, rate_lag11, roll_mean3, roll_std3, delta1, net_flow_rate_lag0, aum_growth_lag0, nifty_return_lag0, nifty_drawdown_3m, vix_mean_lag0, vix_change_lag0, [sent_*], target_rate` where `rate = gross_redemption_cr / aum_close_cr of the previous month × 100`.

**predictions.csv** `as_of, target_month, category, model_id, predicted_rate, baseline_rate, actual_rate (blank for future), is_out_of_sample, train_start, train_end, contrib_json`

**alerts.csv** `as_of, target_month, category, level, rules_triggered, forecast_rate, forecast_percentile, robust_z, momentum_3m, est_outflow_cr, reference_aum_cr, aum_month, sentiment_status, sentiment_note, data_freshness_days, limitations`

**nav\_daily.csv** `date, scheme_code, nav, source_url` · **scheme\_master.csv** `scheme_code, scheme_name, fund_house, category, plan_type, option_type, riskometer (nullable)` · **shortlist.csv** `scheme_code, scheme_name, category, cagr_3y, vol, max_drawdown, sortino, consistency, p_return, p_consistency, p_drawdown, p_risk_adj, research_score, metric_date, history_years`

**sentiment\_items.csv** `article_id, published_at, title, source_name, url, p_pos, p_neg, p_neu, label, score, topic_tags, is_live, model_id` · **sentiment\_agg.csv** `period, topic, mean_score, neg_share, n_articles, is_live`

---

## 6. How the system makes a decision

### 6.1 Forecast

1. Target `R(t+1)`, features as in Section 5. Optional `target_mode: change` predicts `R(t+1) − R(t)` and adds back `R(t)`. Pick whichever has lower walk-forward MAE and record the choice.
2. Walk-forward: expanding window, minimum 36 months, one step ahead. Scaler and Ridge fit on training rows only. Alpha chosen by inner `TimeSeriesSplit` on the training window from `[0.1, 1, 10, 100]`.
3. Panel model: all categories pooled with category one-hot. Also report per-category MAE.
4. Compare to persistence `R(t+1)=R(t)`. Report MAE, RMSE, and "% of test months model beat baseline". Report honestly if it loses.
5. Store contributions: `coef_j × scaled_x_j` per prediction.

### 6.2 Anomaly evidence (independent of the model)

- `pct_latest` = percentile of latest observed rate in the category's rates up to as-of.
- `robust_z` = `(R_t − median_24) / (1.4826 × MAD_24)`.
- `momentum_3m` = mean of last 3 rates ÷ mean of the 3 before − 1.
- `pct_forecast` = percentile of forecast within the training-to-date distribution.

### 6.3 Alert rules (exact; thresholds in `config/alerts.yaml`)

- **Elevated:** `pct_forecast ≥ 80` OR `robust_z ≥ 2.0`.
- **Critical:** `pct_forecast ≥ 90` AND (`robust_z ≥ 2.0` OR `momentum_3m ≥ 0.10`).
- **Normal:** otherwise.
- Sentiment is listed as corroboration only if `n_articles ≥ 30` in the last 14 days **and** `is_live` is true **and** `neg_share` is above its own historical 75th percentile; otherwise `sentiment_status = unavailable/insufficient`.
- Backtest the rules: label = actual rate ≥ training-to-date 80th percentile. Report precision, recall, false alerts, missed events **and the event count**. State that few events limit confidence.

### 6.4 Stress lab

`outflow_cr = min(rate,100)/100 × reference_aum_cr`, with reference AUM = latest closing AUM of the category (labelled as proxy).

| Scenario | Rate |
| --- | --- |
| Base | model forecast |
| Band low / high | forecast + P10 / P90 of walk-forward residuals |
| Moderate | 1.25 × forecast (illustrative) |
| Severe | 1.50 × forecast (illustrative) |
| Historical worst | max rate in the category's history |
| Custom | user input |

Outputs: outflow, incremental outflow versus base, and the label observed / forecast / scenario. No liquidity or holdings claims.

### 6.5 Fund research ranking

- Filter first: category, Direct-Growth, ≥3 years of NAV, no large NAV gaps.
- Metrics: 3Y CAGR, annualised volatility, max drawdown, Sortino, rolling-1Y consistency (share of windows beating category median).
- Score = `0.30·P_return + 0.25·P_consistency + 0.25·P_drawdown + 0.20·P_risk_adj`, each a within-category percentile 0–100.
- Show a **weight sensitivity** check: perturb each weight ±10 points, report Spearman rank correlation with the base ranking and top-5 overlap.
- Disclose: survivorship bias, history ≠ future, not advice. Category flow context shown separately; never used to reject a fund.

### 6.6 Sentiment

- Live lane: RSS headlines → dedupe by normalised title + url → classifier → `score = p_pos − p_neg` → aggregate per day/week/topic with `n_articles` and `neg_share`.
- History lane (P2): GDELT monthly tone for India finance themes, aligned by month, lagged one month. Run the same Ridge with and without it; keep it only if out-of-sample MAE improves. Say GDELT tone is not the same as the headline classifier.
- Topic tags by keyword dictionary (rates, equity markets, bond yields, credit, regulation). Untagged → `general`.

---

## 7. Repository structure and file contents

```
fundflow-sentinel/
├── README.md                 setup, commands, sources, licences, limitations, results table
├── LICENSE                   MIT or Apache-2.0 (your code)
├── requirements.txt          pinned versions
├── Makefile                  make data | train | alerts | app | test | all
├── .gitignore
├── config/
│   ├── sources.yaml          URL, frequency, licence note, terms URL per source
│   ├── categories.yaml       universe, exclusions (liquid/overnight), min history
│   ├── category_map.csv      raw AMFI label -> canonical category, valid_from, valid_to
│   ├── model.yaml            min_train_months, alphas, lags, target_mode, seed
│   ├── alerts.yaml           percentiles, z threshold, momentum, sentiment min articles
│   └── ranking.yaml          weights, min_history_years, plan filter
├── data/
│   ├── README.md             how files are produced, units, freshness
│   ├── raw/                  untouched downloads (gitignored except tiny samples)
│   ├── processed/            validated datasets
│   ├── outputs/              predictions, alerts, shortlist, sentiment, model_results.json
│   └── snapshots/            committed demo-safe copies of processed + outputs
├── src/fundflow/
│   ├── __init__.py
│   ├── contracts.py          column lists + pandera/pydantic schemas for every table above
│   ├── registry.py           write/read source_registry.csv (url, licence, retrieved_at, sha256)
│   ├── ingest/
│   │   ├── amfi_flows.py     download_monthly_reports(start,end); parse_report(path)->DataFrame; layout adapters
│   │   ├── nav.py            fetch_scheme_list(); fetch_nav_history(code) (mfapi.in, chunked fallback to AMFI NAV)
│   │   ├── market.py         fetch_nifty_vix(start,end) (yfinance or niftyindices CSV) -> monthly
│   │   └── news.py           fetch_rss(feeds)->headlines; fetch_gdelt_tone(query,start,end)
│   ├── validate.py           validate_flows(raw)->(df, report); asserts units, dupes, gaps, available_from
│   ├── flows.py              compute_rates(df); category aggregation; reference_aum()
│   ├── features.py           build_feature_matrix(flows, market, sentiment=None, as_of_rule)
│   ├── forecasting.py        persistence(), ridge_fit_predict(), walk_forward(), metrics(), residual_bands()
│   ├── anomaly.py            percentile_score(), robust_z(), momentum()
│   ├── alerts.py             generate_alerts(preds, history, sentiment_agg)->alerts_df; backtest_alerts()
│   ├── explain.py            contributions(), alert_text(row)  (templates fill from computed values only)
│   ├── stress.py             stress_outflow(aum, rate); scenario_table(forecast, bands, history)
│   ├── sentiment.py          clean_dedupe(), classify(), aggregate(), tag_topics(), licence check helper
│   ├── nav_metrics.py        cagr(), vol(), max_drawdown(), sortino(), rolling_consistency()
│   ├── ranking.py            filter_eligible(), score(), weight_sensitivity()
│   ├── reporting.py          write model_results.json; evidence pack markdown
│   └── cli.py                `python -m fundflow.cli build-data|train|alerts|sentiment|rank|all`
├── app/
│   ├── Home.py               Command Centre
│   ├── pages/
│   │   ├── 1_Forecast_Lab.py
│   │   ├── 2_Sentiment_Monitor.py
│   │   ├── 3_Fund_Research.py
│   │   ├── 4_Stress_Lab.py
│   │   └── 5_Evidence_and_Limits.py   sources, licences, freshness, metrics, limitations
│   ├── components.py         labelled metric card (OBSERVED / FORECAST / SCENARIO badge), freshness banner
│   └── loaders.py            cached readers of outputs/ with empty-state handling
├── tests/
│   ├── test_units_and_dupes.py
│   ├── test_rates.py
│   ├── test_no_leakage.py        mutate future rows; past forecasts must be identical
│   ├── test_walk_forward.py      no training row after its as_of
│   ├── test_alert_rules.py       synthetic series triggers each level exactly
│   ├── test_stress.py            reconciliation + 100% cap
│   ├── test_nav_metrics.py       known toy series
│   ├── test_ranking.py           filters, weights sum to 1, sensitivity
│   ├── test_import_isolation.py  ranking does not import forecasting/alerts
│   └── test_app_smoke.py         pages load from snapshots
└── notebooks/
    └── 00_source_inspection.ipynb   Agent A's field inspection record
```

**Function contracts (signatures agents must keep):**

```python
validate_flows(raw: pd.DataFrame) -> tuple[pd.DataFrame, dict]
compute_rates(flows: pd.DataFrame) -> pd.DataFrame            # adds rate, prev_aum
build_feature_matrix(flows, market, sentiment=None) -> pd.DataFrame
walk_forward(features, cfg) -> tuple[pd.DataFrame, dict]      # predictions, metrics
generate_alerts(predictions, history, sentiment_agg=None) -> pd.DataFrame
stress_outflow(aum_cr: float, rate_pct: float) -> dict
scenario_table(forecast_rate, bands, hist_max, aum_cr) -> pd.DataFrame
rank_funds(nav, scheme_master, cfg) -> tuple[pd.DataFrame, pd.DataFrame]  # shortlist, exclusions
```

---

## 8. Module dependency matrix (who reads what)

| Module | Reads | Writes | Must NOT import |
| --- | --- | --- | --- |
| `ingest/*` | `config/sources.yaml` | `data/raw/*`, `source_registry.csv` | everything downstream |
| `validate.py` | raw files, `category_map.csv` | `processed/flows_category_month.csv`, `quality_report.json` | forecasting, alerts |
| `flows.py` | validated flows | rate columns | ranking, sentiment |
| `features.py` | flows, market, optional sentiment\_agg | `feature_matrix.csv` | alerts, app |
| `forecasting.py` | feature matrix, `model.yaml` | `predictions.csv`, `model_results.json` | app, ranking |
| `anomaly.py` | rate history | `anomaly_scores.csv` | forecasting internals |
| `alerts.py` | predictions, anomaly, sentiment\_agg | `alerts.csv` | ranking |
| `stress.py` | forecast rate, bands, AUM | scenario tables | ingestion |
| `sentiment.py` | headlines | `sentiment_items.csv`, `sentiment_agg.csv` | forecasting |
| `nav_metrics.py` + `ranking.py` | `nav_daily.csv`, `scheme_master.csv` | `shortlist.csv`, exclusions | forecasting, alerts, flows |
| `app/*` | `data/outputs/*`, `stress.py`, `explain.py` | nothing | any recalculation of rates, forecasts or scores |

---

## 9. Open-source stack and licence register

Agent A and C fill the last two columns during the build. Do not guess; record what the source page says on the retrieval date.

| Component | Choice | Cost | Licence / terms to record |
| --- | --- | --- | --- |
| Language, data | Python 3.11, pandas, NumPy, openpyxl/xlrd | free | BSD / MIT-style |
| ML | scikit-learn (Ridge, TimeSeriesSplit, optional HistGradientBoosting) | free | BSD-3 |
| Schemas | pandera or pydantic | free | MIT |
| Charts, UI | Plotly, Streamlit | free | MIT / Apache-2.0 |
| Tests | pytest | free | MIT |
| Flow data | AMFI monthly reports | free | check AMFI terms page; record URL and date |
| NAV data | AMFI NAV files; mfapi.in as community wrapper | free | mfapi.in is unofficial: label it, cache it, fall back to AMFI |
| Market data | yfinance (`^NSEI`, `^INDIAVIX`) or niftyindices.com CSV | free | yfinance is unofficial and for personal use; commit a snapshot |
| News, live | RSS from publishers that expose feeds | free | each feed's terms; store headline, url, timestamp only |
| News, history | GDELT DOC 2.0 / GKG tone | free | open data; note rate limits |
| Sentiment model | a FinBERT-class model from Hugging Face; fallback VADER or Loughran-McDonald lexicon | free | read the model card licence on the day; log it in `sentiment.py` output as `model_id` + licence string |
| Classifier check | Financial PhraseBank or FiQA sample | free | dataset licence is often non-commercial; fine for a prototype, state it |
| Hosting | local; optional Streamlit Community Cloud | free | public repo required |
| Optional narrative | none needed. Alert text is template-filled from computed values | n/a | n/a |

A free dataset is not automatically redistributable. Do not commit raw third-party files to a public repo unless the terms allow it; commit only what you can, and keep a `data/README.md` explaining how to re-fetch the rest.

---

## 10. Build order and agent work orders

Your existing Master Brief and four agent briefs are good. Add these amendments and run in this order.

**Phase 0 — you, 30 minutes (blocks everything).** Create the repo skeleton from Section 7, write `contracts.py`, the YAML configs, and tiny fixture CSVs matching the Section 5 schemas in `data/snapshots/fixtures/`. This lets agents work in parallel without guessing columns.

**Phase 1 — parallel.**

| Agent | Amended task | Done when |
| --- | --- | --- |
| A Data | First write `notebooks/00_source_inspection.ipynb` listing which AMFI fields exist per year, the publication dates, and layout changes. Then build `ingest/amfi_flows.py`, `validate.py`, `market.py`, `nav.py`. Add `available_from`. Fill `category_map.csv`. | `make data` produces `flows_category_month.csv` with ≥60 months for ≥3 categories, `quality_report.json` passes, tests green |
| B Quant | Build features, persistence, Ridge, walk-forward, residual bands, anomaly, alert rules and alert backtest, contributions. Run on fixtures until A delivers. | `make train` writes `predictions.csv` and `model_results.json`; leakage tests pass; baseline comparison printed |
| C Intelligence | `sentiment.py` with a swappable classifier and lexicon fallback; RSS + GDELT ingest; `nav_metrics.py`, `ranking.py`, weight sensitivity. | classifier runs offline from a cached model or the fallback; shortlist for one category produced with exclusions listed |
| D App | Five pages plus Evidence page, badge component, freshness banner, empty states. Reads fixtures first, then real outputs. | `streamlit run app/Home.py` works from `data/snapshots/` with the network off |

**Phase 2 — you, integration (1 hour).** Replace fixtures with real outputs, run `make all`, run `pytest`, freeze a snapshot into `data/snapshots/`, fill the README results table from `model_results.json` only.

**Phase 3 — stretch.** GDELT lane backtest, extra categories, macro features, deploy.

**Rules every agent gets:**

1. Inspect real data before coding against it. If a field is missing, stop and report; do not substitute.
2. No invented numbers. Metrics come from files in `outputs/`.
3. Keep function signatures from Section 7. Schema changes go through you.
4. Every UI number carries an OBSERVED / FORECAST / SCENARIO badge plus the month and source.
5. Commit small, with messages that name the module.

**Using open-source coding agents:** paste Sections 5, 7 and 8 plus one agent brief per tool session (for example Aider, OpenHands, Continue with a local or free-tier model, or Claude Code). Keep one agent per module folder to avoid merge fights.

---

## 11. Evaluation you can show judges

| Question | Evidence file | What to show honestly |
| --- | --- | --- |
| Is the data real and traceable? | `source_registry.csv`, `quality_report.json` | sources, dates, gaps, exclusions |
| Does the model add value? | `model_results.json` | MAE, RMSE, win-rate versus persistence, per category; if it loses, say so |
| Do alerts work? | alert backtest in `model_results.json` | precision, recall, false alerts, number of events |
| Is sentiment useful? | with/without comparison (P2) | classifier quality and forecast value are separate claims |
| Is the ranking stable? | `weight_sensitivity` output | Spearman and top-5 overlap |
| Do numbers reconcile? | `test_stress.py` | outflow = rate × AUM |

---

## 12. Demo script (5 minutes)

1. **Command Centre:** pick a category, show last data month and freshness banner.
2. **Forecast Lab:** actual versus forecast versus persistence; read MAE from the file, not from memory.
3. **Alert detail:** show which rules fired, the percentile, momentum, and contributions chart.
4. **Sentiment:** headlines with timestamps and the live/archived badge; say it is context unless the P2 test passed.
5. **Stress Lab:** base, band, severe, historical worst; show the reconciliation line.
6. **Fund Research:** filters, component scores, sensitivity check, survivorship disclaimer.
7. **Close:** "Every number traces to a source, a calculation, or a labelled assumption."

**Never say:** accuracy percentages you did not measure; that alerts predict a liquidity crisis; that top-ranked funds will outperform; that sentiment drives redemptions.

---

## 13. Final pre-submission checklist

- [ ] Source inspection notebook committed; real fields documented.
- [ ] `available_from` used; leakage tests pass.
- [ ] Liquid and overnight categories excluded or separately labelled.
- [ ] Persistence baseline and Ridge compared on held-out months only.
- [ ] Alert backtest reports event counts.
- [ ] Flow stability removed from the ranking score; sensitivity check present.
- [ ] Licence register complete, including the sentiment model.
- [ ] App runs offline from snapshots; README works from a clean clone.
- [ ] Stress scenarios reconcile; 100% cap tested.
- [ ] Presentation has selectable text and stays under the size limit; all required submission forms completed.
