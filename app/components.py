"""Presentation and institutional UI components for FundFlow Sentinel.

Provides:
- Premium white-theme financial analytics and risk-monitoring platform.
- Strictly formatted tabular numerals, high-contrast surfaces, and semantic colors.
- Clear separation between OBSERVED, FORECAST, and SCENARIO data.
- User-defined quantitative forecasting (Phase 4) with zero-leakage walk-forward evaluation.
- Resilient error boundaries, input sanitization, and URL security.
"""
from __future__ import annotations

import html
import logging
import math
import os
from pathlib import Path
from typing import Any, Optional

import altair as alt
import pandas as pd
import streamlit as st
import yaml

from app.styles import GLOBAL_CSS, COLORS
from app.formatters import (
    format_currency_crore,
    format_rate_pct,
    format_number,
    format_period,
    format_timestamp,
    format_provenance_label,
    format_metric_display,
)
from app.loaders import (
    load_table,
    load_model_results,
    load_quality_metadata,
    load_source_metadata,
    get_bundle_fingerprint,
)
from fundflow.stress import stress_outflow, scenario_table
from fundflow.explain import generate_stress_narrative, compute_empirical_residual_bands
from fundflow.flows import compute_rates
from fundflow.user_forecast import run_user_forecast, calculate_forecast_gap

ROOT = Path(__file__).resolve().parents[1]

KINDS = {"OBSERVED", "FORECAST", "SCENARIO"}


def safe_url(url: Optional[str]) -> Optional[str]:
    """Validate that a URL uses http or https scheme only without external network dependencies."""
    if not url or not isinstance(url, str):
        return None
    url_str = url.strip()
    if "://" not in url_str:
        return None
    scheme, rest = url_str.split("://", 1)
    if scheme.lower() not in {"http", "https"}:
        return None
    netloc = rest.split("/", 1)[0].split("?", 1)[0].split("#", 1)[0].strip()
    if not netloc:
        return None
    return url_str


def sanitize_display_text(text: Any) -> str:
    """Sanitize untrusted text to prevent markdown injection and HTML execution."""
    if text is None:
        return ""
    s = str(text)
    s = s.replace("[", "(").replace("]", ")")
    s = html.escape(s, quote=True)
    return s


def safe_page_boundary(page_name: str, render_fn):
    """Execute a page function within a secure, user-safe error boundary."""
    try:
        render_fn()
    except Exception as exc:
        logging.error(f"[AppResilience] Error rendering {page_name}: {type(exc).__name__}: {exc}")
        st.error(
            f"⚠️ An unexpected error occurred while loading {page_name}. "
            "The application is operating in safe fallback mode. "
            "No internal configuration details or stack traces are exposed."
        )
        st.info("Please verify data bundle integrity using 'make check' or contact system administrators.")


@st.cache_data(show_spinner=False)
def get_cached_table_frame(name: str, fingerprint: str) -> pd.DataFrame:
    """Cached accessor for table frames, keyed by bundle fingerprint."""
    return load_table(name).frame


def page_header(title: str, description: str) -> None:
    """Render page shell and classify the loaded bundle without overstating provenance."""
    st.set_page_config(
        page_title=f"{title} · FundFlow Sentinel",
        page_icon="🛡️",
        layout="wide",
    )
    st.markdown(GLOBAL_CSS, unsafe_allow_html=True)
    st.sidebar.title("FundFlow Sentinel")

    try:
        result = load_table("flows_category_month")
        metadata = result.metadata
        mode = str(getattr(metadata, "mode", "unknown")).lower()
        source = str(getattr(metadata, "source", "unavailable"))
        source_lower = source.lower()
        synthetic = (
            mode == "synthetic"
            or "synthetic" in source_lower
            or "demo" in source_lower
            or "FUNDFLOW_FIXTURE_DIR" in os.environ
            or mode not in {"live", "offline_snapshot"}
        )
        if synthetic:
            badge = "MODE: SYNTHETIC FIXTURE"
        elif mode == "live":
            # A manifest mode describes the materialized bundle; page rendering itself
            # performs no network fetch and does not independently prove source freshness.
            badge = "MODE: LIVE-MODE BUNDLE"
        elif mode == "offline_snapshot":
            badge = "MODE: OFFLINE SNAPSHOT"
        else:
            badge = "MODE: SOURCE UNVERIFIED"
        st.sidebar.markdown(
            f'<span class="badge-pill badge-scenario">{html.escape(badge)}</span>',
            unsafe_allow_html=True,
        )
    except Exception:
        metadata = None
        mode = "unknown"
        source = "unavailable"
        synthetic = True
        st.sidebar.markdown(
            '<span class="badge-pill badge-scenario">MODE: SOURCE UNVERIFIED</span>',
            unsafe_allow_html=True,
        )

    # Keep demo records available for interface development, but never use them
    # as financial inputs in production-facing pages.
    st.session_state["_fundflow_synthetic_bundle"] = synthetic

    st.sidebar.caption("Category research · institutional risk monitor")
    st.sidebar.divider()
    st.title(title)
    st.caption(description)

    # Never infer live verification from a label alone. The dashboard reads local
    # artifacts; it does not refresh external sources during page rendering.
    if synthetic:
        st.warning(
            "SYNTHETIC DEMO DATA · This bundle contains synthetic fixture records. "
            "Do not interpret its values as real market observations or validated forecasts."
        )
        st.caption(
            "Production readiness: BLOCKED until real, permission-cleared source data "
            "replace these fixtures and their provenance is independently validated."
        )
    elif mode == "offline_snapshot":
        st.warning(
            "OFFLINE SNAPSHOT · The dashboard is reading a local snapshot, not fetching "
            "live data. Check its observation period and source provenance before use."
        )
    elif mode == "live":
        st.info(
            "LIVE-MODE BUNDLE · The local bundle declares live mode, but this page does "
            "not perform a network refresh. Verify source URL, retrieval time, observation "
            "date, and accepted/rejected row counts in the evidence ledger."
        )
    else:
        st.warning(
            "DATA SOURCE UNVERIFIED · No verified live-data status can be established "
            "from the current bundle. Observations and derived metrics are withheld where unavailable."
        )


def stop_if_synthetic_bundle() -> bool:
    """Withhold analysis when the selected bundle is explicitly synthetic."""
    if st.session_state.get("_fundflow_synthetic_bundle", False):
        st.info(
            "Financial outputs are withheld because this bundle contains synthetic records. "
            "Select a permission-cleared, provenance-validated data bundle to continue."
        )
        return True
    return False

def _optional_numeric(value: Any, precision: int = 2) -> float | None:
    """Return a finite rounded number, or None when unavailable."""
    if value is None or isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return round(number, precision) if math.isfinite(number) else None


def _metric_can_be_negative(title: str, units: str) -> bool:
    """Classify metric sign using domain semantics, not numeric sign alone."""
    title_l, units_l = title.casefold(), units.casefold()
    nonnegative_units = ("scheme", "table", "check", "article", "observation count", "tier", "pctile", "percentile", "volatility")
    if any(x in units_l for x in nonnegative_units):
        return False
    nonnegative_titles = ("aum", "gross redemption", "redemption count", "inflow", "outflow", "volatility", "consistency", "percentile", "pctile", "shortlist count", "count", "checks", "sources", "articles", "evaluated folds", "mae", "rmse", "tracking error", "standard deviation", "variance")
    if any(x in title_l for x in nonnegative_titles):
        return False
    signed_titles = ("net flow", "return", "cagr", "drawdown", "forecast gap", "gap", "z-score", "robust z", "robust_z", "momentum", "polarity", "sentiment", "change", "delta", "excess return", "mean score")
    return any(x in title_l for x in signed_titles) or "[-1, 1]" in units_l or "[-1,1]" in units_l


def metric_card(title: str, value: Any, *, kind: str, period: str, units: str, source: str) -> None:
    """Render a metric without presenting missing/error values as financial observations."""
    if kind not in KINDS:
        raise ValueError("Metric kind must be OBSERVED, FORECAST or SCENARIO")
    if not period or not units or not source:
        raise ValueError("Metric period, units and source are required")
    shown = format_metric_display(value, units, precision=2, can_be_negative=_metric_can_be_negative(title, units))
    st.metric(f"{kind} · {title}", shown)
    st.caption(f"Period: {format_period(period)} · Provenance: {format_provenance_label(source)}")


def freshness_banner(*, as_of: str = "unavailable", period: str = "unavailable", metadata=None) -> None:
    """Render a compact freshness status strip."""
    mode_str = getattr(metadata, "mode", "unknown") if metadata else "unknown"
    source_str = getattr(metadata, "source", "unavailable") if metadata else "unavailable"
    prov_clean = format_provenance_label(source_str)

    st.info(
        f"Freshness · Period: {format_period(period)} · As of: {format_timestamp(as_of)} · "
        f"Mode: {mode_str.upper()} · Source: {prov_clean}"
    )


def selected_row(name: str):
    """Retrieve selected category row with fallback handling."""
    result = load_table(name)
    if result.frame.empty:
        freshness_banner(metadata=result.metadata)
        st.info(result.message or "No data available in the current bundle.")
        return None
    frame = result.frame
    if "category" in frame:
        category = st.selectbox("Category", sorted(frame["category"].unique()), key=f"category_{name}")
        frame = frame[frame["category"] == category]
    if frame.empty:
        st.info("No matching records found for selected category.")
        return None
    row = frame.iloc[-1]
    period = row.get("target_month", row.get("month", row.get("metric_date", row.get("period", "unavailable"))))
    timestamp = row.get("as_of", row.get("retrieved_at", row.get("published_at", "unavailable")))
    freshness_banner(as_of=timestamp, period=period, metadata=result.metadata)
    return row


# ---------------------------------------------------------------------------
# Page 1: Command Centre
# ---------------------------------------------------------------------------

def _render_command_centre():
    page_header(
        "FundFlow Sentinel — Command Centre",
        "Monitor mutual-fund flows, forecast outflows, compare model performance, and quantify risk scenarios.",
    )
    if stop_if_synthetic_bundle():
        return

    flow_res = load_table("flows_category_month")
    flow_df = flow_res.frame

    if flow_df.empty:
        freshness_banner(metadata=flow_res.metadata)
        st.info("No flow observations available in current bundle.")
        return

    categories = sorted(flow_df["category"].unique()) if "category" in flow_df.columns else []

    # 1. Global Filter Row
    st.markdown('<div class="fin-card">', unsafe_allow_html=True)
    f1, f2, f3, f4 = st.columns([2, 2, 2, 1.5])
    with f1:
        st.caption(f"Data bundle: {flow_res.metadata.source} · Mode: {flow_res.metadata.mode.upper()}")
    with f2:
        selected_cat = st.selectbox("Category Universe", categories, index=0 if categories else 0, key="cc_category")
    
    cat_df = flow_df[flow_df["category"] == selected_cat].sort_values("month") if "category" in flow_df.columns else flow_df

    with f3:
        months = cat_df["month"].tolist() if "month" in cat_df.columns else []
        selected_month = st.selectbox("Observation Period", months[::-1] if months else ["N/A"], key="cc_month")

    with f4:
        st.markdown('<div style="height: 28px;"></div>', unsafe_allow_html=True)
        if st.button("↻ Reload Local Bundle", key="cc_refresh_btn", use_container_width=True):
            # This is a local reload only; no external feed has been queried.
            st.cache_data.clear()
            st.rerun()

    st.markdown('</div>', unsafe_allow_html=True)

    row = cat_df[cat_df["month"] == selected_month].iloc[-1] if not cat_df.empty and selected_month in months else cat_df.iloc[-1] if not cat_df.empty else None
    as_of_val = row.get("available_from", row.get("as_of", "unavailable")) if row is not None else "unavailable"

    # Status Panel
    freshness_banner(as_of=as_of_val, period=selected_month, metadata=flow_res.metadata)

    # 2. Executive Metric Cards (6 Distinct Financial Cards)
    st.markdown('<div style="height: 12px;"></div>', unsafe_allow_html=True)
    st.subheader("Executive Risk & Flow Overview")

    alert_res = load_table("alerts")
    alerts_df = alert_res.frame
    cat_alert = None
    if not alerts_df.empty and "category" in alerts_df.columns:
        matching_alerts = alerts_df[alerts_df["category"] == selected_cat]
        if not matching_alerts.empty:
            cat_alert = matching_alerts.iloc[-1]

    f_rate = cat_alert.get("forecast_rate") if cat_alert is not None else None
    f_target = cat_alert.get("target_month", "N/A") if cat_alert is not None else "N/A"
    outflow_cr = cat_alert.get("est_outflow_cr") if cat_alert is not None else None
    alert_lvl = cat_alert.get("level", "Unavailable") if cat_alert is not None else "Unavailable"

    # Evaluate Actual-versus-Forecast Gap for target period
    # When target month has an actual observation in cat_df, calculate realized forecast error
    actual_target_row = cat_df[cat_df["month"] == f_target] if not cat_df.empty and f_target in months else pd.DataFrame()
    actual_target_outflow = float(actual_target_row.iloc[0]["gross_redemption_cr"]) if not actual_target_row.empty else None
    
    if actual_target_outflow is not None and outflow_cr is not None:
        try:
            forecast_outflow_value = float(outflow_cr)
            gap_info = calculate_forecast_gap(actual_target_outflow, forecast_outflow_value) if math.isfinite(forecast_outflow_value) else {"status": "unobserved", "gap": None, "abs_gap": None, "pct_error": None, "direction": "unobserved"}
        except (TypeError, ValueError, OverflowError):
            gap_info = {"status": "unobserved", "gap": None, "abs_gap": None, "pct_error": None, "direction": "unobserved"}
    else:
        gap_info = {"status": "unobserved", "gap": None, "abs_gap": None, "pct_error": None, "direction": "unobserved"}

    # Row 1: 3 Cards (Observed AUM, Observed Redemptions, Forecast Rate)
    c1, c2, c3 = st.columns(3)
    with c1:
        metric_card(
            "Closing AUM",
            row.get("aum_close_cr") if row is not None else "N/A",
            kind="OBSERVED",
            period=str(row.get("month", selected_month)) if row is not None else selected_month,
            units="₹ crore",
            source=str(row.get("source_url", "")).strip() if row is not None and str(row.get("source_url", "")).strip() else "unavailable",
        )
    with c2:
        metric_card(
            "Gross redemptions",
            row.get("gross_redemption_cr") if row is not None else "N/A",
            kind="OBSERVED",
            period=str(row.get("month", selected_month)) if row is not None else selected_month,
            units="₹ crore",
            source=str(row.get("source_url", "")).strip() if row is not None and str(row.get("source_url", "")).strip() else "unavailable",
        )
    with c3:
        metric_card(
            "Forecast redemption rate",
            f_rate if f_rate is not None else "N/A",
            kind="FORECAST",
            period=str(f_target),
            units="%",
            source="walk-forward Ridge",
        )

    # Row 2: 3 Cards (Forecast Outflow, Forecast-vs-Actual Gap, Alert Level)
    r1, r2, r3 = st.columns(3)
    with r1:
        metric_card(
            "Est. outflow",
            outflow_cr if outflow_cr is not None else "N/A",
            kind="FORECAST",
            period=str(f_target),
            units="₹ crore",
            source="baseline/ridge model",
        )
    with r2:
        if gap_info["status"] == "observed":
            gap_disp = f"{gap_info['gap']:+0.2f}"
            gap_caption = f"Abs Gap: ₹{gap_info['abs_gap']:,.2f} cr ({gap_info['direction']})"
            if gap_info['pct_error'] is not None:
                gap_caption += f" · Error: {gap_info['pct_error']}%"
        else:
            gap_disp = "N/A"
            gap_caption = "Forecast target unobserved · Outcome pending release"

        metric_card(
            "Realized outflow gap",
            gap_disp,
            kind="FORECAST",
            period=str(f_target),
            units="₹ crore",
            source="actual vs model",
        )
    with r3:
        metric_card(
            "Alert level",
            alert_lvl,
            kind="FORECAST",
            period=str(f_target),
            units="tier",
            source="risk engine",
        )

    if cat_alert is not None:
        st.caption(
            f"Risk Rule Triggers: `{cat_alert.get('rules_triggered', 'none')}` · "
            f"Robust Z-Score: `{format_number(cat_alert.get('robust_z'))}` · "
            f"Percentile Rank: `{format_number(cat_alert.get('forecast_percentile'))}%` · "
            f"Model Limitations: {cat_alert.get('limitations', 'none')}"
        )

    # 3. Historical Context & Trend Analysis (White Theme Altair Charts)
    if len(cat_df) >= 2:
        st.markdown('<div style="height: 20px;"></div>', unsafe_allow_html=True)
        st.subheader("Historical Category Flow Dynamics")
        chart_data = cat_df.tail(24).copy()

        c_left, c_right = st.columns(2)
        with c_left:
            chart_red = (
                alt.Chart(chart_data)
                .mark_area(
                    line={"color": "#15803D", "width": 2},
                    color=alt.Gradient(
                        gradient="linear",
                        stops=[
                            alt.GradientStop(color="#15803D", offset=0),
                            alt.GradientStop(color="rgba(21, 128, 61, 0.05)", offset=1),
                        ],
                        x1=1, x2=1, y1=1, y2=0,
                    ),
                )
                .encode(
                    x=alt.X("month:N", title="Observation Month", axis=alt.Axis(labelAngle=-45, labelColor="#667085", titleColor="#667085", gridColor="#F2F4F7")),
                    y=alt.Y("gross_redemption_cr:Q", title="Gross Redemptions (₹ cr)", axis=alt.Axis(labelColor="#667085", titleColor="#667085", gridColor="#F2F4F7")),
                    tooltip=[
                        alt.Tooltip("month:N", title="Month"),
                        alt.Tooltip("gross_redemption_cr:Q", title="Gross Redemptions (₹ cr)", format=",.2f"),
                        alt.Tooltip("net_flow_cr:Q", title="Net Flow (₹ cr)", format=",.2f"),
                    ],
                )
                .properties(title="Monthly Gross Redemptions Trend", height=240)
            )
            st.altair_chart(chart_red, use_container_width=True)

        with c_right:
            chart_aum = (
                alt.Chart(chart_data)
                .mark_area(
                    line={"color": "#175CD3", "width": 2},
                    color=alt.Gradient(
                        gradient="linear",
                        stops=[
                            alt.GradientStop(color="#175CD3", offset=0),
                            alt.GradientStop(color="rgba(23, 92, 211, 0.05)", offset=1),
                        ],
                        x1=1, x2=1, y1=1, y2=0,
                    ),
                )
                .encode(
                    x=alt.X("month:N", title="Observation Month", axis=alt.Axis(labelAngle=-45, labelColor="#667085", titleColor="#667085", gridColor="#F2F4F7")),
                    y=alt.Y("aum_close_cr:Q", title="Closing AUM (₹ cr)", axis=alt.Axis(labelColor="#667085", titleColor="#667085", gridColor="#F2F4F7")),
                    tooltip=[
                        alt.Tooltip("month:N", title="Month"),
                        alt.Tooltip("aum_close_cr:Q", title="Closing AUM (₹ cr)", format=",.2f"),
                    ],
                )
                .properties(title="Monthly Closing AUM Trend", height=240)
            )
            st.altair_chart(chart_aum, use_container_width=True)

    # 4. Cross-Category Risk Overview Table
    st.markdown('<div style="height: 20px;"></div>', unsafe_allow_html=True)
    st.subheader("Cross-Category Risk Overview")

    summary_rows = []
    latest_month = flow_df["month"].max() if "month" in flow_df.columns else "unavailable"
    latest_flows = flow_df[flow_df["month"] == latest_month]

    for cat in sorted(flow_df["category"].unique()):
        cf = latest_flows[latest_flows["category"] == cat]
        if cf.empty:
            continue
        c_row = cf.iloc[0]
        c_alert = (
            alerts_df[(alerts_df["category"] == cat)].iloc[-1]
            if not alerts_df.empty and len(alerts_df[alerts_df["category"] == cat]) > 0
            else None
        )

        summary_rows.append({
            "Category": cat,
            "Latest Month": str(c_row.get("month", latest_month)),
            "Closing AUM (₹ cr)": _optional_numeric(c_row.get("aum_close_cr")),
            "Gross Redemptions (₹ cr)": _optional_numeric(c_row.get("gross_redemption_cr")),
            "Forecast Rate (%)": _optional_numeric(c_alert.get("forecast_rate")) if c_alert is not None else None,
            "Target Month": str(c_alert.get("target_month", "N/A")) if c_alert is not None else "N/A",
            "Alert Level": str(c_alert.get("level", "Unavailable")) if c_alert is not None else "Unavailable",
            "Data Status": str(flow_res.status).upper(),
        })

    if summary_rows:
        sum_df = pd.DataFrame(summary_rows)
        st.dataframe(sum_df, use_container_width=True, hide_index=True)

    # 5. Provenance & Limitations Expander
    st.markdown('<div style="height: 16px;"></div>', unsafe_allow_html=True)
    with st.expander("Audit Provenance & System Limitations"):
        st.markdown(
            f"""
            - **Primary Data Source:** Official AMFI Monthly Category Flow Reports (`https://portal.amfiindia.com`)
            - **Observation Period:** {selected_month} (Release lag cutoff: {as_of_val})
            - **Data Integrity Mode:** {flow_res.metadata.mode.upper()} ({flow_res.metadata.source})
            - **Forecast Model:** 1-step ahead walk-forward Ridge regression with expanding warmup
            - **Gap Definition:** Gap = Actual Outflow − Forecast Outflow. Positive values indicate underprediction; negative indicate overprediction.
            - **Limitations:** Category redemption pressure forecasts do not represent scheme-level liquidation claims.
            """
        )


def command_centre():
    safe_page_boundary("Command Centre", _render_command_centre)


# ---------------------------------------------------------------------------
# Page 2: Forecast Lab (Phase 4 User-Defined Forecasting)
# ---------------------------------------------------------------------------

def _render_forecast_lab():
    page_header(
        "Forecast Lab",
        "Configure custom quantitative models, compare out-of-sample performance, and evaluate empirical prediction intervals.",
    )
    if stop_if_synthetic_bundle():
        return
    flow_res = load_table("flows_category_month")
    freshness_banner(as_of="2024-09-30", period="v1", metadata=flow_res.metadata)

    if flow_res.frame.empty:
        st.info("No flow observations available in current bundle.")
        st.info("Uncertainty Governance Policy: INSUFFICIENT_HISTORY. Empirical P10/P90 uncertainty bands require at least 10 prior out-of-sample forecast residuals.")
        return

    # 1. Interactive User-Defined Forecast Configuration Panel
    st.subheader("User-Defined Forecast Configuration")
    
    with st.container():
        st.markdown('<div class="fin-card">', unsafe_allow_html=True)
        col1, col2, col3 = st.columns(3)
        with col1:
            dataset_choice = st.selectbox(
                "Dataset",
                ["AMFI Category Flows (Monthly)", "Scheme NAV History (Daily)"],
                key="fl_dataset_choice",
            )
        
        # Load dataset according to selection
        if "NAV" in dataset_choice:
            nav_res = load_table("nav_daily")
            data_df = nav_res.frame
            date_col = "date"
            supported_targets = ["nav"]
            target_labels = {"nav": "Net Asset Value (NAV)"}
            schemes = sorted(data_df["scheme_code"].unique().tolist()) if not data_df.empty and "scheme_code" in data_df.columns else ["119551"]
            with col2:
                target_choice = st.selectbox("Forecast Target", supported_targets, format_func=lambda x: target_labels.get(x, x), key="fl_target_choice")
            with col3:
                entity_choice = st.selectbox("Scheme Code", schemes, key="fl_entity_choice")
            sub_df = data_df[data_df["scheme_code"] == entity_choice] if not data_df.empty and "scheme_code" in data_df.columns else data_df
        else:
            flow_res = load_table("flows_category_month")
            data_df = flow_res.frame
            date_col = "month"
            supported_targets = ["gross_redemption_cr", "net_flow_cr", "redemption_rate", "aum_close_cr"]
            target_labels = {
                "gross_redemption_cr": "Gross Redemptions (₹ cr)",
                "net_flow_cr": "Net Flows (₹ cr)",
                "redemption_rate": "Redemption Rate (%)",
                "aum_close_cr": "Closing AUM (₹ cr)",
            }
            cats = sorted(data_df["category"].unique().tolist()) if not data_df.empty and "category" in data_df.columns else ["Equity Scheme - Large Cap Fund"]
            with col2:
                target_choice = st.selectbox("Forecast Target", supported_targets, format_func=lambda x: target_labels.get(x, x), key="fl_target_choice")
            with col3:
                entity_choice = st.selectbox("Category", cats, key="fl_entity_choice")
            sub_df = data_df[data_df["category"] == entity_choice] if not data_df.empty and "category" in data_df.columns else data_df

        row2_col1, row2_col2, row2_col3 = st.columns(3)
        with row2_col1:
            horizon_choice = st.selectbox("Forecast Horizon", [1, 3, 6, 12], format_func=lambda h: f"{h} Step{'s' if h > 1 else ''} Ahead", key="fl_horizon")
        with row2_col2:
            models_choice = st.multiselect(
                "Models to Compare",
                ["persistence", "seasonal_naive", "ridge"],
                default=["persistence", "seasonal_naive", "ridge"],
                format_func=lambda m: {"persistence": "Persistence Baseline", "seasonal_naive": "Seasonal Naive", "ridge": "Ridge Regression"}.get(m, m),
                key="fl_models",
            )
        with row2_col3:
            eval_method = st.selectbox("Evaluation Method", ["Walk-Forward Expanding Window (Zero-Leakage)"], key="fl_eval_method")

        run_clicked = st.button("Run Forecast Comparison", type="primary", key="fl_run_btn")
        st.markdown('</div>', unsafe_allow_html=True)

    # 2. Run User Forecast Engine
    if not models_choice:
        models_choice = ["persistence", "ridge"]

    user_results = run_user_forecast(
        sub_df,
        target_col=target_choice,
        date_col=date_col,
        horizon=horizon_choice,
        models=models_choice,
        min_train_obs=6,
    )

    # 3. Output Metric Strip
    st.markdown('<div style="height: 16px;"></div>', unsafe_allow_html=True)
    st.subheader(f"Out-of-Sample Forecast Output — {target_labels.get(target_choice, target_choice)}")

    m_forecasts = user_results.get("model_forecasts", {})
    if m_forecasts:
        cols = st.columns(len(m_forecasts))
        for idx, (m_name, m_data) in enumerate(m_forecasts.items()):
            with cols[idx]:
                metric_card(
                    f"{m_name.replace('_', ' ').title()}",
                    m_data["value"],
                    kind="FORECAST",
                    period=f"+{horizon_choice} steps",
                    units="pts",
                    source=m_data.get("method", "user model"),
                )

    # 4. Out-of-Sample Performance Comparison Table
    comp_df = user_results.get("comparison_table", pd.DataFrame())
    if not comp_df.empty:
        st.markdown('<div style="height: 16px;"></div>', unsafe_allow_html=True)
        st.write("**Model Evaluation & Benchmark Comparison (Out-of-Sample)**")
        st.dataframe(comp_df, use_container_width=True, hide_index=True)

    # 5. Precomputed Diagnostics & Protocol Status
    st.divider()
    st.subheader("Model Performance Diagnostics (Protocol Baseline)")
    mr = load_model_results()
    if mr.payload and "metrics" in mr.payload and mr.payload["metrics"]:
        m = mr.payload["metrics"]
        st.write(f"**Ridge MAE:** {m.get('ridge_mae', 'N/A')} pp · **Persistence MAE:** {m.get('persistence_mae', 'N/A')} pp")
        st.write(f"**Ridge Beat Fraction:** {m.get('ridge_beat_fraction', 'N/A')} · **Evaluated Folds:** {m.get('n_predictions', 0)}")
        if mr.payload.get("limitations"):
            for lim in mr.payload["limitations"]:
                st.warning(f"Protocol limitation: {lim}")
    else:
        st.info("Detailed model results unavailable in current bundle.")

    # 6. Empirical Uncertainty Bands & Governance Policy
    st.divider()
    st.subheader("Empirical Uncertainty Bands")
    pred_res = load_table("predictions")
    pred_df = pred_res.frame
    bands = None

    if not pred_df.empty:
        cat_preds = pred_df[pred_df["category"] == entity_choice] if entity_choice and "category" in pred_df.columns else pred_df
        try:
            if not cat_preds.empty:
                pred_rate = pd.to_numeric(cat_preds.iloc[-1].get("predicted_rate"), errors="coerce")
                as_of_val = str(cat_preds.iloc[-1].get("as_of", "")).strip()
                if pd.notna(pred_rate) and math.isfinite(float(pred_rate)) and as_of_val and as_of_val.lower() not in {"none", "nan", "n/a", "unavailable"}:
                    bands = compute_empirical_residual_bands(cat_preds, current_as_of=as_of_val, predicted_rate=float(pred_rate))
                    if bands.get("band_status") != "ok" and len(pred_df) >= 10:
                        bands = compute_empirical_residual_bands(pred_df, current_as_of=as_of_val, predicted_rate=float(pred_rate))
        except Exception:
            bands = None

    if bands and bands.get("band_status") == "ok":
        st.success(f"Empirical Residual Bands Active ({bands.get('residual_count', 0)} out-of-sample residuals, span {bands.get('residual_date_range', '')})")
        b1, b2, b3 = st.columns(3)
        with b1:
            metric_card("Lower bound (P10)", bands["lower_band"], kind="SCENARIO", period="1M", units="%", source="empirical quantile")
        with b2:
            metric_card("Point forecast", bands.get("predicted_rate"), kind="FORECAST", period="1M", units="%", source="Ridge regression")
        with b3:
            metric_card("Upper bound (P90)", bands["upper_band"], kind="SCENARIO", period="1M", units="%", source="empirical quantile")
        st.caption(f"Offsets: P10 offset = {bands.get('q10_offset')} pp, P90 offset = +{bands.get('q90_offset')} pp relative to point forecast.")
        st.info("Uncertainty Governance Policy: Bands require >= 10 out-of-sample residuals. Any category with fewer observations is classified as INSUFFICIENT_HISTORY and withheld.")
    else:
        st.info(
            "Band Status: INSUFFICIENT_HISTORY. Empirical P10/P90 uncertainty bands require at least 10 prior out-of-sample forecast residuals. "
            "When operating on sample history with fewer than 10 evaluated folds, uncertainty intervals are honestly withheld to prevent statistical fabrication."
        )


def forecast_lab():
    safe_page_boundary("Forecast Lab", _render_forecast_lab)


# ---------------------------------------------------------------------------
# Page 3: Sentiment Monitor
# ---------------------------------------------------------------------------

def _render_sentiment_monitor():
    page_header("Sentiment Monitor", "Context only; sentiment does not drive forecasts or fund scores.")
    if stop_if_synthetic_bundle():
        return
    row = selected_row("sentiment_agg")

    if row is not None:
        c1, c2, c3 = st.columns(3)
        with c1:
            metric_card("Negative share", row["neg_share"], kind="OBSERVED", period=str(row["period"]), units="fraction", source=f"sentiment engine · {row.get('topic', 'all')}")
        with c2:
            metric_card("Mean score", row["mean_score"], kind="OBSERVED", period=str(row["period"]), units="score [-1, 1]", source="sentiment engine")
        with c3:
            metric_card("Article count", row["n_articles"], kind="OBSERVED", period=str(row["period"]), units="articles", source="feed aggregator")
        st.caption(f"Topic: {row.get('topic', 'all')} · Mode: {'LIVE' if row.get('is_live') else 'SNAPSHOT'}")

    st.divider()
    st.subheader("Data Sufficiency & Source Distinction")
    st.info(
        "Source Distinction Mandate: RSS headline sentiment (lexical analysis) reflects immediate media tone, "
        "whereas GDELT represents broad macro media tone. They are distinct measurements and never merged."
    )

    items_res = load_table("sentiment_items")
    items_df = items_res.frame

    if not items_df.empty:
        st.markdown('<div style="height: 16px;"></div>', unsafe_allow_html=True)
        st.subheader("Recent Financial Headlines & Media Intelligence")
        display_items = items_df.tail(8)
        for _, item in display_items.iterrows():
            title_clean = sanitize_display_text(item.get("title", "Headline unavailable"))
            # The frozen sentiment_items contract calls this field "score". Missing
            # values remain unavailable; they must not be represented as neutral zero.
            score_val = item.get("score")
            try:
                parsed_score = float(score_val) if score_val not in (None, "") else float("nan")
                score_num = parsed_score if math.isfinite(parsed_score) else None
            except (TypeError, ValueError, OverflowError):
                score_num = None
            badge_class = "badge-critical" if score_num is not None and score_num < -0.2 else "badge-forecast" if score_num is not None and score_num > 0.2 else "badge-normal"
            score_label = f"SCORE: {score_num:+.2f}" if score_num is not None else "SCORE: N/A"
            source_url = safe_url(item.get("url"))

            link_html = f'<a href="{source_url}" target="_blank" style="color: #175CD3; text-decoration: none;">🔗 Source</a>' if source_url else '<span style="color: #98A2B3;">Direct feed</span>'

            st.markdown(
                f"""
                <div class="fin-card" style="padding: 14px 18px; margin-bottom: 10px;">
                    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px;">
                        <span class="badge-pill {badge_class}">{score_label}</span>
                        <span style="font-size: 11px; color: #98A2B3;">{item.get('published_at', '')[:10]} · {link_html}</span>
                    </div>
                    <div style="font-size: 14px; font-weight: 600; color: #172033; line-height: 1.4;">
                        {title_clean}
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )


def sentiment_monitor():
    safe_page_boundary("Sentiment Monitor", _render_sentiment_monitor)


# ---------------------------------------------------------------------------
# Page 4: Fund Research
# ---------------------------------------------------------------------------

def _render_fund_research():
    page_header("Fund Research", "Transparent percentile shortlist across active mutual fund schemes.")
    if stop_if_synthetic_bundle():
        return

    sl_res = load_table("shortlist")
    sl_df = sl_res.frame

    if sl_df.empty:
        freshness_banner(metadata=sl_res.metadata)
        st.info("No scheme research shortlist records available in current bundle.")
        return

    # Invariant: Survivorship Bias Disclosure
    st.markdown(
        """
        > **Regulatory Disclosure: Survivorship Bias Warning**  
        > Mutual fund return and consistency percentiles are computed across currently active schemes in the AMFI registry. 
        > Merged, renamed, or liquidated historical schemes may not appear in current historical NAV files.
        """
    )

    as_of_val = sl_df["as_of"].max() if "as_of" in sl_df.columns else "unavailable"
    period_val = sl_df["period"].max() if "period" in sl_df.columns else "unavailable"
    freshness_banner(as_of=as_of_val, period=period_val, metadata=sl_res.metadata)

    m1, m2, m3 = st.columns(3)
    with m1:
        metric_card("Shortlist count", len(sl_df), kind="OBSERVED", period=str(period_val), units="schemes", source="shortlist rule")
    with m2:
        min_ret = sl_df["p_return"].min() if "p_return" in sl_df.columns else None
        metric_card("Min 3Y Return", min_ret, kind="OBSERVED", period=str(period_val), units="pctile", source="AMFI NAV 36M")
    with m3:
        max_ret = sl_df["p_return"].max() if "p_return" in sl_df.columns else None
        metric_card("Max 3Y Return", max_ret, kind="OBSERVED", period=str(period_val), units="pctile", source="AMFI NAV 36M")

    st.markdown('<div style="height: 16px;"></div>', unsafe_allow_html=True)
    st.subheader("Eligible Fund Shortlist Candidates")

    display_cols = [c for c in ["scheme_code", "p_return", "p_consistency", "p_drawdown", "p_risk_adj", "eligible"] if c in sl_df.columns]
    st.dataframe(sl_df[display_cols], use_container_width=True, hide_index=True)


def fund_research():
    safe_page_boundary("Fund Research", _render_fund_research)


# ---------------------------------------------------------------------------
# Page 5: Stress Lab
# ---------------------------------------------------------------------------

def _render_stress_lab():
    page_header("Stress Lab", "Scenario stress testing across category redemption outflow shocks.")
    if stop_if_synthetic_bundle():
        return

    flow_res = load_table("flows_category_month")
    flow_df = flow_res.frame

    if flow_df.empty:
        freshness_banner(metadata=flow_res.metadata)
        st.info("No flow records available for scenario modeling.")
        return

    # Invariant: INSUFFICIENT_HISTORY warning
    st.warning("INSUFFICIENT_HISTORY: Tail risk models require 36+ months history; currently evaluated under diagnostic historical multipliers.")

    categories = sorted(flow_df["category"].unique()) if "category" in flow_df.columns else []
    sel_cat = st.selectbox("Category to Stress", categories, key="stress_cat")

    cat_df = flow_df[flow_df["category"] == sel_cat].sort_values("month") if "category" in flow_df.columns else flow_df
    latest_row = cat_df.iloc[-1] if not cat_df.empty else None
    raw_aum = latest_row.get("aum_close_cr") if latest_row is not None else None
    latest_month = str(latest_row.get("month", "")).strip() if latest_row is not None else ""
    ref_aum = _optional_numeric(raw_aum)
    if ref_aum is None or ref_aum <= 0 or not latest_month or latest_month.lower() in {"none", "nan", "n/a", "unavailable"}:
        freshness_banner(as_of="unavailable", period=latest_month or "unavailable", metadata=flow_res.metadata)
        st.warning("Stress scenarios are unavailable because a valid reference AUM observation and period are missing.")
        return
    freshness_banner(as_of=latest_month, period=latest_month, metadata=flow_res.metadata)
    scenarios = scenario_table(ref_aum)
    severe_rows = scenarios[scenarios["scenario_name"] == "severe"] if "scenario_name" in scenarios.columns else pd.DataFrame()
    sev_out = _optional_numeric(severe_rows.iloc[0].get("est_outflow_cr")) if not severe_rows.empty else None
    share_pct = round((sev_out / ref_aum) * 100.0, 2) if sev_out is not None and ref_aum > 0 else None
    c1, c2, c3 = st.columns(3)
    with c1:
        metric_card("Category AUM", ref_aum, kind="OBSERVED", period=latest_month, units="₹ crore", source="validated flow bundle")
    with c2:
        metric_card("Severe stress outflow", sev_out, kind="SCENARIO", period=latest_month, units="₹ crore", source="stress scenario engine")
    with c3:
        metric_card("Outflow share", share_pct, kind="SCENARIO", period=latest_month, units="%", source="scenario ratio")

    st.markdown('<div style="height: 20px;"></div>', unsafe_allow_html=True)
    st.subheader("Multi-Scenario Redemption Outflow Breakdown")

    # Altair Bar Chart for Scenarios
    bar_chart = (
        alt.Chart(scenarios)
        .mark_bar(cornerRadiusTopLeft=4, cornerRadiusTopRight=4, color="#15803D")
        .encode(
            x=alt.X("scenario_name:N", title="Stress Scenario", sort=None, axis=alt.Axis(labelAngle=-30, labelColor="#667085", titleColor="#667085")),
            y=alt.Y("est_outflow_cr:Q", title="Estimated Outflow (₹ crore)", axis=alt.Axis(labelColor="#667085", titleColor="#667085", gridColor="#F2F4F7")),
            tooltip=[
                alt.Tooltip("scenario_name:N", title="Scenario"),
                alt.Tooltip("est_outflow_cr:Q", title="Estimated Outflow (₹ cr)", format=",.2f"),
                alt.Tooltip("description:N", title="Assumptions"),
            ],
        )
        .properties(height=260)
    )
    st.altair_chart(bar_chart, use_container_width=True)

    st.dataframe(scenarios, use_container_width=True, hide_index=True)


def stress_lab():
    safe_page_boundary("Stress Lab", _render_stress_lab)


# ---------------------------------------------------------------------------
# Page 6: Evidence & Limitations
# ---------------------------------------------------------------------------

def _render_evidence_and_limits():
    page_header("Evidence and Limits", "Registered public data sources, quality checks, and redistribution boundaries.")

    # Invariant: STRICT REDISTRIBUTION POLICY warning
    st.warning("STRICT REDISTRIBUTION POLICY: Commercial redistribution of third-party public data files without licensing is prohibited.")

    qr = load_quality_metadata()
    sr = load_source_metadata()

    if qr.status != "ok":
        st.error(qr.message or "Quality report unavailable; no current quality result can be shown.")
    if sr.status != "ok":
        st.error(sr.message or "Source registry metadata unavailable.")

    synthetic_bundle = st.session_state.get("_fundflow_synthetic_bundle", False)
    if qr.status == "ok" and qr.payload and not synthetic_bundle:
        c1, c2, c3 = st.columns(3)
        with c1:
            metric_card("Checks in report", len(qr.payload.get("checks", [])), kind="OBSERVED", period=qr.metadata.generated_at or "unavailable", units="checks", source=qr.metadata.source)
        with c2:
            metric_card("Registered sources", len(sr.payload.get("sources", [])) if sr.payload and "sources" in sr.payload else "Unavailable", kind="OBSERVED", period=sr.metadata.generated_at or "unavailable", units="sources", source=sr.metadata.source)
        with c3:
            status_val = qr.payload.get("status", "unknown") if qr.payload else "unknown"
            metric_card("Recorded check status", status_val.upper(), kind="OBSERVED", period=qr.metadata.generated_at or "unavailable", units="status", source=qr.metadata.source)

    if synthetic_bundle:
        st.warning("The available audit bundle describes synthetic demo records. Its PASS labels do not establish real-source validation.")
    freshness_banner(as_of=qr.metadata.generated_at or "unavailable", period=qr.metadata.last_period or "unavailable", metadata=qr.metadata)

    st.markdown('<div style="height: 16px;"></div>', unsafe_allow_html=True)
    st.subheader("Data Quality Checks & Verification Status")
    if qr.payload and "checks" in qr.payload:
        checks_df = pd.DataFrame(qr.payload["checks"])
        if synthetic_bundle and "status" in checks_df:
            checks_df["status"] = "not evidence for live data"
        st.dataframe(checks_df, use_container_width=True, hide_index=True)

    st.markdown('<div style="height: 16px;"></div>', unsafe_allow_html=True)
    st.subheader("Registered Public Data Sources & Licenses")
    if sr.payload and "sources" in sr.payload:
        src_df = pd.DataFrame(sr.payload["sources"])
        st.dataframe(src_df, use_container_width=True, hide_index=True)


def evidence_and_limits():
    safe_page_boundary("Evidence and Limits", _render_evidence_and_limits)
