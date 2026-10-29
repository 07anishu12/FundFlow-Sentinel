# Frozen interfaces v1

Integrator freeze: 2026-10-28. Authority: architecture sections 5, 7, 8. Exact ordered CSV columns are in `src/fundflow/contracts.py:COLUMNS`; no extra columns, private renames or undeclared `sent_*` extensions. `validate_table(name, frame)` raises ValueError for invalid input and returns the unmodified frame. Empty tables are valid for UI empty states. This is structural validation, not a substitute for future domain/coverage/leakage tests.

Money: INR crore. Rates: percentage points (10 means 10%); sentiment probabilities/shares: fractions. Months: YYYY-MM. Daily NAV and metric dates: YYYY-MM-DD. Availability, retrieval, as-of, publication and training-boundary timestamps: ISO UTC with Z or +00:00, never naive. Scheme IDs are strings. `period` is an ISO day for v1 daily sentiment aggregates; weekly/P2 aggregates require an explicit extension. `riskometer`, future `actual_rate`/`target_rate`, and `sentiment_note` may be blank. CSV booleans are true/false. `contrib_json` is a JSON object. Alert levels are Normal/Elevated/Critical.

Every flow row requires evidence-backed `available_from`; never infer availability from month-end alone. Source fields in synthetic fixtures use the non-network marker `synthetic:not-a-source`. Fixture manifest declares synthetic=true; all fixture views must display SYNTHETIC DEMO DATA. Fixtures are interface examples only, not credible trained predictions. Real dataset acceptance requires a separate quality report.

## Function signatures (reserved; not implemented by this freeze)

```python
validate_flows(raw: pd.DataFrame) -> tuple[pd.DataFrame, dict]
compute_rates(flows: pd.DataFrame) -> pd.DataFrame
build_feature_matrix(flows, market, sentiment=None) -> pd.DataFrame
walk_forward(features, cfg) -> tuple[pd.DataFrame, dict]
generate_alerts(predictions, history, sentiment_agg=None) -> pd.DataFrame
stress_outflow(aum_cr: float, rate_pct: float) -> dict
scenario_table(forecast_rate, bands, hist_max, aum_cr) -> pd.DataFrame
rank_funds(nav, scheme_master, cfg) -> tuple[pd.DataFrame, pd.DataFrame]
```

Use the explicit signature block over the illustrative tree's extra `as_of_rule` argument. No fake callable stubs are supplied. Model configuration selects level target initially. Any level/change comparison must be selected inside training folds; held-out results cannot select the target mode. All categories for a target month stay in one fold; both inner and outer folds use calendar boundaries. Training labels must themselves be available by prediction as-of. Residual bands and anomaly reference distributions use only previously available history. Basic bands are P0; polish is P2.

## Ownership and changes

Lead owns contracts, dependencies, Makefile, interfaces, fixtures, shared config except the explicit Wave 1 delegation of `config/sources.yaml` to Agent A. A owns registry.py, sources.yaml, source ledger and registry tests. B owns app/** and tests/test_app_shell.py. Later modeling and ingestion ownership is assigned separately. Propose a contract change in writing with rationale, affected callers, migration and tests; integrator approval must precede edits. Neither agent may silently alter the freeze or the other's files. No commits required in this wave.

Registry is an additional ledger, not an extension to the ten tables. Agent A documents its columns and retrieval/outcome semantics. No network or model work belongs in the UI. Loaders read files, validate them and handle absent optional tables. Ranking must never import forecasts, alerts or flow calculations. App may eventually call stress/explain public functions; neither exists yet. Source policy may deny redistribution even when retrieval is free.

## Commands

Use Python 3.11 (`python3` on this Mac is 3.14). Setup: `python3.11 -m venv .venv`, then `.venv/bin/python -m pip install -r requirements.txt`. `make validate` runs schema/config tests; `make test` runs all tests. `make app` runs `.venv/bin/python -m streamlit run app/Home.py`; after activation, `streamlit run app/Home.py` is equivalent. The app target is wired to Agent B's owned entry point and becomes runnable at the Wave 1 gate. No data/train/all target is advertised until implemented. Dependencies are direct pins for this wave, not a transitive lock or a completed ML stack.

## Deferred decisions before modeling / ranking

Real source inspection must settle release-date evidence, revision vintages, historical category mapping and source permissions. Before Quant begins, Lead must approve zero-MAD/zero-denominator behavior, missing lag policy, negative forecast/stress policy (architecture only defines upper cap), percentile ties, prediction-band artifact schema and anomaly schema. Before ranking, define NAV gap tolerance, trading-day calendar, Sortino target, score direction and weight perturbation renormalization. No agent may invent these decisions. These do not block registry or fixture shell work.

## Wave 2 additive loader contract — approved by Lead, 2026-10-28

Rationale: the ten CSV contracts do not describe bundle provenance, generation time, or JSON output shapes. The UI needs those facts to distinguish missing/stale/invalid data and synthetic fallback without performing business calculations. This additive envelope does not rename CSV columns, change existing function signatures, or freeze model evaluation metric names. Existing flat synthetic fixtures remain supported without modification.

Agent B owns only `app/loaders.py`, `app/components.py`, and `tests/test_app_loaders.py` in this wave. Agent A owns `docs/AMFI_FIELD_INSPECTION.md` and the source inspection notebook/script. Lead approves interface additions and field-map decisions; config/category_map.csv and shared dependencies remain unchanged pending evidence.

### Local bundles

- Current local output bundle: `data/manifest.json`, `data/processed/<table>.csv`, `data/outputs/<table>.csv`.
- Offline snapshot bundle: `data/snapshots/manifest.json` with equivalent processed/outputs children.
- Legacy synthetic bundle: `data/snapshots/fixtures/manifest.json` and flat table CSVs.
- Flows, market, feature_matrix, nav_daily and scheme_master live under processed; predictions, alerts, shortlist and sentiment tables live under outputs.
- JSON artifacts: `outputs/model_results.json`, root `quality_report.json`, root `source_metadata.json`, relative to the selected bundle.

Modern manifest: version=1, mode=`offline_snapshot` / `live` / `synthetic`, generated_at=ISO UTC, source=nonempty string, tables=list of known table names, artifacts=list drawn from `model_results`, `quality_report`, `source_metadata`. `live` describes locally materialized refresh provenance only; it guarantees neither fresh data nor network access. Every loader remains network-free. The legacy `synthetic: true` fixture manifest lacks generated_at; generation time/freshness must remain unknown rather than inferred from filesystem mtime.

Default selection tries current, snapshot, then fixtures only when earlier bundles are absent. An explicit bundle selection must not silently choose another bundle. Malformed candidates are reported invalid, not silently replaced. Every use of fixtures, including fallback, must carry a prominent SYNTHETIC DEMO DATA warning. Resolve all bundle/file/manifest paths under the repository data root, rejecting traversal and symlink escapes. Environment variables cannot redefine that trust root; a data-root injection is permitted only as an explicit programmatic test argument.

### JSON envelopes

Each artifact is an object with `version: 1`, ISO UTC `generated_at`, nonempty `source`, and object `payload`:

- model_results payload requires `metrics` object and `limitations` list of strings. Metric key names remain open pending the modeling task. Numeric metric values must be finite. Structural acceptance does not establish out-of-sample evaluation, units, or model quality.
- quality_report payload requires `status` (`pass`, `fail`, `unknown`) and `checks` list of objects. This is a carrier for producer findings, not a substitute for domain validation.
- source_metadata payload requires `sources` list of objects. Source-specific permission and provenance are governed by the registry; loader acceptance confers no permission.

Additional payload fields are permitted. Arbitrary producer payload fields must not become unlabelled displayed metrics. Non-finite JSON numbers are invalid. Explicit empty-state handling is required for missing, empty or malformed files.

Typed loader metadata exposes state (`ok`, `missing`, `empty`, `invalid`, `stale`), source, last data period, generated time and mode. Missing temporal evidence is represented as unknown. The default 45-day stale threshold is a configurable UI display policy, not a forecast availability rule; tests use an injected clock. No loader may infer `available_from`, recalculate rates/scores/forecasts or fill missing metrics with fabricated values.
