"""Frozen v1 CSV contracts. No I/O or model dependencies."""
import json
import math
import re
from datetime import datetime
import pandas as pd

COLUMNS = {'flows_category_month': ('month',
                          'category',
                          'gross_inflow_cr',
                          'gross_redemption_cr',
                          'net_flow_cr',
                          'aum_close_cr',
                          'aaum_cr',
                          'available_from',
                          'source_url',
                          'retrieved_at'),
 'market_month': ('month',
                  'nifty_return',
                  'nifty_drawdown_3m',
                  'vix_mean',
                  'vix_change',
                  'available_from',
                  'source_name',
                  'retrieved_at'),
 'feature_matrix': ('as_of',
                    'target_month',
                    'category',
                    'rate_lag0',
                    'rate_lag1',
                    'rate_lag2',
                    'rate_lag11',
                    'roll_mean3',
                    'roll_std3',
                    'delta1',
                    'net_flow_rate_lag0',
                    'aum_growth_lag0',
                    'nifty_return_lag0',
                    'nifty_drawdown_3m',
                    'vix_mean_lag0',
                    'vix_change_lag0',
                    'target_rate'),
 'predictions': ('as_of',
                 'target_month',
                 'category',
                 'model_id',
                 'predicted_rate',
                 'baseline_rate',
                 'actual_rate',
                 'is_out_of_sample',
                 'train_start',
                 'train_end',
                 'contrib_json'),
 'alerts': ('as_of',
            'target_month',
            'category',
            'level',
            'rules_triggered',
            'forecast_rate',
            'forecast_percentile',
            'robust_z',
            'momentum_3m',
            'est_outflow_cr',
            'reference_aum_cr',
            'aum_month',
            'sentiment_status',
            'sentiment_note',
            'data_freshness_days',
            'limitations'),
 'nav_daily': ('date', 'scheme_code', 'nav', 'source_url'),
 'scheme_master': ('scheme_code',
                   'scheme_name',
                   'fund_house',
                   'category',
                   'plan_type',
                   'option_type',
                   'riskometer'),
 'shortlist': ('scheme_code',
               'scheme_name',
               'category',
               'cagr_3y',
               'vol',
               'max_drawdown',
               'sortino',
               'consistency',
               'p_return',
               'p_consistency',
               'p_drawdown',
               'p_risk_adj',
               'research_score',
               'metric_date',
               'history_years'),
 'sentiment_items': ('article_id',
                     'published_at',
                     'title',
                     'source_name',
                     'url',
                     'p_pos',
                     'p_neg',
                     'p_neu',
                     'label',
                     'score',
                     'topic_tags',
                     'is_live',
                     'model_id'),
 'sentiment_agg': ('period', 'topic', 'mean_score', 'neg_share', 'n_articles', 'is_live')}
TEXT = set("month category available_from source_url retrieved_at as_of target_month source_name model_id train_start train_end contrib_json level rules_triggered aum_month sentiment_status sentiment_note limitations date scheme_code scheme_name fund_house plan_type option_type riskometer metric_date article_id published_at title url label topic_tags period topic".split())
BOOLEAN = {"is_live", "is_out_of_sample"}
NULLABLE = {"riskometer", "actual_rate", "target_rate", "sentiment_note"}
MONTHS = {"month", "target_month", "aum_month"}
DATES = {"date", "metric_date", "period"}
TIMESTAMPS = {"available_from", "retrieved_at", "as_of", "train_start", "train_end", "published_at"}
KEYS = {'flows_category_month': ['month', 'category'],
 'market_month': ['month'],
 'feature_matrix': ['as_of', 'target_month', 'category'],
 'predictions': ['as_of', 'target_month', 'category', 'model_id'],
 'alerts': ['as_of', 'target_month', 'category'],
 'nav_daily': ['date', 'scheme_code'],
 'scheme_master': ['scheme_code'],
 'shortlist': ['scheme_code', 'metric_date'],
 'sentiment_items': ['article_id'],
 'sentiment_agg': ['period', 'topic', 'is_live']}


def validate_table(name: str, frame: pd.DataFrame) -> pd.DataFrame:
    """Validate exact ordered columns and values; return input without coercion.

    Empty tables are valid for empty states. Unknown extensions require approval.
    Percent rates are percentage points, sentiment shares are fractions.
    """
    if name not in COLUMNS:
        raise ValueError(f"Unknown contract: {name}")
    if tuple(frame.columns) != COLUMNS[name]:
        raise ValueError(f"{name}: expected ordered columns {COLUMNS[name]}")
    for column in frame:
        for value in frame[column]:
            if pd.isna(value) or value == "":
                if column not in NULLABLE:
                    raise ValueError(f"{name}.{column}: required")
                continue
            text = str(value)
            if column in BOOLEAN:
                if text.lower() not in {"true", "false"}:
                    raise ValueError(f"{column}: boolean required")
            elif column in MONTHS:
                if not re.fullmatch(r"\d{4}-(0[1-9]|1[0-2])", text):
                    raise ValueError(f"{column}: YYYY-MM required")
            elif column in DATES:
                if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", text):
                    raise ValueError(f"{column}: ISO date required")
                datetime.strptime(text, "%Y-%m-%d")
            elif column in TIMESTAMPS:
                parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
                if "T" not in text or parsed.utcoffset() is None or parsed.utcoffset().total_seconds() != 0:
                    raise ValueError(f"{column}: ISO UTC timestamp required")
            elif column not in TEXT:
                if isinstance(value, bool) or not math.isfinite(float(value)):
                    raise ValueError(f"{column}: finite numeric value required")
            if column == "contrib_json" and not isinstance(json.loads(text), dict):
                raise ValueError("contrib_json: object required")
            if column == "level" and text not in {"Normal", "Elevated", "Critical"}:
                raise ValueError("Invalid alert level")
            if column in {"p_pos", "p_neg", "p_neu", "neg_share"} and not 0 <= float(value) <= 1:
                raise ValueError(f"{column}: fraction outside [0,1]")
    for column in {"n_articles", "data_freshness_days"} & set(frame.columns):
        values = pd.to_numeric(frame[column])
        if ((values < 0) | (values % 1 != 0)).any():
            raise ValueError(f"{column}: nonnegative integer required")
    if frame.duplicated(KEYS[name]).any():
        raise ValueError(f"{name}: duplicate key")
    return frame
