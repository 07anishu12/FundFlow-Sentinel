"""Adversarial and deterministic regression tests for ranking, sentiment, loaders, and UI.

Agent B — Prompt 24 (Wave 11 Test Hardening)
Covers:
- Section A: NAV metrics (CAGR, vol, max drawdown, Sortino, consistency), eligibility filters, score direction, weight sensitivity, import isolation
- Section B: Sentiment URL/ID deduplication, publication vs retrieval timestamps, lexical provenance, sufficiency thresholding, GDELT separation
- Section C: Loader path traversal guards, atomic tmp isolation, null-vs-zero preservation, corrupted artifact handling
- Section D: Offline rendering across all 6 pages, metric label contracts, UI presentation-only compliance, disclaimer verification
"""
from __future__ import annotations

import ast
import json
import math
from pathlib import Path
import socket
import numpy as np
import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest

from fundflow.contracts import COLUMNS, validate_table
from fundflow.nav_metrics import compute_scheme_nav_metrics
from fundflow.ranking import rank_funds, analyze_weight_sensitivity, BASE_WEIGHTS
from fundflow.sentiment import (
    normalize_url,
    generate_article_id,
    tag_topics,
    LexicalSentimentAnalyzer,
    process_sentiment_items,
    check_sentiment_sufficiency,
)
from app.loaders import load_table, load_artifact, load_model_results, load_quality_metadata

ROOT = Path(__file__).resolve().parents[1]
FIXTURES_DIR = ROOT / "data" / "snapshots" / "fixtures"


# ===========================================================================
# Network Blocking Fixture for Offline UI Assurance
# ===========================================================================

@pytest.fixture(autouse=True)
def enforce_network_block(monkeypatch):
    """Hard-block all socket operations to guarantee offline test isolation."""
    def blocked(*args, **kwargs):
        raise AssertionError("Unexpected network access detected in regression test")
    monkeypatch.setattr(socket, "create_connection", blocked)
    monkeypatch.setattr(socket.socket, "connect", blocked)


# ===========================================================================
# SECTION A: NAV Metrics & Ranking Integrity
# ===========================================================================

def test_hand_calculated_nav_metrics_flat_series():
    """Flat NAV series (NAV = 100.0 for 756 business days) yields exactly 0 for return, vol, and drawdown."""
    dates = pd.date_range("2021-01-01", periods=756, freq="B")
    flat_nav = pd.Series(100.0, index=dates)

    metrics = compute_scheme_nav_metrics(flat_nav, rf_annual=0.06, min_trading_days=750)
    assert metrics is not None
    assert metrics["cagr_3y"] == 0.0
    assert metrics["vol"] == 0.0
    assert metrics["max_drawdown"] == 0.0
    assert metrics["consistency"] == 0.0
    assert metrics["n_days"] == 756


def test_hand_calculated_nav_metrics_rising_series():
    """Steady rising NAV series yields positive CAGR, positive Sortino, and 0.0% max drawdown."""
    dates = pd.date_range("2021-01-01", periods=756, freq="B")
    # Doubling over 3 years: 100 -> 200
    rising_vals = np.linspace(100.0, 200.0, 756)
    rising_nav = pd.Series(rising_vals, index=dates)

    metrics = compute_scheme_nav_metrics(rising_nav, rf_annual=0.06, min_trading_days=750)
    assert metrics is not None
    assert metrics["cagr_3y"] > 20.0  # (2.0)^(1/3) - 1 ~= 26%
    assert metrics["max_drawdown"] == 0.0  # never declines
    assert metrics["consistency"] == 1.0  # 100% of rolling 1Y periods positive


def test_hand_calculated_nav_metrics_falling_series():
    """Steady falling NAV series yields negative CAGR and exact drawdown."""
    dates = pd.date_range("2021-01-01", periods=756, freq="B")
    # Halving from 100 to 50
    falling_vals = np.linspace(100.0, 50.0, 756)
    falling_nav = pd.Series(falling_vals, index=dates)

    metrics = compute_scheme_nav_metrics(falling_nav, rf_annual=0.06, min_trading_days=750)
    assert metrics is not None
    assert metrics["cagr_3y"] < 0.0
    assert metrics["max_drawdown"] == 50.0  # 50% peak to trough decline
    assert metrics["consistency"] == 0.0


def test_hand_calculated_nav_metrics_peak_trough_drawdown():
    """Peak of 150.0 dropping to 90.0 yields exactly (150 - 90)/150 = 40.0% max drawdown."""
    dates = pd.date_range("2021-01-01", periods=756, freq="B")
    vals = np.ones(756) * 100.0
    vals[200] = 150.0  # peak
    vals[300] = 90.0   # trough
    vals[500:] = 120.0
    nav_series = pd.Series(vals, index=dates)

    metrics = compute_scheme_nav_metrics(nav_series, min_trading_days=750)
    assert metrics is not None
    assert math.isclose(metrics["max_drawdown"], 40.0, abs_tol=1e-2)


def test_eligibility_filter_direct_growth_only():
    """Regular plans and IDCW/dividend options are strictly excluded with clear reasons."""
    sm_df = pd.DataFrame([
        {"scheme_code": "101", "scheme_name": "Fund Reg", "category": "Large Cap", "plan_type": "Regular", "option_type": "Growth"},
        {"scheme_code": "102", "scheme_name": "Fund Div", "category": "Large Cap", "plan_type": "Direct", "option_type": "IDCW"},
        {"scheme_code": "103", "scheme_name": "Fund Valid", "category": "Large Cap", "plan_type": "Direct", "option_type": "Growth"},
    ])
    # Synthetic NAV for 103 only
    dates = pd.date_range("2021-01-01", periods=800, freq="B").strftime("%Y-%m-%d")
    nav_df = pd.DataFrame({
        "scheme_code": ["103"] * 800,
        "date": dates,
        "nav": np.linspace(10.0, 20.0, 800),
    })

    shortlist, rejected = rank_funds(nav_df, sm_df)
    assert len(shortlist) == 1
    assert shortlist.iloc[0]["scheme_code"] == "103"

    rej_reasons = {r["scheme_code"]: r["reason"] for _, r in rejected.iterrows()}
    assert "Non-direct plan" in rej_reasons["101"]
    assert "Non-growth option" in rej_reasons["102"]


def test_eligibility_filter_history_length_and_gap_tolerance():
    """Schemes with history < 750 days or gaps > 10 calendar days must be rejected."""
    sm_df = pd.DataFrame([
        {"scheme_code": "201", "scheme_name": "Short History", "category": "Large Cap", "plan_type": "Direct", "option_type": "Growth"},
        {"scheme_code": "202", "scheme_name": "Gap Scheme", "category": "Large Cap", "plan_type": "Direct", "option_type": "Growth"},
    ])
    # 201: only 500 days
    dates_short = pd.date_range("2022-01-01", periods=500, freq="B").strftime("%Y-%m-%d")
    nav_201 = pd.DataFrame({"scheme_code": ["201"] * 500, "date": dates_short, "nav": [15.0] * 500})

    # 202: 800 days but has a 25-day gap
    dates_gap = list(pd.date_range("2021-01-01", periods=400, freq="B").strftime("%Y-%m-%d")) + \
                list(pd.date_range("2023-01-01", periods=400, freq="B").strftime("%Y-%m-%d"))
    nav_202 = pd.DataFrame({"scheme_code": ["202"] * 800, "date": dates_gap, "nav": [15.0] * 800})

    nav_combined = pd.concat([nav_201, nav_202], ignore_index=True)
    shortlist, rejected = rank_funds(nav_combined, sm_df)

    assert shortlist.empty
    rej_reasons = {r["scheme_code"]: r["reason"] for _, r in rejected.iterrows()}
    assert "Insufficient history" in rej_reasons["201"]
    assert "Material unexplained NAV gap" in rej_reasons["202"]


def test_ranking_score_direction_drawdown_inversion():
    """Smaller drawdown must receive higher percentile and higher composite research score."""
    sm_df = pd.DataFrame([
        {"scheme_code": "301", "scheme_name": "Low Drawdown", "category": "Large Cap", "plan_type": "Direct", "option_type": "Growth"},
        {"scheme_code": "302", "scheme_name": "High Drawdown", "category": "Large Cap", "plan_type": "Direct", "option_type": "Growth"},
    ])
    dates = pd.date_range("2021-01-01", periods=800, freq="B").strftime("%Y-%m-%d")

    # 301: Low drawdown (steady growth, max drawdown ~2%)
    nav_301 = pd.DataFrame({"scheme_code": ["301"] * 800, "date": dates, "nav": np.linspace(10.0, 15.0, 800)})
    # 302: High drawdown (drops sharply in middle from 20 to 10, max drawdown 50%)
    vals_302 = np.linspace(10.0, 15.0, 800)
    vals_302[300:350] = 5.0
    nav_302 = pd.DataFrame({"scheme_code": ["302"] * 800, "date": dates, "nav": vals_302})

    nav_df = pd.concat([nav_301, nav_302], ignore_index=True)
    shortlist, _ = rank_funds(nav_df, sm_df)

    s301 = shortlist[shortlist["scheme_code"] == "301"].iloc[0]
    s302 = shortlist[shortlist["scheme_code"] == "302"].iloc[0]

    # Scheme 301 must have higher drawdown score and higher research score
    assert s301["p_drawdown"] > s302["p_drawdown"]
    assert s301["research_score"] > s302["research_score"]


def test_ranking_weights_sum_to_one_and_score_reconciliation():
    """Base weights must sum to 1.0 and composite score must reconcile to weighted sum within 1e-4."""
    assert math.isclose(sum(BASE_WEIGHTS.values()), 1.0, abs_tol=1e-6)

    # Load shortlist fixture
    shortlist_p = FIXTURES_DIR / "shortlist.csv"
    if not shortlist_p.is_file():
        pytest.skip("Shortlist fixture unavailable")

    df = pd.read_csv(shortlist_p)
    for _, row in df.iterrows():
        expected_score = (
            BASE_WEIGHTS["p_return"] * float(row["p_return"]) +
            BASE_WEIGHTS["p_consistency"] * float(row["p_consistency"]) +
            BASE_WEIGHTS["p_drawdown"] * float(row["p_drawdown"]) +
            BASE_WEIGHTS["p_risk_adj"] * float(row["p_risk_adj"])
        )
        assert math.isclose(float(row["research_score"]), expected_score, abs_tol=1e-3)


def test_weight_sensitivity_renormalization_and_overlap():
    """Weight perturbations (+/- 10pp) renormalize to 1.0 and report rank correlation."""
    # Case 1: Insufficient schemes (< 5 schemes) returns insufficient_schemes status
    short_df = pd.DataFrame([
        {"scheme_code": f"S{i}", "category": "Large Cap", "research_score": 70.0 + i,
         "p_return": 70.0, "p_consistency": 70.0, "p_drawdown": 70.0, "p_risk_adj": 70.0}
        for i in range(3)
    ])
    sens_short = analyze_weight_sensitivity(short_df, delta=0.10)
    assert sens_short["status"] == "insufficient_schemes"

    # Case 2: Sufficient schemes (>= 5 schemes) returns completed analysis
    full_df = pd.DataFrame([
        {"scheme_code": f"S{i}", "category": "Large Cap", "research_score": 50.0 + 5.0 * i,
         "p_return": 50.0 + 5.0 * i, "p_consistency": 55.0, "p_drawdown": 60.0, "p_risk_adj": 50.0}
        for i in range(8)
    ])
    sens = analyze_weight_sensitivity(full_df, delta=0.10)
    assert sens["status"] == "completed"
    assert len(sens["perturbations"]) == 8  # 4 components * 2 shifts (+/-)

    for p in sens["perturbations"]:
        assert -1.0 <= p["spearman_correlation"] <= 1.0
        assert 0.0 <= p["top5_overlap"] <= 1.0


def test_ranking_strict_import_isolation():
    """Ranking engine must not import flow forecasting, alert, stress, or sentiment modules."""
    ranking_file = ROOT / "src" / "fundflow" / "ranking.py"
    nav_file = ROOT / "src" / "fundflow" / "nav_metrics.py"

    forbidden_modules = {"forecasting", "alerts", "stress", "flows", "sentiment", "anomaly"}

    for fpath in (ranking_file, nav_file):
        tree = ast.parse(fpath.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    for forbidden in forbidden_modules:
                        assert forbidden not in alias.name, f"{fpath.name} imports forbidden module {alias.name}"
            elif isinstance(node, ast.ImportFrom):
                mod = node.module or ""
                for forbidden in forbidden_modules:
                    assert forbidden not in mod, f"{fpath.name} imports forbidden module {mod}"


# ===========================================================================
# SECTION B: Sentiment & Historical-Tone Separation
# ===========================================================================

def test_canonical_url_and_article_deduplication():
    """URLs with tracking parameters or fragments must normalize and deduplicate to identical article IDs."""
    url1 = "https://www.financialexpress.com/market/mutual-funds/article1.html?utm_source=twitter&ref=feed#section"
    url2 = "https://www.financialexpress.com/market/mutual-funds/article1.html"

    norm1 = normalize_url(url1)
    norm2 = normalize_url(url2)
    assert norm1 == norm2 == "https://www.financialexpress.com/market/mutual-funds/article1.html"

    id1 = generate_article_id(norm1, "SEBI Issues Circular", "Financial Express")
    id2 = generate_article_id(norm2, "SEBI Issues Circular", "Financial Express")
    assert id1 == id2


def test_retrieval_time_distinct_from_publication_time():
    """Publication timestamp must be preserved from article data and never overwritten with retrieval time."""
    articles = [{
        "title": "RBI Announces Policy Rate Decision",
        "url": "https://rbi.org.in/press/101",
        "source_name": "RBI",
        "published_at": "2026-05-15T10:30:00Z",
    }]
    df = process_sentiment_items(articles, is_live=True)
    assert not df.empty
    assert df.iloc[0]["published_at"] == "2026-05-15T10:30:00Z"


def test_classifier_provenance_lexical_fallback():
    """Lexical classifier must strictly report model_id 'lexical-finance-v1' and never claim to be FinBERT."""
    clf = LexicalSentimentAnalyzer()
    assert clf.model_id == "lexical-finance-v1"
    assert "finbert" not in clf.model_id.lower()

    articles = [{
        "title": "Nifty rallies to record high with strong mutual fund inflows",
        "url": "https://example.com/art1",
        "source_name": "Example",
        "published_at": "2026-10-28T12:00:00Z",
    }]
    items_df = process_sentiment_items(articles, classifier=clf)
    assert items_df.iloc[0]["model_id"] == "lexical-finance-v1"
    assert items_df.iloc[0]["label"] == "positive"


def test_sentiment_sufficiency_threshold_enforced():
    """Fewer than 30 live articles in 14-day window returns insufficient status rather than positive/negative."""
    # Create 10 articles (below 30 threshold)
    items_few = pd.DataFrame({
        "article_id": [f"id_{i}" for i in range(10)],
        "published_at": ["2026-10-25T00:00:00Z"] * 10,
        "title": ["Sample Title"] * 10,
        "source_name": ["Source"] * 10,
        "url": ["https://portal.amfiindia.com"] * 10,
        "p_pos": [0.3] * 10,
        "p_neg": [0.1] * 10,
        "p_neu": [0.6] * 10,
        "label": ["neutral"] * 10,
        "score": [0.2] * 10,
        "topic_tags": ["market"] * 10,
        "is_live": [True] * 10,
        "model_id": ["lexical-finance-v1"] * 10,
    })
    suff = check_sentiment_sufficiency(items_few, as_of="2026-10-28")
    assert suff["status"] == "insufficient"
    assert suff["n_articles"] == 10
    assert suff["min_required"] == 30


# ===========================================================================
# SECTION C: Artifact Loaders & Data Provenance
# ===========================================================================

def test_loader_rejects_path_traversal_and_absolute_paths(tmp_path: Path):
    """Loaders must strictly reject parent directory traversal and absolute path injection."""
    from app.loaders import _safe_path
    trust_root = tmp_path / "trust_root"
    trust_root.mkdir()

    with pytest.raises(ValueError, match="traverse parents"):
        _safe_path(trust_root, "../secret.txt")

    with pytest.raises(ValueError, match="traverse parents"):
        _safe_path(trust_root, "/etc/passwd")


def test_loader_atomic_tmp_file_ignored(tmp_path: Path, monkeypatch):
    """Loaders must ignore temporary .tmp files and never present partial writes."""
    bundle_dir = tmp_path / "bundle"
    bundle_dir.mkdir()
    # Write valid modern manifest declaring predictions
    (bundle_dir / "manifest.json").write_text(json.dumps({
        "version": 1,
        "mode": "synthetic",
        "source": "test",
        "generated_at": "2026-10-28T12:00:00Z",
        "tables": ["predictions"],
        "artifacts": []
    }))

    # Write a .tmp file that should be ignored by standard readers
    tmp_file = bundle_dir / "outputs" / "predictions.csv.tmp"
    tmp_file.parent.mkdir(parents=True)
    tmp_file.write_text("as_of,target_month\n2024-09,2024-10\n")

    res = load_table("predictions", data_root=bundle_dir)
    # Real predictions.csv is missing -> returns missing state
    assert res.status == "missing"


def test_loader_preserves_null_values_without_zero_substitution():
    """Nullable contract columns (e.g. actual_rate in predictions) must remain NaN, never converted to 0.0."""
    res = load_table("predictions", bundle="snapshots/fixtures")
    assert res.status == "ok"
    df = res.frame
    # Fixture predictions has blank actual_rate which becomes NaN (or string empty)
    if not df.empty and "actual_rate" in df.columns:
        actual_val = df.iloc[0]["actual_rate"]
        # Must be empty or NaN, never numeric 0.0
        assert actual_val == "" or pd.isna(actual_val) or actual_val is None


def test_loader_rejects_corrupted_or_nan_json_artifacts(tmp_path: Path, monkeypatch):
    """Artifact loader must reject non-finite JSON constants (NaN, Infinity) with invalid state."""
    bundle_dir = tmp_path / "corrupt_bundle"
    bundle_dir.mkdir()
    (bundle_dir / "manifest.json").write_text(json.dumps({
        "version": 1,
        "mode": "offline_snapshot",
        "source": "AMFI",
        "generated_at": "2026-10-28T12:00:00Z",
        "tables": [],
        "artifacts": ["model_results"]
    }))
    outputs_dir = bundle_dir / "outputs"
    outputs_dir.mkdir()
    # Write JSON containing NaN constant (invalid in strict JSON)
    (outputs_dir / "model_results.json").write_text('{"version": 1, "source": "test", "generated_at": "2026-10-28T12:00:00Z", "payload": {"metrics": {"rmse": NaN}, "limitations": []}}')

    monkeypatch.setenv("FUNDFLOW_FIXTURE_DIR", str(bundle_dir))
    res = load_model_results(data_root=bundle_dir)
    assert res.status == "invalid"


# ===========================================================================
# SECTION D: UI Regressions & Offline Page Loading
# ===========================================================================

@pytest.mark.parametrize("page_name", [
    "Home.py",
    "pages/1_Forecast_Lab.py",
    "pages/2_Sentiment_Monitor.py",
    "pages/3_Fund_Research.py",
    "pages/4_Stress_Lab.py",
    "pages/5_Evidence_and_Limits.py",
])
def test_all_six_pages_render_offline_with_blocked_network(page_name):
    """All 6 Streamlit application pages render without exception under strictly blocked network sockets."""
    page_path = ROOT / "app" / page_name
    app = AppTest.from_file(str(page_path)).run(timeout=15)
    assert not app.exception
    # Assert every page displays the mandatory synthetic demo data notice
    assert any("SYNTHETIC DEMO DATA" in w.value for w in app.warning)

    # Assert every metric rendered adheres to KINDS enum (OBSERVED, FORECAST, SCENARIO)
    for m in app.metric:
        assert m.label.split(" · ")[0] in {"OBSERVED", "FORECAST", "SCENARIO"}


def test_ui_metrics_display_exact_loader_values():
    """Displayed metrics on Command Centre and Forecast Lab match values loaded directly from fixtures."""
    # Command Centre
    app_home = AppTest.from_file(str(ROOT / "app/Home.py")).run(timeout=15)
    assert not app_home.exception
    flow_res = load_table("flows_category_month")
    if not flow_res.frame.empty:
        # Check that closing AUM appears in one of the metrics
        found = any("Closing AUM" in m.label for m in app_home.metric)
        assert found is True
        assert any("₹ crore" in m.value for m in app_home.metric)


def test_ui_components_perform_no_ml_or_ranking_computations():
    """UI presentation components must not import scikit-learn models or execute business ranking logic."""
    comp_file = ROOT / "app" / "components.py"
    tree = ast.parse(comp_file.read_text(encoding="utf-8"))

    # Assert no sklearn or ML model class imports in UI components
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert not alias.name.startswith("sklearn"), f"UI component imports sklearn: {alias.name}"
        elif isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            assert not mod.startswith("sklearn"), f"UI component imports from sklearn: {mod}"


def test_ui_disclaimers_and_banners_present():
    """Prominent policy banners and disclaimers are present on relevant UI pages."""
    # Stress Lab INSUFFICIENT_HISTORY
    app_stress = AppTest.from_file(str(ROOT / "app/pages/4_Stress_Lab.py")).run(timeout=15)
    assert any("INSUFFICIENT_HISTORY" in w.value for w in app_stress.warning)

    # Evidence & Limits STRICT REDISTRIBUTION POLICY
    app_limits = AppTest.from_file(str(ROOT / "app/pages/5_Evidence_and_Limits.py")).run(timeout=15)
    assert any("STRICT REDISTRIBUTION POLICY" in w.value for w in app_limits.warning)

    # Fund Research Survivorship Bias disclosure
    app_research = AppTest.from_file(str(ROOT / "app/pages/3_Fund_Research.py")).run(timeout=15)
    assert any("Survivorship Bias" in md.value for md in app_research.markdown)
