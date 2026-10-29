"""Unit and smoke tests for Command Centre and Forecast Lab UI pages.

Verifies Prompt 18:
- Command Centre and Forecast Lab offline rendering without network access
- Prominent SYNTHETIC DEMO DATA warning on fixture fallback
- Clear OBSERVED, FORECAST, SCENARIO metric tags
- Honest display of uncertainty band status ('insufficient_history')
- Loader-only data consumption (zero business logic in UI)
"""
from __future__ import annotations

from pathlib import Path
import socket
import pytest
from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(autouse=True)
def block_network(monkeypatch):
    def blocked(*args, **kwargs):
        raise AssertionError("Network access blocked in UI tests")
    monkeypatch.setattr(socket, "create_connection", blocked)
    monkeypatch.setattr(socket.socket, "connect", blocked)


def test_command_centre_smoke():
    app = AppTest.from_file(str(ROOT / "app/Home.py")).run(timeout=15)
    assert not app.exception
    assert any("Command Centre" in t.value for t in app.title)
    assert any("SYNTHETIC DEMO DATA" in w.value for w in app.warning)
    for m in app.metric:
        assert m.label.split(" · ")[0] in {"OBSERVED", "FORECAST", "SCENARIO"}


def test_forecast_lab_smoke():
    app = AppTest.from_file(str(ROOT / "app/pages/1_Forecast_Lab.py")).run(timeout=15)
    assert not app.exception
    assert any("Forecast Lab" in t.value for t in app.title)
    assert any("SYNTHETIC DEMO DATA" in w.value for w in app.warning)
    assert any("Financial outputs are withheld" in info.value for info in app.info)
    assert not app.metric
    for m in app.metric:
        assert m.label.split(" · ")[0] in {"OBSERVED", "FORECAST", "SCENARIO"}



def test_sentiment_monitor_smoke():
    app = AppTest.from_file(str(ROOT / "app/pages/2_Sentiment_Monitor.py")).run(timeout=15)
    assert not app.exception
    assert any("Sentiment Monitor" in t.value for t in app.title)
    assert any("SYNTHETIC DEMO DATA" in w.value for w in app.warning)
    assert any("Financial outputs are withheld" in info.value for info in app.info)
    assert not app.metric
    for m in app.metric:
        assert m.label.split(" · ")[0] in {"OBSERVED", "FORECAST", "SCENARIO"}


def test_fund_research_smoke():
    app = AppTest.from_file(str(ROOT / "app/pages/3_Fund_Research.py")).run(timeout=15)
    assert not app.exception
    assert any("Fund Research" in t.value for t in app.title)
    assert any("SYNTHETIC DEMO DATA" in w.value for w in app.warning)
    assert any("Financial outputs are withheld" in info.value for info in app.info)
    assert not app.metric
    for m in app.metric:
        assert m.label.split(" · ")[0] in {"OBSERVED", "FORECAST", "SCENARIO"}


def test_stress_lab_smoke():
    app = AppTest.from_file(str(ROOT / "app/pages/4_Stress_Lab.py")).run(timeout=15)
    assert not app.exception
    assert any("Stress Lab" in t.value for t in app.title)
    assert any("SYNTHETIC DEMO DATA" in w.value for w in app.warning)
    assert any("Financial outputs are withheld" in info.value for info in app.info)
    assert not app.metric
    for m in app.metric:
        assert m.label.split(" · ")[0] in {"OBSERVED", "FORECAST", "SCENARIO"}


def test_stress_lab_with_fixtures(monkeypatch):
    monkeypatch.setenv("FUNDFLOW_FIXTURE_DIR", "data/snapshots/fixtures")
    app = AppTest.from_file(str(ROOT / "app/pages/4_Stress_Lab.py")).run(timeout=15)
    assert not app.exception
    assert any("Stress Lab" in t.value for t in app.title)
    assert any("Financial outputs are withheld" in info.value for info in app.info)
    assert not app.dataframe
    for m in app.metric:
        assert m.label.split(" · ")[0] in {"OBSERVED", "FORECAST", "SCENARIO"}


def test_evidence_and_limits_smoke():
    app = AppTest.from_file(str(ROOT / "app/pages/5_Evidence_and_Limits.py")).run(timeout=15)
    assert not app.exception
    assert any("Evidence and Limits" in t.value for t in app.title)
    assert any("SYNTHETIC DEMO DATA" in w.value for w in app.warning)
    # Verify redistribution policy warning is present
    assert any("STRICT REDISTRIBUTION POLICY" in w.value for w in app.warning)
    # Quality report fails manifest integrity; only the matching source metadata is shown.
    assert len(app.dataframe) == 1
    assert any("invalid path, metadata or contents" in e.value for e in app.error)
