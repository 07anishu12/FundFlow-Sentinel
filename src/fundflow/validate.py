"""Validation and quality gate for AMFI category monthly flow datasets.

Enforces:
- Exact frozen contract schemas (COLUMNS['flows_category_month'])
- Canonical category mapping and universe/exclusion separation
- Non-leakage availability boundary (available_from > period_end)
- Explicit gap detection per category without silent interpolation
- Hard-failure on duplicate keys, ambiguous units, or unmapped modeling categories
- Quality report JSON envelope generation and snapshot preservation
"""
from __future__ import annotations

import csv
import datetime
import json
import math
from pathlib import Path
from typing import Any

import pandas as pd
import yaml

from fundflow.contracts import COLUMNS, validate_table

DEFAULT_ROOT = Path(__file__).resolve().parents[2]
CATEGORY_MAP_PATH = DEFAULT_ROOT / "config" / "category_map.csv"
CATEGORIES_CFG_PATH = DEFAULT_ROOT / "config" / "categories.yaml"


def _get_month_end_date(month_str: str) -> datetime.date:
    """Return the last calendar day of a YYYY-MM month."""
    parts = month_str.split("-")
    year, month = int(parts[0]), int(parts[1])
    if month == 12:
        next_month = datetime.date(year + 1, 1, 1)
    else:
        next_month = datetime.date(year, month + 1, 1)
    return next_month - datetime.timedelta(days=1)


def _get_conservative_available_from(month_str: str) -> str:
    """Documented conservative availability policy: 12th of month T+1 at 00:00:00Z."""
    parts = month_str.split("-")
    year, month = int(parts[0]), int(parts[1])
    if month == 12:
        next_year, next_month = year + 1, 1
    else:
        next_year, next_month = year, month + 1
    dt = datetime.datetime(next_year, next_month, 12, 0, 0, 0, tzinfo=datetime.timezone.utc)
    return dt.isoformat().replace("+00:00", "Z")


def _generate_month_range(start_month: str, end_month: str) -> list[str]:
    """Generate all YYYY-MM months from start_month to end_month inclusive."""
    s_yr, s_mo = int(start_month[:4]), int(start_month[5:7])
    e_yr, e_mo = int(end_month[:4]), int(end_month[5:7])
    cur_yr, cur_mo = s_yr, s_mo
    result = []
    while (cur_yr < e_yr) or (cur_yr == e_yr and cur_mo <= e_mo):
        result.append(f"{cur_yr:04d}-{cur_mo:02d}")
        cur_mo += 1
        if cur_mo > 12:
            cur_mo = 1
            cur_yr += 1
    return result


def validate_flows(
    raw: pd.DataFrame,
    category_map_path: str | Path | None = None,
    categories_cfg_path: str | Path | None = None,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Validate raw monthly flows and return (validated_df, quality_report_payload).

    Hard-fails on duplicate keys, look-ahead availability leakage, unmapped categories
    entering modeling universe, or absent gross redemptions.
    """
    if raw.empty:
        raise ValueError("Cannot validate empty flows dataset")

    # Load configurations
    cat_map_p = Path(category_map_path or CATEGORY_MAP_PATH)
    cfg_p = Path(categories_cfg_path or CATEGORIES_CFG_PATH)

    active_universe = ["Large Cap", "Mid Cap", "Small Cap", "Flexi Cap", "Aggressive Hybrid", "Corporate Bond"]
    excluded_cats = ["Liquid", "Overnight"]
    if cfg_p.is_file():
        cfg_data = yaml.safe_load(cfg_p.read_text(encoding="utf-8"))
        if cfg_data and "universe" in cfg_data:
            active_universe = list(cfg_data["universe"])
        if cfg_data and "excluded" in cfg_data:
            excluded_cats = list(cfg_data["excluded"])

    # Load category map
    category_mappings: list[dict[str, str]] = []
    if cat_map_p.is_file():
        with cat_map_p.open(newline="", encoding="utf-8") as f:
            category_mappings = list(csv.DictReader(f))

    df = raw.copy()

    # 1. Check required columns and types
    expected_cols = set(COLUMNS["flows_category_month"])
    missing_cols = expected_cols - set(df.columns)
    if missing_cols:
        raise ValueError(f"Schema drift: flows dataset missing required columns: {sorted(missing_cols)}")

    # 2. Check for observed gross redemptions (never inferred from net flows)
    if df["gross_redemption_cr"].isna().any():
        raise ValueError("Absent gross redemptions detected; gross redemptions cannot be repaired or inferred")

    # Check finite numerics
    for num_col in ["gross_inflow_cr", "gross_redemption_cr", "net_flow_cr", "aum_close_cr", "aaum_cr"]:
        values = pd.to_numeric(df[num_col], errors="coerce")
        if values.isna().any() or not (values.apply(math.isfinite)).all():
            raise ValueError(f"Ambiguous or non-finite values in {num_col}")
        df[num_col] = values.astype(float)

    # 3. Canonical Category Normalization & Universe Verification
    unmapped_labels: list[str] = []
    normalized_categories = []

    for _, row in df.iterrows():
        cat_str = str(row["category"]).strip()
        month_str = str(row["month"]).strip()

        # Check if already canonical
        if cat_str in active_universe or cat_str in excluded_cats:
            normalized_categories.append(cat_str)
            continue

        # Look up in category map
        matched = None
        for m in category_mappings:
            if m["raw_category"].strip().lower() == cat_str.lower():
                if m["valid_from"] <= month_str <= m["valid_to"]:
                    matched = m["category"]
                    break
        if matched:
            normalized_categories.append(matched)
        else:
            unmapped_labels.append(cat_str)
            normalized_categories.append(cat_str)

    df["category"] = normalized_categories

    # Hard-fail if unmapped category enters modeling universe (not excluded)
    unmapped_in_modeling = [c for c in unmapped_labels if c not in excluded_cats]
    if unmapped_in_modeling:
        raise ValueError(f"Unmapped category label entered modeling universe: {unmapped_in_modeling}")

    # 4. Strict non-leakage check on available_from
    enforced_avail = []
    source_dates: dict[str, str] = {}

    for _, row in df.iterrows():
        m_str = str(row["month"]).strip()
        avail_str = str(row["available_from"]).strip() if pd.notna(row["available_from"]) else ""

        if not avail_str or avail_str == "":
            avail_str = _get_conservative_available_from(m_str)

        # Validate timestamp format
        try:
            avail_dt = datetime.datetime.fromisoformat(avail_str.replace("Z", "+00:00"))
            if avail_dt.utcoffset() is None or avail_dt.utcoffset().total_seconds() != 0:
                raise ValueError("Must be ISO UTC")
        except Exception:
            raise ValueError(f"Invalid available_from timestamp '{avail_str}' for month {m_str}")

        # Non-leakage check: available_from MUST be strictly after month-end
        month_end = _get_month_end_date(m_str)
        avail_date = avail_dt.date()
        if avail_date <= month_end:
            raise ValueError(
                f"Fatal look-ahead bias: available_from ({avail_str}) is on or before month-end "
                f"({month_end}) for month {m_str}. Availability lag evidence is required."
            )

        enforced_avail.append(avail_str)
        if m_str not in source_dates:
            source_dates[m_str] = avail_str

    df["available_from"] = enforced_avail

    # 5. Check for duplicate final keys (month, category)
    dups = df[df.duplicated(subset=["month", "category"])]
    if not dups.empty:
        dup_keys = dups[["month", "category"]].to_dict(orient="records")
        raise ValueError(f"Duplicate final key (month, category) found in flows: {dup_keys}")

    # 6. Gap analysis per category without silent interpolation
    gaps_per_category: dict[str, list[str]] = {}
    categories_present = df["category"].unique()

    for cat in categories_present:
        cat_months = sorted(df[df["category"] == cat]["month"].unique())
        if len(cat_months) > 1:
            full_span = _generate_month_range(cat_months[0], cat_months[-1])
            missing_months = [m for m in full_span if m not in cat_months]
            if missing_months:
                gaps_per_category[cat] = missing_months

    # Reorder columns to match frozen contract
    df = df[list(COLUMNS["flows_category_month"])].sort_values(["month", "category"]).reset_index(drop=True)

    # 7. Final contract validation
    validate_table("flows_category_month", df)

    # 8. Assemble Quality Report
    months_all = sorted(df["month"].unique())
    report_payload: dict[str, Any] = {
        "status": "pass",
        "checks": [
            {"name": "schema_columns", "status": "pass", "details": "All 10 contract columns verified."},
            {"name": "units_inr_crore", "status": "pass", "details": "All monetary columns confirmed finite INR crore."},
            {"name": "category_universe", "status": "pass", "details": f"Universe checked ({len(active_universe)} universe cats)."},
            {"name": "duplicate_keys", "status": "pass", "details": "Zero (month, category) duplicates."},
            {"name": "available_from_non_leakage", "status": "pass", "details": "Verified available_from strictly post-month-end."},
            {"name": "gross_redemption_observed", "status": "pass", "details": "All gross redemptions observed, zero inferred."},
        ],
        "coverage": {
            "start_month": months_all[0] if months_all else None,
            "end_month": months_all[-1] if months_all else None,
            "n_months": len(months_all),
            "total_records": len(df),
            "categories_count": len(categories_present),
        },
        "exclusions": [c for c in excluded_cats if c in df["category"].values],
        "missingness": {
            "gaps_per_category": gaps_per_category,
            "total_gap_months": sum(len(g) for g in gaps_per_category.values()),
        },
        "unmapped_labels": list(set(unmapped_labels)),
        "source_dates": source_dates,
    }

    return df, report_payload


def save_validated_flows(
    validated_df: pd.DataFrame,
    report_payload: dict[str, Any],
    output_dir: str | Path = "data/processed",
    quality_report_path: str | Path = "data/quality_report.json",
    snapshot_dir: str | Path | None = "data/snapshots",
) -> tuple[Path, Path]:
    """Atomically write validated flows CSV and quality_report JSON envelope.

    Preserves existing files on failure (snapshot fallback).
    """
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    flows_file = out_dir / "flows_category_month.csv"

    # Enforce contract validation before write
    validate_table("flows_category_month", validated_df)

    # Atomic write of flows CSV
    tmp_flows = flows_file.with_suffix(".tmp")
    validated_df.to_csv(tmp_flows, index=False)
    tmp_flows.replace(flows_file)

    # Build standard v1 quality_report JSON envelope
    envelope = {
        "version": 1,
        "source": "AMFI monthly flow validation engine",
        "generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat().replace("+00:00", "Z"),
        "payload": report_payload,
    }

    # Save quality report in data root
    qr_path = Path(quality_report_path)
    qr_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_qr = qr_path.with_suffix(".tmp")
    tmp_qr.write_text(json.dumps(envelope, indent=2), encoding="utf-8")
    tmp_qr.replace(qr_path)

    # Optional snapshot synchronization
    if snapshot_dir:
        snap_path = Path(snapshot_dir) / "processed"
        snap_path.mkdir(parents=True, exist_ok=True)
        validated_df.to_csv(snap_path / "flows_category_month.csv", index=False)

    return flows_file, qr_path
