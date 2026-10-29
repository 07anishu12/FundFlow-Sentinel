"""FundFlow stress calculation and scenario analysis engine.

Provides:
- stress_outflow(aum_cr, rate_pct): Pure deterministic gross redemption outflow estimation.
- scenario_table(forecast_rate, bands, hist_max, aum_cr): Multi-scenario outflow comparison.
- Reference AUM proxy resolution with observation month tagging.
- Transparent rate capping (>100%), negative rate rejection, and missingness preservation.
"""
from __future__ import annotations

import math
from typing import Optional, Sequence
import numpy as np
import pandas as pd


def stress_outflow(aum_cr: float, rate_pct: float) -> dict:
    """Compute estimated gross redemption outflow from reference AUM and a scenario rate.
    
    Arithmetic:
        estimated_outflow_cr = aum_cr * effective_rate_pct / 100.0
    
    Validation & Capping Rules:
    - aum_cr must be finite and >= 0.0. (Negative or non-finite -> invalid_input).
    - rate_pct must be finite and >= 0.0. (Negative -> invalid_input; never shows negative gross redemptions).
    - rate_pct > 100.0 is explicitly capped at 100.0% with status 'capped_at_100'.
    - If inputs are valid, returns status 'valid'.
    """
    # 1. Validate AUM
    if aum_cr is None or not (isinstance(aum_cr, (int, float)) and math.isfinite(float(aum_cr))):
        return {
            "status": "invalid_input",
            "estimated_outflow_cr": None,
            "rate_pct": rate_pct if isinstance(rate_pct, (int, float)) else None,
            "effective_rate_pct": None,
            "aum_cr": None,
            "units": "₹ crore",
            "reason": "Reference AUM must be a finite numeric value.",
        }

    aum_f = float(aum_cr)
    if aum_f < 0.0:
        return {
            "status": "invalid_input",
            "estimated_outflow_cr": None,
            "rate_pct": rate_pct if isinstance(rate_pct, (int, float)) else None,
            "effective_rate_pct": None,
            "aum_cr": aum_f,
            "units": "₹ crore",
            "reason": "Reference AUM cannot be negative.",
        }

    # 2. Validate Rate
    if rate_pct is None or not (isinstance(rate_pct, (int, float)) and math.isfinite(float(rate_pct))):
        return {
            "status": "invalid_input",
            "estimated_outflow_cr": None,
            "rate_pct": None,
            "effective_rate_pct": None,
            "aum_cr": aum_f,
            "units": "₹ crore",
            "reason": "Redemption rate must be a finite numeric value.",
        }

    rate_f = float(rate_pct)
    if rate_f < 0.0:
        return {
            "status": "invalid_input",
            "estimated_outflow_cr": None,
            "rate_pct": rate_f,
            "effective_rate_pct": None,
            "aum_cr": aum_f,
            "units": "₹ crore",
            "reason": "Gross redemption rate cannot be negative.",
        }

    # 3. Handle Capping above 100%
    status = "valid"
    effective_rate = rate_f
    reason = "Deterministic scenario outflow calculated successfully."

    if rate_f > 100.0:
        status = "capped_at_100"
        effective_rate = 100.0
        reason = f"Specified rate ({rate_f:.2f}%) exceeds 100%; capped at 100.0% of reference AUM."

    # 4. Outflow arithmetic
    estimated_outflow = round((aum_f * effective_rate) / 100.0, 2)

    return {
        "status": status,
        "estimated_outflow_cr": estimated_outflow,
        "rate_pct": round(rate_f, 4),
        "effective_rate_pct": round(effective_rate, 4),
        "aum_cr": round(aum_f, 2),
        "units": "₹ crore",
        "reason": reason,
    }


def scenario_table(
    forecast_rate: Optional[float],
    bands: Optional[dict] = None,
    hist_max: Optional[dict] = None,
    aum_cr: Optional[float] = None,
    custom_rate: Optional[float] = None,
) -> pd.DataFrame:
    """Construct multi-scenario redemption outflow table with incremental calculations.
    
    Scenarios evaluated:
    1. Base Forecast
    2. Empirical Lower Case (P10) - only if bands status == 'ok'
    3. Empirical Upper Case (P90) - only if bands status == 'ok'
    4. Moderate Stress (1.25x) - illustrative multiplier on base
    5. Severe Stress (1.50x) - illustrative multiplier on base
    6. Historical Maximum Rate - only if sample adequacy established
    7. Custom Scenario - if custom_rate provided
    
    Incremental outflows:
        incremental_outflow_cr = scenario_outflow - base_outflow
    """
    rows = []

    # 1. Base Forecast
    base_calc = None
    base_outflow = None
    base_status = "unavailable"
    base_assumption = "Central out-of-sample model point forecast."

    if forecast_rate is not None and aum_cr is not None and aum_cr > 0:
        base_calc = stress_outflow(aum_cr, forecast_rate)
        if base_calc["status"] in ("valid", "capped_at_100"):
            base_outflow = base_calc["estimated_outflow_cr"]
            base_status = base_calc["status"]
        else:
            base_status = base_calc["status"]
            base_assumption = f"Base forecast unavailable: {base_calc.get('reason', '')}"
    else:
        base_assumption = "Base forecast or reference AUM is missing."

    rows.append({
        "scenario_name": "Base Forecast",
        "scenario_type": "baseline",
        "rate_pct": base_calc["rate_pct"] if base_calc else None,
        "effective_rate_pct": base_calc["effective_rate_pct"] if base_calc else None,
        "estimated_outflow_cr": base_outflow,
        "incremental_outflow_cr": 0.0 if base_outflow is not None else None,
        "status": base_status,
        "assumption": base_assumption,
    })

    # 2. Empirical Lower Bound (P10)
    p10_calc = None
    p10_outflow = None
    p10_inc = None
    p10_status = "unavailable"
    p10_assumption = "Empirical P10 lower residual bound."

    if bands and bands.get("band_status") == "ok" and bands.get("lower_band") is not None and aum_cr is not None:
        p10_calc = stress_outflow(aum_cr, bands["lower_band"])
        p10_status = p10_calc["status"]
        p10_outflow = p10_calc["estimated_outflow_cr"]
        if base_outflow is not None and p10_outflow is not None:
            p10_inc = round(p10_outflow - base_outflow, 2)
    else:
        p10_status = "insufficient_history" if bands and bands.get("band_status") == "insufficient_history" else "unavailable"
        p10_assumption = "Empirical P10 bound unavailable: insufficient historical out-of-sample residuals."

    rows.append({
        "scenario_name": "Lower Bound (P10)",
        "scenario_type": "empirical_bound",
        "rate_pct": p10_calc["rate_pct"] if p10_calc else None,
        "effective_rate_pct": p10_calc["effective_rate_pct"] if p10_calc else None,
        "estimated_outflow_cr": p10_outflow,
        "incremental_outflow_cr": p10_inc,
        "status": p10_status,
        "assumption": p10_assumption,
    })

    # 3. Empirical Upper Bound (P90)
    p90_calc = None
    p90_outflow = None
    p90_inc = None
    p90_status = "unavailable"
    p90_assumption = "Empirical P90 upper residual bound."

    if bands and bands.get("band_status") == "ok" and bands.get("upper_band") is not None and aum_cr is not None:
        p90_calc = stress_outflow(aum_cr, bands["upper_band"])
        p90_status = p90_calc["status"]
        p90_outflow = p90_calc["estimated_outflow_cr"]
        if base_outflow is not None and p90_outflow is not None:
            p90_inc = round(p90_outflow - base_outflow, 2)
    else:
        p90_status = "insufficient_history" if bands and bands.get("band_status") == "insufficient_history" else "unavailable"
        p90_assumption = "Empirical P90 bound unavailable: insufficient historical out-of-sample residuals."

    rows.append({
        "scenario_name": "Upper Bound (P90)",
        "scenario_type": "empirical_bound",
        "rate_pct": p90_calc["rate_pct"] if p90_calc else None,
        "effective_rate_pct": p90_calc["effective_rate_pct"] if p90_calc else None,
        "estimated_outflow_cr": p90_outflow,
        "incremental_outflow_cr": p90_inc,
        "status": p90_status,
        "assumption": p90_assumption,
    })

    # 4. Moderate Stress (1.25x)
    mod_calc = None
    mod_outflow = None
    mod_inc = None
    mod_status = "unavailable"
    mod_assumption = "Illustrative scenario applying 1.25x multiplier to base forecast."

    if forecast_rate is not None and aum_cr is not None and aum_cr > 0:
        mod_calc = stress_outflow(aum_cr, forecast_rate * 1.25)
        mod_status = mod_calc["status"]
        mod_outflow = mod_calc["estimated_outflow_cr"]
        if base_outflow is not None and mod_outflow is not None:
            mod_inc = round(mod_outflow - base_outflow, 2)
    else:
        mod_assumption = "Moderate stress unavailable: base forecast or AUM is missing."

    rows.append({
        "scenario_name": "Moderate Stress (1.25x)",
        "scenario_type": "multiplier_stress",
        "rate_pct": mod_calc["rate_pct"] if mod_calc else None,
        "effective_rate_pct": mod_calc["effective_rate_pct"] if mod_calc else None,
        "estimated_outflow_cr": mod_outflow,
        "incremental_outflow_cr": mod_inc,
        "status": mod_status,
        "assumption": mod_assumption,
    })

    # 5. Severe Stress (1.50x)
    sev_calc = None
    sev_outflow = None
    sev_inc = None
    sev_status = "unavailable"
    sev_assumption = "Illustrative scenario applying 1.50x multiplier to base forecast."

    if forecast_rate is not None and aum_cr is not None and aum_cr > 0:
        sev_calc = stress_outflow(aum_cr, forecast_rate * 1.50)
        sev_status = sev_calc["status"]
        sev_outflow = sev_calc["estimated_outflow_cr"]
        if base_outflow is not None and sev_outflow is not None:
            sev_inc = round(sev_outflow - base_outflow, 2)
    else:
        sev_assumption = "Severe stress unavailable: base forecast or AUM is missing."

    rows.append({
        "scenario_name": "Severe Stress (1.50x)",
        "scenario_type": "multiplier_stress",
        "rate_pct": sev_calc["rate_pct"] if sev_calc else None,
        "effective_rate_pct": sev_calc["effective_rate_pct"] if sev_calc else None,
        "estimated_outflow_cr": sev_outflow,
        "incremental_outflow_cr": sev_inc,
        "status": sev_status,
        "assumption": sev_assumption,
    })

    # 6. Historical Maximum Rate
    h_calc = None
    h_outflow = None
    h_inc = None
    h_status = "unavailable"
    h_assumption = "Worst historical observed redemption rate in category."

    if hist_max and hist_max.get("sample_size", 0) >= 24 and hist_max.get("rate") is not None and aum_cr is not None:
        h_calc = stress_outflow(aum_cr, hist_max["rate"])
        h_status = h_calc["status"]
        h_outflow = h_calc["estimated_outflow_cr"]
        if base_outflow is not None and h_outflow is not None:
            h_inc = round(h_outflow - base_outflow, 2)
        h_assumption = f"Highest observed rate ({hist_max['rate']:.2f}%) in sample (n={hist_max['sample_size']} months)."
    else:
        n_obs = hist_max.get("sample_size", 0) if hist_max else 0
        h_status = "insufficient_history"
        h_assumption = f"Historical maximum unavailable: sample size (n={n_obs}) is insufficient for worst-case calibration."

    rows.append({
        "scenario_name": "Historical Maximum",
        "scenario_type": "historical_max",
        "rate_pct": h_calc["rate_pct"] if h_calc else None,
        "effective_rate_pct": h_calc["effective_rate_pct"] if h_calc else None,
        "estimated_outflow_cr": h_outflow,
        "incremental_outflow_cr": h_inc,
        "status": h_status,
        "assumption": h_assumption,
    })

    # 7. Custom Scenario (Optional)
    if custom_rate is not None:
        c_calc = stress_outflow(aum_cr, custom_rate) if aum_cr is not None else None
        c_outflow = c_calc["estimated_outflow_cr"] if c_calc else None
        c_inc = round(c_outflow - base_outflow, 2) if base_outflow is not None and c_outflow is not None else None
        rows.append({
            "scenario_name": "Custom Scenario",
            "scenario_type": "custom",
            "rate_pct": c_calc["rate_pct"] if c_calc else custom_rate,
            "effective_rate_pct": c_calc["effective_rate_pct"] if c_calc else None,
            "estimated_outflow_cr": c_outflow,
            "incremental_outflow_cr": c_inc,
            "status": c_calc["status"] if c_calc else "unavailable",
            "assumption": f"User-specified custom redemption rate ({custom_rate:.2f}%).",
        })

    return pd.DataFrame(rows)
