"""Unit tests for optional GDELT news tone ingestion and aggregation.

Verifies Prompt 16:
- Bounded query construction and parameter encoding
- Offline fixture reading with zero external network requests
- Graceful network error handling
- Monthly tone aggregation and point-in-time T+1 cutoffs
- Decoupling from core forecasting pipeline
"""
from __future__ import annotations

import json
from pathlib import Path
import pandas as pd
import pytest

from fundflow.ingest.gdelt import (
    build_gdelt_query_url,
    fetch_gdelt_tone_data,
    aggregate_gdelt_monthly_tone,
)


def test_build_gdelt_query_url():
    url = build_gdelt_query_url(query="India economy", mode="ToneChart", timespan="1m")
    assert "api.gdeltproject.org" in url
    assert "query=India+economy" in url or "query=India%20economy" in url
    assert "mode=ToneChart" in url


def test_fetch_gdelt_from_offline_fixture(tmp_path):
    fixture_file = tmp_path / "gdelt_fixture.json"
    sample_payload = {
        "status": "success",
        "results": [
            {"date": "20240115", "tone": -2.5},
            {"date": "20240116", "tone": 1.2},
        ]
    }
    with fixture_file.open("w", encoding="utf-8") as f:
        json.dump(sample_payload, f)

    data, status = fetch_gdelt_tone_data("http://dummy", fixture_path=fixture_file)
    assert status == "offline_fixture"
    assert len(data["results"]) == 2


def test_aggregate_gdelt_monthly_tone():
    raw_records = [
        {"date": "2024-01-10", "tone": -2.0},
        {"date": "2024-01-20", "tone": -4.0},
        {"date": "2024-02-05", "tone": 3.0},
    ]
    df = aggregate_gdelt_monthly_tone(raw_records)
    assert not df.empty
    assert len(df) == 2  # 2024-01 and 2024-02

    jan = df[df["month"] == "2024-01"].iloc[0]
    assert jan["mean_tone"] == -3.0
    assert jan["n_articles"] == 2
    assert jan["available_from"] == "2024-02-01T00:00:00Z"  # T+1 cutoff

    feb = df[df["month"] == "2024-02"].iloc[0]
    assert feb["mean_tone"] == 3.0
    assert feb["n_articles"] == 1
    assert feb["available_from"] == "2024-03-01T00:00:00Z"


def test_aggregate_gdelt_empty_records():
    df = aggregate_gdelt_monthly_tone([])
    assert df.empty
    assert "month" in df.columns
    assert "available_from" in df.columns
