"""FundFlow feature engineering engine.

Constructs point-in-time category-level feature matrices adhering to the frozen contract.
Enforces strict temporal availability, non-leakage boundaries, prior-only rolling statistics,
and isolation from live sentiment.
"""
from __future__ import annotations

import math
from pathlib import Path
from typing import Optional
import numpy as np
import pandas as pd
import yaml

from fundflow.contracts import validate_table, COLUMNS
from fundflow.flows import compute_rates, _load_category_map

ROOT = Path(__file__).resolve().parents[2]
CATEGORIES_FILE = ROOT / "config" / "categories.yaml"


def _load_universe_categories(cfg_path: Optional[Path] = None) -> set[str]:
    """Load the approved universe categories from config."""
    path = cfg_path or CATEGORIES_FILE
    if not path.is_file():
        return {"Large Cap", "Mid Cap", "Small Cap", "Flexi Cap", "Aggressive Hybrid", "Corporate Bond"}
    with path.open("r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    return set(cfg.get("universe", []))


def _month_diff(m1: str, m2: str) -> int:
    """Return the number of months from m1 to m2 (m2 - m1)."""
    y1, mo1 = map(int, m1.split("-"))
    y2, mo2 = map(int, m2.split("-"))
    return (y2 - y1) * 12 + (mo2 - mo1)


def _offset_month(m: str, offset: int) -> str:
    """Return month string shifted by offset months."""
    y, mo = map(int, m.split("-"))
    total_m = (y * 12 + mo - 1) + offset
    new_y = total_m // 12
    new_mo = (total_m % 12) + 1
    return f"{new_y:04d}-{new_mo:02d}"


def build_feature_matrix(
    flows: pd.DataFrame,
    market: pd.DataFrame,
    sentiment: Optional[pd.DataFrame] = None,
    as_of: Optional[str] = None,
    universe: Optional[set[str]] = None,
) -> pd.DataFrame:
    """Build the leakage-safe feature matrix conforming to the frozen contract.
    
    COLUMNS['feature_matrix']:
    - as_of: ISO UTC timestamp representing the forecast decision origin
    - target_month: YYYY-MM of the month being forecast
    - category: canonical category string
    - rate_lag0: redemption rate of month t-1 (latest available at as_of)
    - rate_lag1: redemption rate of month t-2
    - rate_lag2: redemption rate of month t-3
    - rate_lag11: seasonal redemption rate of month t-12
    - roll_mean3: mean of rate_lag0, rate_lag1, rate_lag2
    - roll_std3: sample standard deviation of rate_lag0, rate_lag1, rate_lag2
    - delta1: rate_lag0 - rate_lag1
    - net_flow_rate_lag0: net flow rate of month t-1 relative to AUM(t-2)
    - aum_growth_lag0: AUM growth of month t-1 relative to AUM(t-2)
    - nifty_return_lag0: Nifty 50 monthly return of month t-1
    - nifty_drawdown_3m: Nifty 3M rolling drawdown of month t-1
    - vix_mean_lag0: India VIX mean of month t-1
    - vix_change_lag0: India VIX monthly change of month t-1
    - target_rate: redemption rate of target month t (nullable if predicting out-of-sample)
    
    Temporal Non-Leakage Rules:
    1. Features use strictly records with available_from <= as_of.
    2. target_rate is never used as an input feature.
    3. Live sentiment is excluded by default from the historical feature matrix.
    4. Deterministic sorting by target_month, category.
    """
    if universe is None:
        universe = _load_universe_categories()

    # 1. Compute rates on flows
    rate_df = compute_rates(flows)
    if rate_df.empty:
        return pd.DataFrame(columns=COLUMNS["feature_matrix"])

    # 2. Filter to universe categories
    rate_df = rate_df[rate_df["category"].isin(universe)].copy()
    if rate_df.empty:
        return pd.DataFrame(columns=COLUMNS["feature_matrix"])

    # Index rate_df by (month, category) for fast O(1) lookup
    rate_map: dict[tuple[str, str], dict] = {}
    for _, row in rate_df.iterrows():
        key = (str(row["month"]), str(row["category"]))
        rate_map[key] = row.to_dict()

    # Prepare market lookup: key by month, verify available_from
    market_map: dict[str, dict] = {}
    if market is not None and not market.empty:
        market_clean = market.copy()
        for col in ["nifty_return", "nifty_drawdown_3m", "vix_mean", "vix_change"]:
            if col in market_clean.columns:
                market_clean[col] = pd.to_numeric(market_clean[col], errors="coerce")
        for _, row in market_clean.iterrows():
            m_key = str(row["month"])
            market_map[m_key] = row.to_dict()

    # 3. Determine candidate target months
    all_months = sorted(rate_df["month"].unique())
    all_cats = sorted(rate_df["category"].unique())

    rows: list[dict] = []

    for t_month in all_months:
        # Month t-1 is the most recent month whose data is available for predicting t
        lag0_month = _offset_month(t_month, -1)
        lag1_month = _offset_month(t_month, -2)
        lag2_month = _offset_month(t_month, -3)
        lag11_month = _offset_month(t_month, -12)

        # Determine decision as_of timestamp for predicting target month t
        # If explicitly passed, use it; otherwise, default to the 12th of month t at 00:00:00 UTC
        # (guaranteed post lag0_month availability and prior to t_month release)
        if as_of is not None:
            cutoff_iso = as_of
        else:
            cutoff_iso = f"{t_month}-12T00:00:00Z"

        for cat in all_cats:
            # Check if lag0, lag1, lag2, lag11 exist
            k0 = (lag0_month, cat)
            k1 = (lag1_month, cat)
            k2 = (lag2_month, cat)
            k11 = (lag11_month, cat)

            if k0 not in rate_map or k1 not in rate_map or k2 not in rate_map or k11 not in rate_map:
                # Insufficient history for required lags
                continue

            r0 = rate_map[k0]
            r1 = rate_map[k1]
            r2 = rate_map[k2]
            r11 = rate_map[k11]

            # Verify point-in-time availability at cutoff
            avail0 = str(r0.get("available_from", ""))
            if avail0 and avail0 > cutoff_iso:
                # Flow data for lag0 was not yet published at cutoff_iso
                continue

            rate_lag0 = r0.get("redemption_rate_pct")
            rate_lag1 = r1.get("redemption_rate_pct")
            rate_lag2 = r2.get("redemption_rate_pct")
            rate_lag11 = r11.get("redemption_rate_pct")

            # Check that all lag rates are valid finite numbers
            if not (pd.notna(rate_lag0) and pd.notna(rate_lag1) and pd.notna(rate_lag2) and pd.notna(rate_lag11)):
                continue
            if not (math.isfinite(rate_lag0) and math.isfinite(rate_lag1) and math.isfinite(rate_lag2) and math.isfinite(rate_lag11)):
                continue

            # Prior-only rolling statistics (lag0, lag1, lag2)
            lag_rates = [rate_lag0, rate_lag1, rate_lag2]
            roll_mean3 = float(np.mean(lag_rates))
            roll_std3 = float(np.std(lag_rates, ddof=1)) if len(lag_rates) > 1 else 0.0
            if not math.isfinite(roll_std3):
                roll_std3 = 0.0

            delta1 = float(rate_lag0 - rate_lag1)

            net_flow_rate_lag0 = r0.get("net_flow_rate_pct")
            aum_growth_lag0 = r0.get("aum_growth_pct")
            if not (pd.notna(net_flow_rate_lag0) and math.isfinite(net_flow_rate_lag0)):
                continue
            if not (pd.notna(aum_growth_lag0) and math.isfinite(aum_growth_lag0)):
                continue

            # Market features for lag0_month
            if lag0_month not in market_map:
                continue
            m_row = market_map[lag0_month]
            m_avail = str(m_row.get("available_from", ""))
            if m_avail and m_avail > cutoff_iso:
                # Market data not yet available at cutoff
                continue

            nifty_ret = m_row.get("nifty_return")
            nifty_dd = m_row.get("nifty_drawdown_3m")
            vix_m = m_row.get("vix_mean")
            vix_chg = m_row.get("vix_change")

            if not (pd.notna(nifty_ret) and pd.notna(nifty_dd) and pd.notna(vix_m) and pd.notna(vix_chg)):
                continue
            if not (math.isfinite(nifty_ret) and math.isfinite(nifty_dd) and math.isfinite(vix_m) and math.isfinite(vix_chg)):
                continue

            # Target rate for target month t
            kt = (t_month, cat)
            target_rate = None
            if kt in rate_map:
                target_val = rate_map[kt].get("redemption_rate_pct")
                if pd.notna(target_val) and math.isfinite(target_val):
                    target_rate = float(target_val)

            row_dict = {
                "as_of": cutoff_iso,
                "target_month": t_month,
                "category": cat,
                "rate_lag0": float(rate_lag0),
                "rate_lag1": float(rate_lag1),
                "rate_lag2": float(rate_lag2),
                "rate_lag11": float(rate_lag11),
                "roll_mean3": roll_mean3,
                "roll_std3": roll_std3,
                "delta1": delta1,
                "net_flow_rate_lag0": float(net_flow_rate_lag0),
                "aum_growth_lag0": float(aum_growth_lag0),
                "nifty_return_lag0": float(nifty_ret),
                "nifty_drawdown_3m": float(nifty_dd),
                "vix_mean_lag0": float(vix_m),
                "vix_change_lag0": float(vix_chg),
                "target_rate": target_rate if target_rate is not None else np.nan,
            }
            rows.append(row_dict)

    if not rows:
        return pd.DataFrame(columns=COLUMNS["feature_matrix"])

    res_df = pd.DataFrame(rows, columns=COLUMNS["feature_matrix"])
    # Deterministic sorting
    res_df = res_df.sort_values(["target_month", "category"]).reset_index(drop=True)
    return validate_table("feature_matrix", res_df)
