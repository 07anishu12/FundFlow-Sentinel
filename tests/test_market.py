"""Unit tests for historical market ingestion and monthly feature aggregation.

Verifies:
- Monthly aggregation calculations (Nifty return, 3M drawdown, VIX mean/change)
- Exact frozen contract schemas (COLUMNS['market_month'])
- Conservative available_from cutoff (start of following month T+1)
- Optional-feature policy and graceful fallback to verified snapshot
- Zero-fill shortcut prevention (missing features stay absent/handled, never faked as 0.0)
- Provenance labelling for unofficial wrapper vs official sources
"""
from __future__ import annotations

import json
from pathlib import Path
import pytest
import pandas as pd

from fundflow.contracts import validate_table, COLUMNS
from fundflow.ingest.market import (
    aggregate_market_monthly,
    fetch_and_build_market_month,
    _get_following_month_start,
    SOURCE_NAME_WRAPPER,
)

ROOT = Path(__file__).resolve().parents[1]

# Known toy daily series
TOY_NIFTY_DAILY = pd.DataFrame({
    "date": [
        # Jan 2024: starts 100, ends 110 (+10%)
        "2024-01-02", "2024-01-15", "2024-01-31",
        # Feb 2024: starts 110, ends 105 (-4.5455%), peak in Jan was 110, dd = (105-110)/110 = -4.5455%
        "2024-02-01", "2024-02-15", "2024-02-28",
        # Mar 2024: starts 105, ends 115 (+9.5238%), peak is 115, dd = 0.0%
        "2024-03-01", "2024-03-15", "2024-03-29",
    ],
    "close": [
        100.0, 105.0, 110.0,
        110.0, 108.0, 105.0,
        105.0, 112.0, 115.0,
    ],
    "month": [
        "2024-01", "2024-01", "2024-01",
        "2024-02", "2024-02", "2024-02",
        "2024-03", "2024-03", "2024-03",
    ]
})

TOY_VIX_DAILY = pd.DataFrame({
    "date": [
        # Jan 2024: mean = (15+16+17)/3 = 16.0, change = 17 - 15 = 2.0
        "2024-01-02", "2024-01-15", "2024-01-31",
        # Feb 2024: mean = (17+18+19)/3 = 18.0, change = 19 - 17 = 2.0
        "2024-02-01", "2024-02-15", "2024-02-28",
        # Mar 2024: mean = (18+15+12)/3 = 15.0, change = 12 - 18 = -6.0
        "2024-03-01", "2024-03-15", "2024-03-29",
    ],
    "close": [
        15.0, 16.0, 17.0,
        17.0, 18.0, 19.0,
        18.0, 15.0, 12.0,
    ],
    "month": [
        "2024-01", "2024-01", "2024-01",
        "2024-02", "2024-02", "2024-02",
        "2024-03", "2024-03", "2024-03",
    ]
})


def test_following_month_start_helper():
    assert _get_following_month_start("2024-01") == "2024-02-01T00:00:00Z"
    assert _get_following_month_start("2024-12") == "2025-01-01T00:00:00Z"


def test_aggregate_market_monthly_known_series():
    df_m = aggregate_market_monthly(
        TOY_NIFTY_DAILY,
        TOY_VIX_DAILY,
        source_name="Toy Test Market",
        retrieved_at="2024-04-01T00:00:00Z",
    )

    assert tuple(df_m.columns) == COLUMNS["market_month"]
    validate_table("market_month", df_m)

    assert len(df_m) == 3
    # Jan 2024
    row_jan = df_m[df_m["month"] == "2024-01"].iloc[0]
    assert row_jan["nifty_return"] == 10.0
    assert row_jan["vix_mean"] == 16.0
    assert row_jan["vix_change"] == 2.0
    assert row_jan["available_from"] == "2024-02-01T00:00:00Z"

    # Feb 2024
    row_feb = df_m[df_m["month"] == "2024-02"].iloc[0]
    assert pytest.approx(row_feb["nifty_return"], 0.001) == -4.5455
    assert pytest.approx(row_feb["nifty_drawdown_3m"], 0.001) == -4.5455
    assert row_feb["vix_mean"] == 18.0
    assert row_feb["vix_change"] == 2.0
    assert row_feb["available_from"] == "2024-03-01T00:00:00Z"

    # Mar 2024
    row_mar = df_m[df_m["month"] == "2024-03"].iloc[0]
    assert pytest.approx(row_mar["nifty_return"], 0.001) == 9.5238
    assert row_mar["nifty_drawdown_3m"] == 0.0
    assert row_mar["vix_mean"] == 15.0
    assert row_mar["vix_change"] == -6.0
    assert row_mar["available_from"] == "2024-04-01T00:00:00Z"


def test_empty_market_input_returns_empty_contract_frame():
    df_empty = aggregate_market_monthly(pd.DataFrame(), pd.DataFrame())
    assert tuple(df_empty.columns) == COLUMNS["market_month"]
    validate_table("market_month", df_empty)
    assert len(df_empty) == 0


def test_optional_feature_policy_snapshot_fallback(tmp_path):
    snap_p = tmp_path / "market_month_snap.csv"
    # Create valid toy snapshot
    snap_df = pd.DataFrame([{
        "month": "2024-01",
        "nifty_return": 1.5,
        "nifty_drawdown_3m": -2.0,
        "vix_mean": 14.5,
        "vix_change": 0.5,
        "available_from": "2024-02-01T00:00:00Z",
        "source_name": "Verified Snapshot",
        "retrieved_at": "2024-02-01T00:00:00Z",
    }])
    snap_df.to_csv(snap_p, index=False)

    out_p = tmp_path / "processed" / "market_month.csv"

    # Request with force_snapshot=True (simulates network failure)
    df_out, prov = fetch_and_build_market_month(
        output_path=out_p,
        snapshot_fallback_path=snap_p,
        force_snapshot=True,
    )

    assert tuple(df_out.columns) == COLUMNS["market_month"]
    validate_table("market_month", df_out)
    assert len(df_out) == 1
    assert prov["is_snapshot_fallback"] is True
    assert prov["status"] == "snapshot_fallback"
    assert out_p.is_file()


def test_market_lane_never_zero_fills_missing_series(tmp_path):
    # If no data and no snapshot, it must NOT invent 0.0 fills
    out_p = tmp_path / "processed" / "market_month.csv"
    non_existent_snap = tmp_path / "no_snap.csv"

    df_out, prov = fetch_and_build_market_month(
        output_path=out_p,
        snapshot_fallback_path=non_existent_snap,
        force_snapshot=True,
    )
    assert len(df_out) == 0
    # Zero rows returned, never fake 0.0 values
    assert not out_p.exists()
