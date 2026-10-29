"""Interactive user-defined forecasting and forecast gap evaluation engine.

Provides:
- Strict forecast-versus-actual gap calculations with zero-division protection.
- Dynamic dataset and target selection:
    * AMFI Category Flows (gross_redemption_cr, net_flow_cr, redemption_rate, aum_close_cr)
    * Scheme NAV History (nav)
- Multiple model comparisons:
    * Persistence Baseline: R_hat(t+h) = R(t)
    * Seasonal Naive: R_hat(t+h) = R(t+h-12)
    * Regularized Ridge: Multi-lag autoregressive with expanding-window cross-validation
- Pure out-of-sample walk-forward evaluation (MAE, RMSE, Baseline Comparison, P10/P90 intervals).
- Zero-leakage preprocessing fitted strictly within each training fold.
"""
from __future__ import annotations

import math
from typing import Any, Optional, Sequence
import numpy as np
import pandas as pd
from sklearn.linear_model import Ridge


def calculate_forecast_gap(actual_val: Optional[float], forecast_val: float) -> dict[str, Any]:
    """Calculate signed gap, absolute gap, and absolute percentage error.
    
    Conventions:
    - Gap = Actual - Forecast
    - Absolute Gap = |Actual - Forecast|
    - Absolute Percentage Error = |Actual - Forecast| / |Actual| * 100
      (Unavailable / None when actual is 0 or None)
    - Direction:
      * 'overpredicted' when forecast > actual
      * 'underpredicted' when forecast < actual
      * 'exact' when forecast == actual
      * 'unobserved' when actual is None
    """
    if actual_val is None or not math.isfinite(actual_val):
        return {
            "status": "unobserved",
            "gap": None,
            "abs_gap": None,
            "pct_error": None,
            "direction": "unobserved",
            "label": "Forecast target unobserved",
        }

    gap = round(float(actual_val - forecast_val), 4)
    abs_gap = round(float(abs(actual_val - forecast_val)), 4)

    if abs(actual_val) > 1e-9:
        pct_error = round(float((abs_gap / abs(actual_val)) * 100.0), 2)
    else:
        pct_error = None

    if gap > 1e-6:
        direction = "underpredicted"  # Actual was higher than forecast
    elif gap < -1e-6:
        direction = "overpredicted"   # Forecast was higher than actual
    else:
        direction = "exact"

    return {
        "status": "observed",
        "gap": gap,
        "abs_gap": abs_gap,
        "pct_error": pct_error,
        "direction": direction,
        "label": f"Gap: {gap:+0.2f} ({direction})",
    }


def run_user_forecast(
    df: pd.DataFrame,
    target_col: str,
    date_col: str = "period",
    horizon: int = 1,
    models: Sequence[str] = ("persistence", "seasonal_naive", "ridge"),
    min_train_obs: int = 6,
) -> dict[str, Any]:
    """Run walk-forward evaluation and forecast for user-specified dataset and target.
    
    Parameters:
    - df: DataFrame sorted chronologically containing date_col and target_col
    - target_col: Variable to predict
    - date_col: Time column ('period' for monthly flows, 'date' for daily NAV)
    - horizon: Forecast step horizon (1, 3, 6, 12)
    - models: List of models to evaluate ('persistence', 'seasonal_naive', 'ridge')
    - min_train_obs: Minimum observations to begin walk-forward validation
    
    Returns structured results dictionary containing:
    - latest_observation: Most recent observed value and date
    - target_period: Forecast target period (t + horizon)
    - model_forecasts: Dict mapping model name to forecast value & uncertainty bounds
    - comparison_table: DataFrame of out-of-sample performance (MAE, RMSE, baseline comp)
    - limitations: List of notices (e.g. INSUFFICIENT_HISTORY)
    """
    clean_df = df.dropna(subset=[target_col]).copy()
    if clean_df.empty or len(clean_df) < 2:
        return {
            "status": "insufficient_data",
            "limitations": ["INSUFFICIENT_HISTORY: Less than 2 valid observations available."],
            "model_forecasts": {},
            "comparison_table": pd.DataFrame(),
        }

    # Clean and sort values
    clean_df[target_col] = pd.to_numeric(clean_df[target_col], errors="coerce")
    clean_df = clean_df.dropna(subset=[target_col]).sort_values(date_col).reset_index(drop=True)

    n_obs = len(clean_df)
    limitations: list[str] = []
    
    # Check history sufficiency
    if n_obs < min_train_obs:
        limitations.append(
            f"INSUFFICIENT_HISTORY: Dataset has {n_obs} observations; "
            f"recommended minimum is {min_train_obs} for robust out-of-sample validation."
        )

    series = clean_df[target_col].values.astype(float)
    dates = clean_df[date_col].astype(str).values

    latest_val = float(series[-1])
    latest_date = str(dates[-1])

    # Build lag features for Ridge
    # X features: lag0, lag1, lag2, roll_mean3
    def _create_features(s: np.ndarray, idx: int) -> np.ndarray:
        l0 = s[idx]
        l1 = s[idx - 1] if idx >= 1 else l0
        l2 = s[idx - 2] if idx >= 2 else l1
        roll3 = np.mean(s[max(0, idx - 2): idx + 1])
        return np.array([l0, l1, l2, roll3], dtype=float)

    # Walk-forward out-of-sample simulation
    # Fold t predicts t + horizon
    walk_forward_preds: dict[str, list[float]] = {m: [] for m in models}
    walk_forward_actuals: list[float] = []
    
    effective_min = max(3, min(min_train_obs, n_obs // 2))

    for t in range(effective_min, n_obs - horizon + 1):
        actual_t_h = float(series[t + horizon - 1])
        walk_forward_actuals.append(actual_t_h)

        # 1. Persistence Baseline: R_hat(t+h) = R(t)
        if "persistence" in models:
            walk_forward_preds["persistence"].append(float(series[t - 1]))

        # 2. Seasonal Naive: R_hat(t+h) = R(t - 12) if available else R(t - 1)
        if "seasonal_naive" in models:
            if t >= 12:
                s_pred = float(series[t - 12])
            else:
                s_pred = float(series[t - 1])
            walk_forward_preds["seasonal_naive"].append(s_pred)

        # 3. Ridge Regression: fitted strictly on historical folds [:t]
        if "ridge" in models:
            if t >= 4:
                X_train = []
                y_train = []
                # Construct training pairs within fold
                for sub_t in range(2, t - horizon + 1):
                    X_train.append(_create_features(series, sub_t - 1))
                    y_train.append(series[sub_t + horizon - 1])
                
                if len(X_train) >= 2:
                    X_tr = np.array(X_train)
                    y_tr = np.array(y_train)
                    ridge = Ridge(alpha=1.0)
                    ridge.fit(X_tr, y_tr)
                    feat_test = _create_features(series, t - 1).reshape(1, -1)
                    r_pred = float(ridge.predict(feat_test)[0])
                else:
                    r_pred = float(series[t - 1])
            else:
                r_pred = float(series[t - 1])
            walk_forward_preds["ridge"].append(r_pred)

    # Compute evaluation metrics across common evaluation pairs
    comp_rows = []
    base_mae = None

    if walk_forward_actuals:
        y_true = np.array(walk_forward_actuals)
        
        # Calculate baseline MAE first for comparison
        if "persistence" in walk_forward_preds and len(walk_forward_preds["persistence"]) == len(y_true):
            p_err = np.abs(np.array(walk_forward_preds["persistence"]) - y_true)
            base_mae = float(np.mean(p_err))

        for m in models:
            preds_m = np.array(walk_forward_preds[m])
            if len(preds_m) == len(y_true) and len(y_true) > 0:
                err = preds_m - y_true
                mae = float(np.mean(np.abs(err)))
                rmse = float(np.sqrt(np.mean(err ** 2)))
                
                if base_mae and base_mae > 1e-9:
                    rel_diff = ((mae - base_mae) / base_mae) * 100.0
                    if m == "persistence":
                        comp_str = "Baseline Reference"
                    elif rel_diff < 0:
                        comp_str = f"Outperforms baseline ({abs(rel_diff):0.1f}% lower MAE)"
                    elif rel_diff > 0:
                        comp_str = f"Underperforms baseline ({rel_diff:0.1f}% higher MAE)"
                    else:
                        comp_str = "Tied with baseline"
                else:
                    comp_str = "Reference"

                comp_rows.append({
                    "Model": m.replace("_", " ").title(),
                    "MAE": round(mae, 4),
                    "RMSE": round(rmse, 4),
                    "Baseline Comparison": comp_str,
                    "OOS Observations": len(y_true),
                    "Status": "Evaluated (Out-of-Sample)",
                })

    # Now compute the LIVE forecast from the end of the series for target period t + horizon
    final_forecasts = {}
    
    # 1. Persistence
    if "persistence" in models:
        p_val = round(latest_val, 4)
        final_forecasts["persistence"] = {
            "value": p_val,
            "lower_p10": None,
            "upper_p90": None,
            "method": "R_hat(t+h) = R(t)",
        }

    # 2. Seasonal Naive
    if "seasonal_naive" in models:
        if n_obs >= 12:
            sn_val = round(float(series[-12]), 4)
        else:
            sn_val = round(latest_val, 4)
        final_forecasts["seasonal_naive"] = {
            "value": sn_val,
            "lower_p10": None,
            "upper_p90": None,
            "method": "R_hat(t+h) = R(t+h-12)",
        }

    # 3. Ridge
    if "ridge" in models:
        if n_obs >= 4:
            X_all = []
            y_all = []
            for sub_t in range(2, n_obs - horizon + 1):
                X_all.append(_create_features(series, sub_t - 1))
                y_all.append(series[sub_t + horizon - 1])
            
            if len(X_all) >= 2:
                r_model = Ridge(alpha=1.0)
                r_model.fit(np.array(X_all), np.array(y_all))
                cur_feat = _create_features(series, n_obs - 1).reshape(1, -1)
                r_val = round(float(r_model.predict(cur_feat)[0]), 4)
            else:
                r_val = round(latest_val, 4)
        else:
            r_val = round(latest_val, 4)

        # Compute empirical residual uncertainty intervals if residuals exist
        lower_p10, upper_p90 = None, None
        if "ridge" in walk_forward_preds and walk_forward_actuals:
            residuals = np.array(walk_forward_preds["ridge"]) - np.array(walk_forward_actuals)
            if len(residuals) >= 5:
                lower_p10 = round(float(r_val + np.percentile(residuals, 10)), 4)
                upper_p90 = round(float(r_val + np.percentile(residuals, 90)), 4)
            elif len(residuals) >= 2:
                std_res = float(np.std(residuals))
                lower_p10 = round(float(r_val - 1.645 * std_res), 4)
                upper_p90 = round(float(r_val + 1.645 * std_res), 4)

        final_forecasts["ridge"] = {
            "value": r_val,
            "lower_p10": lower_p10,
            "upper_p90": upper_p90,
            "method": "Ridge AR(3) Expanding Window",
        }

    return {
        "status": "success",
        "latest_date": latest_date,
        "latest_value": latest_val,
        "horizon": horizon,
        "n_observations": n_obs,
        "model_forecasts": final_forecasts,
        "comparison_table": pd.DataFrame(comp_rows),
        "limitations": limitations,
    }
