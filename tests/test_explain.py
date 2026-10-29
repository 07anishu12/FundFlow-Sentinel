"""Unit tests for Ridge model explanation and empirical uncertainty bands.

Verifies Prompt 15:
- Exact linear contribution decomposition reconciling to model prediction (tolerance <= 1e-4)
- Standardized feature space and category effect handling
- Unavailable explanation handling on missing inputs
- Prior-only residual P10/P90 uncertainty bands
- Insufficient history behavior (returns None and band_status='insufficient_history')
- Temporal mutation test: adding/modifying future residuals produces zero change in past bands
"""
from __future__ import annotations

import math
import numpy as np
import pandas as pd
import pytest

from fundflow.explain import explain_ridge_prediction, compute_empirical_residual_bands


def test_explain_ridge_prediction_reconciliation():
    feature_cols = ["feat1", "feat2", "feat3"]
    raw_row = {
        "feat1": 10.0,
        "feat2": 5.0,
        "feat3": 2.0,
        "category": "Large Cap",
    }
    model_coefs = {
        "intercept": 1.5,
        "feat1": 0.4,
        "feat2": -0.2,
        "feat3": 0.1,
        "cat_Large Cap": 0.3,
        "cat_Mid Cap": -0.1,
    }
    scaler_mean = {"feat1": 8.0, "feat2": 5.0, "feat3": 1.0}
    scaler_scale = {"feat1": 2.0, "feat2": 2.0, "feat3": 1.0}

    # Transformed:
    # z1 = (10 - 8)/2 = 1.0 -> contrib = 0.4 * 1.0 = 0.4
    # z2 = (5 - 5)/2 = 0.0 -> contrib = -0.2 * 0.0 = 0.0
    # z3 = (2 - 1)/1 = 1.0 -> contrib = 0.1 * 1.0 = 0.1
    # cat_contrib = 0.3
    # intercept = 1.5
    # total = 1.5 + 0.4 + 0.0 + 0.1 + 0.3 = 2.3

    res = explain_ridge_prediction(
        raw_row, model_coefs, feature_cols,
        scaler_mean=scaler_mean, scaler_scale=scaler_scale
    )

    assert res["explanation_status"] == "reconciled"
    assert pytest.approx(res["total_reconciled"], abs=1e-4) == 2.3
    assert len(res["feature_contributions"]) == 3
    assert res["category_contribution"] == 0.3


def test_explain_ridge_prediction_unavailable_on_missing_val():
    raw_row = {"feat1": np.nan, "category": "Large Cap"}
    res = explain_ridge_prediction(raw_row, {}, ["feat1"])
    assert res["explanation_status"] == "unavailable"
    assert "Missing or non-finite" in res["reason"]


def test_residual_bands_insufficient_history():
    # Only 3 historical predictions (below minimum 10)
    df = pd.DataFrame([
        {"as_of": "2023-01-12T00:00:00Z", "target_month": "2023-01", "predicted_rate": 1.2, "actual_rate": 1.1, "is_out_of_sample": True},
        {"as_of": "2023-02-12T00:00:00Z", "target_month": "2023-02", "predicted_rate": 1.3, "actual_rate": 1.4, "is_out_of_sample": True},
        {"as_of": "2023-03-12T00:00:00Z", "target_month": "2023-03", "predicted_rate": 1.5, "actual_rate": 1.6, "is_out_of_sample": True},
    ])
    bands = compute_empirical_residual_bands(df, current_as_of="2023-04-12T00:00:00Z", predicted_rate=1.5, min_residuals=10)
    assert bands["band_status"] == "insufficient_history"
    assert bands["lower_band"] is None
    assert bands["upper_band"] is None
    assert bands["residual_count"] == 3


def test_residual_bands_sufficient_history():
    # Generate 15 historical predictions
    rows = []
    for i in range(15):
        m = i + 1
        as_of_ts = f"2023-{m:02d}-12T00:00:00Z"
        rows.append({
            "as_of": as_of_ts,
            "target_month": f"2023-{m:02d}",
            "predicted_rate": 1.5 + (i % 3) * 0.1,
            "actual_rate": 1.5 + (i % 3) * 0.1 + ((i % 5) - 2) * 0.05,
            "is_out_of_sample": True,
        })
    df = pd.DataFrame(rows)

    bands = compute_empirical_residual_bands(df, current_as_of="2024-01-12T00:00:00Z", predicted_rate=2.0, min_residuals=10)
    assert bands["band_status"] == "ok"
    assert bands["lower_band"] is not None
    assert bands["upper_band"] is not None
    assert bands["lower_band"] <= 2.0 <= bands["upper_band"]
    assert bands["residual_count"] == 15


def test_residual_bands_temporal_mutation_invariance():
    # Base history of 12 predictions
    rows = []
    for i in range(12):
        m = i + 1
        as_of_ts = f"2023-{m:02d}-12T00:00:00Z"
        rows.append({
            "as_of": as_of_ts,
            "target_month": f"2023-{m:02d}",
            "predicted_rate": 1.5,
            "actual_rate": 1.5 + ((i % 3) - 1) * 0.1,
            "is_out_of_sample": True,
        })
    df_base = pd.DataFrame(rows)

    bands_base = compute_empirical_residual_bands(df_base, current_as_of="2024-01-12T00:00:00Z", predicted_rate=2.0, min_residuals=10)

    # Add a future prediction (as_of 2024-02-12T00:00:00Z > current_as_of 2024-01-12T00:00:00Z)
    future_row = {
        "as_of": "2024-02-12T00:00:00Z",
        "target_month": "2024-02",
        "predicted_rate": 10.0,
        "actual_rate": 50.0,
        "is_out_of_sample": True,
    }
    df_mutated = pd.concat([df_base, pd.DataFrame([future_row])], ignore_index=True)

    bands_mutated = compute_empirical_residual_bands(df_mutated, current_as_of="2024-01-12T00:00:00Z", predicted_rate=2.0, min_residuals=10)

    # Bands must be identical because future residual is ignored
    assert bands_base["lower_band"] == bands_mutated["lower_band"]
    assert bands_base["upper_band"] == bands_mutated["upper_band"]
    assert bands_base["residual_count"] == bands_mutated["residual_count"]
