"""FundFlow alert generation and rules engine.

Evaluates hierarchical rules:
- Critical: pct_forecast >= 90 AND (robust_z >= 2.0 OR momentum_3m >= 0.10)
- Elevated: pct_forecast >= 80 OR robust_z >= 2.0
- Normal: otherwise
Enforces strict precedence, prior-only history, and explicit limitation logging.
Conforms to frozen COLUMNS['alerts'] contract.
"""
from __future__ import annotations

from datetime import datetime
import math
from pathlib import Path
from typing import Optional
import numpy as np
import pandas as pd

from fundflow.contracts import validate_table, COLUMNS
from fundflow.anomaly import compute_robust_z, compute_momentum_3m, compute_percentile_rank


def generate_alerts(
    predictions: pd.DataFrame,
    history: pd.DataFrame,
    sentiment_agg: Optional[pd.DataFrame] = None,
    as_of: Optional[str] = None,
) -> pd.DataFrame:
    """Evaluate alert rules for each forecast observation.
    
    COLUMNS['alerts']:
    ('as_of', 'target_month', 'category', 'level', 'rules_triggered', 'forecast_rate',
     'forecast_percentile', 'robust_z', 'momentum_3m', 'est_outflow_cr', 'reference_aum_cr',
     'aum_month', 'sentiment_status', 'sentiment_note', 'data_freshness_days', 'limitations')
    """
    if predictions.empty:
        return pd.DataFrame(columns=COLUMNS["alerts"])

    preds = predictions.copy()
    hist = history.copy() if history is not None else pd.DataFrame()

    alert_rows = []

    # Map historical rates and AUM by category
    # Ensure history is strictly prior to as_of
    for _, p_row in preds.iterrows():
        cat = str(p_row["category"])
        t_month = str(p_row["target_month"])
        row_as_of = str(p_row.get("as_of", as_of or f"{t_month}-12T00:00:00Z"))
        forecast_rate = float(p_row["predicted_rate"])

        # Filter historical rows for this category available before row_as_of
        cat_hist = pd.DataFrame()
        if not hist.empty and "category" in hist.columns:
            cat_hist = hist[hist["category"] == cat].copy()
            for c_name in ["gross_redemption_cr", "aum_close_cr", "redemption_rate_pct"]:
                if c_name in cat_hist.columns:
                    cat_hist[c_name] = pd.to_numeric(cat_hist[c_name], errors="coerce")
            if "available_from" in cat_hist.columns:
                cat_hist = cat_hist[cat_hist["available_from"] <= row_as_of]
            # Must strictly precede target_month
            if "month" in cat_hist.columns:
                cat_hist = cat_hist[cat_hist["month"] < t_month].sort_values("month")

        # Extract rates series
        rate_series = []
        ref_aum = 100000.0
        ref_aum_month = "2024-09"
        freshness_days = 30

        if not cat_hist.empty:
            if "redemption_rate_pct" in cat_hist.columns:
                rate_series = cat_hist["redemption_rate_pct"].dropna().tolist()
            elif "gross_redemption_cr" in cat_hist.columns and "aum_close_cr" in cat_hist.columns:
                # Compute rough rates if redemption_rate_pct is missing
                rates = (cat_hist["gross_redemption_cr"] / cat_hist["aum_close_cr"].shift(1)) * 100.0
                rate_series = rates.dropna().tolist()

            latest_hist_row = cat_hist.iloc[-1]
            ref_aum = float(latest_hist_row.get("aum_close_cr", 100000.0))
            ref_aum_month = str(latest_hist_row.get("month", "2024-09"))

            # Calculate freshness days
            try:
                dt_as_of = datetime.fromisoformat(row_as_of.replace("Z", "+00:00"))
                m_end = pd.Period(ref_aum_month, freq="M").end_time
                freshness_days = max(0, (dt_as_of.date() - m_end.date()).days)
            except Exception:
                freshness_days = 30

        latest_observed_rate = rate_series[-1] if rate_series else forecast_rate

        # Statistical evidence
        pct_forecast = compute_percentile_rank(rate_series, forecast_rate, min_obs=6)
        robust_z = compute_robust_z(rate_series, latest_observed_rate, min_obs=6)
        momentum_3m = compute_momentum_3m(rate_series, min_obs=6)

        # Rule evaluation
        rules_triggered = []
        limitations = []
        level = "Normal"

        if len(rate_series) < 6:
            limitations.append("insufficient_history: fewer than 6 observations")
            rules_triggered.append("none")
            pct_forecast_val = 50.0  # neutral placeholder for contract
            robust_z_val = 0.0
            momentum_3m_val = 0.0
        else:
            pct_forecast_val = pct_forecast if pct_forecast is not None else 50.0
            robust_z_val = robust_z if robust_z is not None else 0.0
            momentum_3m_val = momentum_3m if momentum_3m is not None else 0.0

            # 1. Critical Check: pct_forecast >= 90 AND (robust_z >= 2.0 OR momentum_3m >= 0.10)
            if pct_forecast_val >= 90.0 and (robust_z_val >= 2.0 or momentum_3m_val >= 0.10):
                level = "Critical"
                rules_triggered.append("critical_pct90_robust_or_mom")
            # 2. Elevated Check: pct_forecast >= 80 OR robust_z >= 2.0
            elif pct_forecast_val >= 80.0 or robust_z_val >= 2.0:
                level = "Elevated"
                rules_triggered.append("elevated_pct80_or_robust2")
            else:
                level = "Normal"
                rules_triggered.append("none")

        # Estimated outflow
        est_outflow = round((forecast_rate / 100.0) * ref_aum, 2)

        # Sentiment corroboration
        sentiment_status = "unavailable"
        sentiment_note = ""
        if sentiment_agg is not None and not sentiment_agg.empty:
            # Check 14-day sufficiency
            live_agg = sentiment_agg[sentiment_agg["is_live"] == True]
            total_arts = int(live_agg["n_articles"].sum()) if "n_articles" in live_agg.columns else 0
            if total_arts >= 30:
                sentiment_status = "active"
                sentiment_note = f"Active sentiment monitoring ({total_arts} articles in window)"
            else:
                sentiment_status = "insufficient"
                sentiment_note = f"Insufficient sentiment articles ({total_arts} < 30)"

        alert_rows.append({
            "as_of": row_as_of,
            "target_month": t_month,
            "category": cat,
            "level": level,
            "rules_triggered": ";".join(rules_triggered),
            "forecast_rate": round(forecast_rate, 4),
            "forecast_percentile": round(pct_forecast_val, 2),
            "robust_z": round(robust_z_val, 4),
            "momentum_3m": round(momentum_3m_val, 4),
            "est_outflow_cr": est_outflow,
            "reference_aum_cr": round(ref_aum, 2),
            "aum_month": ref_aum_month,
            "sentiment_status": sentiment_status,
            "sentiment_note": sentiment_note,
            "data_freshness_days": int(freshness_days),
            "limitations": ";".join(limitations) if limitations else "none",
        })

    df_alerts = pd.DataFrame(alert_rows, columns=COLUMNS["alerts"])
    df_alerts = df_alerts.sort_values(["target_month", "category"]).reset_index(drop=True)
    return validate_table("alerts", df_alerts)
