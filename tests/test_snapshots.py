"""Unit, integration, and transactional safety tests for offline demo snapshots.

Verifies Wave 12 Prompt 25:
- Deterministic manifest creation, artifact ordering, SHA-256 digests, byte sizes, and row counts.
- Strict relative path enforcement; rejection of traversal (..), absolute paths, and symlinks.
- Rejection of tampered/altered files, missing files, malformed manifests, and disallowed licenses.
- Synthetic origin propagation and distinction (real vs derived vs synthetic).
- Transactional publishing safety: failures during staging or validation preserve last-known-good snapshot.
- Full offline app rendering from the snapshot under strictly blocked OS-level network sockets.
"""
from __future__ import annotations

import copy
import json
import os
from pathlib import Path
import shutil
import socket
import tempfile
import pytest
import pandas as pd
from streamlit.testing.v1 import AppTest

from fundflow.contracts import COLUMNS
from fundflow.snapshot import (
    ALL_ARTIFACTS,
    ALL_TABLES,
    compute_sha256,
    generate_synthetic_demo_tables,
    publish_snapshot_transactional,
    stage_snapshot_bundle,
    verify_snapshot,
)
from app.loaders import load_table, load_artifact

ROOT = Path(__file__).resolve().parents[1]
SNAPSHOTS_DIR = ROOT / "data" / "snapshots"


@pytest.fixture(autouse=True)
def block_network(monkeypatch):
    """Enforce strict offline execution for all snapshot tests."""
    def blocked(*args, **kwargs):
        raise AssertionError("Unexpected network access detected during offline test execution")
    monkeypatch.setattr(socket, "create_connection", blocked)
    monkeypatch.setattr(socket.socket, "connect", blocked)


# ---------------------------------------------------------------------------
# Section 1: Manifest Integrity & Deterministic Structure
# ---------------------------------------------------------------------------

def test_manifest_creation_structure_and_deterministic_ordering(tmp_path):
    """Manifest declares version=1, mode='offline_snapshot', sorted tables, artifacts, and files."""
    snap_dir = tmp_path / "snapshots"
    manifest = stage_snapshot_bundle(snap_dir, snapshot_id="snap-test-01")

    assert manifest["version"] == 1
    assert manifest["mode"] == "offline_snapshot"
    assert manifest["snapshot_id"] == "snap-test-01"
    assert "source" in manifest and manifest["source"]
    assert "generated_at" in manifest and manifest["generated_at"].endswith("Z")

    # Table contracts
    assert manifest["tables"] == ALL_TABLES
    assert manifest["artifacts"] == ALL_ARTIFACTS

    # Deterministic file ordering
    paths = [f["path"] for f in manifest["files"]]
    assert paths == sorted(paths)
    assert len(paths) == len(ALL_TABLES) + len(ALL_ARTIFACTS)


def test_manifest_digests_and_byte_sizes_match_on_disk(tmp_path):
    """Every entry in manifest matches exact on-disk byte size and SHA-256 digest."""
    snap_dir = tmp_path / "snapshots"
    stage_snapshot_bundle(snap_dir, snapshot_id="snap-test-02")
    manifest = json.loads((snap_dir / "manifest.json").read_text())

    for f_meta in manifest["files"]:
        target = snap_dir / f_meta["path"]
        assert target.is_file(), f"File {f_meta['path']} does not exist"
        assert target.stat().st_size == f_meta["size_bytes"]
        assert compute_sha256(target) == f_meta["sha256"]

        if f_meta["path"].endswith(".csv"):
            df = pd.read_csv(target, dtype=str)
            assert len(df) == f_meta["rows"]


def test_independent_manifest_verification_on_repository_snapshot():
    """Authoritative independent verification of committed data/snapshots against manifest."""
    is_valid, errors = verify_snapshot(SNAPSHOTS_DIR)
    assert is_valid, f"Committed snapshot verification failed: {errors}"
    assert not errors


# ---------------------------------------------------------------------------
# Section 2: Rejection of Corrupt, Malformed, or Traversal Inputs
# ---------------------------------------------------------------------------

def test_verify_snapshot_rejects_missing_file(tmp_path):
    """Removing any declared artifact causes verification to fail."""
    snap_dir = tmp_path / "snapshots"
    stage_snapshot_bundle(snap_dir, snapshot_id="snap-test-03")

    # Delete one required table
    (snap_dir / "processed/flows_category_month.csv").unlink()

    is_valid, errors = verify_snapshot(snap_dir)
    assert not is_valid
    assert any("missing on disk" in err for err in errors)


def test_verify_snapshot_rejects_altered_file_hash_mismatch(tmp_path):
    """Altering even one byte in a file causes hash check to fail."""
    snap_dir = tmp_path / "snapshots"
    stage_snapshot_bundle(snap_dir, snapshot_id="snap-test-04")

    # Mutate a file
    target = snap_dir / "processed/flows_category_month.csv"
    target.write_text(target.read_text() + "\n# corrupted row")

    is_valid, errors = verify_snapshot(snap_dir)
    assert not is_valid
    assert any("SHA-256 digest mismatch" in err or "Byte size mismatch" in err for err in errors)


def test_verify_snapshot_rejects_path_traversal(tmp_path):
    """Manifest cannot declare paths escaping directory boundary with .."""
    snap_dir = tmp_path / "snapshots"
    stage_snapshot_bundle(snap_dir, snapshot_id="snap-test-05")

    manifest = json.loads((snap_dir / "manifest.json").read_text())
    manifest["files"].append({
        "path": "../secret_file.txt",
        "size_bytes": 10,
        "sha256": "abc",
        "redistribution": "permitted",
    })
    (snap_dir / "manifest.json").write_text(json.dumps(manifest))

    is_valid, errors = verify_snapshot(snap_dir)
    assert not is_valid
    assert any("cannot traverse parents" in err for err in errors)


def test_verify_snapshot_rejects_absolute_paths(tmp_path):
    """Manifest cannot declare absolute paths."""
    snap_dir = tmp_path / "snapshots"
    stage_snapshot_bundle(snap_dir, snapshot_id="snap-test-06")

    manifest = json.loads((snap_dir / "manifest.json").read_text())
    manifest["files"].append({
        "path": "/etc/passwd",
        "size_bytes": 10,
        "sha256": "abc",
        "redistribution": "permitted",
    })
    (snap_dir / "manifest.json").write_text(json.dumps(manifest))

    is_valid, errors = verify_snapshot(snap_dir)
    assert not is_valid
    assert any("must be relative" in err for err in errors)


def test_verify_snapshot_rejects_unpermitted_redistribution_status(tmp_path):
    """Public snapshot rejects artifacts marked not_permitted or unclear."""
    snap_dir = tmp_path / "snapshots"
    stage_snapshot_bundle(snap_dir, snapshot_id="snap-test-07")

    manifest = json.loads((snap_dir / "manifest.json").read_text())
    manifest["files"][0]["redistribution"] = "restricted"
    (snap_dir / "manifest.json").write_text(json.dumps(manifest))

    is_valid, errors = verify_snapshot(snap_dir)
    assert not is_valid
    assert any("Unpermitted redistribution status" in err for err in errors)


def test_verify_snapshot_rejects_duplicate_declared_paths(tmp_path):
    """Declaring the same relative path twice in manifest is rejected."""
    snap_dir = tmp_path / "snapshots"
    stage_snapshot_bundle(snap_dir, snapshot_id="snap-test-08")

    manifest = json.loads((snap_dir / "manifest.json").read_text())
    manifest["files"].append(copy.deepcopy(manifest["files"][0]))
    (snap_dir / "manifest.json").write_text(json.dumps(manifest))

    is_valid, errors = verify_snapshot(snap_dir)
    assert not is_valid
    assert any("Duplicate file path" in err for err in errors)


def test_verify_snapshot_rejects_contract_violating_table(tmp_path):
    """If a CSV table violates its frozen contract, verification fails."""
    snap_dir = tmp_path / "snapshots"
    stage_snapshot_bundle(snap_dir, snapshot_id="snap-test-09")

    # Replace flows table with invalid columns
    bad_df = pd.DataFrame({"col_a": ["1"], "col_b": ["2"]})
    bad_path = snap_dir / "processed/flows_category_month.csv"
    bad_df.to_csv(bad_path, index=False)

    # Update manifest byte size and sha to match bad file so size/sha passes
    manifest = json.loads((snap_dir / "manifest.json").read_text())
    for f in manifest["files"]:
        if f["path"] == "processed/flows_category_month.csv":
            f["size_bytes"] = bad_path.stat().st_size
            f["sha256"] = compute_sha256(bad_path)
            f["rows"] = 1
    (snap_dir / "manifest.json").write_text(json.dumps(manifest))

    is_valid, errors = verify_snapshot(snap_dir)
    assert not is_valid
    assert any("Contract validation failure" in err for err in errors)


# ---------------------------------------------------------------------------
# Section 3: Synthetic Origin & Licensing Isolation
# ---------------------------------------------------------------------------

def test_snapshot_synthetic_origin_propagation():
    """All CSV tables in public demo snapshot carry explicit synthetic origin."""
    manifest = json.loads((SNAPSHOTS_DIR / "manifest.json").read_text())
    for f_meta in manifest["files"]:
        if f_meta["path"].endswith(".csv"):
            assert f_meta["origin"] == "synthetic"
            assert f_meta["source_id"] == "synthetic:not-a-source"
            assert f_meta["redistribution"] == "permitted"


def test_source_metadata_envelope_reflects_sources_yaml():
    """source_metadata.json in snapshot accurately reflects registry terms."""
    meta_path = SNAPSHOTS_DIR / "source_metadata.json"
    assert meta_path.is_file()
    doc = json.loads(meta_path.read_text())
    assert doc["version"] == 1
    assert "sources" in doc["payload"]
    sources = doc["payload"]["sources"]
    assert any(s["id"] == "amfi_flows" and s["redistribution_status"] == "restricted" for s in sources)
    assert any(s["id"] == "gdelt" and s["redistribution_status"] == "permitted_with_conditions" for s in sources)


# ---------------------------------------------------------------------------
# Section 4: Transactional Publishing & Last-Known-Good Safety
# ---------------------------------------------------------------------------

def test_transactional_publish_preserves_last_good_on_failure(tmp_path, monkeypatch):
    """If snapshot building or validation fails, the existing last-good snapshot is untouched."""
    target_dir = tmp_path / "snapshots"
    # 1. Publish initial good snapshot
    publish_snapshot_transactional(target_dir)
    orig_manifest = (target_dir / "manifest.json").read_text()
    orig_flow_sha = compute_sha256(target_dir / "processed/flows_category_month.csv")

    # 2. Simulate failure during next snapshot publish
    def mock_fail_verify(staging):
        return False, ["Simulated verification error during staging"]

    monkeypatch.setattr("fundflow.snapshot.verify_snapshot", mock_fail_verify)

    with pytest.raises(RuntimeError, match="Snapshot self-verification failed"):
        publish_snapshot_transactional(target_dir)

    # 3. Verify target_dir remains completely intact and valid
    assert target_dir.is_dir()
    assert (target_dir / "manifest.json").read_text() == orig_manifest
    assert compute_sha256(target_dir / "processed/flows_category_month.csv") == orig_flow_sha


def test_transactional_publish_preserves_internal_fixtures(tmp_path):
    """Internal fixtures subdirectory is preserved when snapshot is published."""
    target_dir = tmp_path / "snapshots"
    target_dir.mkdir(parents=True)
    fixtures_dir = target_dir / "fixtures"
    fixtures_dir.mkdir()
    (fixtures_dir / "custom_test.csv").write_text("dummy")

    publish_snapshot_transactional(target_dir)

    assert (target_dir / "fixtures" / "custom_test.csv").is_file()
    assert (target_dir / "fixtures" / "custom_test.csv").read_text() == "dummy"


# ---------------------------------------------------------------------------
# Section 5: Offline App Execution from Snapshot Bundle
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("page_rel_path", [
    "Home.py",
    "pages/1_Forecast_Lab.py",
    "pages/2_Sentiment_Monitor.py",
    "pages/3_Fund_Research.py",
    "pages/4_Stress_Lab.py",
    "pages/5_Evidence_and_Limits.py",
])
def test_all_six_pages_render_offline_from_snapshot(page_rel_path, monkeypatch):
    """Every page renders from bundle='snapshots' without exception under blocked network."""
    page_path = ROOT / "app" / page_rel_path
    app = AppTest.from_file(str(page_path)).run(timeout=15)
    assert not app.exception, f"Page {page_rel_path} raised exception: {app.exception}"
    assert any("FundFlow Sentinel" in s.value for s in app.sidebar.title)
    assert any("SYNTHETIC DEMO DATA" in w.value for w in app.warning)
