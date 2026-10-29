# FundFlow Sentinel

A transparent research dashboard for Indian mutual-fund industry flows and scheme NAV history. The application does not manufacture observations: unavailable data is shown as unavailable, forecasts are distinguished from observations, and every dataset carries source and freshness metadata.

## Important data scope

- **Category-level industry flows:** downloaded from AMFI's monthly Excel reports when available. Official report layouts can change; ingestion validates expected fields and reports failures rather than substituting demo values.
- **Scheme NAV:** latest scheme NAV snapshot from AMFI's NAVAll feed. This is a daily snapshot, not a historical NAV series. Historical scheme analytics require a historical source and are disabled unless sufficient real dated observations are available.
- No synthetic data is shipped or loaded by the production UI. Unit tests use explicitly labelled in-memory fixtures only.
- An AMFI monthly report is category/industry data; it must never be attributed to a particular scheme.

## Run locally

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
streamlit run app.py
```

Use **Refresh data** to retrieve current sources. Network failures result in an explicit unavailable/error state. Cached data, if configured later, must be labelled cached and retain its source timestamp.

## Research and model caveats

Forecasts are research estimates, not investment advice or liquidity estimates. Walk-forward validation is chronological and reports the actual held-out periods and metrics. A gap is calculated only when a target-period actual exists: `actual - forecast`. AUM is not a proxy for redemption capacity, holdings liquidity, or cash available to redeem.

## Sources

- AMFI monthly industry reports: https://www.amfiindia.com/research-information/amfi-monthly
- AMFI NAV download: https://portal.amfiindia.com/spages/NAVAll.txt
- AMFI NAV information/history: https://www.amfiindia.com/net-asset-value/nav-download

See `DEPLOYMENT.md` for runtime guidance and `tests/` for deterministic tests.
