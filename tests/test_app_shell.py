"""Offline smoke coverage for every page and the loader trust boundary."""
import ast
import json
from pathlib import Path
import socket

import pytest
from streamlit.testing.v1 import AppTest

from app.components import metric_card
from app.loaders import load_table

ROOT = Path(__file__).resolve().parents[1]
PAGES = [ROOT / "app/Home.py", *sorted((ROOT / "app/pages").glob("*.py"))]


@pytest.fixture(autouse=True)
def forbid_network(monkeypatch):
    def blocked(*args, **kwargs):
        raise AssertionError("The shell must not access the network")
    monkeypatch.setattr(socket, "create_connection", blocked)
    monkeypatch.setattr(socket.socket, "connect", blocked)


@pytest.mark.parametrize("page", PAGES, ids=lambda p: p.stem)
def test_pages_render_offline(page):
    app = AppTest.from_file(str(page)).run(timeout=15)
    assert not app.exception
    assert any("SYNTHETIC DEMO DATA" in warning.value for warning in app.warning)
    assert any("Freshness" in info.value for info in app.info)
    for metric in app.metric:
        assert metric.label.split(" · ")[0] in {"OBSERVED", "FORECAST", "SCENARIO"}


@pytest.mark.parametrize("page", PAGES, ids=lambda p: p.stem)
def test_missing_optional_files_render(page, tmp_path, monkeypatch):
    (tmp_path / "manifest.json").write_text((ROOT / "data/snapshots/fixtures/manifest.json").read_text())
    monkeypatch.setenv("FUNDFLOW_FIXTURE_DIR", str(tmp_path))
    app = AppTest.from_file(str(page)).run(timeout=15)
    assert not app.exception
    assert not app.metric
    assert any("SYNTHETIC DEMO DATA" in warning.value for warning in app.warning)


@pytest.mark.parametrize("manifest", [{}, {"synthetic": False, "tables": ["predictions"]}])
def test_loader_rejects_undeclared_data(tmp_path, monkeypatch, manifest):
    (tmp_path / "manifest.json").write_text(json.dumps(manifest))
    monkeypatch.setenv("FUNDFLOW_FIXTURE_DIR", str(tmp_path))
    assert load_table("predictions").frame.empty
    assert "withheld" in load_table("predictions").message


def test_invalid_csv_is_not_displayed(tmp_path, monkeypatch):
    (tmp_path / "manifest.json").write_text(json.dumps({"synthetic": True, "tables": ["predictions"]}))
    (tmp_path / "predictions.csv").write_text("wrong_column\n42\n")
    monkeypatch.setenv("FUNDFLOW_FIXTURE_DIR", str(tmp_path))
    result = load_table("predictions")
    assert result.frame.empty
    assert "unavailable" in result.message


def test_metric_requires_label_and_context():
    with pytest.raises(ValueError):
        metric_card("Example", 1, kind="UNKNOWN", period="2020-01", units="%", source="synthetic")
    with pytest.raises(ValueError):
        metric_card("Example", 1, kind="SCENARIO", period="", units="%", source="synthetic")


def test_no_model_or_network_imports():
    forbidden = {"forecasting", "ranking", "requests", "urllib", "httpx", "yfinance"}
    for path in (ROOT / "app").rglob("*.py"):
        tree = ast.parse(path.read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names = [item.name for item in node.names]
            elif isinstance(node, ast.ImportFrom):
                names = [node.module or ""]
            else:
                continue
            assert not any(forbidden.intersection(name.split(".")) for name in names), path
