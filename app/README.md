# Offline shell

Design mode: operate. Use native Streamlit navigation and a consistent hierarchy: page purpose, synthetic-data warning, freshness, selected category, labelled metric, limitations. This stage prioritizes a clear, usable research workflow over decorative styling.

From the repository root, activate `.venv`, then run `streamlit run app/Home.py`. The sidebar contains Command Centre, Forecast Lab, Sentiment Monitor, Fund Research, Stress Lab, and Evidence and Limits. No `PYTHONPATH` setup is needed.

Only `data/snapshots/fixtures/` is used by default. `FUNDFLOW_FIXTURE_DIR` may point to another local synthetic fixture directory for tests. The loader requires its manifest to declare `synthetic: true` and list each table, then validates the frozen CSV contract. It withholds invalid data and displays an empty state. Real data mode, live refresh, model fitting, scoring and scenario arithmetic are intentionally not implemented in this wave.

Automated smoke: `.venv/bin/python -m pytest -q tests/test_app_shell.py`. Tests render all six pages with socket connections forbidden, then again with all optional CSVs absent. They also reject malformed CSVs and undeclared data and check label requirements/import boundaries.

Manual smoke: launch from the root, visit each sidebar page, check the prominent SYNTHETIC DEMO DATA warning, context beneath each metric, and freshness banner. Switch categories where present. No page should imply that the fixture values are measured model results. Stress Lab must show its unavailable state rather than calculate a scenario. To exercise missing data, set `FUNDFLOW_FIXTURE_DIR` to an empty local folder and restart; pages must remain navigable.
