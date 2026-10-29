# Production data readiness — 29 October 2026

## Current release decision

**Status: not production-data-ready.** The repository contains a useful Streamlit shell and data contracts, but the default materialized snapshot is not real market data.

The checked-in `data/snapshots/manifest.json` declares:
- `mode: offline_snapshot`
- source: `FundFlow Sentinel Verified Offline Demo Snapshot`
- source period: `2024-09`
- source files for category flows, NAV, scheme master, features, predictions, alerts, sentiment, and shortlist with `origin: synthetic` and `source_id: synthetic:not-a-source`.

The current UI must keep the synthetic warning for this bundle. Removing the warning without replacing the rows would misrepresent synthetic values as financial observations.

## What the UI change does

The page shell now distinguishes:
- **Synthetic fixture:** explicitly warns that values are illustrative and blocks production-readiness claims.
- **Offline snapshot:** says the app is reading local data, not fetching live data.
- **Live-mode bundle:** avoids calling it “LIVE VERIFIED”; a mode label is not proof that the current page fetched data or that the underlying data are fresh.
- **Unknown/unverified:** reports that provenance is not established.

This is a presentation and governance correction. It does not manufacture real data or turn the offline bundle into a live feed.

## Why the remaining pages show N/A

### Category flow forecasting

The current category flow table contains only eight synthetic category-month rows for September 2024. That is not enough to satisfy the 36-month model-training requirement, and it cannot support a valid out-of-sample evaluation. Missing calendar months must not be interpolated or filled with fabricated values.

The CLI's ingestion stage expects local files under `data/raw/amfi/` matching `am*repo.xls*`; it is not evidence that a live monthly flow workbook was fetched. The source registry currently marks AMFI flow retrieval disabled/restricted. Before enabling ingestion, verify the precise source endpoint, permitted use, storage and redistribution terms, workbook layout, publication/revision dates, and category definitions. If permission is unavailable, keep the flow dataset unavailable rather than scrape or redistribute restricted data.

### NAV and fund research

The adapter for AMFI's daily NAV snapshot is separate from the historical NAV series required for 3-year CAGR, volatility, Sortino, and drawdown. A successful current NAV snapshot cannot supply years of history by itself. Historical scheme NAV must be ingested from a source whose terms allow the intended storage and use; retain source URLs, retrieval timestamps, observation dates, and rejected-row counts. Rankings stay unavailable until sample coverage is sufficient.

### Sentiment

A live headline adapter and an independently validated historical sentiment series are separate requirements. No verified recent article sample means sentiment must remain unavailable, not zero. Do not merge RSS headline tone with GDELT macro tone. Keep sentiment contextual unless a proper historical out-of-sample test establishes incremental forecasting value.

## Required execution sequence

1. **Quarantine demo rows from production use.** Keep fixtures only under an explicitly named test/demo bundle. Never use `synthetic:not-a-source` as a real source.
2. **Approve sources and terms.** Update `config/sources.yaml` only after the actual endpoint, permitted use, redistribution status, and retrieval policy are verified. Do not enable restricted sources merely because an HTTP request succeeds.
3. **Implement real ingestion per source.** Build and test the AMFI monthly workbook parser against dated real files, including layout variants and publication lag. Implement historical NAV ingestion separately. Add retry, size limits, schema validation, duplicate detection, atomic cache replacement, and a machine-readable run report.
4. **Materialize a provenance-complete real bundle.** Every row must carry or map to a verified source, retrieval time, observation period/date, and availability/publication date. The manifest must not contain synthetic origins for production tables.
5. **Validate coverage.** Require at least 36 valid dated monthly observations for model training (prefer 60+ months for research), a complete monthly calendar for each category, and explicit missing-period reporting. Never convert missing values into zero.
6. **Rebuild features and models.** Apply `available_from <= as_of`, expanding-window walk-forward validation, train-fold-only preprocessing, inner time-series model selection, and persistence baseline comparisons. Publish metrics only when held-out samples exist.
7. **Enable sentiment and ranking independently.** Sentiment needs a verified recent article sample and clear provenance. Ranking needs adequate historical scheme NAV and a survivorship-bias disclosure.
8. **Run gates and inspect the UI.** Run `make check`, the page AppTests, live adapter tests with mocked responses, parser tests using licensed sample workbooks, and a separate opt-in source connectivity check. Review the source ledger and a fresh dashboard screenshot before release.
9. **Deploy only after release gates pass.** The cloud container being healthy does not prove the data pipeline is healthy. Add scheduled refresh, monitoring, alerting for stale/missing feeds, and a last-known-good cache with visible age.

## Acceptance criteria

- No production page renders a synthetic value as an observed value.
- The dashboard never labels a local mode flag alone as “LIVE VERIFIED.”
- Every shown metric identifies observed/forecast/scenario type, units, period, source, and freshness.
- Forecast output is withheld when the training window or calendar coverage is insufficient.
- N/A means unavailable; it is never silently changed to zero.
- Live feed tests record HTTP status, retrieval timestamp, received/accepted/rejected records, duplicates, latest observation date, and cache status.
- Source terms permit the intended storage, processing, and distribution.
- Model performance claims are reproducible from actual out-of-sample predictions.

## Important limitation

This document and the UI correction do not claim that live monthly category flows, historical NAV, news sentiment, or cloud deployment have been completed. The next substantive blocker is obtaining and validating permission-cleared real source data and wiring it into the ingestion pipeline. Until then, keep production observations and forecasts withheld and use the demo bundle only for interface/testing.
