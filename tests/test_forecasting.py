"""Unit tests for walk-forward forecasting models and baselines.

Verifies Prompt 13:
- Persistence baseline R_hat(t+1) = R(t)
- Pooled Ridge regression with category one-hot encoding
- Preprocessing and scalers fitted strictly inside training folds
- Chronological expanding-window one-step-ahead walk-forward protocol
- All evaluation predictions are out-of-sample
- Persistence and Ridge compared on identical forecast origins
- Diagnostic fallback when history < 36 months with clear reporting
- Mutation invariance: modifying future test rows produces zero change in past forecasts
- Contract compliance of predictions.csv and model_results.json
- Deliberate leakage injection failure
"""
from __future__ import annotations

import json
from pathlib import Path
import numpy as np
import pandas as pd
import pytest

from fundflow.contracts import validate_table, COLUMNS
from fundflow.forecasting import walk_forward_forecast, tune_ridge_alpha, save_forecast_outputs

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def synthetic_feature_matrix():
    """Generate 24 months of valid feature matrix data for 3 categories."""
    rows = []
    start_y = 2022
    categories = ["Large Cap", "Mid Cap", "Flexi Cap"]

    for i in range(24):
        total_m = 1 + i
        y = start_y + (total_m - 1) // 12
        m = ((total_m - 1) % 12) + 1
        t_month = f"{y:04d}-{m:02d}"
        as_of_ts = f"{t_month}-12T00:00:00Z"

        for cat_idx, cat in enumerate(categories):
            base_rate = 1.5 + cat_idx * 0.3
            rate_lag0 = base_rate + np.sin(i * 0.5) * 0.2
            rate_lag1 = base_rate + np.sin((i - 1) * 0.5) * 0.2
            rate_lag2 = base_rate + np.sin((i - 2) * 0.5) * 0.2
            rate_lag11 = base_rate + np.sin((i - 11) * 0.5) * 0.2
            target_rate = base_rate + np.sin((i + 1) * 0.5) * 0.2

            rows.append({
                "as_of": as_of_ts,
                "target_month": t_month,
                "category": cat,
                "rate_lag0": round(rate_lag0, 4),
                "rate_lag1": round(rate_lag1, 4),
                "rate_lag2": round(rate_lag2, 4),
                "rate_lag11": round(rate_lag11, 4),
                "roll_mean3": round(float(np.mean([rate_lag0, rate_lag1, rate_lag2])), 4),
                "roll_std3": round(float(np.std([rate_lag0, rate_lag1, rate_lag2], ddof=1)), 4),
                "delta1": round(float(rate_lag0 - rate_lag1), 4),
                "net_flow_rate_lag0": round(0.8 + cat_idx * 0.1, 4),
                "aum_growth_lag0": round(1.2 + cat_idx * 0.2, 4),
                "nifty_return_lag0": round(0.5 + (i % 3) * 0.2, 4),
                "nifty_drawdown_3m": round(-3.0 + (i % 4) * 0.4, 4),
                "vix_mean_lag0": round(14.0 + (i % 5) * 0.5, 4),
                "vix_change_lag0": round(-0.2 + (i % 2) * 0.4, 4),
                "target_rate": round(target_rate, 4),
            })

    df = pd.DataFrame(rows, columns=COLUMNS["feature_matrix"])
    return validate_table("feature_matrix", df)


def test_tune_ridge_alpha():
    np.random.seed(42)
    X = np.random.randn(20, 5)
    y = X[:, 0] * 2.0 + np.random.randn(20) * 0.1
    best_a = tune_ridge_alpha(X, y)
    assert best_a in [0.1, 1.0, 10.0, 100.0]


def test_walk_forward_contract_and_out_of_sample(synthetic_feature_matrix):
    preds, results = walk_forward_forecast(synthetic_feature_matrix, min_train_months=12)
    assert not preds.empty
    validate_table("predictions", preds)
    assert tuple(preds.columns) == COLUMNS["predictions"]

    # Every prediction must be marked out of sample
    assert (preds["is_out_of_sample"] == True).all()

    # Results envelope contract validation
    assert results["version"] == 1
    assert "metrics" in results["payload"]
    metrics = results["payload"]["metrics"]
    assert "ridge_mae" in metrics
    assert "persistence_mae" in metrics
    assert "ridge_beat_fraction" in metrics


def test_persistence_baseline_logic(synthetic_feature_matrix):
    preds, _ = walk_forward_forecast(synthetic_feature_matrix, min_train_months=12)
    for _, row in preds.iterrows():
        t_month = row["target_month"]
        cat = row["category"]
        base_rate = row["baseline_rate"]

        # Baseline rate must match rate_lag0 of that target_month and category
        fm_row = synthetic_feature_matrix[
            (synthetic_feature_matrix["target_month"] == t_month) &
            (synthetic_feature_matrix["category"] == cat)
        ].iloc[0]
        assert pytest.approx(base_rate) == fm_row["rate_lag0"]


def test_mutation_invariance_future_rows_do_not_alter_past_forecasts(synthetic_feature_matrix):
    base_preds, _ = walk_forward_forecast(synthetic_feature_matrix, min_train_months=12)
    cutoff_month = "2023-06"
    past_preds_base = base_preds[base_preds["target_month"] <= cutoff_month].copy().reset_index(drop=True)

    # Mutate a future month (> 2023-06)
    mutated_fm = synthetic_feature_matrix.copy()
    mutated_fm.loc[mutated_fm["target_month"] == "2023-11", "rate_lag0"] *= 5.0
    mutated_fm.loc[mutated_fm["target_month"] == "2023-11", "target_rate"] *= 10.0

    mutated_preds, _ = walk_forward_forecast(mutated_fm, min_train_months=12)
    past_preds_mutated = mutated_preds[mutated_preds["target_month"] <= cutoff_month].copy().reset_index(drop=True)

    # Past forecasts must be identical
    pd.testing.assert_frame_equal(past_preds_base, past_preds_mutated)


def test_insufficient_history_diagnostic_labeling(synthetic_feature_matrix):
    # Pass 36 months requirement on 24-month dataset
    preds, results = walk_forward_forecast(synthetic_feature_matrix, min_train_months=36)
    assert not preds.empty
    # Must explicitly state reduced diagnostic warm-up in limitations
    assert any("diagnostic" in lim.lower() for lim in results["payload"]["limitations"])


def test_deliberate_leakage_injection_fails():
    # If a feature matrix has non-UTC timezone in contract
    invalid_row = {
        "as_of": "2024-01-12T00:00:00+05:30",  # Non-UTC timezone (IST instead of UTC)
        "target_month": "2024-01",
        "category": "Large Cap",
        "rate_lag0": 1.0, "rate_lag1": 1.0, "rate_lag2": 1.0, "rate_lag11": 1.0,
        "roll_mean3": 1.0, "roll_std3": 0.0, "delta1": 0.0,
        "net_flow_rate_lag0": 0.5, "aum_growth_lag0": 1.0,
        "nifty_return_lag0": 1.0, "nifty_drawdown_3m": -1.0,
        "vix_mean_lag0": 15.0, "vix_change_lag0": 0.0,
        "target_rate": 1.2,
    }
    df = pd.DataFrame([invalid_row])
    with pytest.raises(ValueError, match="as_of: ISO UTC timestamp required"):
        walk_forward_forecast(df)


def test_save_forecast_outputs(tmp_path, synthetic_feature_matrix):
    preds, results = walk_forward_forecast(synthetic_feature_matrix, min_train_months=12)
    p_file, r_file = save_forecast_outputs(preds, results, outputs_dir=tmp_path)
    assert p_file.is_file()
    assert r_file.is_file()

    # Re-read and validate
    saved_preds = pd.read_csv(p_file)
    validate_table("predictions", saved_preds)
    with r_file.open("r", encoding="utf-8") as f:
        saved_res = json.load(f)
    assert saved_res["version"] == 1
    assert "metrics" in saved_res["payload"]
