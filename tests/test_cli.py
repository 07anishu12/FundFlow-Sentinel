"""Unit and integration tests for FundFlow CLI orchestrator."""
from __future__ import annotations

import json
from pathlib import Path
import pytest
import pandas as pd

from fundflow.contracts import COLUMNS, validate_table
from fundflow.cli import (
    main,
    atomic_write_csv,
    run_stage_build_data,
    run_stage_train,
    run_stage_alerts,
    run_stage_sentiment,
    run_stage_rank,
    run_all,
)
from fundflow.reporting import RunReporter

ROOT = Path(__file__).resolve().parents[1]
FIXTURES_DIR = ROOT / "data" / "snapshots" / "fixtures"


@pytest.fixture
def sample_dataset(tmp_path: Path) -> tuple[Path, Path]:
    """Create a self-consistent temporary data bundle with valid universe categories."""
    data_dir = tmp_path / "data"
    proc_dir = data_dir / "processed"
    out_dir = data_dir / "outputs"
    proc_dir.mkdir(parents=True)
    out_dir.mkdir(parents=True)

    # Copy real processed flows and market datasets
    real_flows = ROOT / "data" / "processed" / "flows_category_month.csv"
    real_market = ROOT / "data" / "processed" / "market_month.csv"
    (proc_dir / "flows_category_month.csv").write_text(real_flows.read_text())
    (proc_dir / "market_month.csv").write_text(real_market.read_text())

    # Copy scheme_master and nav_daily from fixtures for ranking
    (proc_dir / "scheme_master.csv").write_text((FIXTURES_DIR / "scheme_master.csv").read_text())
    (proc_dir / "nav_daily.csv").write_text((FIXTURES_DIR / "nav_daily.csv").read_text())

    # Pre-seed feature_matrix fixture for train step
    (proc_dir / "feature_matrix.csv").write_text((FIXTURES_DIR / "feature_matrix.csv").read_text())

    return data_dir, out_dir


def test_cli_no_args_exits_code_2(capsys):
    ret = main([])
    assert ret == 2
    captured = capsys.readouterr()
    assert "usage: fundflow" in captured.err.lower() or "usage: fundflow" in captured.out.lower()


def test_cli_help_exits_code_0(capsys):
    with pytest.raises(SystemExit) as exc:
        main(["--help"])
    assert exc.value.code == 0


def test_atomic_write_csv_success(tmp_path: Path):
    target = tmp_path / "valid.csv"
    df = pd.DataFrame({
        "month": ["2024-09"],
        "category": ["Large Cap"],
        "gross_inflow_cr": [100.0],
        "gross_redemption_cr": [50.0],
        "net_flow_cr": [50.0],
        "aum_close_cr": [1000.0],
        "aaum_cr": [950.0],
        "available_from": ["2024-10-10T00:00:00Z"],
        "source_url": ["https://portal.amfiindia.com"],
        "retrieved_at": ["2024-10-10T00:00:00Z"],
    })
    res_path = atomic_write_csv(df, target, contract_name="flows_category_month")
    assert res_path == target
    assert target.is_file()
    assert not (tmp_path / "valid.csv.tmp").exists()


def test_atomic_write_csv_invalid_contract_preserves_target(tmp_path: Path):
    target = tmp_path / "protected.csv"
    target.write_text("initial,content\n1,2\n")

    # Invalid DataFrame missing contract columns
    bad_df = pd.DataFrame({"bad_col": [1, 2]})

    with pytest.raises(ValueError):
        atomic_write_csv(bad_df, target, contract_name="flows_category_month")

    # Verify original file untouched and no leftover .tmp
    assert target.read_text() == "initial,content\n1,2\n"
    assert not (tmp_path / "protected.csv.tmp").exists()


def test_cli_stage_build_data(sample_dataset):
    data_dir, out_dir = sample_dataset
    reporter = RunReporter(base_dir=ROOT)
    ok = run_stage_build_data(
        data_dir=data_dir,
        output_dir=out_dir,
        reporter=reporter,
    )
    assert ok is True
    assert "build-data" in reporter.stages
    assert reporter.stages["build-data"]["status"] == "success"
    assert (data_dir / "processed" / "feature_matrix.csv").is_file()


def test_cli_stage_train_with_fixtures(tmp_path: Path):
    out_dir = tmp_path / "outputs"
    reporter = RunReporter(base_dir=ROOT)

    ok = run_stage_train(
        data_dir=FIXTURES_DIR,
        output_dir=out_dir,
        reporter=reporter,
        min_train_months=6,
    )
    assert ok is True
    assert (out_dir / "predictions.csv").is_file()
    assert (out_dir / "model_results.json").is_file()


def test_cli_stage_alerts_with_fixtures(tmp_path: Path):
    out_dir = tmp_path / "outputs"
    out_dir.mkdir(parents=True)

    # Copy predictions fixture to out_dir
    preds_fixture = FIXTURES_DIR / "predictions.csv"
    (out_dir / "predictions.csv").write_text(preds_fixture.read_text())

    reporter = RunReporter(base_dir=ROOT)
    ok = run_stage_alerts(
        data_dir=FIXTURES_DIR,
        output_dir=out_dir,
        reporter=reporter,
    )
    assert ok is True
    assert (out_dir / "alerts.csv").is_file()


def test_cli_stage_sentiment_offline(tmp_path: Path):
    out_dir = tmp_path / "outputs"
    reporter = RunReporter(base_dir=ROOT)

    ok = run_stage_sentiment(
        data_dir=FIXTURES_DIR,
        output_dir=out_dir,
        reporter=reporter,
        offline=True,
    )
    assert ok is True
    assert (out_dir / "sentiment_agg.csv").is_file()


def test_cli_stage_rank_with_fixtures(tmp_path: Path):
    out_dir = tmp_path / "outputs"
    reporter = RunReporter(base_dir=ROOT)

    ok = run_stage_rank(
        data_dir=FIXTURES_DIR,
        output_dir=out_dir,
        reporter=reporter,
    )
    assert ok is True
    assert (out_dir / "shortlist.csv").is_file()


def test_cli_run_all_end_to_end(sample_dataset):
    data_dir, out_dir = sample_dataset
    rep_file = out_dir / "custom_run_report.json"

    ret = main([
        "--data-dir", str(data_dir),
        "--output-dir", str(out_dir),
        "--report-file", str(rep_file),
        "--offline",
        "--min-train-months", "6",
        "all",
    ])
    assert ret == 0
    assert rep_file.is_file()

    report = json.loads(rep_file.read_text())
    assert report["version"] == 1
    assert report["status"] in ("success", "partial_success")
    assert report["summary"]["successful_stages"] >= 4
    assert report["summary"]["failed_stages"] == 0

    # Verify input hashes and output hashes exist in the report
    assert len(report["inputs"]) > 0
    for inp_meta in report["inputs"].values():
        assert "sha256" in inp_meta
        assert len(inp_meta["sha256"]) == 64

    assert len(report["outputs"]) > 0
    for out_meta in report["outputs"].values():
        assert "sha256" in out_meta
        assert len(out_meta["sha256"]) == 64


def test_cli_failure_on_corrupt_input_preserves_last_good(tmp_path: Path):
    out_dir = tmp_path / "outputs"
    out_dir.mkdir(parents=True)
    rep_file = out_dir / "run_report.json"

    # Seed an existing last-good predictions.csv
    preds_file = out_dir / "predictions.csv"
    preds_file.write_text("as_of,target_month\n2024-09,2024-10\n")

    # Create empty/corrupt data_dir
    bad_data_dir = tmp_path / "bad_data"
    bad_data_dir.mkdir()

    ret = main([
        "--data-dir", str(bad_data_dir),
        "--output-dir", str(out_dir),
        "--report-file", str(rep_file),
        "train",
    ])
    # Expect failure exit code 1
    assert ret == 1
    # Check that previous file was preserved and not corrupted
    assert preds_file.read_text() == "as_of,target_month\n2024-09,2024-10\n"

    # Check report was written with failure status
    assert rep_file.is_file()
    rep = json.loads(rep_file.read_text())
    assert rep["status"] == "failure"
    assert rep["summary"]["failed_stages"] == 1
