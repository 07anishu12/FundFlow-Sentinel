# FundFlow Sentinel — Historical Verification Report

> **SUPERSEDED — historical report, not current release evidence.**
>
> The default flow table in `data/snapshots/processed/flows_category_month.csv` contains eight demonstration rows for `2024-09`, with row-level source marker `synthetic:not-a-source`. It is not evidence of 72 months of real AMFI observations. The latest recorded GitHub Actions run on main (`40933515446`) failed before the full suite because `python -m fundflow.cli` could not import `fundflow.cli`; subsequent test and UI smoke steps were skipped.
>
> Do not use historical test counts, live-source claims, forecast metrics or screenshots as proof of the present branch's production readiness. See [Current Production Readiness](production_readiness.md) and the follow-up remediation report for current findings.

## Historical context

This file previously described a 72-month flow dataset, live-source retrieval, forecasts and NAV results. Those claims are not supported by the currently committed default snapshot.

## Current decision

**Production data release remains blocked** pending permission-cleared ingestion, sufficient real history, successful current CI, and a fresh visual review.
