# Wave 11 Agent B Results Report

**Owner:** Agent B (Research Intelligence & UI Architecture)  
**Date:** 2026-10-29  
**Scope:** Prompt 24 — Ranking, Sentiment, Artifact Loaders, and UI Regression Tests  
**Status:** **PASS — 27 REGRESSION TESTS PASSED; ZERO FAILURES; ZERO NETWORK DEPENDENCIES**

---

## 1. Overview & Scope

Agent B implemented adversarial, deterministic regression suites hardening the independent fund research ranking engine, NAV metrics calculation, sentiment provenance and topic monitoring, artifact loaders, and complete offline application UI rendering across all 6 pages.

* **Primary Test Suite:** [`tests/test_regression_agent_b.py`](file:///Users/anny/Desktop/mutual-fund/tests/test_regression_agent_b.py) (27 dedicated tests)
* **Modules Hardened:**
  * [`src/fundflow/nav_metrics.py`](file:///Users/anny/Desktop/mutual-fund/src/fundflow/nav_metrics.py)
  * [`src/fundflow/ranking.py`](file:///Users/anny/Desktop/mutual-fund/src/fundflow/ranking.py)
  * [`src/fundflow/sentiment.py`](file:///Users/anny/Desktop/mutual-fund/src/fundflow/sentiment.py)
  * [`src/fundflow/ingest/gdelt.py`](file:///Users/anny/Desktop/mutual-fund/src/fundflow/ingest/gdelt.py)
  * [`app/loaders.py`](file:///Users/anny/Desktop/mutual-fund/app/loaders.py)
  * [`app/components.py`](file:///Users/anny/Desktop/mutual-fund/app/components.py)
  * All 6 Streamlit pages under [`app/`](file:///Users/anny/Desktop/mutual-fund/app/)

---

## 2. Requirement Mapping & Test Results

### Section A: NAV Metrics & Ranking Integrity
| Test Name | Behavioral Invariant Tested | Exit Code | Result |
|---|---|---|---|
| `test_hand_calculated_nav_metrics_flat_series` | Flat NAV series produces exactly 0% return, 0% vol, and 0% drawdown | 0 | **PASS** |
| `test_hand_calculated_nav_metrics_rising_series` | Steady doubling NAV yields >20% CAGR, positive Sortino, 0.0% drawdown | 0 | **PASS** |
| `test_hand_calculated_nav_metrics_falling_series` | Steady halving NAV yields negative CAGR and exact 50.0% max drawdown | 0 | **PASS** |
| `test_hand_calculated_nav_metrics_peak_trough_drawdown` | Peak 150 to trough 90 yields exactly 40.0% max drawdown | 0 | **PASS** |
| `test_eligibility_filter_direct_growth_only` | Regular plans & IDCW options rejected with documented audit reasons | 0 | **PASS** |
| `test_eligibility_filter_history_length_and_gap_tolerance` | History < 750 days or gaps > 10 days rejected with clear audit reasons | 0 | **PASS** |
| `test_ranking_score_direction_drawdown_inversion` | Lower drawdown receives higher percentile and higher composite score | 0 | **PASS** |
| `test_ranking_weights_sum_to_one_and_score_reconciliation` | Weights sum to 1.0; score reconciles to weighted sum within $10^{-3}$ | 0 | **PASS** |
| `test_weight_sensitivity_renormalization_and_overlap` | Perturbations renormalize to 1.0; top-5 overlap and rank correlation tested | 0 | **PASS** |
| `test_ranking_strict_import_isolation` | AST check verifies ranking imports 0 forecasting, alert, stress, or flow files | 0 | **PASS** |

### Section B: Sentiment & Historical-Tone Separation
| Test Name | Behavioral Invariant Tested | Exit Code | Result |
|---|---|---|---|
| `test_canonical_url_and_article_deduplication` | URLs with fragments/tracking normalize to identical article IDs | 0 | **PASS** |
| `test_retrieval_time_distinct_from_publication_time` | Publication timestamp preserved from article and not replaced by retrieval date | 0 | **PASS** |
| `test_classifier_provenance_lexical_fallback` | Classifier reports model_id `lexical-finance-v1`, never claims FinBERT | 0 | **PASS** |
| `test_sentiment_sufficiency_threshold_enforced` | $<30$ articles in 14-day window returns `insufficient` status | 0 | **PASS** |

### Section C: Artifact Loaders & Data Provenance
| Test Name | Behavioral Invariant Tested | Exit Code | Result |
|---|---|---|---|
| `test_loader_rejects_path_traversal_and_absolute_paths` | `../` and absolute paths strictly rejected by `_safe_path` guard | 0 | **PASS** |
| `test_loader_atomic_tmp_file_ignored` | Temporary `.tmp` files are never loaded as valid contract tables | 0 | **PASS** |
| `test_loader_preserves_null_values_without_zero_substitution` | Nullable columns (e.g. `actual_rate`) remain NaN/empty, never converted to 0.0 | 0 | **PASS** |
| `test_loader_rejects_corrupted_or_nan_json_artifacts` | Non-finite JSON constants (NaN, Infinity) trigger invalid loader status | 0 | **PASS** |

### Section D: UI Regressions & Offline Page Loading
| Test Name | Behavioral Invariant Tested | Exit Code | Result |
|---|---|---|---|
| `test_all_six_pages_render_offline_with_blocked_network[Home.py]` | Command Centre renders offline with sockets blocked | 0 | **PASS** |
| `test_all_six_pages_render_offline_with_blocked_network[pages/1_Forecast_Lab.py]` | Forecast Lab renders offline with sockets blocked | 0 | **PASS** |
| `test_all_six_pages_render_offline_with_blocked_network[pages/2_Sentiment_Monitor.py]` | Sentiment Monitor renders offline with sockets blocked | 0 | **PASS** |
| `test_all_six_pages_render_offline_with_blocked_network[pages/3_Fund_Research.py]` | Fund Research renders offline with sockets blocked | 0 | **PASS** |
| `test_all_six_pages_render_offline_with_blocked_network[pages/4_Stress_Lab.py]` | Stress Lab renders offline with sockets blocked | 0 | **PASS** |
| `test_all_six_pages_render_offline_with_blocked_network[pages/5_Evidence_and_Limits.py]` | Evidence & Limits renders offline with sockets blocked | 0 | **PASS** |
| `test_ui_metrics_display_exact_loader_values` | Displayed metric values match loader/fixture values | 0 | **PASS** |
| `test_ui_components_perform_no_ml_or_ranking_computations` | AST check verifies UI components import no ML models or compute ranks | 0 | **PASS** |
| `test_ui_disclaimers_and_banners_present` | All mandatory banners (`SYNTHETIC DEMO DATA`, `INSUFFICIENT_HISTORY`, etc.) present | 0 | **PASS** |

---

## 3. Test Execution Command & Evidence

```text
.venv/bin/python -m pytest -q tests/test_regression_agent_b.py
...........................                                              [100%]
27 passed in 0.73s
```

* **Offline Verification:** All network sockets were disabled via pytest monkeypatch (`socket.create_connection`, `socket.socket.connect`). Zero network requests were made.
* **Manual / Offline Smoke Procedure:** For manual inspection without running pytest:
  ```bash
  make app
  # Inspect all 6 tabs in sidebar: Command Centre, Forecast Lab, Sentiment Monitor,
  # Fund Research, Stress Lab, Evidence & Limits.
  ```

All Prompt 24 requirements are completely satisfied.
