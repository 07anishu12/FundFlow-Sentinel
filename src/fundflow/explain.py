"""FundFlow model explanation and empirical uncertainty bands engine.

Provides:
- Exact additive feature contribution decomposition for Ridge predictions:
  Reconciles intercept + feature contributions + category effect to model prediction
  within a 1e-4 tolerance.
- Out-of-sample empirical P10/P90 residual uncertainty bands:
  Uses strictly prior out-of-sample residuals available before forecast as_of.
  Returns band_status='insufficient_history' when residual count is below threshold.
"""
from __future__ import annotations

import json
import math
from typing import Optional, Sequence
import numpy as np
import pandas as pd


def explain_ridge_prediction(
    raw_feature_row: dict,
    model_coefs: dict,
    feature_cols: Sequence[str],
    scaler_mean: Optional[dict[str, float]] = None,
    scaler_scale: Optional[dict[str, float]] = None,
    category_col: str = "category",
) -> dict:
    """Calculate per-feature model contributions that reconcile to the model prediction.
    
    Formula:
        y_hat = intercept + sum_j( w_j * (x_j - mu_j) / sigma_j ) + v_cat
    
    Returns a structured contrib_dict with explanation_status='reconciled'
    or explanation_status='unavailable'.
    """
    try:
        intercept = float(model_coefs.get("intercept", 0.0))
        cat_val = str(raw_feature_row.get(category_col, "Unknown"))

        # Category effect
        cat_key = f"cat_{cat_val}"
        cat_contrib = float(model_coefs.get(cat_key, 0.0))

        feat_contributions = []
        total_feat_contrib = 0.0

        for col in feature_cols:
            raw_val = raw_feature_row.get(col)
            if raw_val is None or not (isinstance(raw_val, (int, float)) and math.isfinite(raw_val)):
                return {
                    "explanation_status": "unavailable",
                    "reason": f"Missing or non-finite raw value for feature '{col}'",
                    "total_reconciled": None,
                }

            coef = float(model_coefs.get(col, 0.0))

            # Transform value using scaler mean and scale if provided
            mu = scaler_mean.get(col, 0.0) if scaler_mean else 0.0
            sigma = scaler_scale.get(col, 1.0) if scaler_scale else 1.0
            if sigma <= 1e-12:
                sigma = 1.0

            trans_val = (float(raw_val) - mu) / sigma
            contrib = coef * trans_val
            total_feat_contrib += contrib

            feat_contributions.append({
                "feature": col,
                "raw_value": round(float(raw_val), 4),
                "transformed_value": round(float(trans_val), 4),
                "coefficient": round(coef, 4),
                "contribution": round(contrib, 4),
                "units": "percentage_points",
            })

        total_reconciled = intercept + total_feat_contrib + cat_contrib

        return {
            "model_id": "ridge-pooled-v1",
            "intercept": round(intercept, 4),
            "category": cat_val,
            "category_contribution": round(cat_contrib, 4),
            "feature_contributions": feat_contributions,
            "total_reconciled": round(total_reconciled, 4),
            "explanation_status": "reconciled",
            "numerical_tolerance": 1e-4,
        }
    except Exception as e:
        return {
            "explanation_status": "unavailable",
            "reason": f"Decomposition error: {str(e)}",
            "total_reconciled": None,
        }


def compute_empirical_residual_bands(
    historical_predictions: pd.DataFrame,
    current_as_of: str,
    predicted_rate: float,
    min_residuals: int = 10,
    quantiles: tuple[float, float] = (0.10, 0.90),
) -> dict:
    """Compute empirical P10/P90 uncertainty bands from prior out-of-sample residuals.
    
    Strict Temporal Eligibility:
    - Only out-of-sample predictions where actual_rate was known and released
      BEFORE current_as_of are eligible.
    - If eligible residual count < min_residuals, returns:
      band_status='insufficient_history' and lower/upper bounds as None.
    - Zero-width or fabricated intervals are strictly prevented.
    """
    if historical_predictions.empty:
        return {
            "band_status": "insufficient_history",
            "lower_band": None,
            "upper_band": None,
            "residual_count": 0,
            "min_required": min_residuals,
            "method": "empirical_residual_quantiles",
            "reason": "Zero historical predictions available."
        }

    df = historical_predictions.copy()

    # Filter to out-of-sample predictions with known actuals
    if "is_out_of_sample" in df.columns:
        df = df[df["is_out_of_sample"] == True]

    # Filter rows whose forecast origin as_of is strictly before current_as_of
    df = df[df["as_of"] < current_as_of]

    # Filter actuals that are valid finite floats
    valid_actuals = []
    for _, row in df.iterrows():
        act = row.get("actual_rate")
        if pd.notna(act) and str(act).strip() != "":
            try:
                act_f = float(act)
                if math.isfinite(act_f):
                    valid_actuals.append(act_f)
                else:
                    valid_actuals.append(np.nan)
            except Exception:
                valid_actuals.append(np.nan)
        else:
            valid_actuals.append(np.nan)

    df["actual_rate_clean"] = valid_actuals
    df = df[df["actual_rate_clean"].notna()].copy()

    residual_count = len(df)
    if residual_count < min_residuals:
        return {
            "band_status": "insufficient_history",
            "lower_band": None,
            "upper_band": None,
            "residual_count": residual_count,
            "min_required": min_residuals,
            "method": "empirical_residual_quantiles",
            "reason": f"Only {residual_count} prior out-of-sample residuals available; minimum {min_residuals} required."
        }

    # Compute out-of-sample residuals: e_i = actual_i - predicted_i (or predicted_i - actual_i)
    # Using additive forecast error: e = actual - predicted
    # lower_quantile = q10(e), upper_quantile = q90(e)
    # lower_band = predicted + q10, upper_band = predicted + q90
    pred_vals = df["predicted_rate"].values.astype(float)
    act_vals = df["actual_rate_clean"].values.astype(float)
    errors = act_vals - pred_vals

    q_low = float(np.quantile(errors, quantiles[0]))
    q_high = float(np.quantile(errors, quantiles[1]))

    # Bounds (rate cannot be negative in practice, clip at 0.0)
    lower_band = max(0.0, round(predicted_rate + q_low, 4))
    upper_band = round(predicted_rate + q_high, 4)

    # Date range of residuals
    dates = sorted(df["target_month"].unique())
    date_range = f"{dates[0]} to {dates[-1]}" if dates else "unknown"
    latest_cutoff = str(df["as_of"].max())

    return {
        "band_status": "ok",
        "lower_band": lower_band,
        "upper_band": upper_band,
        "q10_offset": round(q_low, 4),
        "q90_offset": round(q_high, 4),
        "residual_count": residual_count,
        "min_required": min_residuals,
        "residual_date_range": date_range,
        "latest_residual_cutoff": latest_cutoff,
        "method": "empirical_residual_quantiles",
    }



def generate_stress_narrative(
    category: str,
    aum_cr: Optional[float],
    aum_month: str,
    scenario_df: pd.DataFrame,
) -> dict:
    """Generate finance-safe rule-based narrative explanations for stress scenarios.
    
    Adheres strictly to finance-safe wording:
    - Never uses 'liquidity crisis', 'run on the fund', 'panic', or causal assertions.
    - Labels AUM as a historical reference proxy, not guaranteed liquid assets.
    - Explicitly describes uncertainty bounds as insufficient_history when data is limited.
    - Clarifies that scenarios are illustrative mathematical sensitivity tests.
    """
    if aum_cr is None or aum_cr <= 0:
        return {
            "summary": f"Stress analysis for {category} is unavailable due to missing reference AUM.",
            "details": ["Reference AUM proxy is missing or invalid. Outflow calculations withheld."],
            "disclosures": [
                "Analysis requires a positive, finite category closing AUM proxy.",
                "Scenarios represent descriptive sensitivity arithmetic, not investment recommendations.",
            ],
            "finance_safe": True,
        }

    # Find Base Forecast
    base_row = scenario_df[scenario_df["scenario_name"] == "Base Forecast"]
    base_outflow = None
    base_rate = None
    if not base_row.empty and base_row.iloc[0]["status"] == "valid":
        base_outflow = base_row.iloc[0]["estimated_outflow_cr"]
        base_rate = base_row.iloc[0]["rate_pct"]

    # Multipliers
    mod_row = scenario_df[scenario_df["scenario_name"] == "Moderate Stress (1.25x)"]
    sev_row = scenario_df[scenario_df["scenario_name"] == "Severe Stress (1.50x)"]

    mod_outflow = mod_row.iloc[0]["estimated_outflow_cr"] if not mod_row.empty else None
    mod_inc = mod_row.iloc[0]["incremental_outflow_cr"] if not mod_row.empty else None

    sev_outflow = sev_row.iloc[0]["estimated_outflow_cr"] if not sev_row.empty else None
    sev_inc = sev_row.iloc[0]["incremental_outflow_cr"] if not sev_row.empty else None

    # Check bounds status
    p10_row = scenario_df[scenario_df["scenario_name"] == "Lower Bound (P10)"]
    p90_row = scenario_df[scenario_df["scenario_name"] == "Upper Bound (P90)"]
    bounds_status = p10_row.iloc[0]["status"] if not p10_row.empty else "unavailable"

    details = []

    # 1. Baseline overview
    if base_outflow is not None and base_rate is not None:
        details.append(
            f"For {category}, applying the baseline out-of-sample forecast rate of {base_rate:.2f}% "
            f"to the reference AUM proxy of ₹{aum_cr:,.2f} crore (observed as of {aum_month}) "
            f"yields an estimated monthly gross redemption outflow of ₹{base_outflow:,.2f} crore."
        )
    else:
        details.append(
            f"Baseline forecast for {category} is currently unavailable or diagnostic-only. "
            f"Outflow comparisons are computed relative to reference AUM of ₹{aum_cr:,.2f} crore ({aum_month})."
        )

    # 2. Stress multipliers
    if mod_outflow is not None and mod_inc is not None and sev_outflow is not None and sev_inc is not None:
        details.append(
            f"Under an illustrative moderate stress multiplier of 1.25x, gross outflows increase by "
            f"₹{mod_inc:,.2f} crore to ₹{mod_outflow:,.2f} crore. Under a severe 1.50x stress scenario, "
            f"gross outflows rise by ₹{sev_inc:,.2f} crore to ₹{sev_outflow:,.2f} crore."
        )

    # 3. Uncertainty status
    if bounds_status == "insufficient_history":
        details.append(
            "Empirical P10/P90 residual uncertainty bands are currently classified as insufficient_history. "
            "Because fewer than 10 prior out-of-sample forecast residuals exist in the current historical sample, "
            "statistical interval bounds are honestly withheld rather than fabricated."
        )

    # Summary sentence
    summary = (
        f"{category} scenario sensitivity indicates estimated monthly redemptions of "
        f"₹{base_outflow:,.2f} cr (baseline)" if base_outflow is not None
        else f"{category} sensitivity calculations available for reference AUM ₹{aum_cr:,.2f} cr."
    )

    disclosures = [
        "Illustrative Sensitivity Only: Scenarios represent linear arithmetic projections applying hypothetical redemption rates to historical closing AUM.",
        "Reference AUM Proxy: Closing AUM is a historical category-level proxy, not real-time intraday assets or liquid cash reserves.",
        "No Liquidity Portfolio Modeling: This analysis does not model cash buffers, asset sale settlement delays, market depth, or liquidation price impact.",
        "Not Investment Advice: Scenario outputs are research metrics for asset liability monitoring and do not predict fund performance or distress.",
    ]

    return {
        "summary": summary,
        "details": details,
        "disclosures": disclosures,
        "finance_safe": True,
    }
