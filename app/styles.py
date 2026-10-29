"""Institutional design tokens and centralized CSS styling for FundFlow Sentinel.

Provides:
- Premium, white-theme financial analytics interface.
- Strict spacing tokens (8px scale) and typography scale with tabular numerals.
- Institutional color tokens for observed, forecast, scenario, and risk alert levels.
"""
from __future__ import annotations

# Centralized design tokens (Phase 2 White Theme)
COLORS = {
    "app_bg": "#F7F9FC",
    "sidebar_bg": "#FFFFFF",
    "surface": "#FFFFFF",
    "card_bg": "#FFFFFF",
    "border": "#E4E7EC",
    "border_light": "#F2F4F7",
    "text_primary": "#172033",
    "text_secondary": "#667085",
    "text_muted": "#98A2B3",
    "primary_green": "#15803D",
    "light_green": "#ECFDF3",
    "info_blue": "#175CD3",
    "warning_amber": "#B54708",
    "critical_red": "#B42318",
}

SPACING = {
    "space_1": "4px",
    "space_2": "8px",
    "space_3": "12px",
    "space_4": "16px",
    "space_5": "20px",
    "space_6": "24px",
    "space_8": "32px",
    "space_10": "40px",
    "space_12": "48px",
}

GLOBAL_CSS = """
<style>
/* 1. Global Reset & Typography */
html, body, [class*="css"] {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
    color: #172033;
    -webkit-font-smoothing: antialiased;
}

/* Force Tabular Numerals for Financial Accuracy */
.tabular-nums, [data-testid="stMetricValue"], [data-testid="stDataFrame"] {
    font-variant-numeric: tabular-nums;
    font-feature-settings: "tnum";
}

/* Main Content Container Max-Width */
.main .block-container {
    max-width: 1440px !important;
    padding-top: 1.5rem !important;
    padding-bottom: 3rem !important;
    padding-left: 2rem !important;
    padding-right: 2rem !important;
}

/* 2. Sidebar Styling */
[data-testid="stSidebar"] {
    background-color: #FFFFFF !important;
    border-right: 1px solid #E4E7EC !important;
}

[data-testid="stSidebar"] .block-container {
    padding-top: 1.5rem !important;
    padding-left: 1rem !important;
    padding-right: 1rem !important;
}

/* Sidebar Nav Items */
[data-testid="stSidebarNav"] li {
    margin-bottom: 8px !important;
}

[data-testid="stSidebarNav"] a {
    min-height: 42px !important;
    display: flex !important;
    align-items: center !important;
    border-radius: 6px !important;
    padding: 10px 16px !important;
    color: #667085 !important;
    font-size: 14px !important;
    font-weight: 500 !important;
    transition: all 0.15s ease-in-out !important;
}

[data-testid="stSidebarNav"] a:hover {
    background-color: #F8F9FC !important;
    color: #172033 !important;
}

[data-testid="stSidebarNav"] a[aria-current="page"] {
    background-color: #ECFDF3 !important;
    color: #15803D !important;
    font-weight: 600 !important;
    border-left: 3px solid #15803D !important;
}

/* 3. Custom Financial Card Components */
.fin-card {
    background-color: #FFFFFF;
    border: 1px solid #E4E7EC;
    border-radius: 8px;
    padding: 20px;
    margin-bottom: 16px;
    box-shadow: 0 1px 3px rgba(16, 24, 40, 0.05);
}

.fin-card-elevated {
    background-color: #FFFFFF;
    border: 1px solid #D0D5DD;
    border-radius: 8px;
    padding: 20px;
    margin-bottom: 16px;
    box-shadow: 0 4px 6px -1px rgba(16, 24, 40, 0.08), 0 2px 4px -2px rgba(16, 24, 40, 0.04);
}

.fin-card-title {
    font-size: 13px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    color: #667085;
    margin-bottom: 8px;
    display: flex;
    align-items: center;
    justify-content: space-between;
}

.fin-card-value {
    font-size: 28px;
    font-weight: 700;
    color: #172033;
    font-variant-numeric: tabular-nums;
    line-height: 1.2;
    margin-bottom: 6px;
}

.fin-card-caption {
    font-size: 12px;
    color: #98A2B3;
    line-height: 1.3;
}

/* 4. Classification Pill Badges */
.badge-pill {
    display: inline-flex;
    align-items: center;
    padding: 3px 8px;
    border-radius: 12px;
    font-size: 11px;
    font-weight: 600;
    letter-spacing: 0.02em;
}

.badge-observed {
    background-color: #EFF8FF;
    color: #175CD3;
    border: 1px solid #B2DDFF;
}

.badge-forecast {
    background-color: #ECFDF3;
    color: #15803D;
    border: 1px solid #A6F4C5;
}

.badge-scenario {
    background-color: #FEF0C7;
    color: #B54708;
    border: 1px solid #FEDF89;
}

.badge-normal {
    background-color: #ECFDF3;
    color: #15803D;
    border: 1px solid #15803D;
}

.badge-elevated {
    background-color: #FEF0C7;
    color: #B54708;
    border: 1px solid #B54708;
}

.badge-critical {
    background-color: #FEF3F2;
    color: #B42318;
    border: 1px solid #B42318;
}

/* 5. Institutional Streamlit Alerts & Integrity Banners */
[data-testid="stAlert"] {
    padding: 12px 16px !important;
    border-radius: 6px !important;
    border: 1px solid #E4E7EC !important;
    background-color: #FFFFFF !important;
    color: #172033 !important;
    font-size: 13px !important;
    box-shadow: 0 1px 2px rgba(16, 24, 40, 0.05) !important;
    margin-bottom: 20px !important;
}

[data-testid="stAlert"] [data-testid="stMarkdownContainer"] p {
    font-size: 13px !important;
    font-weight: 500 !important;
    line-height: 1.4 !important;
    color: #172033 !important;
}

/* 6. Form Controls & Selectboxes */
[data-testid="stSelectbox"] label, [data-testid="stNumberInput"] label {
    font-size: 13px !important;
    font-weight: 600 !important;
    color: #344054 !important;
    margin-bottom: 6px !important;
}

div[data-baseweb="select"] > div {
    background-color: #FFFFFF !important;
    border: 1px solid #D0D5DD !important;
    border-radius: 6px !important;
    color: #172033 !important;
}

div[data-baseweb="select"] > div:hover {
    border-color: #15803D !important;
}

/* 7. Streamlit Native Metrics Customization */
[data-testid="stMetric"] {
    background-color: #FFFFFF !important;
    border: 1px solid #E4E7EC !important;
    border-radius: 8px !important;
    padding: 16px 20px !important;
    box-shadow: 0 1px 3px rgba(16, 24, 40, 0.05) !important;
}

[data-testid="stMetricLabel"] {
    font-size: 12px !important;
    font-weight: 600 !important;
    color: #667085 !important;
    text-transform: uppercase !important;
    letter-spacing: 0.04em !important;
}

[data-testid="stMetricValue"] {
    font-size: 26px !important;
    font-weight: 700 !important;
    color: #172033 !important;
    font-variant-numeric: tabular-nums !important;
}

/* 8. Dataframe Enhancements */
[data-testid="stDataFrame"] {
    border: 1px solid #E4E7EC !important;
    border-radius: 6px !important;
    overflow: hidden !important;
    background-color: #FFFFFF !important;
}

/* 9. Header Branding Section */
.shell-brand-header {
    display: flex;
    align-items: center;
    gap: 10px;
    padding-bottom: 16px;
    margin-bottom: 16px;
    border-bottom: 1px solid #E4E7EC;
}

.shell-brand-title {
    font-size: 16px;
    font-weight: 700;
    letter-spacing: 0.02em;
    color: #172033;
}

.shell-brand-subtitle {
    font-size: 11px;
    color: #667085;
}

/* 10. Horizontal Rules & Dividers */
hr {
    border: 0 !important;
    border-top: 1px solid #E4E7EC !important;
    margin: 24px 0 !important;
}
</style>
"""
