"""Unit and property tests for stress calculations and finance-safe explanations.

Verifies Prompt 19:
- stress_outflow arithmetic and unit precision (₹ crore)
- Zero, negative, and non-finite AUM validation
- Negative rate rejection (never negative gross redemption)
- Above-100% rate capping with explicit capped_at_100 status
- Multi-scenario construction with scenario_table
- Incremental outflow reconciliation
- Insufficient history handling for residual bounds and historical max
- Finance-safe narrative generation without causal/crisis claims
"""
from __future__ import annotations

import math
import numpy as np
import pandas as pd
import pytest

from fundflow.stress import stress_outflow, scenario_table
from fundflow.explain import generate_stress_narrative


# --- 1. Pure Arithmetic & Boundary Tests for stress_outflow ---

def test_stress_outflow_valid_cases():
    # 10,000 cr AUM at 2.5% -> 250 cr
    res = stress_outflow(10000.0, 2.5)
    assert res["status"] == "valid"
    assert res["estimated_outflow_cr"] == 250.0
    assert res["rate_pct"] == 2.5
    assert res["effective_rate_pct"] == 2.5
    assert res["units"] == "₹ crore"

    # Zero rate -> 0.0 cr
    res_zero_rate = stress_outflow(10000.0, 0.0)
    assert res_zero_rate["status"] == "valid"
    assert res_zero_rate["estimated_outflow_cr"] == 0.0

    # Zero AUM -> 0.0 cr
    res_zero_aum = stress_outflow(0.0, 5.0)
    assert res_zero_aum["status"] == "valid"
    assert res_zero_aum["estimated_outflow_cr"] == 0.0

    # 100% rate -> 100% of AUM
    res_100 = stress_outflow(50000.0, 100.0)
    assert res_100["status"] == "valid"
    assert res_100["estimated_outflow_cr"] == 50000.0


def test_stress_outflow_negative_inputs_rejected():
    # Negative rate must be rejected (never output negative redemptions)
    res_neg_rate = stress_outflow(10000.0, -1.5)
    assert res_neg_rate["status"] == "invalid_input"
    assert res_neg_rate["estimated_outflow_cr"] is None
    assert "cannot be negative" in res_neg_rate["reason"]

    # Negative AUM must be rejected
    res_neg_aum = stress_outflow(-500.0, 2.0)
    assert res_neg_aum["status"] == "invalid_input"
    assert res_neg_aum["estimated_outflow_cr"] is None


def test_stress_outflow_non_finite_inputs_rejected():
    assert stress_outflow(np.nan, 2.0)["status"] == "invalid_input"
    assert stress_outflow(1000.0, np.nan)["status"] == "invalid_input"
    assert stress_outflow(float("inf"), 2.0)["status"] == "invalid_input"
    assert stress_outflow(1000.0, float("inf"))["status"] == "invalid_input"
    assert stress_outflow(None, 2.0)["status"] == "invalid_input"
    assert stress_outflow(1000.0, None)["status"] == "invalid_input"


def test_stress_outflow_capping_above_100():
    # 125% rate on 10,000 cr AUM -> capped at 100%, outflow 10,000 cr
    res = stress_outflow(10000.0, 125.0)
    assert res["status"] == "capped_at_100"
    assert res["rate_pct"] == 125.0
    assert res["effective_rate_pct"] == 100.0
    assert res["estimated_outflow_cr"] == 10000.0
    assert "capped at 100.0%" in res["reason"]


# --- 2. Scenario Table Construction Tests ---

def test_scenario_table_with_valid_base_and_multipliers():
    # Forecast rate 2.0% on 100,000 cr AUM
    st = scenario_table(
        forecast_rate=2.0,
        bands={"band_status": "insufficient_history", "lower_band": None, "upper_band": None},
        hist_max={"rate": 4.5, "sample_size": 1},  # n=1 is insufficient
        aum_cr=100000.0,
        custom_rate=3.0,
    )
    assert len(st) == 7

    # Check Base Forecast: 2.0% of 100k = 2,000 cr
    base = st[st["scenario_name"] == "Base Forecast"].iloc[0]
    assert base["status"] == "valid"
    assert base["estimated_outflow_cr"] == 2000.0
    assert base["incremental_outflow_cr"] == 0.0

    # Moderate Stress: 1.25x = 2.5% -> 2,500 cr; incremental = +500 cr
    mod = st[st["scenario_name"] == "Moderate Stress (1.25x)"].iloc[0]
    assert mod["status"] == "valid"
    assert mod["effective_rate_pct"] == 2.5
    assert mod["estimated_outflow_cr"] == 2500.0
    assert mod["incremental_outflow_cr"] == 500.0

    # Severe Stress: 1.50x = 3.0% -> 3,000 cr; incremental = +1,000 cr
    sev = st[st["scenario_name"] == "Severe Stress (1.50x)"].iloc[0]
    assert sev["status"] == "valid"
    assert sev["effective_rate_pct"] == 3.0
    assert sev["estimated_outflow_cr"] == 3000.0
    assert sev["incremental_outflow_cr"] == 1000.0

    # Bands must be insufficient_history with None/NaN outflow
    p10 = st[st["scenario_name"] == "Lower Bound (P10)"].iloc[0]
    assert p10["status"] == "insufficient_history"
    assert pd.isna(p10["estimated_outflow_cr"])
    assert pd.isna(p10["incremental_outflow_cr"])

    # Historical Max with n=1 must be insufficient_history
    h_max = st[st["scenario_name"] == "Historical Maximum"].iloc[0]
    assert h_max["status"] == "insufficient_history"
    assert pd.isna(h_max["estimated_outflow_cr"])

    # Custom rate: 3.0% -> 3,000 cr; incremental = +1,000 cr
    custom = st[st["scenario_name"] == "Custom Scenario"].iloc[0]
    assert custom["status"] == "valid"
    assert custom["estimated_outflow_cr"] == 3000.0
    assert custom["incremental_outflow_cr"] == 1000.0


def test_scenario_table_with_valid_empirical_bands():
    st = scenario_table(
        forecast_rate=2.0,
        bands={"band_status": "ok", "lower_band": 1.5, "upper_band": 2.8},
        hist_max={"rate": 3.5, "sample_size": 36},
        aum_cr=50000.0,
    )
    p10 = st[st["scenario_name"] == "Lower Bound (P10)"].iloc[0]
    assert p10["status"] == "valid"
    assert p10["estimated_outflow_cr"] == 750.0  # 1.5% of 50k
    assert p10["incremental_outflow_cr"] == -250.0  # 750 - 1000

    p90 = st[st["scenario_name"] == "Upper Bound (P90)"].iloc[0]
    assert p90["status"] == "valid"
    assert p90["estimated_outflow_cr"] == 1400.0  # 2.8% of 50k
    assert p90["incremental_outflow_cr"] == 400.0  # 1400 - 1000

    h_max = st[st["scenario_name"] == "Historical Maximum"].iloc[0]
    assert h_max["status"] == "valid"
    assert h_max["estimated_outflow_cr"] == 1750.0  # 3.5% of 50k


def test_scenario_table_missing_base_makes_incremental_unavailable():
    st = scenario_table(
        forecast_rate=None,  # Missing forecast
        bands=None,
        hist_max=None,
        aum_cr=10000.0,
        custom_rate=2.0,
    )
    base = st[st["scenario_name"] == "Base Forecast"].iloc[0]
    assert base["status"] == "unavailable"

    custom = st[st["scenario_name"] == "Custom Scenario"].iloc[0]
    assert custom["status"] == "valid"
    assert custom["estimated_outflow_cr"] == 200.0
    # Because base was unavailable, incremental must be None / NaN
    assert pd.isna(custom["incremental_outflow_cr"])


# --- 3. Finance-Safe Narrative Tests ---

def test_generate_stress_narrative_finance_safe():
    st = scenario_table(
        forecast_rate=1.8,
        bands={"band_status": "insufficient_history", "lower_band": None, "upper_band": None},
        hist_max={"rate": 2.5, "sample_size": 1},
        aum_cr=300000.0,
    )
    narrative = generate_stress_narrative("Large Cap", 300000.0, "2024-09", st)

    assert narrative["finance_safe"] is True
    full_text = " ".join([narrative["summary"]] + narrative["details"] + narrative["disclosures"]).lower()

    # Strictly verify absence of crisis, panic, run-on-the-fund claims
    forbidden_terms = [
        "liquidity crisis",
        "run on the fund",
        "panic",
        "insolvent",
        "insolvency",
        "guaranteed redemption",
        "fire sale",
    ]
    for term in forbidden_terms:
        assert term not in full_text, f"Forbidden non-finance-safe term found: '{term}'"

    # Verify presence of mandatory disclosures
    assert any("illustrative sensitivity only" in d.lower() for d in narrative["disclosures"])
    assert any("reference aum proxy" in d.lower() for d in narrative["disclosures"])
    assert any("no liquidity portfolio modeling" in d.lower() for d in narrative["disclosures"])
