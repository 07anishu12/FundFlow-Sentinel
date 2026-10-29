"""Validation of 10 Indian Mutual Funds across live AMFI, cache, and quantitative contracts.

Generates:
- reports/live_validation/scheme_validation.csv
- reports/live_validation/data_quality_report.json
"""
from __future__ import annotations

import csv
import json
import math
from pathlib import Path
from typing import Any, Dict, List

import numpy as np
import pandas as pd

from fundflow.data_sources import fetch_amfi_nav
from fundflow.nav_metrics import compute_scheme_nav_metrics
from fundflow.ranking import rank_funds, BASE_WEIGHTS

TARGET_SCHEMES = [
    {
        "target_name": "Parag Parikh Flexi Cap Fund",
        "scheme_code": "122639",
        "isin": "INF879O01027",
        "expected_category": "Flexi Cap",
    },
    {
        "target_name": "Nippon India Large Cap Fund",
        "scheme_code": "118632",
        "isin": "INF204K01XI3",
        "expected_category": "Large Cap",
    },
    {
        "target_name": "HDFC Flexi Cap Fund",
        "scheme_code": "118955",
        "isin": "INF179K01UT0",
        "expected_category": "Flexi Cap",
    },
    {
        "target_name": "ICICI Prudential Large Cap Fund",
        "scheme_code": "120586",
        "isin": "INF109K016L0",
        "expected_category": "Large Cap",
        "renamed_from": "ICICI Prudential Bluechip Fund",
    },
    {
        "target_name": "SBI Large Cap Fund",
        "scheme_code": "119598",
        "isin": "INF200K01QX4",
        "expected_category": "Large Cap",
        "renamed_from": "SBI Bluechip Fund",
    },
    {
        "target_name": "UTI Nifty 50 Index Fund",
        "scheme_code": "120716",
        "isin": "INF789F01XA0",
        "expected_category": "Large Cap",  # Index tracking Large Cap Nifty 50
    },
    {
        "target_name": "Kotak Midcap Fund",
        "scheme_code": "119775",
        "isin": "INF174K01LT0",
        "expected_category": "Mid Cap",
        "renamed_from": "Kotak Emerging Equity Fund",
    },
    {
        "target_name": "Axis Small Cap Fund",
        "scheme_code": "125354",
        "isin": "INF846K01K35",
        "expected_category": "Small Cap",
    },
    {
        "target_name": "Mirae Asset Large & Midcap Fund",
        "scheme_code": "118834",
        "isin": "INF769K01BI1",
        "expected_category": "Aggressive Hybrid / Large & Mid Cap",
        "renamed_from": "Mirae Asset Emerging Bluechip Fund",
    },
    {
        "target_name": "DSP Mid Cap Fund",
        "scheme_code": "119071",
        "isin": "INF740K01PX1",
        "expected_category": "Mid Cap",
    },
]


def load_category_map() -> Dict[str, str]:
    cmap_path = Path("config/category_map.csv")
    if not cmap_path.exists():
        return {}
    df = pd.read_csv(cmap_path)
    return dict(zip(df["raw_category"], df["category"]))


def normalize_category(raw_cat: str, target_name: str) -> str:
    raw_clean = raw_cat.strip()
    if "flexi cap" in raw_clean.lower() or "flexicap" in raw_clean.lower():
        return "Flexi Cap"
    if "large cap" in raw_clean.lower() or "largecap" in raw_clean.lower():
        return "Large Cap"
    if "mid cap" in raw_clean.lower() or "midcap" in raw_clean.lower():
        return "Mid Cap"
    if "small cap" in raw_clean.lower() or "smallcap" in raw_clean.lower():
        return "Small Cap"
    if "index" in raw_clean.lower() or "nifty 50" in raw_clean.lower():
        return "Large Cap"
    if "large & mid" in raw_clean.lower():
        return "Large & Mid Cap"
    return "Other"


def main():
    out_dir = Path("reports/live_validation")
    out_dir.mkdir(parents=True, exist_ok=True)

    print("=== Step 1: Querying Official AMFI NAVAll Live Feed ===")
    live_df, live_status = fetch_amfi_nav(timeout=20)
    print(f"AMFI Live Status: {live_status.status} (HTTP {live_status.http_status}), Records: {live_status.records_accepted}")

    # Load cached Jan 2024 AMFI history
    jan24_path = Path("data/cache/nav/amfi_nav_2024-01-01_2024-01-05.txt")
    jan24_lines = jan24_path.read_text().splitlines() if jan24_path.exists() else []

    # Mapping
    category_map = load_category_map()

    scheme_rows = []
    quality_summary = {
        "validation_timestamp": pd.Timestamp.utcnow().isoformat(),
        "total_schemes_tested": len(TARGET_SCHEMES),
        "live_endpoint": "https://portal.amfiindia.com/spages/NAVAll.txt",
        "live_http_status": live_status.http_status,
        "schemes": [],
    }

    for item in TARGET_SCHEMES:
        sc = item["scheme_code"]
        name_target = item["target_name"]
        isin_expected = item["isin"]
        renamed_note = item.get("renamed_from", "")

        # Look in live snapshot
        match = live_df[live_df["scheme_code"] == sc]
        has_live = not match.empty

        if has_live:
            row = match.iloc[0]
            official_name = str(row["scheme_name"])
            latest_nav = float(row["nav"])
            latest_date = str(row["nav_date"])
            amc = str(row["amc"])
            raw_category = str(row["scheme_category"])
            isin_actual = str(row["isin_div_payout"]) if pd.notna(row["isin_div_payout"]) else isin_expected
            data_mode = "LIVE"
        else:
            official_name = name_target
            latest_nav = np.nan
            latest_date = "unavailable"
            amc = "unavailable"
            raw_category = "unavailable"
            isin_actual = isin_expected
            data_mode = "UNAVAILABLE"

        # Direct-Growth identification
        name_lower = official_name.lower()
        is_direct = "direct" in name_lower
        is_growth = "growth" in name_lower and "idcw" not in name_lower
        norm_category = normalize_category(raw_category, name_target)

        # Historical coverage audit
        history_records = []

        # 1. Check if single-scheme JSON cache exists
        json_cache = Path(f"data/cache/nav/mfapi_{sc}.json")
        has_3y_cache = False
        if json_cache.exists():
            try:
                cached_data = json.loads(json_cache.read_text())
                for h in cached_data.get("data", []):
                    dt_iso = pd.to_datetime(h["date"], format="%d-%m-%Y").strftime("%Y-%m-%d")
                    v = float(h["nav"])
                    if math.isfinite(v) and v > 0:
                        history_records.append({"date": dt_iso, "nav": v})
                has_3y_cache = len(history_records) >= 750
            except Exception:
                pass

        # 2. Check Jan 2024 AMFI cache
        if not history_records:
            for line in jan24_lines:
                if line.startswith(f"{sc};"):
                    parts = line.split(";")
                    try:
                        dt_iso = pd.to_datetime(parts[-1].strip(), format="%d-%b-%Y").strftime("%Y-%m-%d")
                        v = float(parts[-2].strip())
                        history_records.append({"date": dt_iso, "nav": v})
                    except Exception:
                        pass

        # 3. Append latest live date if available
        if has_live and latest_date != "unavailable":
            history_records.append({"date": latest_date, "nav": latest_nav})

        hist_df = pd.DataFrame(history_records).drop_duplicates(subset=["date"]).sort_values("date").reset_index(drop=True) if history_records else pd.DataFrame(columns=["date", "nav"])

        # Integrity checks
        n_obs = len(hist_df)
        is_positive = (hist_df["nav"] > 0).all() if n_obs > 0 else True
        is_finite = np.isfinite(hist_df["nav"]).all() if n_obs > 0 else True
        is_chronological = hist_df["date"].is_monotonic_increasing if n_obs > 1 else True
        duplicate_dates = len(hist_df) - len(hist_df["date"].unique())

        max_gap_days = 0
        if n_obs > 1:
            diffs = pd.to_datetime(hist_df["date"]).diff().dt.days.dropna()
            max_gap_days = int(diffs.max())

        # Evaluate Ranking eligibility
        eligibility = "REJECTED"
        rejection_reason = "None"
        cagr_3y = "N/A"
        vol_3y = "N/A"
        max_dd_3y = "N/A"
        sortino_3y = "N/A"
        consistency_1y = "N/A"

        if not is_direct:
            rejection_reason = "Non-direct plan"
        elif not is_growth:
            rejection_reason = "Non-growth option"
        elif n_obs < 750:
            rejection_reason = f"Insufficient history ({n_obs} < 750 trading days)"
        elif max_gap_days > 10:
            rejection_reason = f"Material unexplained NAV gap ({max_gap_days} > 10 calendar days)"
        elif not is_positive or not is_finite:
            rejection_reason = "Invalid non-positive or non-finite NAV"
        else:
            # Eligible! Compute 3Y metrics
            metrics = compute_scheme_nav_metrics(hist_df.set_index("date")["nav"])
            if metrics:
                eligibility = "ELIGIBLE"
                rejection_reason = "None (Passed all gates)"
                cagr_3y = f"{metrics['cagr_3y']:.2f}%"
                vol_3y = f"{metrics['vol']:.2f}%"
                max_dd_3y = f"{metrics['max_drawdown']:.2f}%"
                sortino_3y = f"{metrics['sortino']:.2f}"
                consistency_1y = f"{metrics['consistency'] * 100:.1f}%"

        scheme_summary = {
            "target_fund": name_target,
            "scheme_code": sc,
            "isin": isin_actual,
            "official_name": official_name,
            "fund_house": amc,
            "category": norm_category,
            "raw_category": raw_category,
            "plan": "Direct" if is_direct else "Regular",
            "option": "Growth" if is_growth else "IDCW",
            "latest_nav": latest_nav,
            "latest_nav_date": latest_date,
            "data_mode": data_mode,
            "historical_mode": "CACHED" if has_3y_cache else ("CACHED_PARTIAL" if n_obs > 1 else "UNAVAILABLE"),
            "historical_observations": n_obs,
            "max_date_gap_days": max_gap_days,
            "positive_nav": bool(is_positive),
            "finite_nav": bool(is_finite),
            "chronological_order": bool(is_chronological),
            "duplicate_dates": int(duplicate_dates),
            "ranking_eligibility": eligibility,
            "rejection_reason": rejection_reason,
            "cagr_3y": cagr_3y,
            "vol_3y": vol_3y,
            "max_drawdown_3y": max_dd_3y,
            "sortino_3y": sortino_3y,
            "consistency_1y": consistency_1y,
            "renamed_notes": renamed_note if renamed_note else "Original name",
        }

        scheme_rows.append(scheme_summary)
        quality_summary["schemes"].append(scheme_summary)

    # Save CSV
    csv_path = out_dir / "scheme_validation.csv"
    keys = list(scheme_rows[0].keys())
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=keys)
        writer.writeheader()
        writer.writerows(scheme_rows)
    print(f"Saved: {csv_path} ({len(scheme_rows)} schemes)")

    # Save JSON
    json_path = out_dir / "data_quality_report.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(quality_summary, f, indent=2)
    print(f"Saved: {json_path}")

    # Summary table
    print("\n=== Validation Results for 10 Mutual Funds ===")
    for s in scheme_rows:
        print(f"[{s['scheme_code']}] {s['target_fund']} | Latest: ₹{s['latest_nav']:.2f} ({s['latest_nav_date']}) | Mode: {s['data_mode']} | Hist Obs: {s['historical_observations']} | Status: {s['ranking_eligibility']} ({s['rejection_reason']})")


if __name__ == "__main__":
    main()
