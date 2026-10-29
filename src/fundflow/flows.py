"""FundFlow redemption rates and flow metrics engine.

Computes deterministic category-level target redemption rates and flow ratios
using prior-month closing AUM as the opening AUM proxy.
Enforces strict denominator validation, zero-division prevention,
and validity-dated category mapping.
"""
from __future__ import annotations

import math
from pathlib import Path
from typing import Optional
import numpy as np
import pandas as pd

from fundflow.contracts import validate_table

ROOT = Path(__file__).resolve().parents[2]
CATEGORY_MAP_FILE = ROOT / "config" / "category_map.csv"


def _load_category_map(map_path: Optional[Path] = None) -> pd.DataFrame:
    """Load the validity-dated category mapping configuration."""
    path = map_path or CATEGORY_MAP_FILE
    if not path.is_file():
        return pd.DataFrame(columns=["raw_category", "category", "valid_from", "valid_to"])
    return pd.read_csv(path)


def map_category_with_validity(raw_cat: str, month: str, cat_map_df: Optional[pd.DataFrame] = None) -> str:
    """Map a raw category label to canonical category enforcing validity date windows."""
    if cat_map_df is None:
        cat_map_df = _load_category_map()
    if cat_map_df.empty:
        return raw_cat

    matches = cat_map_df[
        (cat_map_df["raw_category"] == raw_cat)
        & (cat_map_df["valid_from"] <= month)
        & (month <= cat_map_df["valid_to"])
    ]
    if not matches.empty:
        return str(matches.iloc[0]["category"])
    
    # Check if already canonical
    canonical_matches = cat_map_df[
        (cat_map_df["category"] == raw_cat)
        & (cat_map_df["valid_from"] <= month)
        & (month <= cat_map_df["valid_to"])
    ]
    if not canonical_matches.empty:
        return str(canonical_matches.iloc[0]["category"])

    return raw_cat


def compute_rates(flows: pd.DataFrame, cat_map_df: Optional[pd.DataFrame] = None) -> pd.DataFrame:
    """Compute category-level redemption rates and flow metrics.
    
    Target definition:
        redemption_rate_pct(c, t) = 100 * gross_redemptions(c, t) / closing_AUM(c, t-1)
    
    Prior-month closing AUM is explicitly used as a proxy for opening AUM.
    
    Denominator & Missingness Rules:
    - Never divide by zero.
    - If closing_AUM(c, t-1) is missing, zero, negative, or non-finite, rate is NaN.
    - If gross_redemptions(c, t) is NaN, rate is NaN.
    - If gross_redemptions(c, t) == 0.0 and denominator > 0, rate is 0.0 (preserved).
    - Aggregate monetary amounts by (month, category) before computing ratios.
    """
    if flows.empty:
        return pd.DataFrame(columns=[
            "month", "category", "gross_inflow_cr", "gross_redemption_cr", "net_flow_cr",
            "aum_close_cr", "prior_aum_close_cr", "redemption_rate_pct", "net_flow_rate_pct",
            "aum_growth_pct", "available_from", "source_url", "retrieved_at"
        ])

    df = flows.copy()
    if "month" not in df.columns or "category" not in df.columns:
        raise ValueError("Flows dataframe must contain 'month' and 'category' columns")

    # Load category map
    if cat_map_df is None:
        cat_map_df = _load_category_map()

    # Apply validity-dated category mapping
    mapped_cats = []
    for _, row in df.iterrows():
        m_cat = map_category_with_validity(str(row["category"]), str(row["month"]), cat_map_df)
        mapped_cats.append(m_cat)
    df["category"] = mapped_cats

    # Group monetary amounts by (month, category) before computing ratios (aggregation-before-ratio)
    numeric_cols = ["gross_inflow_cr", "gross_redemption_cr", "net_flow_cr", "aum_close_cr"]
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    agg_funcs = {}
    for col in numeric_cols:
        if col in df.columns:
            agg_funcs[col] = lambda s: s.sum(min_count=1)

    # For provenance columns, take first or maximum
    for col in ["available_from", "source_url", "retrieved_at", "aaum_cr"]:
        if col in df.columns:
            agg_funcs[col] = "max"

    grouped = df.groupby(["month", "category"], as_index=False).agg(agg_funcs)

    # Sort deterministically by category and month
    grouped = grouped.sort_values(["category", "month"]).reset_index(drop=True)

    # Compute prior-month closing AUM per category
    # Verify sequential calendar month or explicit prior month match
    grouped["prior_aum_close_cr"] = np.nan
    grouped["redemption_rate_pct"] = np.nan
    grouped["net_flow_rate_pct"] = np.nan
    grouped["aum_growth_pct"] = np.nan

    for cat, cat_group in grouped.groupby("category"):
        cat_indices = cat_group.index.tolist()
        for i, idx in enumerate(cat_indices):
            curr_month = grouped.loc[idx, "month"]
            
            # Find previous month in the category
            # Strict prior month: must be calendar month t-1
            curr_y, curr_m = map(int, curr_month.split("-"))
            if curr_m == 1:
                prev_month = f"{curr_y - 1:04d}-12"
            else:
                prev_month = f"{curr_y:04d}-{curr_m - 1:02d}"

            # Look up prev_month in cat_group
            prev_row = cat_group[cat_group["month"] == prev_month]
            if not prev_row.empty:
                prior_aum = prev_row.iloc[0]["aum_close_cr"]
                if math.isfinite(prior_aum) and prior_aum > 0.0:
                    grouped.loc[idx, "prior_aum_close_cr"] = prior_aum

                    # Compute redemption rate
                    gross_red = grouped.loc[idx, "gross_redemption_cr"]
                    if pd.notna(gross_red) and math.isfinite(gross_red):
                        if gross_red >= 0:
                            grouped.loc[idx, "redemption_rate_pct"] = (gross_red / prior_aum) * 100.0

                    # Compute net flow rate
                    net_fl = grouped.loc[idx, "net_flow_cr"]
                    if pd.notna(net_fl) and math.isfinite(net_fl):
                        grouped.loc[idx, "net_flow_rate_pct"] = (net_fl / prior_aum) * 100.0

                    # Compute AUM growth
                    curr_aum = grouped.loc[idx, "aum_close_cr"]
                    if pd.notna(curr_aum) and math.isfinite(curr_aum):
                        grouped.loc[idx, "aum_growth_pct"] = ((curr_aum - prior_aum) / prior_aum) * 100.0

    return grouped.sort_values(["month", "category"]).reset_index(drop=True)
