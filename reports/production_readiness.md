# FundFlow Sentinel — Current Production Readiness

**Reviewed against main commit:** `0c3ccb54d0b4a09d561cbe7f894515d8ddbec3d9`  
**Current decision:** **NOT PRODUCTION-DATA-READY**

This report supersedes earlier release summaries that described live-flow activation or a full passing quality gate. The checked-in bundle must be assessed from actual repository contents and CI evidence, not copied execution summaries.

## Current findings

| Gate | Current status | Evidence |
|---|---|---|
| Default bundle integrity | **Loader correction needed** | The root-level `data/manifest.json` duplicates `data/snapshots/manifest.json`, while the data files are under `data/snapshots/processed` and `data/snapshots/outputs`. The loader can select the wrong directory. |
| Category flow coverage | **Blocked** | `data/snapshots/processed/flows_category_month.csv` contains eight rows for `2024-09`; each uses `source_url=synthetic:not-a-source`. This is not a historical AMFI dataset. |
| Historical NAV coverage | **Not proven by default bundle** | The offline processed NAV bundle is not evidence of verified multi-year NAV coverage for all ten schemes. A current NAV snapshot cannot replace years of history. |
| Source permission | **Blocked pending entitlement** | `config/sources.yaml` disables retrieval by default; AMFI flows/NAV are restricted and disabled; MFapi is unverified and disabled. |
| Forecast validation | **Insufficient history** | The default flow bundle cannot satisfy the 36-month training requirement or support credible historical out-of-sample forecasting claims. |
| UI value integrity | **Being corrected** | The application had hard-coded fallbacks for forecast rate, AUM, month, stress outflow and missing sentiment, plus a formatter that appended units to invalid values. |
| GitHub CI | **Failed at snapshot verification** | Run [40933515446](https://github.com/07anishu12/FundFlow-Sentinel/actions/runs/40933515446) failed at `python -m fundflow.cli -v snapshot --verify` with `No module named fundflow.cli`; full tests and UI smoke tests were skipped. |
| UI screenshot claims | **Not current evidence** | Feature-branch screenshots do not prove the current main version or a passing CI run. |

## Fixes in this remediation branch

- Set `PYTHONPATH=src` in CI.
- Skip an identical root manifest only when its tables exist in the nested snapshot bundle.
- Add domain-aware formatting: missing/invalid values become `N/A` without units; genuine signed returns, drawdowns, net flows and sentiment scores remain signed.
- Remove default forecast, date, AUM, outflow and neutral-sentiment values.
- Replace the false refresh-success message with a local bundle reload that makes no claim of external refresh.
- Correct stale documentation that described demonstration rows as empirical AMFI data.

## Required before production

1. Obtain appropriate written permission or choose a provider whose licence permits ingestion, storage, processing, and redistribution.
2. Implement and run ingestion for historical monthly category-flow files and historical scheme NAV independently.
3. Build a provenance-complete bundle with source URLs/IDs, observation dates, retrieval timestamps, accepted/rejected counts, hashes, and availability timestamps.
4. Verify at least 36 months of complete category-flow history (preferably 60+); do not interpolate missing months or fill missing financial metrics with zero.
5. Validate at least three years of NAV per scheme before historical metrics; show actual history length and reject insufficient schemes.
6. Rerun `make check`, ensure GitHub Actions passes, and visually validate desktop/tablet/mobile layouts.
7. Show live only after a verified refresh; show cached/offline only when source and freshness are evidenced; otherwise show unavailable.

## Verification note

This is a repository/CI review, not a claim that tests passed in the remediation session. Until all data and CI gates pass, deployment remains **BLOCKED**.
