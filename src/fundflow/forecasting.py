"""FundFlow walk-forward forecasting engine.

Implements:
- Persistence baseline: R_hat(c, t+1) = R(c, t)
- Pooled Ridge regression with category one-hot encoding and inner TimeSeriesSplit tuning
- Chronological expanding-window one-step-ahead walk-forward evaluation
- Zero-leakage preprocessing fitted strictly inside each training fold
- Outputs conforming to frozen predictions and model_results contracts
"""
from __future__ import annotations

from datetime import datetime
import json
import math
from pathlib import Path
from typing import Optional, Sequence
import numpy as np
import pandas as pd
from sklearn.linear_model import Ridge
from sklearn.model_selection import TimeSeriesSplit
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from fundflow.contracts import validate_table, COLUMNS

import warnings
warnings.filterwarnings("ignore", category=RuntimeWarning)

ROOT = Path(__file__).resolve().parents[2]
OUTPUTS_DIR = ROOT / "data" / "outputs"


FEATURE_COLS = [
    "rate_lag0", "rate_lag1", "rate_lag2", "rate_lag11",
    "roll_mean3", "roll_std3", "delta1", "net_flow_rate_lag0",
    "aum_growth_lag0", "nifty_return_lag0", "nifty_drawdown_3m",
    "vix_mean_lag0", "vix_change_lag0"
]
ALPHA_GRID = [0.1, 1.0, 10.0, 100.0]


def tune_ridge_alpha(X_train: np.ndarray, y_train: np.ndarray, alphas: Sequence[float] = ALPHA_GRID) -> float:
    """Select optimal Ridge alpha using inner TimeSeriesSplit on training data only."""
    if len(X_train) < 6:
        return 1.0

    n_splits = min(3, max(2, len(X_train) // 4))
    tscv = TimeSeriesSplit(n_splits=n_splits)

    best_alpha = 1.0
    best_score = float("inf")

    for a in alphas:
        cv_errors = []
        for train_idx, val_idx in tscv.split(X_train):
            X_tr, y_tr = X_train[train_idx], y_train[train_idx]
            X_va, y_va = X_train[val_idx], y_train[val_idx]

            model = Ridge(alpha=a, solver="lsqr")
            model.fit(X_tr, y_tr)
            preds = model.predict(X_va)
            mae = float(np.mean(np.abs(preds - y_va)))
            cv_errors.append(mae)

        mean_cv_err = float(np.mean(cv_errors))
        if mean_cv_err < best_score:
            best_score = mean_cv_err
            best_alpha = a

    return best_alpha


def walk_forward_forecast(
    feature_matrix: pd.DataFrame,
    min_train_months: int = 36,
    alphas: Sequence[float] = ALPHA_GRID,
) -> tuple[pd.DataFrame, dict]:
    """Execute expanding-window one-step-ahead walk-forward evaluation.
    
    Returns:
    - predictions_df: DataFrame matching COLUMNS['predictions']
    - results_envelope: JSON-serializable dict matching model_results contract
    """
    if feature_matrix.empty:
        empty_preds = pd.DataFrame(columns=COLUMNS["predictions"])
        empty_results = {
            "version": 1,
            "source": "FundFlow walk-forward forecasting engine",
            "generated_at": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
            "payload": {
                "status": "empty",
                "metrics": {},
                "limitations": ["Feature matrix is empty; no forecasts produced."]
            }
        }
        return empty_preds, empty_results

    # Validate feature matrix contract
    validate_table("feature_matrix", feature_matrix)

    df = feature_matrix.sort_values(["target_month", "category"]).reset_index(drop=True).copy()
    for col in FEATURE_COLS + ["target_rate"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    unique_months = sorted(df["target_month"].unique())

    limitations = []
    actual_min_train = min_train_months

    if len(unique_months) <= min_train_months:
        # Insufficient history for 36-month warm-up
        # Diagnostic fallback with clear reporting
        actual_min_train = max(3, len(unique_months) // 2)
        limitations.append(
            f"Dataset span ({len(unique_months)} months) is insufficient for 36-month warm-up. "
            f"Executed diagnostic evaluation with reduced warm-up of {actual_min_train} months."
        )

    prediction_rows = []

    # All categories known for categorical one-hot encoding
    all_categories = sorted(df["category"].unique())

    # Expanding window
    for t_idx in range(actual_min_train, len(unique_months)):
        test_month = unique_months[t_idx]
        train_months = unique_months[:t_idx]

        train_df = df[df["target_month"].isin(train_months)].copy()
        test_df = df[df["target_month"] == test_month].copy()

        # Labels must be valid and known
        train_df = train_df[train_df["target_rate"].notna() & np.isfinite(train_df["target_rate"])]
        if train_df.empty or test_df.empty:
            continue

        train_start = f"{train_months[0]}-01T00:00:00Z"
        train_end = f"{train_months[-1]}-28T00:00:00Z"

        # Fit preprocessors strictly inside each fold
        scaler = StandardScaler()
        X_num_train = scaler.fit_transform(train_df[FEATURE_COLS].values)
        X_num_test = scaler.transform(test_df[FEATURE_COLS].values)

        ohe = OneHotEncoder(categories=[all_categories], sparse_output=False, handle_unknown="ignore")
        X_cat_train = ohe.fit_transform(train_df[["category"]].values)
        X_cat_test = ohe.transform(test_df[["category"]].values)

        X_train = np.hstack([X_num_train, X_cat_train])
        y_train = train_df["target_rate"].values.astype(float)
        X_test = np.hstack([X_num_test, X_cat_test])

        # Inner CV hyperparameter tuning
        best_alpha = tune_ridge_alpha(X_train, y_train, alphas=alphas)

        # Fit Ridge model
        ridge = Ridge(alpha=best_alpha, solver="lsqr")
        ridge.fit(X_train, y_train)
        ridge_preds = ridge.predict(X_test)

        # Feature coefficients for contrib_json
        feature_names = FEATURE_COLS + [f"cat_{c}" for c in all_categories]
        coef_dict = {
            f_name: round(float(coef), 4)
            for f_name, coef in zip(feature_names, ridge.coef_)
        }
        coef_dict["alpha"] = best_alpha
        coef_dict["intercept"] = round(float(ridge.intercept_), 4)
        contrib_json_str = json.dumps(coef_dict)

        # Generate predictions for each test observation
        for i, (_, t_row) in enumerate(test_df.iterrows()):
            cat = str(t_row["category"])
            as_of_ts = str(t_row["as_of"])
            target_val = t_row["target_rate"]
            actual_rate = round(float(target_val), 4) if pd.notna(target_val) and math.isfinite(target_val) else None

            # Persistence prediction: R_hat(t+1) = R(t) = rate_lag0
            persistence_rate = round(float(t_row["rate_lag0"]), 4)
            predicted_rate = round(float(ridge_preds[i]), 4)

            prediction_rows.append({
                "as_of": as_of_ts,
                "target_month": test_month,
                "category": cat,
                "model_id": "ridge-pooled-v1",
                "predicted_rate": predicted_rate,
                "baseline_rate": persistence_rate,
                "actual_rate": actual_rate if actual_rate is not None else "",
                "is_out_of_sample": True,
                "train_start": train_start,
                "train_end": train_end,
                "contrib_json": contrib_json_str,
            })

    if not prediction_rows:
        empty_preds = pd.DataFrame(columns=COLUMNS["predictions"])
        empty_results = {
            "version": 1,
            "source": "FundFlow walk-forward forecasting engine",
            "generated_at": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
            "payload": {
                "status": "insufficient_history",
                "metrics": {},
                "limitations": limitations or ["Insufficient history to produce walk-forward folds."]
            }
        }
        return empty_preds, empty_results

    preds_df = pd.DataFrame(prediction_rows, columns=COLUMNS["predictions"])
    preds_df = preds_df.sort_values(["target_month", "category"]).reset_index(drop=True)
    validate_table("predictions", preds_df)

    # Compute evaluation metrics across common evaluation pairs with known actuals
    eval_df = preds_df[preds_df["actual_rate"] != ""].copy()
    eval_df["actual_rate"] = eval_df["actual_rate"].astype(float)

    metrics = {}
    cat_metrics = {}

    if not eval_df.empty:
        ridge_errors = eval_df["predicted_rate"] - eval_df["actual_rate"]
        base_errors = eval_df["baseline_rate"] - eval_df["actual_rate"]

        ridge_mae = float(np.mean(np.abs(ridge_errors)))
        ridge_rmse = float(np.sqrt(np.mean(ridge_errors ** 2)))
        base_mae = float(np.mean(np.abs(base_errors)))
        base_rmse = float(np.sqrt(np.mean(base_errors ** 2)))

        ridge_beats = np.abs(ridge_errors) < np.abs(base_errors)
        beat_fraction = float(np.mean(ridge_beats))

        metrics = {
            "ridge_mae": round(ridge_mae, 4),
            "ridge_rmse": round(ridge_rmse, 4),
            "persistence_mae": round(base_mae, 4),
            "persistence_rmse": round(base_rmse, 4),
            "ridge_beat_fraction": round(beat_fraction, 4),
            "n_predictions": len(eval_df),
            "test_months_count": eval_df["target_month"].nunique(),
        }

        # Category-level breakdown
        for c, c_group in eval_df.groupby("category"):
            c_r_err = c_group["predicted_rate"] - c_group["actual_rate"]
            c_b_err = c_group["baseline_rate"] - c_group["actual_rate"]
            cat_metrics[str(c)] = {
                "ridge_mae": round(float(np.mean(np.abs(c_r_err))), 4),
                "ridge_rmse": round(float(np.sqrt(np.mean(c_r_err ** 2))), 4),
                "persistence_mae": round(float(np.mean(np.abs(c_b_err))), 4),
                "persistence_rmse": round(float(np.sqrt(np.mean(c_b_err ** 2))), 4),
                "n_obs": len(c_group),
            }

    results_envelope = {
        "version": 1,
        "source": "FundFlow walk-forward forecasting engine",
        "generated_at": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "payload": {
            "status": "evaluated" if eval_df is not None and not eval_df.empty else "inferred_only",
            "metrics": metrics,
            "category_metrics": cat_metrics,
            "limitations": limitations,
            "evaluation_protocol": "expanding_window_one_step_ahead",
            "training_warmup_months": actual_min_train,
        }
    }

    return preds_df, results_envelope


def save_forecast_outputs(
    preds_df: pd.DataFrame,
    results_envelope: dict,
    outputs_dir: Optional[Path] = None,
) -> tuple[Path, Path]:
    """Save predictions.csv and model_results.json atomically under outputs directory."""
    out_dir = outputs_dir or OUTPUTS_DIR
    out_dir.mkdir(parents=True, exist_ok=True)

    preds_path = out_dir / "predictions.csv"
    results_path = out_dir / "model_results.json"

    preds_tmp = out_dir / "predictions.csv.tmp"
    results_tmp = out_dir / "model_results.json.tmp"

    preds_df.to_csv(preds_tmp, index=False)
    with results_tmp.open("w", encoding="utf-8") as f:
        json.dump(results_envelope, f, indent=2)

    preds_tmp.replace(preds_path)
    results_tmp.replace(results_path)

    return preds_path, results_path
