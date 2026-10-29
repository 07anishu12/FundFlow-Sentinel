"""Unit tests for FundFlow run reporting and file hashing."""
from __future__ import annotations

import json
from pathlib import Path
import pytest

from fundflow.reporting import (
    compute_file_sha256,
    count_csv_rows,
    get_file_metadata,
    atomic_write_json,
    RunReporter,
)


def test_compute_file_sha256_missing(tmp_path: Path):
    missing_file = tmp_path / "does_not_exist.txt"
    assert compute_file_sha256(missing_file) == ""


def test_compute_file_sha256_content(tmp_path: Path):
    test_file = tmp_path / "sample.txt"
    test_file.write_text("Hello, FundFlow!")
    h = compute_file_sha256(test_file)
    assert len(h) == 64
    assert all(c in "0123456789abcdef" for c in h)


def test_count_csv_rows(tmp_path: Path):
    csv_file = tmp_path / "test.csv"
    csv_file.write_text("col1,col2\n1,a\n2,b\n3,c\n\n")
    assert count_csv_rows(csv_file) == 3


def test_get_file_metadata_csv(tmp_path: Path):
    csv_file = tmp_path / "test.csv"
    csv_file.write_text("h1,h2\nx,y\n")
    meta = get_file_metadata(csv_file)
    assert meta["exists"] is True
    assert meta["rows"] == 1
    assert meta["size_bytes"] > 0
    assert len(meta["sha256"]) == 64


def test_atomic_write_json(tmp_path: Path):
    out = tmp_path / "doc.json"
    data = {"status": "ok", "value": 42}
    atomic_write_json(data, out)
    assert out.is_file()
    assert json.loads(out.read_text()) == data


def test_run_reporter_lifecycle(tmp_path: Path):
    in_file = tmp_path / "in.csv"
    in_file.write_text("a,b\n1,2\n")
    out_file = tmp_path / "out.csv"
    out_file.write_text("x,y\n8,9\n")

    reporter = RunReporter(cli_args={"subcommand": "train"})
    reporter.register_input("train_in", in_file)

    reporter.start_stage("train", {"train_in": in_file})
    reporter.record_metrics({"rmse": 0.05})
    reporter.add_limitation("Sample limitation")
    reporter.end_stage("train", status="success", output_paths={"train_out": out_file})

    report_path = tmp_path / "run_report.json"
    reporter.save(report_path)

    assert report_path.is_file()
    data = json.loads(report_path.read_text())

    assert data["version"] == 1
    assert data["status"] == "success"
    assert data["summary"]["successful_stages"] == 1
    assert data["summary"]["failed_stages"] == 0
    assert "train" in data["stages"]
    assert data["stages"]["train"]["status"] == "success"
    assert data["stages"]["train"]["inputs"]["train_in"]["exists"] is True
    assert data["stages"]["train"]["outputs"]["train_out"]["exists"] is True
    assert data["metrics"]["rmse"] == 0.05
    assert "Sample limitation" in data["limitations"]
