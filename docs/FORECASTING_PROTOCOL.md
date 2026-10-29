# FundFlow Forecasting Protocol & Model Evaluation Specification

**Specification Version:** 1.0.0  
**Owner:** Agent A (Quantitative Modeling Architecture)  
**Contract Authority:** [`src/fundflow/contracts.py:COLUMNS['predictions']`](file:///Users/anny/Desktop/mutual-fund/src/fundflow/contracts.py#L43), [`outputs/model_results.json`](file:///Users/anny/Desktop/mutual-fund/docs/INTERFACES.md#L60)  
**Implementation Module:** [`src/fundflow/forecasting.py`](file:///Users/anny/Desktop/mutual-fund/src/fundflow/forecasting.py)  
**Verification Suite:** [`tests/test_forecasting.py`](file:///Users/anny/Desktop/mutual-fund/tests/test_forecasting.py)

---

## 1. Executive Summary & Model Hierarchy

This document specifies the core machine learning and statistical forecasting methodology for category-level mutual fund gross redemption rates.

The platform evaluates two distinct models on identical out-of-sample forecast dates:
1. **Persistence Baseline (`persistence-v1`):**
   $$\hat{R}_{\text{base}}(c, t+1) = R(c, t)$$
   Assumes that the redemption rate in the target month will equal the latest known redemption rate available at the forecast decision origin ($T_{\text{as\_of}}$).
2. **Pooled Ridge Regression (`ridge-pooled-v1`):**
   A cross-sectional linear model with $L_2$ regularization trained across all universe categories simultaneously:
   $$\hat{R}(c, t+1) = \mathbf{w}^T \mathbf{x}(c, t) + \mathbf{v}^T \mathbf{d}_c + b$$
   where $\mathbf{x}(c, t)$ comprises 13 numeric predictors, $\mathbf{d}_c$ is a one-hot category indicator vector, and $\lambda = \alpha$ is chosen via inner time-series cross-validation.

---

## 2. Walk-Forward Evaluation Protocol

To prevent look-ahead bias and non-stationarity overfitting:
1. **Expanding-Window Protocol:**
   Evaluation proceeds chronologically month-by-month. For each target month $t_{\text{test}}$, the training fold includes all prior months $t < t_{\text{test}}$ whose labels and features were published before $T_{\text{as\_of}}(t_{\text{test}})$.
2. **No Random Splitting:**
   K-fold cross-validation, train-test shuffles, and random splits are strictly prohibited.
3. **In-Fold Preprocessing Fitting:**
   Standard scalers and category one-hot encoders are fitted exclusively on the training slice of each fold and transformed onto the single test step.
4. **Warm-Up Policy:**
   - Standard minimum warm-up is **36 months** of historical training data.
   - If empirical data span is shorter, the protocol automatically executes a **diagnostic evaluation** with an explicit label (`diagnostic_reduced_history: true`) rather than silently altering the target window or reporting in-sample metrics.
5. **Inner Hyperparameter Tuning:**
   The regularization parameter $\alpha \in [0.1, 1.0, 10.0, 100.0]$ is selected inside each fold using `TimeSeriesSplit` on training rows only. Outer test data is never observed during tuning.

---

## 3. Evaluation Metrics & Artifact Contracts

For every forecast fold, predictions and ground truth are persisted into two contract files:

### 3.1 `outputs/predictions.csv`
Conforms to [`COLUMNS['predictions']`](file:///Users/anny/Desktop/mutual-fund/src/fundflow/contracts.py#L43):
* `as_of`: Decision cutoff timestamp (ISO UTC).
* `target_month`: Target calendar month being predicted ($t$).
* `category`: Canonical category name.
* `model_id`: `"ridge-pooled-v1"`.
* `predicted_rate`: Out-of-sample forecast rate.
* `baseline_rate`: Persistence baseline forecast rate.
* `actual_rate`: Realized rate (when known) or blank during inference.
* `is_out_of_sample`: `True`.
* `train_start`, `train_end`: ISO UTC bounds of training fold.
* `contrib_json`: Serialized JSON object containing feature coefficients, $\alpha$, and intercept.

### 3.2 `outputs/model_results.json`
Conforms to the UI loader JSON envelope contract:
```json
{
  "version": 1,
  "source": "FundFlow walk-forward forecasting engine",
  "generated_at": "2026-10-28T18:00:00Z",
  "payload": {
    "status": "evaluated",
    "metrics": {
      "ridge_mae": 0.1420,
      "ridge_rmse": 0.1850,
      "persistence_mae": 0.1650,
      "persistence_rmse": 0.2100,
      "ridge_beat_fraction": 0.6250,
      "n_predictions": 36,
      "test_months_count": 12
    },
    "category_metrics": { ... },
    "limitations": [ ... ]
  }
}
```
