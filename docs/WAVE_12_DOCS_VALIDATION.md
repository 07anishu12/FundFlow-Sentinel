# Wave 12 Documentation Validation Report

**Date:** 2026-10-29  
**Owner:** Agent B (Documentation & Technical Accuracy Audit)  
**Scope:** Wave 12 Prompt 26 — Repository-Accurate Documentation  
**Status:** **PASS — 100% RECONCILED AGAINST CODE, CONFIGURATION, AND DATA ARTIFACTS**

---

## 1. Executive Summary

Agent B conducted an exhaustive audit of all user-facing and technical documentation against the live code, frozen contracts, source governance ledger, generated artifacts, and test suites.

* **Documents Produced / Updated:**
  * [`README.md`](file:///Users/anny/Desktop/mutual-fund/README.md) (Complete overhaul replacing Wave 1 scaffold)
  * [`docs/USER_GUIDE.md`](file:///Users/anny/Desktop/mutual-fund/docs/USER_GUIDE.md) (Comprehensive operational guide for all 6 pages)
  * [`docs/ARCHITECTURE.md`](file:///Users/anny/Desktop/mutual-fund/docs/ARCHITECTURE.md) (Implemented architecture specification with Mermaid data-flow diagram)
  * [`docs/WAVE_12_DOCS_VALIDATION.md`](file:///Users/anny/Desktop/mutual-fund/docs/WAVE_12_DOCS_VALIDATION.md) (This document)
* **Technical Accuracy Invariant:** Every command, path, column name, metric weight, mathematical formula, and empirical observation count matches the actual codebase. Zero hypothetical or planned features are documented as implemented.

---

## 2. Documented Command Verification

Every command documented across `README.md` and `docs/USER_GUIDE.md` was executed and verified:

| Documented Command | Purpose | Working Directory | Exit Code | Verified Evidence |
|---|---|---|---|---|
| `make validate` | Schema & contract test suite | Root | 0 | **32 passed in 0.21s** |
| `make test` | Full test suite | Root | 0 | **287 passed in 5.75s** |
| `make snapshot` | Snapshot creation & publishing | Root | 0 | Published 13 artifacts to `data/snapshots/` |
| `.venv/bin/python -m fundflow.cli snapshot --verify` | Independent hash & schema verification | Root | 0 | All 13 artifacts match manifest digests |
| `.venv/bin/python -m fundflow.cli --offline all` | Pipeline execution end-to-end | Root | 0 | Stages executed; `run_report.json` saved |
| `make app` | Streamlit Command Centre launch | Root | 0 | Verified offline rendering of all 6 pages |

* **Unverified Commands:** None. Every command in the quickstart and user guide was tested directly in the current `.venv` environment.

---

## 3. Claim-to-Evidence Mapping for Numerical & Quantitative Claims

| Documented Claim | Document Reference | Underlying Implementation / Artifact File | Measured Value / Grounded Truth | Verification Status |
|---|---|---|---|---|
| Empirical flow history covers 1 month (September 2024) across 8 categories | `README.md`, `USER_GUIDE.md`, `ARCHITECTURE.md` | [`data/processed/flows_category_month.csv`](file:///Users/anny/Desktop/mutual-fund/data/processed/flows_category_month.csv) | Exactly **8 rows**, month `2024-09` | **VERIFIED** |
| Market context history covers 61 months (September 2019 to September 2024) | `README.md`, `USER_GUIDE.md`, `ARCHITECTURE.md` | [`data/processed/market_month.csv`](file:///Users/anny/Desktop/mutual-fund/data/processed/market_month.csv) | Exactly **61 rows**, span `2019-09` to `2024-09` | **VERIFIED** |
| Walk-forward model warmup requires 36 months; empirical bands marked `insufficient_history` | `README.md`, `USER_GUIDE.md`, `ARCHITECTURE.md` | [`data/outputs/model_results.json`](file:///Users/anny/Desktop/mutual-fund/data/outputs/model_results.json), [`src/fundflow/forecasting.py`](file:///Users/anny/Desktop/mutual-fund/src/fundflow/forecasting.py) | `payload.status == "insufficient_history"`; warmup parameter `min_train_months=36` | **VERIFIED** |
| NAV Ranking weights: 40% CAGR, 20% Vol, 20% Drawdown, 10% Sortino, 10% Consistency | `README.md`, `USER_GUIDE.md`, `ARCHITECTURE.md` | [`src/fundflow/ranking.py:BASE_WEIGHTS`](file:///Users/anny/Desktop/mutual-fund/src/fundflow/ranking.py#L32) | `{"cagr": 0.40, "vol": 0.20, "max_drawdown": 0.20, "sortino": 0.10, "consistency": 0.10}` | **VERIFIED** |
| NAV Scheme eligibility: Direct Plan, Growth Option, $\ge 750$ days, $\le 10$-day gap | `README.md`, `USER_GUIDE.md`, `ARCHITECTURE.md` | [`src/fundflow/ranking.py:filter_eligible_schemes`](file:///Users/anny/Desktop/mutual-fund/src/fundflow/ranking.py#L65) | `plan_type == "Direct"`, `option_type == "Growth"`, `history_days >= 750`, `max_gap <= 10` | **VERIFIED** |
| Alert rules: Critical ($\ge 90\text{th}$ + $Z \ge 2.0$ or mom $\ge 0.10$), Elevated ($\ge 75\text{th}$) | `README.md`, `USER_GUIDE.md`, `ARCHITECTURE.md` | [`src/fundflow/alerts.py:evaluate_alert_rules`](file:///Users/anny/Desktop/mutual-fund/src/fundflow/alerts.py#L68) | Thresholds match exact rule logic | **VERIFIED** |
| Stress outflow is capped at 100% of reference AUM | `README.md`, `USER_GUIDE.md`, `ARCHITECTURE.md` | [`src/fundflow/stress.py:stress_outflow`](file:///Users/anny/Desktop/mutual-fund/src/fundflow/stress.py#L35) | `min(outflow_cr, ref_aum_cr)`; negative rates rejected | **VERIFIED** |
| Ranking imports 0 forecasting/alert/flow modules | `README.md`, `USER_GUIDE.md`, `ARCHITECTURE.md` | [`tests/test_regression_agent_b.py:test_ranking_imports_have_zero_cross_lane_contamination`](file:///Users/anny/Desktop/mutual-fund/tests/test_regression_agent_b.py#L225) | AST verification confirms 0 cross-lane imports | **VERIFIED** |
| Sentiment sufficiency requires $\ge 30$ articles | `README.md`, `USER_GUIDE.md`, `ARCHITECTURE.md` | [`src/fundflow/sentiment.py:check_sentiment_sufficiency`](file:///Users/anny/Desktop/mutual-fund/src/fundflow/sentiment.py#L125) | `min_required = 30`; returns `insufficient_data` if $<30$ | **VERIFIED** |

---

## 4. Discovered Discrepancies & Resolutions

1. **Outdated Root `README.md`:**
   * *Issue:* The existing `README.md` was a Wave 1 placeholder stating that no models, pipelines, or reports existed.
   * *Resolution:* Replaced with an authoritative, comprehensive README covering the full 12-wave implementation, quickstart, data sufficiency bounds, and architecture.
2. **Missing User Guide & Architecture Documentation:**
   * *Issue:* Neither `docs/USER_GUIDE.md` nor `docs/ARCHITECTURE.md` existed in the repository.
   * *Resolution:* Created both documents, including a Mermaid data-flow diagram reflecting the exact implemented subsystems and isolating the NAV fund research lane.
3. **Data Sufficiency Clarity Across Documents:**
   * *Issue:* Ambiguity could lead users to assume that 61 months of market indicators enable 61 months of flow forecasting.
   * *Resolution:* Explicitly documented across all three files that empirical flow data covers only 1 month (September 2024) and that market indicators do not substitute for flow history.
