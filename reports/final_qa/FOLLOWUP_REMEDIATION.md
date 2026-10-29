# Follow-up remediation — independently verified issues

**Main commit reviewed:** `0c3ccb54d0b4a09d561cbe7f894515d8ddbec3d9`  
**Remediation branch:** `fix/final-verification-guardrails`

## Findings

1. **CI import failure:** GitHub Actions run [40933515446](https://github.com/07anishu12/FundFlow-Sentinel/actions/runs/40933515446) failed at `python -m fundflow.cli -v snapshot --verify` with `No module named fundflow.cli`. Compilation and 32 contract tests passed before the failure; the full test and UI-smoke steps were skipped.
2. **Wrong bundle selected:** `data/manifest.json` duplicates `data/snapshots/manifest.json`, but materialized tables are under `data/snapshots/processed` and `data/snapshots/outputs`. Auto-selection can pick the root manifest and then fail to find its table files.
3. **Invalid metric presentation:** The main-branch metric card always appended units and did not apply a domain check to negative values for quantities that cannot be negative.
4. **Invented fallbacks:** The dashboard included fallback forecast `4.0`, timestamp `9999-12-31T23:59:59Z`, fallback reference AUM `10000.0` crore, default month `2024-09`, fallback stress outflow `500.0` crore, zero-valued forecast rates, and neutral-zero sentiment for missing scores.
5. **Sentiment schema mismatch:** The UI read `sentiment_score` although the frozen contract column is `score`, causing missing values to be replaced with zero.
6. **False refresh success:** The refresh button claimed the cache had been re-verified and all records were valid, but it did not refresh or verify external feeds.
7. **Stale reports:** Multiple checked-in reports claimed 72 months of real AMFI flows and current passing release checks despite the default snapshot being demonstration data. Their release verdicts are now marked historical/superseded.

## Remediation in this branch

- Set CI `PYTHONPATH=src`.
- Skip an identical root manifest only when the nested snapshot is the materialized bundle and root table directories are absent; other bundle errors remain fail-closed.
- Add domain-aware formatting and regression tests for invalid non-negative metrics, legitimate negative returns/flows, and missing placeholders.
- Remove fabricated defaults from the command centre, uncertainty bands, sentiment display, cross-category summary, and stress lab.
- Change the refresh control to reload local data only, without claiming external requests occurred.
- Correct README wording and supersede stale readiness/verification reports.

## Data boundary

No new external datasets were added. The default data bundle remains a demonstration bundle and must stay labelled as such. AMFI flows/NAV are restricted/disabled in the source registry and MFapi is unverified/disabled. This remediation does not claim production data integration or production readiness.

## Verification status

Automated tests have not yet been run against the remediation branch. The GitHub Actions result will be checked after the commit/PR triggers CI.
