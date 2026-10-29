"""Unit tests for institutional financial data formatting utilities."""
from __future__ import annotations

import math
import pytest
from app.formatters import (
    format_currency_crore,
    format_rate_pct,
    format_number,
    format_period,
    format_timestamp,
    format_provenance_label,
    is_sentinel_or_missing,
    format_metric_display,
)


def test_format_currency_crore():
    assert format_currency_crore(254594.79049813) == "₹254,594.79 crore"
    assert format_currency_crore(0.0) == "₹0.00 crore"
    assert format_currency_crore(-125.4) == "−₹125.40 crore"
    assert format_currency_crore(None) == "N/A"
    assert format_currency_crore(float("nan")) == "N/A"
    assert format_currency_crore(float("inf")) == "N/A"
    assert format_currency_crore("invalid") == "N/A"


def test_format_rate_pct():
    assert format_rate_pct(0.7486) == "0.75%"
    assert format_rate_pct(0.7486, precision=4) == "0.7486%"
    assert format_rate_pct(-1.25) == "−1.25%"
    assert format_rate_pct(1.25, show_sign=True) == "+1.25%"
    assert format_rate_pct(None) == "N/A"
    assert format_rate_pct("abc") == "N/A"


def test_format_number():
    assert format_number(1234567.89) == "1,234,567.89"
    assert format_number(-500.5) == "−500.50"
    assert format_number(None) == "N/A"


def test_format_period():
    assert format_period("2024-09") == "Sep 2024"
    assert format_period("2024-09-30") == "30 Sep 2024"
    assert format_period("Custom Period") == "Custom Period"
    assert format_period(None) == "N/A"


def test_format_timestamp():
    assert format_timestamp("2026-10-28T19:41:46Z") == "28 Oct 2026, 19:41 UTC"
    assert format_timestamp(None) == "Unavailable"


def test_format_provenance_label():
    assert format_provenance_label("https://www.amfiindia.com/reports") == "AMFI Official"
    assert format_provenance_label("https://api.mfapi.in/mf/122639") == "mfapi (AMFI Wrapper)"
    assert format_provenance_label("synthetic:not-a-source") == "Synthetic Demo"
    assert format_provenance_label(None) == "Internal Engine"


# ---------------------------------------------------------------------------
# Regression Tests: -1 Sentinel Bug & Missing Value Handling
# ---------------------------------------------------------------------------

def test_sentinel_negative_one_detected_on_non_negative_metrics():
    """-1, -1.0, or negative numbers must be treated as invalid sentinels on non-negative metrics."""
    assert is_sentinel_or_missing(-1, can_be_negative=False) is True
    assert is_sentinel_or_missing(-1.0, can_be_negative=False) is True
    assert is_sentinel_or_missing("-1", can_be_negative=False) is True
    assert is_sentinel_or_missing("-1.0", can_be_negative=False) is True
    assert is_sentinel_or_missing("-999", can_be_negative=False) is True
    assert is_sentinel_or_missing(-500.0, can_be_negative=False) is True


def test_legitimate_negative_financial_numbers_preserved():
    """Legitimate negative financial values (returns, drawdowns, net flows) must NOT be masked as N/A."""
    assert is_sentinel_or_missing(-1.25, can_be_negative=True) is False
    assert is_sentinel_or_missing(-125.40, can_be_negative=True) is False
    assert is_sentinel_or_missing(-0.9166, can_be_negative=True) is False


def test_missing_values_render_as_na_never_sentinel_or_trailing_units():
    """Missing or sentinel values must render strictly as 'N/A' without units."""
    # Inherently non-negative metrics with sentinel -1
    assert format_metric_display(-1, units="₹ crore", can_be_negative=False) == "N/A"
    assert format_metric_display(-1.0, units="schemes", can_be_negative=False) == "N/A"
    assert format_metric_display("-1", units="%", can_be_negative=False) == "N/A"

    # Missing inputs (None, NaN, empty, 'None', 'nan')
    assert format_metric_display(None, units="₹ crore") == "N/A"
    assert format_metric_display(float("nan"), units="%") == "N/A"
    assert format_metric_display("", units="₹ crore") == "N/A"
    assert format_metric_display("None", units="tier") == "N/A"
    assert format_metric_display("nan", units="%") == "N/A"
    assert format_metric_display("N/A", units="₹ crore") == "N/A"


def test_valid_positive_and_negative_metric_formatting():
    """Valid numbers must format with correct precision, comma grouping, and minus sign."""
    # Legitimate positive currency
    assert format_metric_display(254594.79, units="₹ crore") == "₹254,594.79 crore"
    # Legitimate negative net flow
    assert format_metric_display(-125.40, units="₹ crore", can_be_negative=True) == "−₹125.40 crore"
    # Legitimate negative return
    assert format_metric_display(-4.55, units="%", can_be_negative=True) == "−4.55%"
    # General count
    assert format_metric_display(10, units="schemes") == "10.00 schemes"
