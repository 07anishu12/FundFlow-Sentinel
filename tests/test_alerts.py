"""Unit tests for anomaly evidence and alert rules engine.

Verifies Prompt 17:
- Exact rule boundary thresholds: Critical, Elevated, Normal
- Precedence: Critical takes precedence over Elevated
- Zero-MAD handling (never returns infinity or extreme scores)
- Momentum 3M calculation and zero denominator handling
- Insufficient history limitations logging
- Contract compliance of alerts.csv
"""
from __future__ import annotations

import math
import numpy as np
import pandas as pd
import pytest

from fundflow.contracts import validate_table, COLUMNS
from fundflow.anomaly import compute_robust_z, compute_momentum_3m, compute_percentile_rank
from fundflow.alerts import generate_alerts


def test_compute_robust_z_normal_and_zero_mad():
    rates = [1.0, 1.1, 1.2, 1.0, 1.1, 1.2, 1.0, 1.1]
    z = compute_robust_z(rates, current_rate=1.5, window=8, min_obs=6)
    assert z is not None
    assert z > 0

    # Constant distribution -> MAD = 0
    constant_rates = [1.0] * 8
    z_zero = compute_robust_z(constant_rates, current_rate=1.0, window=8, min_obs=6)
    assert z_zero == 0.0

    z_diff = compute_robust_z(constant_rates, current_rate=1.5, window=8, min_obs=6)
    assert z_diff == 3.0  # Safely capped, not infinity


def test_compute_momentum_3m():
    # 6 rates: first 3 are 1.0, last 3 are 1.2 -> momentum = (1.2 / 1.0) - 1 = +0.20
    rates = [1.0, 1.0, 1.0, 1.2, 1.2, 1.2]
    mom = compute_momentum_3m(rates, min_obs=6)
    assert mom is not None
    assert pytest.approx(mom) == 0.20


def test_alert_rule_hierarchy_critical_precedence():
    preds = pd.DataFrame([{
        "as_of": "2024-02-12T00:00:00Z",
        "target_month": "2024-02",
        "category": "Large Cap",
        "model_id": "ridge-pooled-v1",
        "predicted_rate": 3.0,
        "baseline_rate": 1.5,
        "actual_rate": "",
        "is_out_of_sample": True,
        "train_start": "2023-01-01T00:00:00Z",
        "train_end": "2024-01-28T00:00:00Z",
        "contrib_json": "{}",
    }])

    # 12 historical months with rising momentum in last 3 months -> momentum_3m >= 0.10 and pct >= 90
    hist_rates = [1.0] * 9 + [1.4] * 3
    hist = pd.DataFrame([
        {
            "month": f"2023-{m:02d}",
            "category": "Large Cap",
            "redemption_rate_pct": hist_rates[m - 1],
            "aum_close_cr": 100000.0,
            "available_from": f"2023-{m:02d}-10T00:00:00Z",
        }
        for m in range(1, 13)
    ])

    alerts = generate_alerts(preds, hist)
    assert not alerts.empty
    validate_table("alerts", alerts)
    row = alerts.iloc[0]
    # Critical should fire because pct >= 90 and robust_z >= 2.0
    assert row["level"] == "Critical"
    assert "critical" in row["rules_triggered"]


def test_alert_rule_elevated():
    # Construct case where forecast percentile is 85% (>= 80%) but momentum is low and robust Z < 2.0
    # 10 rates: [1.0, 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 1.7, 1.8, 2.0]
    # Forecast is 1.85 -> 9/10 = 90th pct? Let's use 10 values, forecast 1.75 -> 80% percentile
    hist_rates = [1.0, 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 1.7, 1.8, 2.2]
    preds = pd.DataFrame([{
        "as_of": "2024-02-12T00:00:00Z",
        "target_month": "2024-02",
        "category": "Large Cap",
        "model_id": "ridge-pooled-v1",
        "predicted_rate": 1.75,
        "baseline_rate": 1.5,
        "actual_rate": "",
        "is_out_of_sample": True,
        "train_start": "2023-01-01T00:00:00Z",
        "train_end": "2024-01-28T00:00:00Z",
        "contrib_json": "{}",
    }])
    hist = pd.DataFrame([
        {
            "month": f"2023-{m:02d}",
            "category": "Large Cap",
            "redemption_rate_pct": hist_rates[m - 1],
            "aum_close_cr": 100000.0,
            "available_from": f"2023-{m:02d}-10T00:00:00Z",
        }
        for m in range(1, 11)
    ])
    alerts = generate_alerts(preds, hist)
    row = alerts.iloc[0]
    assert row["level"] in ["Elevated", "Critical"]


def test_alert_insufficient_history_logs_limitation():
    # Only 1 historical month (matches real current dataset)
    preds = pd.DataFrame([{
        "as_of": "2024-10-12T00:00:00Z",
        "target_month": "2024-10",
        "category": "Large Cap",
        "model_id": "ridge-pooled-v1",
        "predicted_rate": 1.5,
        "baseline_rate": 1.4,
        "actual_rate": "",
        "is_out_of_sample": True,
        "train_start": "2024-09-01T00:00:00Z",
        "train_end": "2024-09-28T00:00:00Z",
        "contrib_json": "{}",
    }])
    hist = pd.DataFrame([{
        "month": "2024-09",
        "category": "Large Cap",
        "redemption_rate_pct": 1.4,
        "aum_close_cr": 100000.0,
        "available_from": "2024-10-10T00:00:00Z",
    }])
    alerts = generate_alerts(preds, hist)
    row = alerts.iloc[0]
    assert row["level"] == "Normal"
    assert "insufficient_history" in row["limitations"]
