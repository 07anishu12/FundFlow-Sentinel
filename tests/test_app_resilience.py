"""Unit and integration tests for application safety, resilience, and caching.

Verifies Wave 13 Prompt 28:
- Safe URL scheme validation (accepts http/https; rejects javascript:, data:, file:, mock markers).
- Untrusted text sanitization (escaping HTML tags, neutralizing markdown bracket hijacking).
- Deterministic bundle fingerprinting & cache invalidation when snapshot/manifest changes.
- Boundary input validation for stress scenario rates (NaN, Inf, negative, >100% capping).
- Error boundary resilience: prevents stack traces and private filesystem paths from surfacing.
- Complete offline rendering across all 6 Streamlit pages with network sockets blocked.
"""
from __future__ import annotations

import html
import json
import math
from pathlib import Path
import socket
import pytest
import pandas as pd
from streamlit.testing.v1 import AppTest

from app.components import (
    safe_url,
    sanitize_display_text,
    safe_page_boundary,
    get_cached_table_frame,
)
from app.loaders import get_bundle_fingerprint, load_table
from fundflow.stress import stress_outflow, scenario_table

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(autouse=True)
def block_network(monkeypatch):
    """Enforce strict offline execution with hard-blocked network sockets."""
    def blocked(*args, **kwargs):
        raise AssertionError("Network access blocked during resilience tests")
    monkeypatch.setattr(socket, "create_connection", blocked)
    monkeypatch.setattr(socket.socket, "connect", blocked)


# ---------------------------------------------------------------------------
# Section 1: Untrusted Input & URL Scheme Sanitization
# ---------------------------------------------------------------------------

def test_safe_url_accepts_valid_http_and_https():
    """Valid public http and https URLs pass validation."""
    assert safe_url("https://www.amfiindia.com/reports") == "https://www.amfiindia.com/reports"
    assert safe_url("http://example.com/data") == "http://example.com/data"
    assert safe_url("  https://portal.amfiindia.com/nav  ") == "https://portal.amfiindia.com/nav"


@pytest.mark.parametrize("dangerous_url", [
    "javascript:alert(document.cookie)",
    "javascript://%0aalert(1)",
    "data:text/html,<script>alert(1)</script>",
    "file:///etc/passwd",
    "vbscript:msgbox(1)",
    "synthetic:not-a-source",
    "#",
    "",
    "   ",
    "https://",
    "http://",
    None,
])
def test_safe_url_rejects_dangerous_or_internal_schemes(dangerous_url):
    """Non-http(s) schemes, dangerous schemes, and internal markers return None."""
    assert safe_url(dangerous_url) is None


def test_sanitize_display_text_neutralizes_html_and_markdown_injection():
    """HTML tags and markdown brackets are neutralized for safe rendering."""
    # HTML injection
    raw_html = "<script>alert('xss')</script>"
    sanitized = sanitize_display_text(raw_html)
    assert "<script>" not in sanitized
    assert "&lt;script&gt;" in sanitized

    # Markdown link injection
    raw_md = "[Click here for free bonus](javascript:alert(1))"
    sanitized_md = sanitize_display_text(raw_md)
    assert "[" not in sanitized_md
    assert "]" not in sanitized_md
    assert "(Click here for free bonus)" in sanitized_md

    # None and empty handling
    assert sanitize_display_text(None) == ""
    assert sanitize_display_text("") == ""
    assert sanitize_display_text(123) == "123"


# ---------------------------------------------------------------------------
# Section 2: Bundle Fingerprint & Cache Invalidation
# ---------------------------------------------------------------------------

def test_bundle_fingerprint_deterministic_and_changes_on_manifest_edit(tmp_path):
    """Bundle fingerprint is stable, deterministic, and updates when manifest changes."""
    snap_dir = tmp_path / "snapshots"
    snap_dir.mkdir(parents=True)
    manifest_p = snap_dir / "manifest.json"
    manifest_p.write_text(json.dumps({"version": 1, "snapshot_id": "snap-v1"}))

    fp1 = get_bundle_fingerprint(data_root=tmp_path, bundle="snapshots")
    fp2 = get_bundle_fingerprint(data_root=tmp_path, bundle="snapshots")
    assert fp1 == fp2
    assert "snapshots:" in fp1

    # Mutate manifest -> fingerprint must change
    manifest_p.write_text(json.dumps({"version": 1, "snapshot_id": "snap-v2-updated"}))
    fp3 = get_bundle_fingerprint(data_root=tmp_path, bundle="snapshots")
    assert fp3 != fp1


def test_get_bundle_fingerprint_handles_missing_manifest(tmp_path):
    """Missing manifest produces honest 'missing' state rather than raising an exception."""
    fp = get_bundle_fingerprint(data_root=tmp_path, bundle="snapshots")
    assert "missing:" in fp


# ---------------------------------------------------------------------------
# Section 3: Scenario Input Boundary Validation
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("invalid_rate", [
    float("nan"),
    float("inf"),
    float("-inf"),
    -5.0,
    -0.01,
])
def test_stress_outflow_rejects_non_finite_and_negative_rates(invalid_rate):
    """Backend stress calculation hard-rejects non-finite and negative redemption rates."""
    res = stress_outflow(10000.0, invalid_rate)
    assert res["status"] == "invalid_input"
    assert res["estimated_outflow_cr"] is None


def test_stress_outflow_caps_excessive_rates_at_100_percent():
    """Rates above 100% are capped strictly at 100% of reference AUM."""
    aum = 50000.0
    res = stress_outflow(aum, 150.0)
    assert res["status"] == "capped_at_100"
    assert res["effective_rate_pct"] == 100.0
    assert res["estimated_outflow_cr"] == aum


# ---------------------------------------------------------------------------
# Section 4: Safe Error Boundary & Path Protection
# ---------------------------------------------------------------------------

def test_safe_page_boundary_catches_exceptions_without_stacktrace():
    """Uncaught exceptions display a sanitized user error without exposing stack traces."""
    class DummyStreamlit:
        def __init__(self):
            self.errors = []
            self.infos = []

        def error(self, msg):
            self.errors.append(msg)

        def info(self, msg):
            self.infos.append(msg)

    # Monkeypatch st inside app.components
    import app.components
    orig_st = app.components.st
    dummy = DummyStreamlit()
    app.components.st = dummy

    try:
        def crashing_fn():
            raise RuntimeError("Database connection string postgresql://user:pass@internal-db:5432 failed")

        # Must not raise
        safe_page_boundary("Test Page", crashing_fn)

        assert len(dummy.errors) == 1
        assert "unexpected error occurred" in dummy.errors[0]
        # Verify secret connection string or stack trace is NOT in user error
        assert "postgresql://" not in dummy.errors[0]
        assert "user:pass" not in dummy.errors[0]
        assert "Traceback" not in dummy.errors[0]
    finally:
        app.components.st = orig_st


# ---------------------------------------------------------------------------
# Section 5: Offline App Rendering Across All Pages
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("page_name", [
    "Home.py",
    "pages/1_Forecast_Lab.py",
    "pages/2_Sentiment_Monitor.py",
    "pages/3_Fund_Research.py",
    "pages/4_Stress_Lab.py",
    "pages/5_Evidence_and_Limits.py",
])
def test_all_pages_render_without_exception_offline(page_name):
    """Every page renders without uncaught exceptions under blocked networking."""
    page_path = ROOT / "app" / page_name
    app = AppTest.from_file(str(page_path)).run(timeout=15)
    assert not app.exception, f"Page {page_name} raised exception: {app.exception}"
    assert any("SYNTHETIC DEMO DATA" in w.value for w in app.warning)
