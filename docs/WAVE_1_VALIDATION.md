# Contract freeze and Wave 1 validation

Date: 2026-10-28. Runtime: Python 3.11.16 in `.venv`.

## Baseline and preservation

The initial directory contained only the architecture document, with no Git repository or executable application. Initialized Git without committing or staging files. The architecture SHA-256 remained `9664c9b1781119638b3a13caac214aaa25020b7ae25efe2f0e6c3c4f04743856`. Git status reports the original document and new scaffold as untracked; no existing user source/config was overwritten. No historical Git diff is possible for a previously unversioned directory. New-file diffs were generated against `/dev/null` and inspected alongside source reads. CSV CRLF whitespace flagged during review was normalized to LF; tests were rerun.

## Files delivered

- Lead: `docs/IMPLEMENTATION_AUDIT.md`, `docs/INTERFACES.md`, this record, `AGENTS.md`, `README.md`, `.gitignore`, `requirements.txt`, `pytest.ini`, `Makefile`, `src/fundflow/__init__.py`, `src/fundflow/contracts.py`, `tests/test_contracts.py`, six config YAML/CSV files, `data/README.md`, ten fixture CSVs and their manifest/README.
- Agent A: `src/fundflow/registry.py`, `config/sources.yaml`, `docs/SOURCES_AND_LICENCES.md`, `tests/test_registry.py`.
- Agent B: `app/Home.py`, `app/__init__.py`, `app/components.py`, `app/loaders.py`, five files under `app/pages/`, `app/README.md`, `tests/test_app_shell.py`.

## Executed checks

| Command / check | Observed result |
|---|---|
| `python3.11 -m venv .venv` and pip install of the five pins now in requirements.txt | Success; installed pandas 2.2.3, NumPy 2.2.6, PyYAML 6.0.2, pytest 8.3.5, Streamlit 1.45.1 |
| `.venv/bin/python -m pip check` | No broken requirements found |
| Initial `.venv/bin/python -m pytest -q tests/test_contracts.py` | 25 passed before launching the two agents |
| `make validate` after additional invalid-value tests | 32 passed |
| `make test` after Wave 1 implementation and fixture newline normalization | 65 passed: 32 contracts/config, 16 registry, 17 app |
| `.venv/bin/python -m compileall -q src app` | Exit 0 |
| `env -u PYTHONPATH .venv/bin/streamlit run app/Home.py --server.headless true --server.address 127.0.0.1 --server.port 8518 --browser.gatherUsageStats false` | Server launched from repository root without PYTHONPATH |
| `curl --fail --silent http://127.0.0.1:8518/_stcore/health` | `ok`; temporary server subsequently stopped |
| Streamlit AppTest | All six pages render with socket connections blocked, and again with optional CSVs absent; malformed/unlabelled fixtures are withheld |
| Architecture checksum and Git status | Original document unchanged; generated files untracked, no commit made |

A health response proves server startup, while AppTest separately exercises page execution. This is automated smoke validation, not a claim of visual browser review. The app's sole data mode is explicitly synthetic. Fixture outputs are not evidence of training, coverage, ranking or alert quality.

## Gate and next dependency

Contract/config/fixture gate passed before delegation. Wave 1 schema/registry/app integration tests pass without changing frozen column names. Sources remain disabled; provenance inventory records `not_attempted` with no fabricated retrieval timestamp or hash. Registry writes are atomic under a single-writer policy, not multi-process locked.

Real source inspection and permission resolution are the next dependencies. AMFI/NSE and model restrictions are documented in the source ledger; unknown permissions remain unknown. No automatic download or public real-data snapshot is authorized by the inventory. Before modeling, resolve AUD-14 edge cases and verify release/revision availability and calendar splits against real records. Before ranking, resolve AUD-15 conventions. No Wave 2 model/data features were built, and no forecast-quality claim is made.
