from __future__ import annotations

import pandas as pd
import streamlit as st

from fundflow.data_sources import fetch_amfi_nav, unavailable_flows

st.set_page_config(
    page_title="FundFlow Sentinel",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
:root { color-scheme: light; }
.stApp { background: #f6f8fb; color: #172033; }
section[data-testid="stSidebar"] { background: #ffffff; border-right: 1px solid #e4e7ec; }
.block-container { max-width: 1500px; padding-top: 2rem; padding-bottom: 3rem; }
div[data-testid="stMetric"] { background:#fff; border:1px solid #e4e7ec; border-radius:12px; padding:16px 18px; }
div[data-testid="stAlert"] { border-radius:10px; }
.small-muted { color:#667085; font-size:.88rem; }
</style>
""", unsafe_allow_html=True)

PAGES = [
    "Command Centre", "Forecast Lab", "Sentiment Monitor",
    "Fund Research", "Stress Lab", "Evidence & Limits",
]
with st.sidebar:
    st.title("FundFlow Sentinel")
    st.caption("Indian mutual-fund flow research · transparent data provenance")
    page = st.radio("Navigation", PAGES, label_visibility="collapsed")
    st.divider()
    st.caption("DATA POLICY")
    st.caption("No synthetic production observations. Missing data stays missing.")

st.title(page)
descriptions = {
    "Command Centre": "Monitor observed industry flows, forecast outputs, and source freshness.",
    "Forecast Lab": "Configure targets and evaluate forecasts only when sufficient dated observations exist.",
    "Sentiment Monitor": "Media tone is contextual evidence; it does not drive forecasts or fund scores.",
    "Fund Research": "Explore scheme NAV observations. Performance and risk metrics require a genuine historical NAV series.",
    "Stress Lab": "Scenario analysis is only available when observed inputs and a documented calibration exist.",
    "Evidence & Limits": "Review source provenance, data quality, licensing, and model limitations.",
}
st.write(descriptions[page])

if "nav_data" not in st.session_state:
    st.session_state.nav_data = pd.DataFrame()
if "nav_status" not in st.session_state:
    st.session_state.nav_status = None
if "flow_data" not in st.session_state:
    st.session_state.flow_data = pd.DataFrame()
if "flow_status" not in st.session_state:
    st.session_state.flow_status = None

def freshness(status):
    if not status:
        st.info("Data has not been refreshed in this session.")
        return
    label = status.status.upper()
    st.info(
        f"**{status.source}** · Status: **{label}** · "
        f"Retrieved (UTC): {status.retrieved_at_utc} · "
        f"HTTP: {status.http_status if status.http_status is not None else 'N/A'} · "
        f"Records accepted: {status.records_accepted}"
    )
    st.caption(status.message)
    st.caption(f"Source: {status.url}")

def refresh_all():
    with st.spinner("Fetching official sources…"):
        nav, nav_status = fetch_amfi_nav()
        flows, flow_status = unavailable_flows()
        st.session_state.nav_data = nav
        st.session_state.nav_status = nav_status.as_dict()
        st.session_state.flow_data = flows
        st.session_state.flow_status = flow_status.as_dict()

def status_obj(raw):
    if raw is None:
        return None
    from fundflow.data_sources import SourceStatus
    return SourceStatus(**raw)

with st.container(border=True):
    st.subheader("Data refresh")
    st.write("Refresh official source data. Failed or unsupported sources remain explicitly unavailable; cached or demo data is never silently substituted.")
    if st.button("↻ Refresh official sources", type="primary"):
        refresh_all()

if page == "Command Centre":
    st.subheader("Executive risk & flow overview")
    st.warning("Industry-flow data is currently unavailable until the official monthly AMFI report parser is verified. No demo figures are shown.")
    c1, c2, c3 = st.columns(3)
    c1.metric("Observed closing AUM", "N/A")
    c2.metric("Observed gross redemptions", "N/A")
    c3.metric("Forecast redemption rate", "N/A")
    c4, c5, c6 = st.columns(3)
    c4.metric("Forecast outflow", "N/A")
    c5.metric("Realized forecast gap", "N/A")
    c6.metric("Alert level", "Unavailable")
    st.caption("Forecast target: N/A · A realized gap is calculated only after the target-period actual is observed.")
    st.subheader("Historical category flow dynamics")
    st.info("No observed monthly-flow series is available. Charts are withheld rather than populated with synthetic data.")
    st.subheader("Cross-category risk overview")
    st.dataframe(pd.DataFrame(columns=[
        "Category", "Latest observed month", "Closing AUM (₹ crore)",
        "Gross redemptions (₹ crore)", "Forecast rate (%)",
        "Target month", "Alert level", "Data status"
    ]), use_container_width=True, hide_index=True)

elif page == "Forecast Lab":
    st.subheader("User-defined forecast")
    dataset = st.selectbox("Dataset", ["AMFI category flows (monthly)", "Scheme NAV snapshot (daily)"])
    if dataset.startswith("AMFI"):
        st.warning("Unavailable: a verified historical monthly category-flow series is required before fitting or evaluating a model.")
    else:
        st.warning("AMFI NAVAll is a current snapshot, not a dated historical time series. Multi-step forecasting and walk-forward validation are disabled until historical NAV observations are sourced.")
    target = st.selectbox("Forecast target", ["Gross redemptions (₹ crore)", "Net flows (₹ crore)", "Redemption rate (%)", "Closing AUM (₹ crore)", "NAV"])
    horizon = st.selectbox("Forecast horizon", [1, 3, 6, 12], index=0, format_func=lambda x: f"{x} step(s)")
    models = st.multiselect("Models", ["Persistence baseline", "Seasonal naive", "Ridge regression"], default=["Persistence baseline", "Ridge regression"])
    st.caption(f"Selected target: {target} · Horizon: {horizon} · Models: {', '.join(models) or 'None'}")
    st.info("Forecasts and residual intervals will appear only after sufficient real observations and leakage-safe walk-forward validation are available. No fabricated forecast is displayed.")

elif page == "Sentiment Monitor":
    st.subheader("Data sufficiency & source distinction")
    st.info("Dataset is empty; no values are displayed.")
    st.write("RSS headline sentiment (lexical analysis) and GDELT macro-media tone are distinct measures and must never be merged.")
    st.metric("Live articles in last 14 days", "N/A")
    st.metric("Negative share", "N/A")
    st.caption("Sentiment corroboration requires at least 30 live articles in the last 14 days and a historical threshold. Until both exist, sentiment status is unavailable.")

elif page == "Fund Research":
    st.subheader("Current AMFI scheme NAV snapshot")
    st.warning("A current NAV snapshot alone cannot support 3-year returns, volatility, drawdown, Sortino ratio, or rolling consistency. Those metrics require real historical NAV observations.")
    freshness(status_obj(st.session_state.nav_status))
    nav = st.session_state.nav_data
    if not nav.empty:
        query = st.text_input("Search scheme name or code")
        shown = nav
        if query:
            mask = nav["scheme_name"].astype(str).str.contains(query, case=False, na=False) | nav["scheme_code"].astype(str).str.contains(query, na=False)
            shown = nav.loc[mask]
        st.metric("Live schemes received", f"{len(nav):,}")
        st.dataframe(shown, use_container_width=True, hide_index=True)
    else:
        st.info("No NAV observations loaded. Select Refresh official sources above.")
    st.caption("Current active-scheme rankings have survivorship bias. Historical comparisons must include merged and liquidated schemes where licensed data is available.")

elif page == "Stress Lab":
    st.subheader("Scenario stress testing")
    st.warning("Unavailable until a validated flow forecast/residual distribution and an observed reference AUM are available.")
    st.write("AUM is not redemption capacity, cash available to redeem, or a proxy for underlying holdings liquidity.")
    st.dataframe(pd.DataFrame([
        {"Scenario": "Base forecast", "Estimated outflow": "N/A", "Status": "Unavailable", "Reason": "No validated forecast"},
        {"Scenario": "Residual P10 / P90", "Estimated outflow": "N/A", "Status": "Unavailable", "Reason": "No out-of-sample residual history"},
        {"Scenario": "Moderate / severe stress", "Estimated outflow": "N/A", "Status": "Unavailable", "Reason": "No validated baseline and reference AUM"},
        {"Scenario": "Historical maximum", "Estimated outflow": "N/A", "Status": "Unavailable", "Reason": "Insufficient historical observations"},
    ]), use_container_width=True, hide_index=True)

elif page == "Evidence & Limits":
    st.subheader("Source status")
    freshness(status_obj(st.session_state.flow_status))
    freshness(status_obj(st.session_state.nav_status))
    st.subheader("Registered sources")
    st.dataframe(pd.DataFrame([
        {"Source": "AMFI monthly industry reports", "Data": "Monthly category-level flows/AUM", "Status": "Not yet parsed/verified", "URL": "https://www.amfiindia.com/research-information/amfi-monthly"},
        {"Source": "AMFI NAVAll", "Data": "Current scheme NAV snapshot", "Status": "Fetched only after refresh", "URL": "https://portal.amfiindia.com/spages/NAVAll.txt"},
        {"Source": "AMFI NAV download/history", "Data": "Potential historical NAV source", "Status": "Historical-series adapter not verified", "URL": "https://www.amfiindia.com/net-asset-value/nav-download"},
    ]), use_container_width=True, hide_index=True)
    st.subheader("Financial definitions")
    with st.expander("What the metrics mean"):
        st.markdown("""
        - **Gross redemptions:** observed redemption value reported for the industry category and period.
        - **Net flow:** subscriptions less redemptions, using the source's documented definition.
        - **Redemption rate:** gross redemptions divided by a clearly defined, time-aligned AUM denominator; never infer an undocumented denominator.
        - **Forecast gap:** actual minus forecast, computed only after the actual for that target period exists.
        - **Stress outflow:** scenario estimate based on disclosed assumptions; not a prediction of scheme liquidity or investor behaviour.
        - **N/A versus zero:** N/A means unavailable/not observed; zero is shown only when a source explicitly reports zero.
        """)
    st.subheader("Research limitations")
    st.markdown("""
    - Industry-level flow data must not be attributed to individual mutual-fund schemes.
    - The AMFI NAVAll feed is a current snapshot and must not be presented as historical NAV history.
    - Forecasts are not investment advice and must include held-out-period metrics and uncertainty.
    - Do not claim a source is verified, a deployment is live, or tests passed unless the corresponding evidence exists.
    - Respect source terms and licensing; do not redistribute restricted datasets without permission.
    """)

st.divider()
st.caption("FundFlow Sentinel · Research prototype · Observed, forecast, and scenario values must remain visibly distinct.")
