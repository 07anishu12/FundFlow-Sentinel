# Implementation audit — 2026-10-28

## Inspected baseline

The workspace originally contained exactly one regular file: `FundFlow Sentinel — Final Build Architecture (for coding agents).md` (28,131 bytes). Read in full, sections 1–13. No source, data, dependency manifest, tests, local AGENTS.md/CLAUDE.md, virtualenv or .git existed. Both Git status and `/usr/bin/git status --short --branch` reported not a Git repository. Thus no existing tracked changes could be enumerated; no source implementation or tests existed to preserve. The architecture is the asset to preserve; SHA-256: `9664c9b1781119638b3a13caac214aaa25020b7ae25efe2f0e6c3c4f04743856`.

Commands executed: `pwd`, `rg --files --hidden -g '!.git' -g '!node_modules' -g '!.venv'`, `/bin/ls -la`, architecture read with `cat`, local instruction existence checks, `command -v python3 python3.11 git rtk`, `python3 --version`, `python3.11 --version`, `python3.11 -m pip --version`, and Git status. Python default: 3.14.7; explicit Python 3.11.16 is installed. No baseline run/test command existed. No baseline tests were run or passed. No source-data licence or remote availability has been verified by this initial audit.

## Architecture mapping and gap register

Paths below are required future paths, absent at baseline. P0 blocks reliable MVP; P1 enriches it; P2 is stretch. File existence alone never closes a gap.

| ID | Severity | Architecture → path | Finding / proposed owner |
|---|---|---|---|
| AUD-01 | P0 | §7 → .git, README.md, requirements.txt, Makefile | No repository/runtime wiring; Lead initializes without replacing architecture and pins 3.11-compatible dependencies. |
| AUD-02 | P0 | §5 → src/fundflow/contracts.py, config/* | All ten contracts/configs absent; Lead freezes exact schemas and synthetic fixtures before delegation. |
| AUD-03 | P0 | §1/4 → ingest/amfi_flows.py, validate.py, config/category_map.csv | No real files, parser, units, release dates or history inspected; Data owner must inspect source fields/layouts and establish >=60 months, >=3 categories. |
| AUD-04 | P0 | §4/9 → registry.py, config/sources.yaml, docs/SOURCES_AND_LICENCES.md | No provenance/licence evidence; Agent A records status/terms and blocks unsupported redistribution. |
| AUD-05 | P0 | §5/6 → flows.py, features.py, forecasting.py, tests/test_no_leakage.py | No rates/baseline/model. Quant must enforce available_from and label availability, prior-month AUM denominator and calendar-grouped nested splits. |
| AUD-06 | P0 | §6 → anomaly.py, alerts.py, stress.py, explain.py | No rules/reconciliation. Quant implements exact precedence, event counts and past-only residuals; Lead first settles edge cases below. |
| AUD-07 | P0 | §3/8 → app/**, data/snapshots/, tests/test_app_shell.py | No app or snapshots; Agent B builds offline fixture shell, then integration verifies licensed real snapshots later. |
| AUD-08 | P0 | §7/11 → tests/**, reporting.py, README.md | No validation/evidence pack. Lead requires executed gates; model results must originate from computations. |
| AUD-09 | P1 | §6.5 → nav_metrics.py, ranking.py, tests/test_import_isolation.py | No shortlist; Intelligence owner implements independent NAV-only score and bias disclosure. |
| AUD-10 | P1 | §6.6 → sentiment.py, ingest/news.py | No live context/model licence record; Intelligence owner verifies terms and offline fallback, never predictive by default. |
| AUD-11 | P2 | §6.6/10 → ingest/news.py, features.py, reporting.py | No historical sentiment, macro or deployment; defer until P0 evaluation. |
| AUD-12 | P0 | §5/7 → docs/INTERFACES.md | Feature signature differs between illustrative tree and explicit block; wildcard sent_* conflicts with exact-column promise. Lead uses explicit signature and no sentiment extension in v1. |
| AUD-13 | P0 | §6 → docs/INTERFACES.md, model.yaml | Pooled TimeSeriesSplit can split the same month across categories; global target-mode selection can leak test results. Lead mandates calendar folds and training-only selection. |
| AUD-14 | P0 | §6 → anomaly.py, stress.py, output contracts | Zero MAD/denominators, negative forecasts, percentile ties, bands/anomaly storage unspecified. Lead must settle before Quant implementation. |
| AUD-15 | P1 | §6.5 → ranking.yaml, nav_metrics.py | NAV gap tolerance, Sortino target, calendar and sensitivity renormalization unspecified. Lead resolves before ranking work. |
| AUD-16 | P0 | §4/9 → data/README.md, snapshots | Required committed snapshots can conflict with source redistribution terms. Source owner verifies permissions; synthetic fixtures remain visibly synthetic, never substitutes for real evaluation. |

## Explicit contradiction checks

There is no existing implementation to contradict the design: no scheme-level flow schema, missing-availability code, random split, ranking import of forecasting or network-dependent app was found because no code exists. These are **not implemented/not tested**, not passing checks. Only the architecture describes scheme-level flow design as a rejected idea. Its calendar splits, availability, import isolation and offline requirements need future executable regression tests.

Other specification tensions: raw storage uses both source/retrieval directories (§3) and month filenames (§4); provenance should preserve immutable retrieved versions. `market_month` is in the pipeline but macro is called P2: core Nifty/VIX features are distinct from optional RBI macro. Basic residual bands appear in P0 stress while band polish is P2. Sentiment corroboration requires its own historical percentile even in the live lane; without a valid reference history it must stay unavailable. No current data can resolve these by inspection.

## Dependency and source risks

No dependency manifest or environment existed at baseline. Required first-wave packages: pandas, NumPy, YAML parser, pytest, Streamlit; later add verified pins for scikit-learn and actual spreadsheet adapters, schema library only if needed. No reason to add unused ML/download infrastructure now. AMFI layout drift, category recategorisation, release/revision timestamps and switch-outs require file evidence; high churn is not scheme-level withdrawal risk. NAV survivorship and unofficial wrappers require disclosure/fallback. Yahoo/NSE access and licences cannot be inferred from accessibility. News/model permissions and GDELT coverage must be checked; no historical sentiment benefit is established.

## Ordered execution plan

1. P0 Lead: freeze ten tables, signatures, dates/units, config, synthetic fixtures, ownership and actual commands; run schema/config tests. Follow-up Prompt 02 authorizes skeleton creation after this baseline audit.
2. P0 Wave 1: only after freeze passes, Agent A registry/source policy and Agent B offline shell run in parallel with disjoint ownership. Lead tests all contracts, registry, every app page, missing files and actual server startup.
3. P0 Data: source inspection first, resolve licences/release dates and real mappings, then ingest/validate/rates. Gate: quality report, >=60 months and >=3 categories; no fabricated substitutions.
4. P0 Quant: resolve AUD-14, then baseline/Ridge, calendar walk-forward, availability and future-mutation tests, anomalies/alerts/stress and evidence outputs. No claims of improvement until measured.
5. P0 integration: licensed snapshots, network-off app smoke, complete existing test suite and README commands/results from outputs.
6. P1: isolated NAV ranking and live sentiment context after their conventions/licences are resolved. P2: historical sentiment paired backtest, macro, intervals polish, deployment.

Exact next dependency at audit completion: Lead's contract/config/fixture freeze. After Wave 1, real source inspection and AUD-14 decisions precede model work. This audit is a baseline record; later implementation results belong in the Wave 1 validation record, not retroactively in the baseline.
