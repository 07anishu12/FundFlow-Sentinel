"""Unit tests for NAV history and scheme master metadata ingestion.

Verifies:
- Scheme master parsing from official AMFI text
- Riskometer remains null (no inference from names)
- Survivorship bias disclosure documentation
- Date range chunking and deduplication
- Unofficial wrapper (mfapi.in) caching, labelling, and schema validation
- Graceful degradation on network / format failures
- Import and operational isolation from P0 flow forecasting
"""
from __future__ import annotations

import json
from pathlib import Path
import pytest
import pandas as pd

from fundflow.contracts import validate_table, COLUMNS
from fundflow.ingest.nav import (
    fetch_scheme_master,
    fetch_nav_history,
    _chunk_date_range,
    _parse_amfi_date_to_iso,
    SURVIVORSHIP_BIAS_DISCLOSURE,
)

SAMPLE_NAVALL_TEXT = """Scheme Code;ISIN Div Payout/ ISIN Growth;ISIN Div Reinvestment;Scheme Name;Plan;Option;Net Asset Value;Date

Open Ended Schemes ( Equity Scheme - Large Cap Fund )

Axis Mutual Fund

135762;INF846K01WO1;-;Axis Large Cap Fund - Direct Plan;Direct Plan;Growth Option;28.9301;27-Oct-2026
135765;INF846K01WP8;-;Axis Large Cap Fund - Direct Plan;Direct Plan;IDCW Option;26.6498;27-Oct-2026
135759;INF846K01WJ1;-;Axis Large Cap Fund - Regular Plan;Regular Plan;Growth Option;25.1678;27-Oct-2026

Open Ended Schemes ( Debt Scheme - Corporate Bond Fund )

HDFC Mutual Fund

128628;INF179KA1JC4;-;HDFC Corporate Bond Fund;Regular Plan;Growth Option;24.1989;27-Oct-2026
128629;INF179KA1IZ7;-;HDFC Corporate Bond Fund;Direct Plan;Growth Option;25.3204;27-Oct-2026
"""

SAMPLE_MFAPI_JSON = {
    "meta": {
        "fund_house": "Aditya Birla Sun Life Mutual Fund",
        "scheme_type": "Open Ended Schemes",
        "scheme_category": "Equity Scheme - Large Cap Fund",
        "scheme_code": 119551,
        "scheme_name": "Aditya Birla Sun Life Frontline Equity Fund - Direct Plan - Growth"
    },
    "data": [
        {"date": "10-01-2024", "nav": "108.4687"},
        {"date": "09-01-2024", "nav": "108.4351"},
        {"date": "08-01-2024", "nav": "108.4013"},
        {"date": "05-01-2024", "nav": "108.2934"},
        {"date": "04-01-2024", "nav": "108.3068"},
        {"date": "03-01-2024", "nav": "108.3033"},
        {"date": "02-01-2024", "nav": "108.3020"},
        {"date": "01-01-2024", "nav": "108.2962"}
    ],
    "status": "SUCCESS"
}


def test_chunk_date_range():
    # Range of 100 days chunked into max 45 days -> 3 chunks
    chunks = _chunk_date_range("2024-01-01", "2024-04-10", chunk_days=45)
    assert len(chunks) == 3
    assert chunks[0] == ("2024-01-01", "2024-02-14")
    assert chunks[1] == ("2024-02-15", "2024-03-30")
    assert chunks[2] == ("2024-03-31", "2024-04-10")


def test_chunk_date_range_invalid():
    with pytest.raises(ValueError, match="cannot be after"):
        _chunk_date_range("2024-05-01", "2024-01-01")


def test_scheme_master_parsing_from_fixture(tmp_path):
    df, meta = fetch_scheme_master(
        raw_text=SAMPLE_NAVALL_TEXT,
        cache_dir=tmp_path / "nav_cache"
    )

    # Validate exact contract
    assert tuple(df.columns) == COLUMNS["scheme_master"]
    validate_table("scheme_master", df)

    assert len(df) == 5
    assert "135762" in df["scheme_code"].values
    assert "128628" in df["scheme_code"].values

    # Invariant: do not infer riskometer from names; riskometer must remain null/blank
    assert (df["riskometer"] == "").all()

    # Invariant: survivorship bias disclosure present in metadata
    assert "Survivorship Bias" in meta["survivorship_bias_disclosure"]
    assert meta["scheme_count"] == 5


def test_scheme_master_deduplicates_codes(tmp_path):
    text_with_dups = SAMPLE_NAVALL_TEXT + "\n135762;INF846K01WO1;-;Duplicate Scheme Code;Direct;Growth;29.0;27-Oct-2026\n"
    df, meta = fetch_scheme_master(raw_text=text_with_dups, cache_dir=tmp_path)
    validate_table("scheme_master", df)
    assert df["scheme_code"].duplicated().sum() == 0


def test_scheme_master_fails_gracefully_on_bad_url(tmp_path):
    # Unreachable port immediately refuses connection and fails gracefully returning empty valid DataFrame
    df, meta = fetch_scheme_master(
        source_url="http://127.0.0.1:9/NAVAll.txt",
        cache_dir=tmp_path,
        timeout=1
    )
    assert tuple(df.columns) == COLUMNS["scheme_master"]
    validate_table("scheme_master", df)
    assert len(df) == 0
    assert "failed" in meta["status"]


def test_nav_history_mfapi_caching_and_contracts(tmp_path):
    # Pre-populate cache for scheme 119551
    cache_dir = tmp_path / "mfapi_cache"
    cache_dir.mkdir(parents=True)
    cache_file = cache_dir / "mfapi_119551.json"
    cache_file.write_text(json.dumps(SAMPLE_MFAPI_JSON), encoding="utf-8")

    df, meta = fetch_nav_history(
        scheme_codes=["119551"],
        start_date="2024-01-01",
        end_date="2024-01-08",
        source="mfapi",
        cache_dir=cache_dir
    )

    assert tuple(df.columns) == COLUMNS["nav_daily"]
    validate_table("nav_daily", df)

    # Date filtering applied
    assert len(df) == 6
    assert df["date"].min() == "2024-01-01"
    assert df["date"].max() == "2024-01-08"

    # Invariant: source_url correctly labelled
    assert (df["source_url"] == "https://api.mfapi.in/mf/119551").all()

    # Invariant: deduplicated
    assert df.duplicated(subset=["date", "scheme_code"]).sum() == 0


def test_nav_history_deduplication_across_overlapping_chunks(tmp_path):
    cache_dir = tmp_path / "dedup_cache"
    cache_dir.mkdir(parents=True)

    # Write overlapping cache responses
    chunk1_content = (
        "Scheme Code;NAV Name;Plan;Option;ISIN;ISIN;Net Asset Value;Date\n"
        "119551;Fund;Direct;Growth;;;100.0;01-Jan-2024\n"
        "119551;Fund;Direct;Growth;;;101.0;02-Jan-2024\n"
    )
    chunk2_content = (
        "Scheme Code;NAV Name;Plan;Option;ISIN;ISIN;Net Asset Value;Date\n"
        "119551;Fund;Direct;Growth;;;101.0;02-Jan-2024\n"  # Overlap on Jan 02
        "119551;Fund;Direct;Growth;;;102.0;03-Jan-2024\n"
    )

    (cache_dir / "amfi_nav_2024-01-01_2024-01-02.txt").write_text(chunk1_content)
    (cache_dir / "amfi_nav_2024-01-02_2024-01-03.txt").write_text(chunk2_content)

    # Query spanning both
    df, meta = fetch_nav_history(
        scheme_codes=["119551"],
        start_date="2024-01-01",
        end_date="2024-01-03",
        source="amfi",
        cache_dir=cache_dir
    )

    assert tuple(df.columns) == COLUMNS["nav_daily"]
    validate_table("nav_daily", df)

    # 3 unique dates (Jan 01, Jan 02, Jan 03) - overlap deduplicated
    assert len(df) == 3
    assert list(df["date"]) == ["2024-01-01", "2024-01-02", "2024-01-03"]
    assert df.duplicated(subset=["date", "scheme_code"]).sum() == 0


def test_nav_history_fails_gracefully_on_network_error(tmp_path):
    df, meta = fetch_nav_history(
        scheme_codes=["999999"],
        start_date="2024-01-01",
        end_date="2024-01-05",
        source="mfapi",
        cache_dir=tmp_path / "bad_cache",
        timeout=1
    )
    assert tuple(df.columns) == COLUMNS["nav_daily"]
    validate_table("nav_daily", df)
    # Returns empty without crashing
    assert len(df) == 0


def test_nav_lane_isolated_from_flow_forecasting():
    # Verify nav lane can be imported and executed without affecting flow contracts or loaders
    import fundflow.ingest.nav as nav_mod
    import fundflow.contracts as contracts_mod
    assert hasattr(nav_mod, "fetch_scheme_master")
    assert hasattr(nav_mod, "fetch_nav_history")
    assert "flows_category_month" in contracts_mod.COLUMNS
    assert "nav_daily" in contracts_mod.COLUMNS
    assert "scheme_master" in contracts_mod.COLUMNS
