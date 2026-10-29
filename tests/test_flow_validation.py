"""Unit tests for AMFI category monthly flow validation and quality reporting.

Verifies:
- Future-release / non-leakage invariant (available_from <= month-end hard-fails)
- Conservative available_from policy (12th of month T+1)
- Duplicate key (month, category) hard-failure
- Gap detection per category without silent interpolation
- Unmapped category entering modeling universe hard-failure
- Observed gross redemption requirement (never inferred/repaired from net flows)
- Quality report schema, coverage, exclusions, and check structure
- Snapshot preservation on failed refresh
"""
from __future__ import annotations

import json
from pathlib import Path
import pytest
import pandas as pd
import yaml

from fundflow.contracts import validate_table, COLUMNS
from fundflow.validate import (
    validate_flows,
    save_validated_flows,
    _get_month_end_date,
    _get_conservative_available_from,
    _generate_month_range,
)

ROOT = Path(__file__).resolve().parents[1]

VALID_SAMPLE_DATA = [
    {
        "month": "2024-09",
        "category": "Large Cap Fund",
        "gross_inflow_cr": 5865.86,
        "gross_redemption_cr": 4096.44,
        "net_flow_cr": 1769.42,
        "aum_close_cr": 379010.08,
        "aaum_cr": 374132.40,
        "available_from": "2024-10-10T00:00:00Z",
        "source_url": "https://portal.amfiindia.com/spages/amsep2024repo.xls",
        "retrieved_at": "2024-10-10T08:57:53Z",
    },
    {
        "month": "2024-09",
        "category": "Mid Cap Fund",
        "gross_inflow_cr": 7671.57,
        "gross_redemption_cr": 4541.14,
        "net_flow_cr": 3130.43,
        "aum_close_cr": 397009.72,
        "aaum_cr": 390000.00,
        "available_from": "2024-10-10T00:00:00Z",
        "source_url": "https://portal.amfiindia.com/spages/amsep2024repo.xls",
        "retrieved_at": "2024-10-10T08:57:53Z",
    },
    {
        "month": "2024-09",
        "category": "Overnight Fund",
        "gross_inflow_cr": 525369.60,
        "gross_redemption_cr": 544732.24,
        "net_flow_cr": -19362.64,
        "aum_close_cr": 67274.59,
        "aaum_cr": 101290.97,
        "available_from": "2024-10-10T00:00:00Z",
        "source_url": "https://portal.amfiindia.com/spages/amsep2024repo.xls",
        "retrieved_at": "2024-10-10T08:57:53Z",
    },
]


def test_month_end_date_helper():
    assert _get_month_end_date("2024-02") == pd.to_datetime("2024-02-29").date()
    assert _get_month_end_date("2024-09") == pd.to_datetime("2024-09-30").date()
    assert _get_month_end_date("2024-12") == pd.to_datetime("2024-12-31").date()


def test_conservative_available_from_policy():
    assert _get_conservative_available_from("2024-09") == "2024-10-12T00:00:00Z"
    assert _get_conservative_available_from("2024-12") == "2025-01-12T00:00:00Z"


def test_generate_month_range_helper():
    months = _generate_month_range("2023-11", "2024-02")
    assert months == ["2023-11", "2023-12", "2024-01", "2024-02"]


def test_validate_flows_happy_path():
    raw_df = pd.DataFrame(VALID_SAMPLE_DATA)
    val_df, report = validate_flows(raw_df)

    assert tuple(val_df.columns) == COLUMNS["flows_category_month"]
    validate_table("flows_category_month", val_df)

    # Category normalization applied
    assert "Large Cap" in val_df["category"].values
    assert "Mid Cap" in val_df["category"].values
    assert "Overnight" in val_df["category"].values

    # Report structure
    assert report["status"] == "pass"
    assert report["coverage"]["total_records"] == 3
    assert "Overnight" in report["exclusions"]
    assert len(report["checks"]) >= 5


def test_future_release_non_leakage_hard_fails():
    # Attempting to declare available_from on month-end date MUST fail
    leaky_data = [dict(VALID_SAMPLE_DATA[0])]
    leaky_data[0]["available_from"] = "2024-09-30T23:59:59Z"  # On period end!
    leaky_df = pd.DataFrame(leaky_data)

    with pytest.raises(ValueError, match="Fatal look-ahead bias"):
        validate_flows(leaky_df)

    # Attempting to declare available_from before month-end MUST fail
    leaky_data[0]["available_from"] = "2024-09-15T00:00:00Z"
    with pytest.raises(ValueError, match="Fatal look-ahead bias"):
        validate_flows(pd.DataFrame(leaky_data))


def test_missing_available_from_uses_conservative_policy():
    data_no_avail = [dict(VALID_SAMPLE_DATA[0])]
    data_no_avail[0]["available_from"] = ""
    df = pd.DataFrame(data_no_avail)

    val_df, report = validate_flows(df)
    # Applied conservative policy (12th of following month)
    assert val_df["available_from"].iloc[0] == "2024-10-12T00:00:00Z"


def test_duplicate_keys_hard_fails():
    dupe_data = VALID_SAMPLE_DATA + [dict(VALID_SAMPLE_DATA[0])]
    dupe_df = pd.DataFrame(dupe_data)

    with pytest.raises(ValueError, match="Duplicate final key"):
        validate_flows(dupe_df)


def test_unmapped_category_entering_modeling_universe_fails(tmp_path):
    bad_cat_data = [
        {
            "month": "2024-09",
            "category": "Unknown Mystery Equity Scheme",
            "gross_inflow_cr": 100.0,
            "gross_redemption_cr": 50.0,
            "net_flow_cr": 50.0,
            "aum_close_cr": 1000.0,
            "aaum_cr": 950.0,
            "available_from": "2024-10-10T00:00:00Z",
            "source_url": "https://example.com/rep.xls",
            "retrieved_at": "2024-10-10T00:00:00Z",
        }
    ]
    # If explicitly mapped to modeling universe but with unmapped label
    cfg_p = tmp_path / "categories.yaml"
    cfg_p.write_text(yaml.dump({"universe": ["Large Cap", "Mid Cap"], "excluded": ["Liquid", "Overnight"]}))

    with pytest.raises(ValueError, match="Unmapped category label entered modeling universe"):
        validate_flows(pd.DataFrame(bad_cat_data), categories_cfg_path=cfg_p)


def test_absent_gross_redemptions_fails():
    absent_red_data = [dict(VALID_SAMPLE_DATA[0])]
    absent_red_data[0]["gross_redemption_cr"] = None
    with pytest.raises(ValueError, match="Absent gross redemptions"):
        validate_flows(pd.DataFrame(absent_red_data))


def test_gap_detection_without_silent_interpolation():
    gap_data = [
        dict(VALID_SAMPLE_DATA[0], month="2024-01"),
        # Missing 2024-02 and 2024-03
        dict(VALID_SAMPLE_DATA[0], month="2024-04"),
    ]
    # Fix available_from dates to be valid post-month-end
    gap_data[0]["available_from"] = "2024-02-12T00:00:00Z"
    gap_data[1]["available_from"] = "2024-05-12T00:00:00Z"

    val_df, report = validate_flows(pd.DataFrame(gap_data))
    assert len(val_df) == 2
    gaps = report["missingness"]["gaps_per_category"]["Large Cap"]
    assert gaps == ["2024-02", "2024-03"]
    # Invariant: missing months are not silently interpolated into val_df
    assert len(val_df) == 2


def test_save_validated_flows_and_snapshot_preservation(tmp_path):
    raw_df = pd.DataFrame(VALID_SAMPLE_DATA)
    val_df, report = validate_flows(raw_df)

    out_dir = tmp_path / "processed"
    qr_p = tmp_path / "quality_report.json"
    snap_dir = tmp_path / "snapshots"

    flows_f, qr_f = save_validated_flows(
        val_df, report, output_dir=out_dir, quality_report_path=qr_p, snapshot_dir=snap_dir
    )

    assert flows_f.is_file()
    assert qr_f.is_file()
    assert (snap_dir / "processed" / "flows_category_month.csv").is_file()

    # Verify JSON envelope structure
    envelope = json.loads(qr_f.read_text())
    assert envelope["version"] == 1
    assert envelope["source"] == "AMFI monthly flow validation engine"
    assert envelope["payload"]["status"] == "pass"

    # Simulate failed refresh: corrupted frame fails validation, leaving original file untouched
    orig_mtime = flows_f.stat().st_mtime
    bad_df = pd.DataFrame({"corrupt": [1, 2, 3]})
    with pytest.raises(ValueError):
        save_validated_flows(bad_df, report, output_dir=out_dir, quality_report_path=qr_p)

    # Original file is preserved
    assert flows_f.stat().st_mtime == orig_mtime
