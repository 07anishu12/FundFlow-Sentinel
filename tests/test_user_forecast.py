"""Unit tests for user-defined forecasting and gap evaluation engine."""
from __future__ import annotations

import pandas as pd
import numpy as np
import pytest

from fundflow.user_forecast import calculate_forecast_gap, run_user_forecast


def test_calculate_forecast_gap_unobserved():
    res = calculate_forecast_gap(None, 120.0)
    assert res["status"] == "unobserved"
    assert res["gap"] is None
    assert res["abs_gap"] is None
    assert res["pct_error"] is None
    assert res["direction"] == "unobserved"


def test_calculate_forecast_gap_underpredicted():
    # Actual 150, Forecast 120 -> Actual higher -> Underpredicted
    res = calculate_forecast_gap(150.0, 120.0)
    assert res["status"] == "observed"
    assert res["gap"] == 30.0
    assert res["abs_gap"] == 30.0
    assert res["pct_error"] == 20.0  # (30 / 150) * 100 = 20%
    assert res["direction"] == "underpredicted"


def test_calculate_forecast_gap_overpredicted():
    # Actual 100, Forecast 120 -> Forecast higher -> Overpredicted
    res = calculate_forecast_gap(100.0, 120.0)
    assert res["status"] == "observed"
    assert res["gap"] == -20.0
    assert res["abs_gap"] == 20.0
    assert res["pct_error"] == 20.0
    assert res["direction"] == "overpredicted"


def test_calculate_forecast_gap_zero_actual():
    # Division by zero safety
    res = calculate_forecast_gap(0.0, 10.0)
    assert res["status"] == "observed"
    assert res["gap"] == -10.0
    assert res["abs_gap"] == 10.0
    assert res["pct_error"] is None
    assert res["direction"] == "overpredicted"


def test_run_user_forecast_insufficient_data():
    df = pd.DataFrame({"period": ["2024-01"], "val": [100.0]})
    res = run_user_forecast(df, target_col="val", date_col="period")
    assert res["status"] == "insufficient_data"
    assert any("INSUFFICIENT_HISTORY" in lim for lim in res["limitations"])


def test_run_user_forecast_walk_forward_evaluation():
    # Generate 15 periods of synthetic series
    periods = [f"2023-{m:02d}" for m in range(1, 13)] + ["2024-01", "2024-02", "2024-03"]
    values = [100.0 + i * 2.5 for i in range(len(periods))]
    df = pd.DataFrame({"period": periods, "target_rate": values})

    res = run_user_forecast(
        df,
        target_col="target_rate",
        date_col="period",
        horizon=1,
        models=["persistence", "seasonal_naive", "ridge"],
        min_train_obs=6,
    )

    assert res["status"] == "success"
    assert res["n_observations"] == 15
    assert "persistence" in res["model_forecasts"]
    assert "seasonal_naive" in res["model_forecasts"]
    assert "ridge" in res["model_forecasts"]

    # Table contains out-of-sample comparison
    table = res["comparison_table"]
    assert len(table) == 3
    assert "Model" in table.columns
    assert "MAE" in table.columns
    assert "RMSE" in table.columns
    assert "Baseline Comparison" in table.columns
