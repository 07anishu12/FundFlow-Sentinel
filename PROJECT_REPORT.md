# FundFlow Sentinel — Project Report

## 1. Project objective

FundFlow Sentinel is a transparent research dashboard for monitoring Indian mutual-fund industry flows, studying redemption pressure, evaluating time-series forecasts, and documenting uncertainty and data limitations. It is a decision-support research tool, not investment advice and not a measure of a scheme's ability to meet redemptions.

## 2. Financial goals

1. **Monitor industry flow conditions:** track observed monthly gross redemptions, net flows, and closing assets under management (AUM) at the category level when the official source provides those fields.
2. **Measure redemption pressure:** calculate a redemption ratio only with a documented, time-aligned denominator and disclose the period and units.
3. **Forecast future category flows:** compare persistence, seasonal-naive, and regularized regression baselines using chronological walk-forward validation.
4. **Quantify forecast error:** report signed gap as actual minus forecast, absolute gap, and percentage error only when the actual is observed and the denominator is non-zero.
5. **Describe uncertainty:** derive prediction envelopes from genuine out-of-sample residuals; do not fabricate confidence intervals.
6. **Support scenario analysis:** estimate conditional outflows only when observed AUM, validated forecasts, and explicit scenario assumptions exist.
7. **Research schemes separately:** use scheme-specific dated NAV observations for returns and risk metrics. Never assign industry-category redemptions to a particular scheme.
8. **Maintain auditability:** display source, observation period, retrieval time, freshness, status, units, and data-quality results for each dataset.
9. **Prevent misleading outputs:** distinguish observed, forecast, scenario, cached, unavailable, and explicitly reported zero values.

## 3. Financial definitions

- **Gross redemptions:** total redemption value reported for the relevant industry category and period.
- **Net flow:** subscriptions minus redemptions, according to the official source definition.
- **Closing AUM:** category assets under management at the reporting period's close.
- **Redemption rate:** gross redemptions divided by a specified AUM denominator. The denominator and timing must be documented; do not assume a formula when the source does not define it.
- **Forecast gap:** actual minus forecast for the same target, unit, entity, and period.
- **Absolute gap:** absolute value of the forecast gap.
- **Absolute percentage error:** absolute gap divided by the absolute actual, multiplied by 100; unavailable when actual is missing or zero.
- **Scenario outflow:** conditional model output under stated assumptions, not a guaranteed outcome and not a measure of underlying-asset liquidity.

## 4. Data governance

AMFI monthly reports are the preferred official source for category-level monthly industry data. AMFI's NAVAll feed is a current scheme NAV snapshot and must not be treated as a historical time series. A historical NAV source is required before calculating multi-year returns, volatility, maximum drawdown, Sortino ratio, or rolling consistency. Missing observations remain missing. No synthetic values are loaded into the production UI.

## 5. Forecast methodology requirements

A production forecasting workflow should compare persistence and seasonal-naive baselines with a regularized regression model. Use expanding-window chronological evaluation, at least 36 monthly training observations where available, training-fold-only transformations, and inner time-series cross-validation for hyperparameter selection. Report held-out periods, MAE, RMSE, baseline win rate, and sample counts. Do not claim predictive skill unless results support it.

## 6. Alert and sentiment governance

Risk alerts require documented, testable thresholds and sufficient historical observations. Media sentiment is corroborating context only; it must not silently change forecast values or fund rankings. Require a disclosed minimum article count and a historical comparison threshold before reporting sentiment confirmation. Otherwise report unavailable/insufficient data.

## 7. Current implementation status

The repository currently contains a source-first Streamlit prototype. It can fetch the current AMFI NAVAll snapshot when a user requests refresh. Monthly flow parsing, historical NAV ingestion, validated forecasting, live sentiment ingestion, calibrated stress analysis, and cloud deployment are not represented as complete until implemented and independently tested. This report intentionally distinguishes implemented capabilities from planned work.

## 8. Limitations

- Category-level industry data cannot establish scheme-level redemption amounts.
- AUM does not measure cash available to redeem, holdings liquidity, or redemption capacity.
- Active-scheme-only comparisons have survivorship bias.
- Source access, workbook format, terms, and data coverage may change.
- Forecast estimates are uncertain and are not investment recommendations.
