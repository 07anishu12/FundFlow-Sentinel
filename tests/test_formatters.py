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
