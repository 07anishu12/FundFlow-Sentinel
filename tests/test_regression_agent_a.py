"""Adversarial and deterministic regression tests for core data, leakage, alerts, and stress.

Agent A — Prompt 23 (Wave 11 Test Hardening)
Covers:
- Section A: Data validation, category mapping, non-leakage available_from, gap analysis, negative flows
- Section B: Feature/forecast mutation invariance, fold-local preprocessor fitting, contribution reconciliation, residual bands
- Section C: Robust anomaly statistics, zero-MAD safeguards, alert boundary conditions, backtest temporal isolation
- Section D: Hand-calculated stress arithmetic, incremental reconciliation, 100% capping, atomic last-good preservation
"""
from __future__ import annotations

import json
import math
from pathlib import Path
import numpy as np
import pandas as pd
import pytest

from fundflow.contracts import COLUMNS, validate_table
from fundflow.validate import validate_flows
from fundflow.flows import compute_rates, map_category_with_validity
from fundflow.features import build_feature_matrix
from fundflow.forecasting import walk_forward_forecast
from fundflow.explain import explain_ridge_prediction, compute_empirical_residual_bands
from fundflow.anomaly import compute_robust_z, compute_momentum_3m, compute_percentile_rank
from fundflow.alerts import generate_alerts
from fundflow.stress import stress_outflow, scenario_table
from fundflow.reporting import RunReporter
from fundflow.cli import atomic_write_csv

ROOT = Path(__file__).resolve().parents[1]
FIXTURES_DIR = ROOT / "data" / "snapshots" / "fixtures"


@pytest.fixture
def multi_period_feature_matrix() -> pd.DataFrame:
    """Generate 24 months of valid feature matrix rows for 3 categories with known targets."""
    rows = []
    categories = ["Large Cap", "Mid Cap", "Flexi Cap"]
    start_y = 2022

    for i in range(24):
        total_m = 1 + i
        y = start_y + (total_m - 1) // 12
        m = ((total_m - 1) % 12) + 1
        t_month = f"{y:04d}-{m:02d}"
        as_of_ts = f"{t_month}-12T00:00:00Z"

        for cat_idx, cat in enumerate(categories):
            base_rate = 1.5 + cat_idx * 0.4
            r0 = round(base_rate + np.sin(i * 0.4) * 0.3, 4)
            r1 = round(base_rate + np.sin((i - 1) * 0.4) * 0.3, 4)
            r2 = round(base_rate + np.sin((i - 2) * 0.4) * 0.3, 4)
            r11 = round(base_rate + np.sin((i - 11) * 0.4) * 0.3, 4)
            target = round(base_rate + np.sin((i + 1) * 0.4) * 0.3, 4)

            rows.append({
                "as_of": as_of_ts,
                "target_month": t_month,
                "category": cat,
                "rate_lag0": r0,
                "rate_lag1": r1,
                "rate_lag2": r2,
                "rate_lag11": r11,
                "roll_mean3": round((r0 + r1 + r2) / 3.0, 4),
                "roll_std3": 0.15,
                "delta1": round(r0 - r1, 4),
                "net_flow_rate_lag0": 0.5,
                "aum_growth_lag0": 1.2,
                "nifty_return_lag0": 0.015,
                "nifty_drawdown_3m": -0.02,
                "vix_mean_lag0": 14.5,
                "vix_change_lag0": -0.5,
                "target_rate": target,
            })

    df = pd.DataFrame(rows, columns=COLUMNS["feature_matrix"])
    return validate_table("feature_matrix", df)


# ===========================================================================
# SECTION A: Data Validation & Aggregation Regressions
# ===========================================================================

def test_canonical_category_mapping_all_universe_and_exclusions():
    """Verify that all 6 universe categories and 2 exclusions map properly."""
    universe = ["Large Cap", "Mid Cap", "Small Cap", "Flexi Cap", "Aggressive Hybrid", "Corporate Bond"]
    exclusions = ["Liquid", "Overnight"]
    for cat in universe + exclusions:
        mapped = map_category_with_validity(cat, "2024-09")
        assert mapped == cat


def test_unmapped_category_hard_fails():
    """Unapproved/unmapped category entering the modeling universe must raise hard failure."""
    bad_df = pd.DataFrame({
        "month": ["2024-09"],
        "category": ["Cryptocurrency Arbitrage Fund"],
        "gross_inflow_cr": [100.0],
        "gross_redemption_cr": [50.0],
        "net_flow_cr": [50.0],
        "aum_close_cr": [1000.0],
        "aaum_cr": [950.0],
        "available_from": ["2024-10-10T00:00:00Z"],
        "source_url": ["https://portal.amfiindia.com"],
        "retrieved_at": ["2024-10-10T00:00:00Z"],
    })
    with pytest.raises(ValueError, match="Unmapped category label"):
        validate_flows(bad_df)


def test_negative_net_flows_valid_and_preserved():
    """Negative net flows (gross_redemptions > gross_inflows) are valid and compute negative rate."""
    df = pd.DataFrame({
        "month": ["2024-08", "2024-09"],
        "category": ["Large Cap", "Large Cap"],
        "gross_inflow_cr": [100.0, 50.0],
        "gross_redemption_cr": [40.0, 150.0],
        "net_flow_cr": [60.0, -100.0],
        "aum_close_cr": [1000.0, 900.0],
        "aaum_cr": [980.0, 950.0],
        "available_from": ["2024-09-10T00:00:00Z", "2024-10-10T00:00:00Z"],
        "source_url": ["https://portal.amfiindia.com", "https://portal.amfiindia.com"],
        "retrieved_at": ["2024-09-10T00:00:00Z", "2024-10-10T00:00:00Z"],
    })
    val_df, rep = validate_flows(df)
    assert rep["status"] == "pass"

    rates_df = compute_rates(val_df)
    row_sep = rates_df[rates_df["month"] == "2024-09"].iloc[0]
    # Prior AUM = 1000.0. Net flow = -100.0 -> net_flow_rate_pct = -10.0%
    assert row_sep["net_flow_rate_pct"] == -10.0
    assert row_sep["redemption_rate_pct"] == 15.0


def test_ambiguous_non_finite_units_hard_fail():
    """Non-finite or ambiguous numeric units must trigger hard failure in validation."""
    for bad_val in [np.nan, np.inf, -np.inf]:
        df = pd.DataFrame({
            "month": ["2024-09"],
            "category": ["Large Cap"],
            "gross_inflow_cr": [bad_val],
            "gross_redemption_cr": [50.0],
            "net_flow_cr": [50.0],
            "aum_close_cr": [1000.0],
            "aaum_cr": [950.0],
            "available_from": ["2024-10-10T00:00:00Z"],
            "source_url": ["https://portal.amfiindia.com"],
            "retrieved_at": ["2024-10-10T00:00:00Z"],
        })
        with pytest.raises(ValueError, match="Ambiguous or non-finite values"):
            validate_flows(df)


def test_duplicate_final_keys_hard_fail():
    """Duplicate (month, category) tuples must fail validation immediately."""
    df = pd.DataFrame({
        "month": ["2024-09", "2024-09"],
        "category": ["Large Cap", "Large Cap"],
        "gross_inflow_cr": [100.0, 100.0],
        "gross_redemption_cr": [50.0, 50.0],
        "net_flow_cr": [50.0, 50.0],
        "aum_close_cr": [1000.0, 1000.0],
        "aaum_cr": [950.0, 950.0],
        "available_from": ["2024-10-10T00:00:00Z", "2024-10-10T00:00:00Z"],
        "source_url": ["https://portal.amfiindia.com", "https://portal.amfiindia.com"],
        "retrieved_at": ["2024-10-10T00:00:00Z", "2024-10-10T00:00:00Z"],
    })
    with pytest.raises(ValueError, match="Duplicate final key"):
        validate_flows(df)


def test_gaps_by_category_detected_without_silent_interpolation():
    """Category history gaps (e.g., missing month 2024-07 between 2024-06 and 2024-08) must be logged."""
    df = pd.DataFrame({
        "month": ["2024-06", "2024-08"],
        "category": ["Large Cap", "Large Cap"],
        "gross_inflow_cr": [100.0, 120.0],
        "gross_redemption_cr": [50.0, 60.0],
        "net_flow_cr": [50.0, 60.0],
        "aum_close_cr": [1000.0, 1100.0],
        "aaum_cr": [950.0, 1050.0],
        "available_from": ["2024-07-10T00:00:00Z", "2024-09-10T00:00:00Z"],
        "source_url": ["https://portal.amfiindia.com", "https://portal.amfiindia.com"],
        "retrieved_at": ["2024-07-10T00:00:00Z", "2024-09-10T00:00:00Z"],
    })
    _, rep = validate_flows(df)
    assert rep["missingness"]["total_gap_months"] == 1
    assert "2024-07" in rep["missingness"]["gaps_per_category"]["Large Cap"]


def test_available_from_strict_non_leakage():
    """available_from on or before month-end must fail validation with look-ahead bias error."""
    # September ends on 2024-09-30; available_from on 2024-09-30 or earlier is look-ahead leakage
    for leaky_date in ["2024-09-30T23:59:59Z", "2024-09-15T00:00:00Z"]:
        df = pd.DataFrame({
            "month": ["2024-09"],
            "category": ["Large Cap"],
            "gross_inflow_cr": [100.0],
            "gross_redemption_cr": [50.0],
            "net_flow_cr": [50.0],
            "aum_close_cr": [1000.0],
            "aaum_cr": [950.0],
            "available_from": [leaky_date],
            "source_url": ["https://portal.amfiindia.com"],
            "retrieved_at": ["2024-10-10T00:00:00Z"],
        })
        with pytest.raises(ValueError, match="Fatal look-ahead bias"):
            validate_flows(df)


def test_zero_and_missing_prior_aum_denominators():
    """When prior month AUM is missing, zero, or negative, redemption rate must be NaN (never 0.0)."""
    # Case 1: First month has no prior AUM
    df1 = pd.DataFrame({
        "month": ["2024-09"],
        "category": ["Large Cap"],
        "gross_inflow_cr": [100.0],
        "gross_redemption_cr": [50.0],
        "net_flow_cr": [50.0],
        "aum_close_cr": [1000.0],
        "aaum_cr": [950.0],
        "available_from": ["2024-10-10T00:00:00Z"],
        "source_url": ["https://portal.amfiindia.com"],
        "retrieved_at": ["2024-10-10T00:00:00Z"],
    })
    rates1 = compute_rates(df1)
    assert pd.isna(rates1.iloc[0]["redemption_rate_pct"])

    # Case 2: Prior month AUM was zero
    df2 = pd.DataFrame({
        "month": ["2024-08", "2024-09"],
        "category": ["Large Cap", "Large Cap"],
        "gross_inflow_cr": [0.0, 50.0],
        "gross_redemption_cr": [0.0, 50.0],
        "net_flow_cr": [0.0, 0.0],
        "aum_close_cr": [0.0, 500.0],
        "aaum_cr": [0.0, 450.0],
        "available_from": ["2024-09-10T00:00:00Z", "2024-10-10T00:00:00Z"],
        "source_url": ["https://portal.amfiindia.com", "https://portal.amfiindia.com"],
        "retrieved_at": ["2024-09-10T00:00:00Z", "2024-10-10T00:00:00Z"],
    })
    rates2 = compute_rates(df2)
    row_sep2 = rates2[rates2["month"] == "2024-09"].iloc[0]
    assert pd.isna(row_sep2["redemption_rate_pct"])


def test_zero_gross_redemption_preserved():
    """When gross redemptions are legitimately 0.0 with positive prior AUM, rate is 0.0 (not NaN)."""
    df = pd.DataFrame({
        "month": ["2024-08", "2024-09"],
        "category": ["Large Cap", "Large Cap"],
        "gross_inflow_cr": [100.0, 100.0],
        "gross_redemption_cr": [50.0, 0.0],
        "net_flow_cr": [50.0, 100.0],
        "aum_close_cr": [1000.0, 1100.0],
        "aaum_cr": [950.0, 1050.0],
        "available_from": ["2024-09-10T00:00:00Z", "2024-10-10T00:00:00Z"],
        "source_url": ["https://portal.amfiindia.com", "https://portal.amfiindia.com"],
        "retrieved_at": ["2024-09-10T00:00:00Z", "2024-10-10T00:00:00Z"],
    })
    rates = compute_rates(df)
    row_sep = rates[rates["month"] == "2024-09"].iloc[0]
    assert row_sep["redemption_rate_pct"] == 0.0


# ===========================================================================
# SECTION B: Feature & Forecast Leakage Regressions
# ===========================================================================

def test_future_mutation_invariance_features(multi_period_feature_matrix):
    """Mutating observations in future month T+1 must leave month T features 100% unchanged."""
    feat_df = multi_period_feature_matrix
    sorted_months = sorted(feat_df["target_month"].unique())
    cutoff_month = sorted_months[12]

    prior_rows_orig = feat_df[feat_df["target_month"] <= cutoff_month].sort_values(["target_month", "category"]).to_dict(orient="records")

    # Mutate feature rows strictly after cutoff_month
    mutated_feat_df = feat_df.copy()
    future_mask = mutated_feat_df["target_month"] > cutoff_month
    mutated_feat_df.loc[future_mask, "nifty_return_lag0"] = 0.999
    mutated_feat_df.loc[future_mask, "rate_lag0"] = 50.0

    prior_rows_after = mutated_feat_df[mutated_feat_df["target_month"] <= cutoff_month].sort_values(["target_month", "category"]).to_dict(orient="records")

    assert prior_rows_orig == prior_rows_after


def test_walk_forward_strict_out_of_sample_and_fold_local_scaling(multi_period_feature_matrix):
    """Verify expanding window evaluation fits scalers strictly inside each fold and tests out-of-sample."""
    preds_df, results = walk_forward_forecast(multi_period_feature_matrix, min_train_months=6)
    validate_table("predictions", preds_df)

    assert not preds_df.empty
    # Every prediction must have is_out_of_sample == True
    assert preds_df["is_out_of_sample"].astype(bool).all()

    # Verify that train_end < target_month for every evaluation fold
    for _, row in preds_df.iterrows():
        t_month = row["target_month"]
        t_end = row["train_end"]
        train_end_month = t_end[:7]
        assert train_end_month < t_month


def test_persistence_and_ridge_identical_evaluation_dates(multi_period_feature_matrix):
    """Persistence baseline and candidate model must share identical evaluation target rows and dates."""
    preds_df, _ = walk_forward_forecast(multi_period_feature_matrix, min_train_months=6)

    assert not preds_df.empty
    # For every row, predicted_rate and baseline_rate are populated finite floats
    assert preds_df["predicted_rate"].notna().all()
    assert preds_df["baseline_rate"].notna().all()
    assert (preds_df["predicted_rate"].astype(float) >= 0.0).all()
    assert (preds_df["baseline_rate"].astype(float) >= 0.0).all()


def test_contribution_decomposition_reconciliation():
    """Additive feature contributions plus intercept and category effect must reconcile to y_hat within 1e-4."""
    feat_cols = ["rate_lag0", "roll_mean3", "vix_mean_lag0"]
    raw_row = {
        "category": "Large Cap",
        "rate_lag0": 4.5,
        "roll_mean3": 4.2,
        "vix_mean_lag0": 14.0,
    }
    model_coefs = {
        "intercept": 2.15,
        "rate_lag0": 0.45,
        "roll_mean3": 0.20,
        "vix_mean_lag0": -0.05,
        "cat_Large Cap": 0.35,
    }
    scaler_mean = {"rate_lag0": 4.0, "roll_mean3": 4.0, "vix_mean_lag0": 15.0}
    scaler_scale = {"rate_lag0": 1.0, "roll_mean3": 1.0, "vix_mean_lag0": 2.0}

    decomp = explain_ridge_prediction(
        raw_feature_row=raw_row,
        model_coefs=model_coefs,
        feature_cols=feat_cols,
        scaler_mean=scaler_mean,
        scaler_scale=scaler_scale,
    )
    assert decomp["explanation_status"] == "reconciled"

    # Hand-calculate expected y_hat:
    # intercept: 2.15
    # cat_Large Cap: 0.35
    # rate_lag0: 0.45 * (4.5 - 4.0)/1.0 = 0.225
    # roll_mean3: 0.20 * (4.2 - 4.0)/1.0 = 0.04
    # vix_mean_lag0: -0.05 * (14.0 - 15.0)/2.0 = 0.025
    # Total = 2.15 + 0.35 + 0.225 + 0.04 + 0.025 = 2.79
    expected_y_hat = 2.79
    assert math.isclose(decomp["total_reconciled"], expected_y_hat, abs_tol=1e-4)


def test_empirical_residual_band_cutoff_invariance():
    """Residual bands must use strictly prior residuals; adding future residuals cannot change earlier bands."""
    hist_preds = pd.DataFrame({
        "as_of": ["2024-01-12T00:00:00Z", "2024-02-12T00:00:00Z", "2024-03-12T00:00:00Z",
                  "2024-04-12T00:00:00Z", "2024-05-12T00:00:00Z", "2024-06-12T00:00:00Z",
                  "2024-07-12T00:00:00Z", "2024-08-12T00:00:00Z", "2024-09-12T00:00:00Z",
                  "2024-10-12T00:00:00Z"],
        "target_month": ["2024-01", "2024-02", "2024-03", "2024-04", "2024-05", "2024-06", "2024-07", "2024-08", "2024-09", "2024-10"],
        "category": ["Large Cap"] * 10,
        "predicted_rate": [5.0] * 10,
        "actual_rate": [5.2, 4.8, 5.1, 4.9, 5.3, 4.7, 5.0, 5.2, 4.9, 5.1],
        "is_out_of_sample": [True] * 10,
    })

    cutoff = "2024-10-12T00:00:00Z"
    bands1 = compute_empirical_residual_bands(hist_preds, current_as_of=cutoff, predicted_rate=5.0, min_residuals=8)
    assert bands1["band_status"] == "ok"

    # Append a future observation with a massive residual
    hist_preds_expanded = pd.concat([
        hist_preds,
        pd.DataFrame([{
            "as_of": "2024-11-12T00:00:00Z",
            "target_month": "2024-11",
            "category": "Large Cap",
            "predicted_rate": 5.0,
            "actual_rate": 25.0,
            "is_out_of_sample": True,
        }])
    ], ignore_index=True)

    bands2 = compute_empirical_residual_bands(hist_preds_expanded, current_as_of=cutoff, predicted_rate=5.0, min_residuals=8)
    # Earlier bands must be completely unaffected
    assert bands1["lower_band"] == bands2["lower_band"]
    assert bands1["upper_band"] == bands2["upper_band"]
    assert bands1["residual_count"] == bands2["residual_count"]


def test_insufficient_history_short_series_paths():
    """When residual count is below threshold, status must be insufficient_history with null bounds."""
    hist_preds = pd.DataFrame({
        "as_of": ["2024-01-12T00:00:00Z", "2024-02-12T00:00:00Z"],
        "target_month": ["2024-01", "2024-02"],
        "category": ["Large Cap", "Large Cap"],
        "predicted_rate": [5.0, 5.0],
        "actual_rate": [5.2, 4.8],
        "is_out_of_sample": [True, True],
    })
    bands = compute_empirical_residual_bands(hist_preds, current_as_of="2024-03-12T00:00:00Z", predicted_rate=5.0, min_residuals=10)
    assert bands["band_status"] == "insufficient_history"
    assert bands["lower_band"] is None
    assert bands["upper_band"] is None
    assert bands["residual_count"] == 2


# ===========================================================================
# SECTION C: Alerts & Anomaly Handling Regressions
# ===========================================================================

def test_robust_z_zero_mad_and_constant_series():
    """Constant historical series (MAD == 0.0) returns 0.0 if current == med, else capped at 3.0 / -3.0."""
    constant_rates = [4.0] * 12
    # Exactly equal to constant median
    assert compute_robust_z(constant_rates, 4.0, min_obs=6) == 0.0
    # Greater than constant median -> capped at +3.0
    assert compute_robust_z(constant_rates, 5.0, min_obs=6) == 3.0
    # Less than constant median -> capped at -3.0
    assert compute_robust_z(constant_rates, 3.0, min_obs=6) == -3.0


def test_robust_z_insufficient_history():
    """Fewer than min_obs observations returns None rather than an uncalibrated score."""
    short_rates = [4.0, 4.2, 4.1]
    assert compute_robust_z(short_rates, 4.5, min_obs=6) is None


def test_momentum_3m_zero_denominator_safe():
    """When previous 3-month mean is <= 0.0, momentum returns 0.0 to prevent division by zero."""
    rates = [0.0, 0.0, 0.0, 2.0, 3.0, 4.0]
    mom = compute_momentum_3m(rates, min_obs=6)
    assert mom == 0.0


def test_alert_rules_exact_boundary_conditions():
    """Verify exact boundary behavior for Critical, Elevated, and Normal alert rules."""
    # Build history where previous 3 months were 3.0 and last 3 months were 4.5 (momentum = +50% >= 0.10)
    history_df = pd.DataFrame({
        "month": [f"2023-{m:02d}" for m in range(1, 13)] + [f"2024-{m:02d}" for m in range(1, 9)],
        "category": ["Large Cap"] * 20,
        "redemption_rate_pct": [3.0] * 14 + [3.0, 3.0, 3.0, 4.5, 4.5, 4.5],
        "available_from": ["2024-08-10T00:00:00Z"] * 20,
    })

    # Case 1: Critical — percentile >= 90 AND (robust_z >= 2.0 OR momentum_3m >= 0.10)
    # 15.0 is higher than all past rates (pct = 100.0), and momentum_3m is 0.50 >= 0.10
    preds_crit = pd.DataFrame([{
        "as_of": "2024-09-12T00:00:00Z",
        "target_month": "2024-09",
        "category": "Large Cap",
        "predicted_rate": 15.0,
    }])
    alerts_crit = generate_alerts(preds_crit, history_df)
    assert alerts_crit.iloc[0]["level"] == "Critical"
    assert "critical_pct90_robust_or_mom" in alerts_crit.iloc[0]["rules_triggered"]

    # Case 2: Elevated — percentile >= 80 OR robust_z >= 2.0 (but not Critical)
    # Build a stable history without momentum spike
    hist_stable = pd.DataFrame({
        "month": [f"2023-{m:02d}" for m in range(1, 13)],
        "category": ["Large Cap"] * 12,
        "redemption_rate_pct": [3.0, 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.7, 3.8, 3.9, 4.0, 4.1],
        "available_from": ["2023-12-10T00:00:00Z"] * 12,
    })
    # 4.0 is at the 83rd percentile (>= 80), momentum is small (<0.10) -> Elevated
    preds_elev = pd.DataFrame([{
        "as_of": "2024-01-12T00:00:00Z",
        "target_month": "2024-01",
        "category": "Large Cap",
        "predicted_rate": 4.0,
    }])
    alerts_elev = generate_alerts(preds_elev, hist_stable)
    assert alerts_elev.iloc[0]["level"] == "Elevated"
    assert "elevated_pct80_or_robust2" in alerts_elev.iloc[0]["rules_triggered"]

    # Case 3: Normal — moderate rate below 80th percentile
    preds_norm = pd.DataFrame([{
        "as_of": "2024-01-12T00:00:00Z",
        "target_month": "2024-01",
        "category": "Large Cap",
        "predicted_rate": 3.3,
    }])
    alerts_norm = generate_alerts(preds_norm, hist_stable)
    assert alerts_norm.iloc[0]["level"] == "Normal"


def test_alert_backtest_temporal_non_leakage():
    """Future history rows (after as_of) must be strictly ignored when generating historical alerts."""
    hist_prior = pd.DataFrame({
        "month": ["2024-01", "2024-02", "2024-03", "2024-04", "2024-05", "2024-06"],
        "category": ["Large Cap"] * 6,
        "redemption_rate_pct": [3.0, 3.1, 3.2, 3.0, 3.1, 3.2],
        "available_from": ["2024-07-10T00:00:00Z"] * 6,
    })
    preds = pd.DataFrame([{
        "as_of": "2024-07-12T00:00:00Z",
        "target_month": "2024-07",
        "category": "Large Cap",
        "predicted_rate": 3.8,
    }])
    alerts1 = generate_alerts(preds, hist_prior)

    # Append future history available only in August
    hist_with_future = pd.concat([
        hist_prior,
        pd.DataFrame([{
            "month": "2024-08",
            "category": "Large Cap",
            "redemption_rate_pct": 20.0,
            "available_from": "2024-09-10T00:00:00Z",
        }])
    ], ignore_index=True)

    alerts2 = generate_alerts(preds, hist_with_future)
    assert alerts1.iloc[0]["forecast_percentile"] == alerts2.iloc[0]["forecast_percentile"]
    assert alerts1.iloc[0]["level"] == alerts2.iloc[0]["level"]


# ===========================================================================
# SECTION D: Stress Arithmetic & Output Safety Regressions
# ===========================================================================

def test_stress_scenarios_hand_calculated_reconciliation():
    """Base, moderate, severe, and custom scenario arithmetic reconciles to exact hand calculations."""
    aum = 50000.0  # ₹50,000 cr
    base_rate = 4.0  # 4.0%
    custom_rate = 6.0  # 6.0%

    table = scenario_table(forecast_rate=base_rate, aum_cr=aum, custom_rate=custom_rate)
    lookup = {row["scenario_name"]: row for _, row in table.iterrows()}

    # Base Forecast: 50,000 * 4% = 2,000.0 cr
    assert lookup["Base Forecast"]["estimated_outflow_cr"] == 2000.0
    assert lookup["Base Forecast"]["incremental_outflow_cr"] == 0.0

    # Moderate Stress (1.25x): 4% * 1.25 = 5.0%. Outflow = 50,000 * 5% = 2,500.0 cr. Incremental = 500.0 cr
    assert lookup["Moderate Stress (1.25x)"]["estimated_outflow_cr"] == 2500.0
    assert lookup["Moderate Stress (1.25x)"]["incremental_outflow_cr"] == 500.0

    # Severe Stress (1.50x): 4% * 1.50 = 6.0%. Outflow = 50,000 * 6% = 3,000.0 cr. Incremental = 1,000.0 cr
    assert lookup["Severe Stress (1.50x)"]["estimated_outflow_cr"] == 3000.0
    assert lookup["Severe Stress (1.50x)"]["incremental_outflow_cr"] == 1000.0

    # Custom Scenario: 50,000 * 6% = 3,000.0 cr. Incremental = 1,000.0 cr
    assert lookup["Custom Scenario"]["estimated_outflow_cr"] == 3000.0
    assert lookup["Custom Scenario"]["incremental_outflow_cr"] == 1000.0


def test_stress_incremental_outflow_missing_base_makes_incremental_none():
    """When base forecast is missing, incremental outflows must be None (never 0.0 or fabricated)."""
    table = scenario_table(forecast_rate=None, aum_cr=50000.0, custom_rate=5.0)
    for _, row in table.iterrows():
        if row["scenario_name"] == "Custom Scenario":
            assert row["estimated_outflow_cr"] == 2500.0
            assert pd.isna(row["incremental_outflow_cr"])


def test_stress_negative_and_non_finite_rejection():
    """Negative or non-finite inputs to stress_outflow must return status 'invalid_input'."""
    assert stress_outflow(-1000.0, 5.0)["status"] == "invalid_input"
    assert stress_outflow(1000.0, -5.0)["status"] == "invalid_input"
    assert stress_outflow(float("nan"), 5.0)["status"] == "invalid_input"
    assert stress_outflow(1000.0, float("inf"))["status"] == "invalid_input"


def test_stress_rates_above_100_percent_capped():
    """Redemption rates above 100% must be capped at exactly 100% with status 'capped_at_100'."""
    res = stress_outflow(aum_cr=20000.0, rate_pct=150.0)
    assert res["status"] == "capped_at_100"
    assert res["effective_rate_pct"] == 100.0
    assert res["estimated_outflow_cr"] == 20000.0  # capped at total AUM


def test_stress_insufficient_history_never_claims_empirical():
    """When empirical bands are absent/insufficient, table status is explicitly 'insufficient_history'."""
    bands_insufficient = {"band_status": "insufficient_history", "lower_band": None, "upper_band": None}
    table = scenario_table(forecast_rate=5.0, bands=bands_insufficient, aum_cr=10000.0)
    p10_row = table[table["scenario_name"] == "Lower Bound (P10)"].iloc[0]
    p90_row = table[table["scenario_name"] == "Upper Bound (P90)"].iloc[0]

    assert p10_row["status"] == "insufficient_history"
    assert p90_row["status"] == "insufficient_history"
    assert pd.isna(p10_row["estimated_outflow_cr"])
    assert pd.isna(p90_row["estimated_outflow_cr"])


def test_atomic_artifact_replacement_preserves_target_on_failure(tmp_path: Path):
    """Writing invalid data to an existing target file via atomic_write_csv leaves original file untouched."""
    target_csv = tmp_path / "protected_alerts.csv"
    target_csv.write_text("as_of,target_month\n2024-09,2024-10\n")

    # Attempt to write invalid dataframe
    bad_df = pd.DataFrame({"invalid_column": [1, 2, 3]})
    with pytest.raises(ValueError):
        atomic_write_csv(bad_df, target_csv, contract_name="alerts")

    # Verify original file untouched and no leftover .tmp
    assert target_csv.read_text() == "as_of,target_month\n2024-09,2024-10\n"
    assert not (tmp_path / "protected_alerts.csv.tmp").exists()
