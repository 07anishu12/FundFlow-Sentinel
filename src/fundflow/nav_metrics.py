"""FundFlow NAV metrics calculation engine.

Computes 3Y CAGR, annualized volatility, maximum drawdown, Sortino ratio,
and rolling 1-year return consistency on daily historical NAV series.
Strictly decoupled from flow forecasting and alert models.
"""
from __future__ import annotations

import math
from typing import Optional
import numpy as np
import pandas as pd


def compute_scheme_nav_metrics(
    daily_nav_series: pd.Series,
    rf_annual: float = 0.06,  # 6.0% RBI repo rate baseline
    min_trading_days: int = 750,  # ~3 years of business days
) -> Optional[dict[str, float]]:
    """Compute risk-adjusted and historical return metrics for a single scheme NAV series.
    
    Returns dict:
    - cagr_3y: 3-year Compound Annual Growth Rate (%)
    - vol: Annualized daily return standard deviation (%)
    - max_drawdown: Maximum peak-to-trough decline (%)
    - sortino: Sortino ratio with downside deviation relative to risk-free rate
    - consistency: Fraction of rolling 1-year (252-day) periods with positive return
    - history_years: Total history span in years
    - n_days: Total number of trading observations
    """
    series = daily_nav_series.dropna().sort_index()
    n_days = len(series)
    if n_days < min_trading_days:
        return None

    nav_vals = series.values.astype(float)
    if (nav_vals <= 0.0).any() or not np.all(np.isfinite(nav_vals)):
        return None

    # History years
    history_years = round(float(n_days / 252.0), 2)

    # 1. 3Y CAGR
    # Use actual 3-year window (last 756 or n_days)
    nav_start = nav_vals[0]
    nav_end = nav_vals[-1]
    years = max(1.0, n_days / 252.0)
    cagr_3y = float((nav_end / nav_start) ** (1.0 / years) - 1.0) * 100.0

    # 2. Daily returns
    daily_returns = np.diff(nav_vals) / nav_vals[:-1]
    if len(daily_returns) == 0:
        return None

    # 3. Annualized Volatility
    vol = float(np.std(daily_returns, ddof=1) * np.sqrt(252.0)) * 100.0

    # 4. Maximum Drawdown (positive percentage)
    running_max = np.maximum.accumulate(nav_vals)
    drawdowns = (running_max - nav_vals) / running_max
    max_drawdown = float(np.max(drawdowns)) * 100.0

    # 5. Sortino Ratio
    # Daily risk-free rate
    rf_daily = (1.0 + rf_annual) ** (1.0 / 252.0) - 1.0
    excess_returns = daily_returns - rf_daily
    downside_returns = np.minimum(excess_returns, 0.0)
    downside_std = np.sqrt(np.mean(downside_returns ** 2)) * np.sqrt(252.0)

    ann_excess_return = (cagr_3y / 100.0) - rf_annual
    if downside_std > 1e-6:
        sortino = float(ann_excess_return / downside_std)
    else:
        # Zero downside deviation
        sortino = 5.0 if ann_excess_return > 0 else 0.0

    # 6. Rolling 1-Year Consistency (252 trading days)
    if n_days >= 252:
        roll_returns = nav_vals[252:] / nav_vals[:-252] - 1.0
        pos_fraction = float(np.mean(roll_returns > 0.0))
        consistency = round(pos_fraction, 4)
    else:
        consistency = 1.0 if cagr_3y > 0 else 0.0

    return {
        "cagr_3y": round(cagr_3y, 4),
        "vol": round(vol, 4),
        "max_drawdown": round(max_drawdown, 4),
        "sortino": round(sortino, 4),
        "consistency": consistency,
        "history_years": history_years,
        "n_days": n_days,
    }
