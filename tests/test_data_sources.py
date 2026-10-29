import pandas as pd
import requests

from fundflow.data_sources import (
    AMFI_NAV_URL,
    fetch_amfi_nav,
    frame_is_observed,
    parse_amfi_nav_text,
    unavailable_flows,
)


def test_unconfigured_flow_source_is_empty_and_explicitly_unavailable():
    frame, status = unavailable_flows()
    assert frame.empty
    assert status.status == "unavailable"
    assert "not configured" in status.message.lower()
    assert "gross_redemption_cr" in frame.columns


def test_empty_frame_is_not_observed():
    assert not frame_is_observed(pd.DataFrame())


def test_real_rows_are_detected_as_observed():
    assert frame_is_observed(pd.DataFrame([{"value": 1}]))


def test_parse_amfi_six_column_format_and_skip_sections():
    text = """Scheme Code;ISIN Div Payout/ ISIN Growth;ISIN Div Reinvestment;Scheme Name;Net Asset Value;Date

Open Ended Schemes(Debt Scheme - Banking and PSU Fund)

Example Mutual Fund
12345;INF000A01000;-;Example Liquid Fund - Direct Growth;12.3456;28-Oct-2026
"""
    frame, rejected = parse_amfi_nav_text(text)
    assert rejected == 0
    assert len(frame) == 1
    assert frame.iloc[0]["scheme_code"] == "12345"
    assert frame.iloc[0]["scheme_name"] == "Example Liquid Fund - Direct Growth"
    assert frame.iloc[0]["nav"] == 12.3456
    assert frame.iloc[0]["nav_date"] == "2026-10-28"
    assert frame.iloc[0]["amc"] == "Example Mutual Fund"


def test_parse_amfi_eight_column_format():
    text = """Scheme Code;ISIN Div Payout/ ISIN Growth;ISIN Div Reinvestment;Scheme Name;Plan;Option;Net Asset Value;Date
12345;INF000A01000;-;Example Fund;Direct;Growth;9.8765;27-Oct-2026
"""
    frame, rejected = parse_amfi_nav_text(text)
    assert rejected == 0
    assert frame.iloc[0]["scheme_name"] == "Example Fund Direct Growth"
    assert frame.iloc[0]["nav"] == 9.8765


def test_malformed_nav_rows_are_rejected_not_coerced_to_zero():
    text = """Scheme Code;ISIN Div Payout/ ISIN Growth;ISIN Div Reinvestment;Scheme Name;Net Asset Value;Date
12345;INF000A01000;-;Bad date;10.0;not-a-date
12346;INF000A01001;-;Bad NAV;not-a-number;28-Oct-2026
"""
    frame, rejected = parse_amfi_nav_text(text)
    assert frame.empty
    assert rejected == 2


def test_fetch_failure_is_explicit(monkeypatch):
    def fail(*args, **kwargs):
        raise requests.Timeout("timed out")
    monkeypatch.setattr("fundflow.data_sources.requests.get", fail)
    frame, status = fetch_amfi_nav()
    assert frame.empty
    assert status.status == "unavailable"
    assert status.url == AMFI_NAV_URL
    assert "timed out" in status.message
