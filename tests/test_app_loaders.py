"""Comprehensive unit and contract tests for app.loaders and app boundary.

Covers:
- Network-free boundary invariant (all network calls blocked)
- Missing file handling (absent files, undeclared files, missing bundles)
- Empty file handling (0-byte CSVs, header-only CSVs)
- Malformed file handling (malformed CSV headers/types, corrupted JSON, non-finite floats)
- Stale data detection with clock injection and configurable thresholds
- Valid snapshot loading across all frozen tables and JSON artifacts
- Safe file-path handling rooted in the data directory (rejection of traversal and absolute paths)
- Safe fallback behavior and synthetic fixture declarations
- Absence of business calculations inside loaders and presentation boundaries
"""
from datetime import datetime, timedelta, timezone
import json
import math
from pathlib import Path
import socket

import pandas as pd
import pytest

from app.loaders import (
    DATA_ROOT,
    DEFAULT_DATA_DIR,
    JsonResult,
    Metadata,
    TableResult,
    load_alerts,
    load_artifact,
    load_feature_matrix,
    load_flows,
    load_market,
    load_model_results,
    load_nav_daily,
    load_predictions,
    load_quality_metadata,
    load_scheme_master,
    load_sentiment,
    load_sentiment_items,
    load_shortlist,
    load_source_metadata,
    load_table,
)
from fundflow.contracts import COLUMNS

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(autouse=True)
def forbid_network(monkeypatch):
    """Enforce strict network isolation: loaders must never access the network."""
    def blocked(*args, **kwargs):
        raise AssertionError("Network access attempted by data loader")

    monkeypatch.setattr(socket, "create_connection", blocked)
    monkeypatch.setattr(socket.socket, "connect", blocked)


# ---------------------------------------------------------------------------
# 1. Network Boundary Tests
# ---------------------------------------------------------------------------

def test_loaders_make_no_network_requests():
    """Verify default loaders operate completely offline."""
    res_pred = load_predictions()
    assert isinstance(res_pred, TableResult)
    res_flows = load_flows()
    assert isinstance(res_flows, TableResult)
    res_mr = load_model_results()
    assert isinstance(res_mr, JsonResult)


# ---------------------------------------------------------------------------
# 2. Missing File & Undeclared Dataset Tests
# ---------------------------------------------------------------------------

def test_missing_table_csv_returns_missing_status(tmp_path):
    manifest = {
        "version": 1,
        "mode": "offline_snapshot",
        "source": "AMFI verified snapshot",
        "generated_at": "2026-10-28T00:00:00Z",
        "tables": ["predictions"],
        "artifacts": []
    }
    (tmp_path / "manifest.json").write_text(json.dumps(manifest))
    (tmp_path / "outputs").mkdir()
    # predictions.csv is absent

    res = load_predictions(data_root=tmp_path)
    assert res.status == "missing"
    assert res.frame.empty
    assert "missing" in res.message.lower() or "withheld" in res.message.lower()
    assert res.metadata.mode == "offline_snapshot"
    assert res.metadata.source == "AMFI verified snapshot"


def test_missing_artifact_json_returns_missing_status(tmp_path):
    manifest = {
        "version": 1,
        "mode": "offline_snapshot",
        "source": "AMFI verified snapshot",
        "generated_at": "2026-10-28T00:00:00Z",
        "tables": [],
        "artifacts": ["model_results"]
    }
    (tmp_path / "manifest.json").write_text(json.dumps(manifest))
    (tmp_path / "outputs").mkdir()
    # model_results.json is absent

    res = load_model_results(data_root=tmp_path)
    assert res.status == "missing"
    assert res.payload is None
    assert "missing" in res.message.lower() or "unavailable" in res.message.lower()


def test_undeclared_table_returns_missing_status(tmp_path):
    manifest = {
        "version": 1,
        "mode": "offline_snapshot",
        "source": "snapshot",
        "generated_at": "2026-10-28T00:00:00Z",
        "tables": ["flows_category_month"],
        "artifacts": []
    }
    (tmp_path / "manifest.json").write_text(json.dumps(manifest))
    (tmp_path / "outputs").mkdir()
    (tmp_path / "outputs/predictions.csv").write_text(",".join(COLUMNS["predictions"]) + "\n")

    res = load_predictions(data_root=tmp_path)
    assert res.status == "missing"
    assert "not declared" in res.message or "withheld" in res.message


def test_undeclared_artifact_returns_missing_status(tmp_path):
    manifest = {
        "version": 1,
        "mode": "offline_snapshot",
        "source": "snapshot",
        "generated_at": "2026-10-28T00:00:00Z",
        "tables": [],
        "artifacts": []
    }
    (tmp_path / "manifest.json").write_text(json.dumps(manifest))

    res = load_model_results(data_root=tmp_path)
    assert res.status == "missing"
    assert "not declared" in res.message


def test_missing_manifest_returns_missing_status(tmp_path):
    # Completely empty directory with no manifest
    res = load_flows(data_root=tmp_path)
    assert res.status == "missing"
    assert res.frame.empty


# ---------------------------------------------------------------------------
# 3. Empty File Handling
# ---------------------------------------------------------------------------

def test_zero_byte_csv_returns_empty_status(tmp_path):
    manifest = {
        "version": 1,
        "mode": "offline_snapshot",
        "source": "test",
        "generated_at": "2026-10-28T00:00:00Z",
        "tables": ["shortlist"],
        "artifacts": []
    }
    (tmp_path / "manifest.json").write_text(json.dumps(manifest))
    (tmp_path / "outputs").mkdir()
    (tmp_path / "outputs/shortlist.csv").write_text("")  # 0 bytes

    res = load_shortlist(data_root=tmp_path)
    assert res.status == "empty"
    assert res.frame.empty
    assert list(res.frame.columns) == list(COLUMNS["shortlist"])
    assert "empty" in res.message.lower()


def test_header_only_csv_returns_empty_status(tmp_path):
    manifest = {
        "version": 1,
        "mode": "offline_snapshot",
        "source": "test",
        "generated_at": "2026-10-28T00:00:00Z",
        "tables": ["shortlist"],
        "artifacts": []
    }
    (tmp_path / "manifest.json").write_text(json.dumps(manifest))
    (tmp_path / "outputs").mkdir()
    (tmp_path / "outputs/shortlist.csv").write_text(",".join(COLUMNS["shortlist"]) + "\n")

    res = load_shortlist(data_root=tmp_path)
    assert res.status == "empty"
    assert res.frame.empty
    assert list(res.frame.columns) == list(COLUMNS["shortlist"])
    assert res.metadata.last_period is None


# ---------------------------------------------------------------------------
# 4. Malformed CSV & JSON Tests
# ---------------------------------------------------------------------------

def test_csv_with_missing_columns_is_invalid(tmp_path):
    manifest = {
        "version": 1,
        "mode": "offline_snapshot",
        "source": "test",
        "generated_at": "2026-10-28T00:00:00Z",
        "tables": ["predictions"],
        "artifacts": []
    }
    (tmp_path / "manifest.json").write_text(json.dumps(manifest))
    (tmp_path / "outputs").mkdir()
    # Missing columns
    (tmp_path / "outputs/predictions.csv").write_text("as_of,target_month\n2026-10-28T00:00:00Z,2026-11\n")

    res = load_predictions(data_root=tmp_path)
    assert res.status == "invalid"
    assert res.frame.empty
    assert "invalid" in res.message.lower() or "withheld" in res.message.lower()


def test_csv_with_extra_columns_is_invalid(tmp_path):
    manifest = {
        "version": 1,
        "mode": "offline_snapshot",
        "source": "test",
        "generated_at": "2026-10-28T00:00:00Z",
        "tables": ["predictions"],
        "artifacts": []
    }
    (tmp_path / "manifest.json").write_text(json.dumps(manifest))
    (tmp_path / "outputs").mkdir()
    cols = list(COLUMNS["predictions"]) + ["extra_column"]
    (tmp_path / "outputs/predictions.csv").write_text(",".join(cols) + "\n")

    res = load_predictions(data_root=tmp_path)
    assert res.status == "invalid"
    assert res.frame.empty


def test_csv_with_invalid_numeric_values_is_invalid(tmp_path):
    manifest = {
        "version": 1,
        "mode": "offline_snapshot",
        "source": "test",
        "generated_at": "2026-10-28T00:00:00Z",
        "tables": ["flows_category_month"],
        "artifacts": []
    }
    (tmp_path / "manifest.json").write_text(json.dumps(manifest))
    (tmp_path / "processed").mkdir()
    cols = list(COLUMNS["flows_category_month"])
    # "not_a_number" in gross_inflow_cr
    row = ["2026-10", "Large Cap", "not_a_number", "100.0", "50.0", "1000.0", "950.0", "2026-11-10T12:00:00Z", "https://amfi.com", "2026-10-28T00:00:00Z"]
    (tmp_path / "processed/flows_category_month.csv").write_text(",".join(cols) + "\n" + ",".join(row) + "\n")

    res = load_flows(data_root=tmp_path)
    assert res.status == "invalid"
    assert res.frame.empty


def test_corrupt_json_artifact_is_invalid(tmp_path):
    manifest = {
        "version": 1,
        "mode": "offline_snapshot",
        "source": "test",
        "generated_at": "2026-10-28T00:00:00Z",
        "tables": [],
        "artifacts": ["model_results"]
    }
    (tmp_path / "manifest.json").write_text(json.dumps(manifest))
    (tmp_path / "outputs").mkdir()
    (tmp_path / "outputs/model_results.json").write_text("{ incomplete json ...")

    res = load_model_results(data_root=tmp_path)
    assert res.status == "invalid"
    assert res.payload is None


def test_json_artifact_with_nan_is_invalid(tmp_path):
    manifest = {
        "version": 1,
        "mode": "offline_snapshot",
        "source": "test",
        "generated_at": "2026-10-28T00:00:00Z",
        "tables": [],
        "artifacts": ["model_results"]
    }
    (tmp_path / "manifest.json").write_text(json.dumps(manifest))
    (tmp_path / "outputs").mkdir()
    # NaN is non-finite and forbidden
    doc_str = '{"version": 1, "source": "test", "generated_at": "2026-10-28T00:00:00Z", "payload": {"metrics": {"rmse": NaN}, "limitations": []}}'
    (tmp_path / "outputs/model_results.json").write_text(doc_str)

    res = load_model_results(data_root=tmp_path)
    assert res.status == "invalid"
    assert res.payload is None


def test_json_artifact_with_missing_payload_contract_is_invalid(tmp_path):
    manifest = {
        "version": 1,
        "mode": "offline_snapshot",
        "source": "test",
        "generated_at": "2026-10-28T00:00:00Z",
        "tables": [],
        "artifacts": ["model_results"]
    }
    (tmp_path / "manifest.json").write_text(json.dumps(manifest))
    (tmp_path / "outputs").mkdir()
    # Missing limitations
    doc = {
        "version": 1,
        "source": "test",
        "generated_at": "2026-10-28T00:00:00Z",
        "payload": {"metrics": {"rmse": 0.5}}
    }
    (tmp_path / "outputs/model_results.json").write_text(json.dumps(doc))

    res = load_model_results(data_root=tmp_path)
    assert res.status == "invalid"


def test_quality_metadata_contract_validation(tmp_path):
    manifest = {
        "version": 1,
        "mode": "offline_snapshot",
        "source": "test",
        "generated_at": "2026-10-28T00:00:00Z",
        "tables": [],
        "artifacts": ["quality_report"]
    }
    (tmp_path / "manifest.json").write_text(json.dumps(manifest))

    # Invalid status: "approved" is not in {pass, fail, unknown}
    bad_doc = {
        "version": 1,
        "source": "test",
        "generated_at": "2026-10-28T00:00:00Z",
        "payload": {"status": "approved", "checks": []}
    }
    (tmp_path / "quality_report.json").write_text(json.dumps(bad_doc))
    res_bad = load_quality_metadata(data_root=tmp_path)
    assert res_bad.status == "invalid"

    # Valid status: "pass"
    good_doc = {
        "version": 1,
        "source": "test",
        "generated_at": "2026-10-28T00:00:00Z",
        "payload": {"status": "pass", "checks": [{"name": "leakage", "ok": True}]}
    }
    (tmp_path / "quality_report.json").write_text(json.dumps(good_doc))
    res_good = load_quality_metadata(data_root=tmp_path)
    assert res_good.status == "ok"
    assert res_good.payload["status"] == "pass"


def test_source_metadata_contract_validation(tmp_path):
    manifest = {
        "version": 1,
        "mode": "offline_snapshot",
        "source": "test",
        "generated_at": "2026-10-28T00:00:00Z",
        "tables": [],
        "artifacts": ["source_metadata"]
    }
    (tmp_path / "manifest.json").write_text(json.dumps(manifest))

    # Valid
    doc = {
        "version": 1,
        "source": "test",
        "generated_at": "2026-10-28T00:00:00Z",
        "payload": {"sources": [{"id": "amfi_flows", "status": "restricted"}]}
    }
    (tmp_path / "source_metadata.json").write_text(json.dumps(doc))
    res = load_source_metadata(data_root=tmp_path)
    assert res.status == "ok"
    assert len(res.payload["sources"]) == 1


# ---------------------------------------------------------------------------
# 5. Stale Data & Freshness Tests
# ---------------------------------------------------------------------------

def test_fresh_data_below_threshold(tmp_path):
    clock = datetime(2026, 10, 28, 12, 0, 0, tzinfo=timezone.utc)
    gen_time = (clock - timedelta(days=20)).isoformat().replace("+00:00", "Z")
    manifest = {
        "version": 1,
        "mode": "offline_snapshot",
        "source": "AMFI official",
        "generated_at": gen_time,
        "tables": ["predictions"],
        "artifacts": []
    }
    (tmp_path / "manifest.json").write_text(json.dumps(manifest))
    (tmp_path / "outputs").mkdir()
    cols = list(COLUMNS["predictions"])
    row = ["2026-10-08T00:00:00Z", "2026-10", "Large Cap", "ridge_v1", "2.1", "2.0", "", "true", "2019-04-01T00:00:00Z", "2026-09-01T00:00:00Z", "{}"]
    (tmp_path / "outputs/predictions.csv").write_text(",".join(cols) + "\n" + ",".join(row) + "\n")

    res = load_predictions(data_root=tmp_path, now=clock, stale_days=45)
    assert res.status == "ok"
    assert res.metadata.freshness == "fresh"


def test_stale_data_above_threshold(tmp_path):
    clock = datetime(2026, 10, 28, 12, 0, 0, tzinfo=timezone.utc)
    # 50 days old > 45 days threshold
    gen_time = (clock - timedelta(days=50)).isoformat().replace("+00:00", "Z")
    manifest = {
        "version": 1,
        "mode": "offline_snapshot",
        "source": "AMFI official",
        "generated_at": gen_time,
        "tables": ["predictions"],
        "artifacts": []
    }
    (tmp_path / "manifest.json").write_text(json.dumps(manifest))
    (tmp_path / "outputs").mkdir()
    cols = list(COLUMNS["predictions"])
    row = ["2026-09-08T00:00:00Z", "2026-09", "Large Cap", "ridge_v1", "2.1", "2.0", "", "true", "2019-04-01T00:00:00Z", "2026-08-01T00:00:00Z", "{}"]
    (tmp_path / "outputs/predictions.csv").write_text(",".join(cols) + "\n" + ",".join(row) + "\n")

    res = load_predictions(data_root=tmp_path, now=clock, stale_days=45)
    assert res.status == "stale"
    assert res.metadata.freshness == "stale"
    assert "older than the display freshness threshold" in res.message


def test_configurable_stale_threshold(tmp_path):
    clock = datetime(2026, 10, 28, 12, 0, 0, tzinfo=timezone.utc)
    # 10 days old: fresh if threshold=15, stale if threshold=5
    gen_time = (clock - timedelta(days=10)).isoformat().replace("+00:00", "Z")
    manifest = {
        "version": 1,
        "mode": "offline_snapshot",
        "source": "AMFI official",
        "generated_at": gen_time,
        "tables": ["predictions"],
        "artifacts": []
    }
    (tmp_path / "manifest.json").write_text(json.dumps(manifest))
    (tmp_path / "outputs").mkdir()
    cols = list(COLUMNS["predictions"])
    row = ["2026-10-18T00:00:00Z", "2026-10", "Large Cap", "ridge_v1", "2.1", "2.0", "", "true", "2019-04-01T00:00:00Z", "2026-09-01T00:00:00Z", "{}"]
    (tmp_path / "outputs/predictions.csv").write_text(",".join(cols) + "\n" + ",".join(row) + "\n")

    res_fresh = load_predictions(data_root=tmp_path, now=clock, stale_days=15)
    assert res_fresh.status == "ok"
    assert res_fresh.metadata.freshness == "fresh"

    res_stale = load_predictions(data_root=tmp_path, now=clock, stale_days=5)
    assert res_stale.status == "stale"
    assert res_stale.metadata.freshness == "stale"


# ---------------------------------------------------------------------------
# 6. Valid Snapshot & Typing Tests
# ---------------------------------------------------------------------------

def test_valid_snapshot_loads_all_columns_and_types(tmp_path):
    manifest = {
        "version": 1,
        "mode": "live",
        "source": "local materialization",
        "generated_at": "2026-10-28T00:00:00Z",
        "tables": ["flows_category_month", "predictions", "alerts"],
        "artifacts": ["model_results"]
    }
    (tmp_path / "manifest.json").write_text(json.dumps(manifest))
    (tmp_path / "processed").mkdir()
    (tmp_path / "outputs").mkdir()

    # 1. flows
    flow_row = ["2026-09", "Large Cap", "5000.5", "3000.2", "2000.3", "100000.0", "98000.0", "2026-10-10T08:57:53Z", "https://amfi.com", "2026-10-28T00:00:00Z"]
    (tmp_path / "processed/flows_category_month.csv").write_text(",".join(COLUMNS["flows_category_month"]) + "\n" + ",".join(flow_row) + "\n")

    # 2. predictions
    pred_row = ["2026-10-28T00:00:00Z", "2026-10", "Large Cap", "ridge_v1", "3.15", "3.10", "", "true", "2019-04-01T00:00:00Z", "2026-09-01T00:00:00Z", '{"rate_lag0": 0.5}']
    (tmp_path / "outputs/predictions.csv").write_text(",".join(COLUMNS["predictions"]) + "\n" + ",".join(pred_row) + "\n")

    # 3. alerts
    alert_row = ["2026-10-28T00:00:00Z", "2026-10", "Large Cap", "Normal", "None", "3.15", "50.0", "0.2", "1.0", "3150.0", "100000.0", "2026-09", "neutral", "", "18", "Demo"]
    (tmp_path / "outputs/alerts.csv").write_text(",".join(COLUMNS["alerts"]) + "\n" + ",".join(alert_row) + "\n")

    # Verify flows
    res_f = load_flows(data_root=tmp_path)
    assert res_f.status == "ok"
    assert res_f.metadata.mode == "live"
    assert res_f.metadata.last_period == "2026-09"
    assert isinstance(res_f.frame["gross_inflow_cr"].iloc[0], float)
    assert res_f.frame["gross_inflow_cr"].iloc[0] == 5000.5

    # Verify predictions
    res_p = load_predictions(data_root=tmp_path)
    assert res_p.status == "ok"
    assert res_p.metadata.last_period == "2026-10"
    assert res_p.frame["is_out_of_sample"].iloc[0] is True or res_p.frame["is_out_of_sample"].iloc[0] == True
    assert isinstance(res_p.frame["predicted_rate"].iloc[0], float)
    assert isinstance(res_p.frame["model_id"].iloc[0], str)

    # Verify alerts
    res_a = load_alerts(data_root=tmp_path)
    assert res_a.status == "ok"
    assert res_a.frame["level"].iloc[0] == "Normal"
    assert isinstance(res_a.frame["reference_aum_cr"].iloc[0], float)


def test_typed_helper_loaders(tmp_path):
    """Verify all convenience helpers (shortlist, sentiment, market, nav, etc.) operate correctly."""
    manifest = {
        "version": 1,
        "mode": "offline_snapshot",
        "source": "test",
        "generated_at": "2026-10-28T00:00:00Z",
        "tables": ["shortlist", "sentiment_agg", "sentiment_items", "market_month", "nav_daily", "scheme_master", "feature_matrix"],
        "artifacts": []
    }
    (tmp_path / "manifest.json").write_text(json.dumps(manifest))
    (tmp_path / "processed").mkdir()
    (tmp_path / "outputs").mkdir()

    # Empty tables check
    for t in ["market_month", "nav_daily", "scheme_master", "feature_matrix"]:
        (tmp_path / f"processed/{t}.csv").write_text(",".join(COLUMNS[t]) + "\n")
    for t in ["shortlist", "sentiment_agg", "sentiment_items"]:
        (tmp_path / f"outputs/{t}.csv").write_text(",".join(COLUMNS[t]) + "\n")

    assert load_shortlist(data_root=tmp_path).status == "empty"
    assert load_sentiment(data_root=tmp_path).status == "empty"
    assert load_sentiment_items(data_root=tmp_path).status == "empty"
    assert load_market(data_root=tmp_path).status == "empty"
    assert load_nav_daily(data_root=tmp_path).status == "empty"
    assert load_scheme_master(data_root=tmp_path).status == "empty"
    assert load_feature_matrix(data_root=tmp_path).status == "empty"


# ---------------------------------------------------------------------------
# 7. Safe File Path & Boundary Protection
# ---------------------------------------------------------------------------

def test_traversal_paths_are_strictly_rejected(tmp_path):
    with pytest.raises(ValueError, match="cannot traverse parents"):
        from app.loaders import _safe_path
        _safe_path(tmp_path, "../outside.csv")

    with pytest.raises(ValueError, match="cannot traverse parents"):
        from app.loaders import _safe_path
        _safe_path(tmp_path, "subdir/../../escape.csv")


def test_absolute_paths_are_strictly_rejected(tmp_path):
    with pytest.raises(ValueError, match="must be relative"):
        from app.loaders import _safe_path
        _safe_path(tmp_path, "/etc/passwd")


def test_unknown_bundle_is_rejected(tmp_path):
    from app.loaders import _bundle
    with pytest.raises(ValueError, match="Unknown bundle"):
        _bundle(tmp_path, "unauthorized_bundle")

    res = load_predictions(data_root=tmp_path, bundle="unauthorized_bundle")
    assert res.status == "invalid"
    assert "invalid" in res.message.lower() or "withheld" in res.message.lower()


def test_explicit_bundle_selection_never_falls_back(tmp_path):
    # If bundle="snapshots" is requested but snapshots/ is missing, do not fall back to fixtures
    res = load_predictions(data_root=tmp_path, bundle="snapshots")
    assert res.status == "missing"
    assert res.frame.empty


def test_malformed_manifest_in_candidate_bundle_is_not_replaced_by_fixtures(tmp_path):
    # Candidate bundle has invalid manifest -> report invalid, do NOT fall back to fixtures
    (tmp_path / "manifest.json").write_text("{ malformed json ...")
    res = load_predictions(data_root=tmp_path)
    assert res.status == "invalid"
    assert res.metadata.mode == "unknown"


def test_fallback_to_fixtures_declares_synthetic_mode(tmp_path):
    """Verify fallback to legacy fixtures reports mode='synthetic' and source='synthetic fixture'."""
    fixtures_dir = tmp_path / "snapshots/fixtures"
    fixtures_dir.mkdir(parents=True)
    for f in (DATA_ROOT / "snapshots/fixtures").iterdir():
        if f.is_file():
            (fixtures_dir / f.name).write_bytes(f.read_bytes())
    res = load_flows(data_root=tmp_path)
    assert res.status == "ok"
    assert res.metadata.mode == "synthetic"
    assert "synthetic" in res.metadata.source.lower()
    assert not res.frame.empty


# ---------------------------------------------------------------------------
# 8. Business Calculations Outside Boundary
# ---------------------------------------------------------------------------

def test_loaders_perform_no_business_calculations(tmp_path):
    """Loaders must never calculate redemption rates, baselines, z-scores or rankings."""
    manifest = {
        "version": 1,
        "mode": "offline_snapshot",
        "source": "test",
        "generated_at": "2026-10-28T00:00:00Z",
        "tables": ["predictions"],
        "artifacts": []
    }
    (tmp_path / "manifest.json").write_text(json.dumps(manifest))
    (tmp_path / "outputs").mkdir()
    cols = list(COLUMNS["predictions"])
    # Supply exact rates in row; loader must return them unmutated
    row = ["2026-10-28T00:00:00Z", "2026-10", "Large Cap", "ridge_v1", "2.75", "2.50", "", "true", "2019-04-01T00:00:00Z", "2026-09-01T00:00:00Z", "{}"]
    (tmp_path / "outputs/predictions.csv").write_text(",".join(cols) + "\n" + ",".join(row) + "\n")

    res = load_predictions(data_root=tmp_path)
    assert res.status == "ok"
    assert res.frame["predicted_rate"].iloc[0] == 2.75
    assert res.frame["baseline_rate"].iloc[0] == 2.50
    # No error or delta columns injected
    assert set(res.frame.columns) == set(COLUMNS["predictions"])
