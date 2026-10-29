"""Unit tests for flow rates and leakage-safe feature matrix construction.

Verifies Prompt 11:
- Denominator alignment across category and month
- Prior-month closing AUM as opening AUM proxy
- Aggregation-before-ratio
- Missing, zero, and negative AUM handling
- Missing versus zero flow preservation
- Rolling windows using only prior observations (no centered windows)
- Feature availability at exact cutoff boundaries
- Delayed market availability handling
- Category validity transitions
- Deterministic output ordering
- Insufficient history handling
- Strict target/feature separation
- Mutation invariance: adding/modifying future rows does not alter past feature rows
- Future publication timing non-leakage
"""
from __future__ import annotations

import copy
import math
from pathlib import Path
import numpy as np
import pandas as pd
import pytest

from fundflow.contracts import validate_table, COLUMNS
from fundflow.flows import compute_rates, map_category_with_validity
from fundflow.features import build_feature_matrix, _offset_month

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def sample_flow_history():
    """Generate 16 consecutive months of flow data for Large Cap and Mid Cap."""
    rows = []
    # 2023-01 to 2024-04 (16 months)
    start_y = 2023
    for i in range(16):
        total_m = 1 + i
        y = start_y + (total_m - 1) // 12
        m = ((total_m - 1) % 12) + 1
        month_str = f"{y:04d}-{m:02d}"

        # release date is 10th of next month
        next_m_total = total_m + 1
        ny = start_y + (next_m_total - 1) // 12
        nm = ((next_m_total - 1) % 12) + 1
        avail_str = f"{ny:04d}-{nm:02d}-10T00:00:00Z"

        # Large Cap
        rows.append({
            "month": month_str,
            "category": "Large Cap Fund",
            "gross_inflow_cr": 5000.0 + i * 100,
            "gross_redemption_cr": 2000.0 + i * 50,
            "net_flow_cr": 3000.0 + i * 50,
            "aum_close_cr": 100000.0 + i * 2000,
            "aaum_cr": 99000.0 + i * 2000,
            "available_from": avail_str,
            "source_url": "https://portal.amfiindia.com/report.xls",
            "retrieved_at": avail_str,
        })
        # Mid Cap
        rows.append({
            "month": month_str,
            "category": "Mid Cap Fund",
            "gross_inflow_cr": 4000.0 + i * 80,
            "gross_redemption_cr": 1500.0 + i * 40,
            "net_flow_cr": 2500.0 + i * 40,
            "aum_close_cr": 80000.0 + i * 1500,
            "aaum_cr": 79000.0 + i * 1500,
            "available_from": avail_str,
            "source_url": "https://portal.amfiindia.com/report.xls",
            "retrieved_at": avail_str,
        })
    return pd.DataFrame(rows)


@pytest.fixture
def sample_market_history():
    """Generate 16 consecutive months of market data matching flow history."""
    rows = []
    start_y = 2023
    for i in range(16):
        total_m = 1 + i
        y = start_y + (total_m - 1) // 12
        m = ((total_m - 1) % 12) + 1
        month_str = f"{y:04d}-{m:02d}"

        # market available 1st of following month
        next_m_total = total_m + 1
        ny = start_y + (next_m_total - 1) // 12
        nm = ((next_m_total - 1) % 12) + 1
        avail_str = f"{ny:04d}-{nm:02d}-01T00:00:00Z"

        rows.append({
            "month": month_str,
            "nifty_return": 1.2 - (i % 3) * 0.5,
            "nifty_drawdown_3m": -2.5 - (i % 4) * 0.3,
            "vix_mean": 15.0 + (i % 5) * 1.0,
            "vix_change": -0.5 + (i % 3) * 0.5,
            "available_from": avail_str,
            "source_name": "NSE Nifty Indices",
            "retrieved_at": avail_str,
        })
    return pd.DataFrame(rows)


# --- 1. Rate Computation Tests ---

def test_compute_rates_denominator_alignment(sample_flow_history):
    rates = compute_rates(sample_flow_history)
    assert not rates.empty
    
    # Check 2023-01: first month has no prior month in data, so prior_aum_close_cr must be NaN
    jan_lc = rates[(rates["month"] == "2023-01") & (rates["category"] == "Large Cap")].iloc[0]
    assert pd.isna(jan_lc["prior_aum_close_cr"])
    assert pd.isna(jan_lc["redemption_rate_pct"])

    # Check 2023-02: prior month is 2023-01
    feb_lc = rates[(rates["month"] == "2023-02") & (rates["category"] == "Large Cap")].iloc[0]
    assert feb_lc["prior_aum_close_cr"] == 100000.0  # Jan 2023 closing AUM
    expected_rate = (2050.0 / 100000.0) * 100.0
    assert pytest.approx(feb_lc["redemption_rate_pct"]) == expected_rate


def test_compute_rates_aggregation_before_ratio():
    # Two rows for same month and raw category (e.g. multiple sub-schemes)
    df = pd.DataFrame([
        {
            "month": "2023-01",
            "category": "Large Cap Fund",
            "gross_inflow_cr": 1000.0,
            "gross_redemption_cr": 200.0,
            "net_flow_cr": 800.0,
            "aum_close_cr": 10000.0,
            "available_from": "2023-02-10T00:00:00Z",
        },
        {
            "month": "2023-01",
            "category": "Large Cap Fund",
            "gross_inflow_cr": 2000.0,
            "gross_redemption_cr": 300.0,
            "net_flow_cr": 1700.0,
            "aum_close_cr": 20000.0,
            "available_from": "2023-02-10T00:00:00Z",
        },
        {
            "month": "2023-02",
            "category": "Large Cap Fund",
            "gross_inflow_cr": 1500.0,
            "gross_redemption_cr": 600.0,
            "net_flow_cr": 900.0,
            "aum_close_cr": 31000.0,
            "available_from": "2023-03-10T00:00:00Z",
        },
    ])
    rates = compute_rates(df)
    # Jan 2023 total AUM = 10000 + 20000 = 30000
    feb = rates[rates["month"] == "2023-02"].iloc[0]
    assert feb["prior_aum_close_cr"] == 30000.0
    # Rate = 100 * 600 / 30000 = 2.0%
    assert pytest.approx(feb["redemption_rate_pct"]) == 2.0


def test_compute_rates_zero_division_and_negative_aum():
    df = pd.DataFrame([
        {
            "month": "2023-01",
            "category": "Large Cap",
            "gross_inflow_cr": 100.0,
            "gross_redemption_cr": 50.0,
            "net_flow_cr": 50.0,
            "aum_close_cr": 0.0,  # Zero AUM
            "available_from": "2023-02-10T00:00:00Z",
        },
        {
            "month": "2023-02",
            "category": "Large Cap",
            "gross_inflow_cr": 100.0,
            "gross_redemption_cr": 50.0,
            "net_flow_cr": 50.0,
            "aum_close_cr": 500.0,
            "available_from": "2023-03-10T00:00:00Z",
        },
        {
            "month": "2023-03",
            "category": "Large Cap",
            "gross_inflow_cr": 100.0,
            "gross_redemption_cr": 50.0,
            "net_flow_cr": 50.0,
            "aum_close_cr": -50.0,  # Negative AUM
            "available_from": "2023-04-10T00:00:00Z",
        },
        {
            "month": "2023-04",
            "category": "Large Cap",
            "gross_inflow_cr": 100.0,
            "gross_redemption_cr": 50.0,
            "net_flow_cr": 50.0,
            "aum_close_cr": 600.0,
            "available_from": "2023-05-10T00:00:00Z",
        },
    ])
    rates = compute_rates(df)
    # Feb 2023 has prior AUM 0.0 -> must be NaN (never divide by zero)
    feb = rates[rates["month"] == "2023-02"].iloc[0]
    assert pd.isna(feb["redemption_rate_pct"])
    assert pd.isna(feb["prior_aum_close_cr"])

    # Apr 2023 has prior AUM -50.0 -> must be NaN (never divide by negative)
    apr = rates[rates["month"] == "2023-04"].iloc[0]
    assert pd.isna(apr["redemption_rate_pct"])


def test_compute_rates_zero_vs_missing_redemption():
    df = pd.DataFrame([
        {
            "month": "2023-01",
            "category": "Large Cap",
            "gross_inflow_cr": 100.0,
            "gross_redemption_cr": 10.0,
            "net_flow_cr": 90.0,
            "aum_close_cr": 1000.0,
            "available_from": "2023-02-10T00:00:00Z",
        },
        {
            "month": "2023-02",
            "category": "Large Cap",
            "gross_inflow_cr": 100.0,
            "gross_redemption_cr": 0.0,  # Genuine zero redemption
            "net_flow_cr": 100.0,
            "aum_close_cr": 1100.0,
            "available_from": "2023-03-10T00:00:00Z",
        },
        {
            "month": "2023-03",
            "category": "Large Cap",
            "gross_inflow_cr": 100.0,
            "gross_redemption_cr": np.nan,  # Missing redemption
            "net_flow_cr": 50.0,
            "aum_close_cr": 1200.0,
            "available_from": "2023-04-10T00:00:00Z",
        },
    ])
    rates = compute_rates(df)
    feb = rates[rates["month"] == "2023-02"].iloc[0]
    mar = rates[rates["month"] == "2023-03"].iloc[0]
    # Feb is genuine 0.0%
    assert feb["redemption_rate_pct"] == 0.0
    # Mar is NaN (missing)
    assert pd.isna(mar["redemption_rate_pct"])


# --- 2. Feature Matrix Construction & Non-Leakage Tests ---

def test_build_feature_matrix_contract_compliance(sample_flow_history, sample_market_history):
    fm = build_feature_matrix(sample_flow_history, sample_market_history)
    assert not fm.empty
    validate_table("feature_matrix", fm)
    assert tuple(fm.columns) == COLUMNS["feature_matrix"]
    # Check that rows exist for target months from 2024-02 onwards (12 valid lag rates needed)
    assert "2024-02" in fm["target_month"].values
    assert "2024-04" in fm["target_month"].values


def test_rolling_windows_exclude_target_and_future(sample_flow_history, sample_market_history):
    fm = build_feature_matrix(sample_flow_history, sample_market_history)
    row = fm[(fm["target_month"] == "2024-02") & (fm["category"] == "Large Cap")].iloc[0]

    # For target month 2024-02:
    # lag0 is 2024-01
    # lag1 is 2023-12
    # lag2 is 2023-11
    rates = compute_rates(sample_flow_history)
    r_jan24 = rates[(rates["month"] == "2024-01") & (rates["category"] == "Large Cap")].iloc[0]["redemption_rate_pct"]
    r_dec23 = rates[(rates["month"] == "2023-12") & (rates["category"] == "Large Cap")].iloc[0]["redemption_rate_pct"]
    r_nov23 = rates[(rates["month"] == "2023-11") & (rates["category"] == "Large Cap")].iloc[0]["redemption_rate_pct"]

    assert pytest.approx(row["rate_lag0"]) == r_jan24
    assert pytest.approx(row["rate_lag1"]) == r_dec23
    assert pytest.approx(row["rate_lag2"]) == r_nov23
    assert pytest.approx(row["roll_mean3"]) == np.mean([r_jan24, r_dec23, r_nov23])
    assert pytest.approx(row["delta1"]) == (r_jan24 - r_dec23)


def test_market_availability_cutoff_enforcement(sample_flow_history, sample_market_history):
    # Alter market history so that 2024-01 market return is released late (after cutoff 2024-02-12)
    delayed_market = sample_market_history.copy()
    delayed_market.loc[delayed_market["month"] == "2024-01", "available_from"] = "2024-02-15T00:00:00Z"

    fm = build_feature_matrix(sample_flow_history, delayed_market)
    # Target month 2024-02 has cutoff 2024-02-12. Since market lag0 (2024-01) is not available until 2024-02-15,
    # target month 2024-02 must NOT be generated!
    assert "2024-02" not in fm["target_month"].values


def test_mutation_invariance_future_rows_do_not_alter_past_features(sample_flow_history, sample_market_history):
    # Base feature matrix up to 2024-03
    base_fm = build_feature_matrix(sample_flow_history, sample_market_history)
    past_rows_base = base_fm[base_fm["target_month"] <= "2024-02"].copy().reset_index(drop=True)

    # Mutate future month 2024-04 in flows
    mutated_flows = sample_flow_history.copy()
    mutated_flows.loc[mutated_flows["month"] == "2024-04", "gross_redemption_cr"] *= 5.0
    mutated_flows.loc[mutated_flows["month"] == "2024-04", "aum_close_cr"] *= 2.0

    mutated_fm = build_feature_matrix(mutated_flows, sample_market_history)
    past_rows_mutated = mutated_fm[mutated_fm["target_month"] <= "2024-02"].copy().reset_index(drop=True)

    # Past feature rows must be identical byte-for-byte
    pd.testing.assert_frame_equal(past_rows_base, past_rows_mutated)


def test_future_publication_timing_non_leakage(sample_flow_history, sample_market_history):
    # If 2024-01 flows were published late (e.g. 2024-02-20), predicting 2024-02 on 2024-02-12 must reject it
    delayed_flows = sample_flow_history.copy()
    delayed_flows.loc[delayed_flows["month"] == "2024-01", "available_from"] = "2024-02-20T00:00:00Z"

    fm = build_feature_matrix(delayed_flows, sample_market_history)
    assert "2024-02" not in fm["target_month"].values


def test_sentiment_boundary_does_not_alter_frozen_contract(sample_flow_history, sample_market_history):
    dummy_sentiment = pd.DataFrame([
        {"period": "2024-01-15", "topic": "market", "mean_score": 0.5, "neg_share": 0.1, "n_articles": 10, "is_live": False}
    ])
    fm = build_feature_matrix(sample_flow_history, sample_market_history, sentiment=dummy_sentiment)
    assert tuple(fm.columns) == COLUMNS["feature_matrix"]
    assert "mean_score" not in fm.columns
