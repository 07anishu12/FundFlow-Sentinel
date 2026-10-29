# FundFlow collaboration rules

Read `docs/INTERFACES.md` and `docs/IMPLEMENTATION_AUDIT.md` before changes. Preserve the architecture document. Every task: inspect owned code/dependencies, state blockers, make the smallest complete change, run focused and relevant existing tests, inspect diff, report files/commands/results/risks/next dependency. Never report unexecuted tests as passed.

Frozen table columns and public signatures require a written proposal and Lead/Integrator approval before modification. Shared configs, dependencies and fixtures are Lead-owned except `config/sources.yaml`, delegated to Agent A in Wave 1. Agent A owns registry.py, source ledger and registry tests. Agent B owns app/** and test_app_shell.py. Do not edit another owner's files silently. No parallel feature development before the schema gate passes.

All fixture data is synthetic. UI must display SYNTHETIC DEMO DATA for fixtures; every displayed metric needs OBSERVED/FORECAST/SCENARIO, period, units and source/freshness. Never invent source URLs, permissions, results or performance claims. Live access is never required by the app. Ranking cannot import forecasting/alerts/flows; sentiment is context unless an approved historical out-of-sample comparison demonstrates benefit. Ingestion and redistribution permissions are separate.

Use Python 3.11 and the local .venv. Run `make validate` for contracts and `make test` for the full suite. Do not add dependencies, infrastructure, fake pipeline stubs or new model calculations to the UI without a task requiring them. Preserve user changes; never reset or clean the workspace to make tests pass.
