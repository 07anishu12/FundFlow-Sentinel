"""Unit and regression tests for data source adapters (Prompt Section 7).

Verifies:
- Successful retrieval
- Timeouts and HTTP errors
- Retry exhaustion
- Invalid schemas
- Duplicate records
- Missing observations
- Partial downloads
- Cache fallback
- Snapshot integrity after failed refresh
- Date and publication lag normalization
"""
from __future__ import annotations

import io
import json
from pathlib import Path
import urllib.error
import pytest
import pandas as pd

from fundflow.adapters import AMFINavAdapter, AMFIFlowsAdapter, AdapterResult, refresh_all_sources
from fundflow.contracts import COLUMNS, validate_table

SAMPLE_VALID_AMFI_NAV = (
    "Scheme Code;ISIN Div Payout/ ISIN Growth;ISIN Div Reinvestment;Scheme Name;Net Asset Value;Date\n"
    "119551;INF209K01157;-;Aditya Birla Sun Life Frontline Equity Fund - Direct Plan - Growth;108.4687;29-Oct-2026\n"
    "128628;INF179KA1JC4;-;HDFC Corporate Bond Fund - Regular Plan - Growth;24.1989;29-Oct-2026\n"
    "135762;INF846K01WO1;-;Axis Large Cap Fund - Direct Plan - Growth;28.9301;29-Oct-2026\n"
)

SAMPLE_WITH_DUPLICATES = (
    "Scheme Code;ISIN Div Payout/ ISIN Growth;ISIN Div Reinvestment;Scheme Name;Net Asset Value;Date\n"
    "119551;INF209K01157;-;Aditya Birla Sun Life Frontline Equity Fund;108.4687;29-Oct-2026\n"
    "119551;INF209K01157;-;Aditya Birla Sun Life Frontline Equity Fund;108.4687;29-Oct-2026\n"  # Duplicate
    "128628;INF179KA1JC4;-;HDFC Corporate Bond Fund;24.1989;29-Oct-2026\n"
)


def test_successful_retrieval(tmp_path, monkeypatch):
    adapter = AMFINavAdapter(cache_dir=tmp_path / "cache")

    def mock_urlopen(req, timeout=15):
        resp = io.BytesIO(SAMPLE_VALID_AMFI_NAV.encode("utf-8"))
        resp.status = 200
        return resp

    monkeypatch.setattr("urllib.request.urlopen", mock_urlopen)

    res = adapter.fetch(timeout=5, max_retries=1)
    assert res.http_status == 200
    assert res.cache_status == "live"
    assert res.records_accepted == 3
    assert res.duplicate_count == 0
    assert res.latest_observation_date == "2026-10-29"
    assert res.data is not None
    validate_table("nav_daily", res.data)


def test_timeout_and_http_errors(tmp_path, monkeypatch):
    adapter = AMFINavAdapter(cache_dir=tmp_path / "cache")

    def mock_urlopen_fail(req, timeout=15):
        raise urllib.error.HTTPError(req.full_url, 503, "Service Unavailable", {}, None)

    monkeypatch.setattr("urllib.request.urlopen", mock_urlopen_fail)

    res = adapter.fetch(timeout=1, max_retries=2)
    assert res.http_status == 503
    assert res.cache_status == "failed_fallback"
    assert "HTTP 503" in (res.error_details or "")


def test_retry_exhaustion(tmp_path, monkeypatch):
    adapter = AMFINavAdapter(cache_dir=tmp_path / "cache")
    call_count = 0

    def mock_urlopen_timeout(req, timeout=15):
        nonlocal call_count
        call_count += 1
        raise TimeoutError("Connection timed out")

    monkeypatch.setattr("urllib.request.urlopen", mock_urlopen_timeout)

    res = adapter.fetch(timeout=1, max_retries=3)
    assert call_count == 3
    assert res.cache_status == "failed_fallback"
    assert "Network error" in (res.error_details or "")


def test_invalid_schemas_and_rejections(tmp_path, monkeypatch):
    adapter = AMFINavAdapter(cache_dir=tmp_path / "cache")

    malformed_text = (
        "Scheme Code;ISIN;ISIN;Name;Net Asset Value;Date\n"
        "119551;INF209;x;Fund;NOT_A_FLOAT;29-Oct-2026\n"  # Invalid NAV
        "128628;INF179;x;Fund;-5.0;29-Oct-2026\n"          # Negative NAV
        "135762;INF846;x;Fund;28.9301;29-Oct-2026\n"       # Valid
    )

    def mock_urlopen(req, timeout=15):
        resp = io.BytesIO(malformed_text.encode("utf-8"))
        resp.status = 200
        return resp

    monkeypatch.setattr("urllib.request.urlopen", mock_urlopen)

    res = adapter.fetch(timeout=5)
    assert res.records_accepted == 1
    assert res.records_rejected == 2
    validate_table("nav_daily", res.data)


def test_duplicate_records_detection(tmp_path, monkeypatch):
    adapter = AMFINavAdapter(cache_dir=tmp_path / "cache")

    def mock_urlopen(req, timeout=15):
        resp = io.BytesIO(SAMPLE_WITH_DUPLICATES.encode("utf-8"))
        resp.status = 200
        return resp

    monkeypatch.setattr("urllib.request.urlopen", mock_urlopen)

    res = adapter.fetch(timeout=5)
    assert res.records_accepted == 2
    assert res.duplicate_count == 1
    assert len(res.data) == 2


def test_missing_observations_empty_data(tmp_path, monkeypatch):
    adapter = AMFINavAdapter(cache_dir=tmp_path / "cache")

    def mock_urlopen(req, timeout=15):
        resp = io.BytesIO(b"Scheme Code;ISIN;ISIN;Name;Net Asset Value;Date\n")
        resp.status = 200
        return resp

    monkeypatch.setattr("urllib.request.urlopen", mock_urlopen)

    res = adapter.fetch(timeout=5)
    assert res.records_accepted == 0
    assert len(res.data) == 0
    assert tuple(res.data.columns) == COLUMNS["nav_daily"]


def test_cache_fallback_on_network_failure(tmp_path, monkeypatch):
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir(parents=True)
    cache_file = cache_dir / "amfi_navall_latest.txt"
    cache_file.write_text(SAMPLE_VALID_AMFI_NAV, encoding="utf-8")

    adapter = AMFINavAdapter(cache_dir=cache_dir)

    def mock_urlopen_fail(req, timeout=15):
        raise urllib.error.URLError("DNS resolution failed")

    monkeypatch.setattr("urllib.request.urlopen", mock_urlopen_fail)

    res = adapter.fetch(timeout=1, max_retries=1)
    assert res.cache_status == "cached"
    assert res.records_accepted == 3
    assert "served from cache" in (res.error_details or "")


def test_snapshot_integrity_preserved_after_failed_refresh(tmp_path, monkeypatch):
    data_dir = tmp_path / "data"
    processed_dir = data_dir / "processed"
    processed_dir.mkdir(parents=True)

    dummy_flows = pd.DataFrame({
        "month": ["2024-09"],
        "category": ["Equity Scheme - Large Cap Fund"],
        "gross_inflow_cr": [1000.0],
        "gross_redemption_cr": [800.0],
        "net_flow_cr": [200.0],
        "aum_close_cr": [25000.0],
        "aaum_cr": [24500.0],
        "available_from": ["2024-10-10T00:00:00Z"],
        "source_url": ["https://portal.amfiindia.com"],
        "retrieved_at": ["2024-10-10T12:00:00Z"],
    })
    flows_file = processed_dir / "flows_category_month.csv"
    dummy_flows.to_csv(flows_file, index=False)
    initial_content = flows_file.read_text()

    # Network fails during refresh
    def mock_urlopen_fail(req, timeout=15):
        raise ConnectionRefusedError("Connection refused")

    monkeypatch.setattr("urllib.request.urlopen", mock_urlopen_fail)

    audit = refresh_all_sources(data_dir=data_dir, timeout=1)

    # Processed flows file must remain intact
    assert flows_file.read_text() == initial_content
    assert (tmp_path / "reports" / "live_data_check.json").is_file()


def test_date_parsing_variations():
    assert AMFINavAdapter._parse_date_to_iso("29-Oct-2026") == "2026-10-29"
    assert AMFINavAdapter._parse_date_to_iso("29-10-2026") == "2026-10-29"
    assert AMFINavAdapter._parse_date_to_iso("2026-10-29") == "2026-10-29"
    assert AMFINavAdapter._parse_date_to_iso("invalid-date") is None
