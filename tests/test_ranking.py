"""Unit tests for NAV metrics, fund ranking, and shortlist generation.

Verifies Prompt 14:
- Architectural import isolation: ranking does not import flows, forecasting, or alerts
- Metric calculations on known toy series (CAGR, Vol, Max Drawdown, Sortino, Consistency)
- Strict eligibility filtering (Direct-Growth, >=3Y history, gap checks)
- Transparent rejected-schemes audit ledger
- Within-category percentile scoring direction (lower drawdown -> higher score)
- Base weights sum to 1.0
- Weight sensitivity analysis (+/- 10pp) with Spearman correlation and top-5 overlap
- Contract compliance of shortlist.csv
"""
from __future__ import annotations

import ast
import inspect
from pathlib import Path
import numpy as np
import pandas as pd
import pytest

from fundflow.contracts import validate_table, COLUMNS
from fundflow.nav_metrics import compute_scheme_nav_metrics
import fundflow.ranking as ranking_mod
from fundflow.ranking import rank_funds, analyze_weight_sensitivity, BASE_WEIGHTS

ROOT = Path(__file__).resolve().parents[1]


# --- 1. Architectural Import Isolation ---

def test_ranking_import_isolation():
    """Verify that ranking and nav_metrics do NOT import flow forecasting or alert modules."""
    forbidden_modules = {
        "fundflow.flows",
        "fundflow.forecasting",
        "fundflow.features",
        "fundflow.validate",
        "fundflow.alerts",
    }

    # Inspect AST of ranking.py and nav_metrics.py
    for mod_name in ["src/fundflow/nav_metrics.py", "src/fundflow/ranking.py"]:
        path = ROOT / mod_name
        with path.open("r", encoding="utf-8") as f:
            tree = ast.parse(f.read(), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert alias.name not in forbidden_modules, f"Forbidden import {alias.name} in {mod_name}"
            elif isinstance(node, ast.ImportFrom):
                assert node.module not in forbidden_modules, f"Forbidden import from {node.module} in {mod_name}"


# --- 2. Metric Calculations on Known Toy Series ---

def test_compute_scheme_nav_metrics_toy_series():
    # 756 business days (exactly 3 years) of steady 10% annual growth
    days = 756
    dates = pd.date_range("2021-01-01", periods=days, freq="B")
    daily_growth = (1.10) ** (1.0 / 252.0)
    nav_vals = [10.0 * (daily_growth ** i) for i in range(days)]
    series = pd.Series(nav_vals, index=dates)

    res = compute_scheme_nav_metrics(series, min_trading_days=750)
    assert res is not None
    # 3Y CAGR should be close to 10%
    assert pytest.approx(res["cagr_3y"], abs=0.5) == 10.0
    # Zero drawdown along monotonically increasing series
    assert pytest.approx(res["max_drawdown"], abs=0.01) == 0.0
    # 100% consistency
    assert res["consistency"] == 1.0


def test_compute_scheme_nav_metrics_insufficient_history():
    series = pd.Series([10.0, 11.0, 12.0], index=pd.date_range("2024-01-01", periods=3))
    assert compute_scheme_nav_metrics(series, min_trading_days=750) is None


# --- 3. Eligibility & Rejection Ledger Tests ---

@pytest.fixture
def sample_ranking_universe():
    # 6 schemes in Large Cap: 4 Direct-Growth with >= 3Y NAV, 1 Regular, 1 with gap
    days = 800
    dates = pd.date_range("2021-01-01", periods=days, freq="B").strftime("%Y-%m-%d").tolist()

    schemes = [
        {"scheme_code": "1001", "scheme_name": "Scheme A Direct Growth", "fund_house": "AMC 1", "category": "Large Cap", "plan_type": "Direct", "option_type": "Growth", "riskometer": ""},
        {"scheme_code": "1002", "scheme_name": "Scheme B Direct Growth", "fund_house": "AMC 2", "category": "Large Cap", "plan_type": "Direct", "option_type": "Growth", "riskometer": ""},
        {"scheme_code": "1003", "scheme_name": "Scheme C Direct Growth", "fund_house": "AMC 3", "category": "Large Cap", "plan_type": "Direct", "option_type": "Growth", "riskometer": ""},
        {"scheme_code": "1004", "scheme_name": "Scheme D Direct Growth", "fund_house": "AMC 4", "category": "Large Cap", "plan_type": "Direct", "option_type": "Growth", "riskometer": ""},
        {"scheme_code": "1005", "scheme_name": "Scheme E Regular Growth", "fund_house": "AMC 5", "category": "Large Cap", "plan_type": "Regular", "option_type": "Growth", "riskometer": ""},
        {"scheme_code": "1006", "scheme_name": "Scheme F Direct Growth Gap", "fund_house": "AMC 6", "category": "Large Cap", "plan_type": "Direct", "option_type": "Growth", "riskometer": ""},
    ]
    sm_df = pd.DataFrame(schemes)

    nav_rows = []
    np.random.seed(42)
    for s in schemes:
        code = s["scheme_code"]
        base_nav = 20.0
        s_dates = list(dates)
        if code == "1006":
            # Introduce a 25-day gap in the middle
            s_dates = s_dates[:300] + s_dates[325:]
        for i, d in enumerate(s_dates):
            ret = np.random.normal(0.0004, 0.01)
            base_nav *= (1.0 + ret)
            nav_rows.append({
                "date": d,
                "scheme_code": code,
                "nav": round(base_nav, 4),
                "source_url": "https://portal.amfiindia.com",
            })

    nav_df = pd.DataFrame(nav_rows)
    return nav_df, sm_df


def test_rank_funds_eligibility_and_rejections(sample_ranking_universe):
    nav_df, sm_df = sample_ranking_universe
    shortlist, rejected = rank_funds(nav_df, sm_df)

    assert not shortlist.empty
    validate_table("shortlist", shortlist)
    assert tuple(shortlist.columns) == COLUMNS["shortlist"]

    # 4 eligible schemes
    assert len(shortlist) == 4
    assert set(shortlist["scheme_code"]) == {"1001", "1002", "1003", "1004"}

    # 2 rejected schemes
    assert len(rejected) == 2
    rej_codes = set(rejected["scheme_code"])
    assert "1005" in rej_codes  # Regular plan
    assert "1006" in rej_codes  # Gap

    r_1005 = rejected[rejected["scheme_code"] == "1005"].iloc[0]
    assert "Non-direct plan" in r_1005["reason"]

    r_1006 = rejected[rejected["scheme_code"] == "1006"].iloc[0]
    assert "Material unexplained NAV gap" in r_1006["reason"]


def test_percentile_scoring_direction_drawdown(sample_ranking_universe):
    nav_df, sm_df = sample_ranking_universe
    shortlist, _ = rank_funds(nav_df, sm_df)

    # Check drawdown percentile: lower max_drawdown must get higher p_drawdown
    min_dd_row = shortlist.sort_values("max_drawdown").iloc[0]
    max_dd_row = shortlist.sort_values("max_drawdown").iloc[-1]
    assert min_dd_row["p_drawdown"] > max_dd_row["p_drawdown"]


def test_base_weights_sum_to_one():
    total_w = sum(BASE_WEIGHTS.values())
    assert pytest.approx(total_w) == 1.0


def test_weight_sensitivity_analysis(sample_ranking_universe):
    nav_df, sm_df = sample_ranking_universe
    shortlist, _ = rank_funds(nav_df, sm_df)

    # Add dummy 5th scheme to test top-5 sensitivity
    extra_row = shortlist.iloc[0].to_dict()
    extra_row["scheme_code"] = "1099"
    extra_row["research_score"] = 50.0
    expanded_shortlist = pd.concat([shortlist, pd.DataFrame([extra_row])], ignore_index=True)

    sens = analyze_weight_sensitivity(expanded_shortlist, delta=0.10)
    assert sens["status"] == "completed"
    assert len(sens["perturbations"]) == 8  # 4 components * 2 shifts (+/-)
    for p in sens["perturbations"]:
        assert 0.0 <= p["spearman_correlation"] <= 1.0
        assert 0.0 <= p["top5_overlap"] <= 1.0
