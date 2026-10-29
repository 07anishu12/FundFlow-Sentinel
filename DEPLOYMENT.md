# Deployment and operational readiness

## Local run

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
streamlit run app.py
```

## Current implementation status

- The Streamlit app is a source-first research prototype and does not load synthetic production data.
- AMFI NAVAll adapter fetches the current scheme NAV snapshot on explicit refresh. The feed is not historical NAV history.
- AMFI monthly flow data is deliberately marked unavailable until a verified download URL, workbook layout, parser, and source-contract tests are implemented.
- Forecast, risk, sentiment, and stress metrics remain N/A until their required observed inputs are present.
- A successful NAV request does not prove the flow adapter, all pages, model validation, or cloud deployment are production-ready.

## Verification

```bash
python -m compileall app.py fundflow tests -q
pytest -q
```

## Before production use

1. Implement and test a parser for a currently published AMFI monthly industry report.
2. Verify terms/licensing for every source and record source URL, retrieval timestamp, HTTP status, accepted/rejected rows, and latest observation date.
3. Add a dated historical NAV source and test its completeness before computing scheme returns or risk metrics.
4. Implement expanding-window walk-forward validation, with train-fold-only preprocessing and an explicit persistence benchmark.
5. Add a durable last-known-good cache only if its age, source timestamp, and cached status are clearly exposed.
6. Configure secrets, monitoring, health checks, pinned dependency locks, CI, and a cloud runtime before claiming production deployment.
