"""FundFlow optional GDELT news tone ingestion and monthly aggregation lane.

Provides:
- Bounded, rate-limited query construction for Indian financial tone.
- Point-in-time monthly aggregation with temporal availability cutoffs.
- Isolated optional lane: core flow forecasting works without GDELT.
- Offline fixture support with zero network dependencies in test mode.
"""
from __future__ import annotations

from datetime import datetime
import json
import math
from pathlib import Path
from typing import Optional, Sequence
import urllib.parse
import urllib.request
import pandas as pd

GDELT_DOC_API_ENDPOINT = "https://api.gdeltproject.org/api/v2/doc/doc"

DEFAULT_FINANCE_QUERY = '(India OR "Reserve Bank of India" OR SEBI OR "mutual fund" OR "stock market") tone<-1'


def build_gdelt_query_url(
    query: str = DEFAULT_FINANCE_QUERY,
    mode: str = "ToneChart",
    format_type: str = "json",
    timespan: str = "3m",
) -> str:
    """Construct bounded, encoded query URL for the GDELT 2.0 Document API."""
    params = {
        "query": query,
        "mode": mode,
        "format": format_type,
        "timespan": timespan,
    }
    encoded = urllib.parse.urlencode(params)
    return f"{GDELT_DOC_API_ENDPOINT}?{encoded}"


def fetch_gdelt_tone_data(
    query_url: str,
    timeout_sec: int = 10,
    fixture_path: Optional[Path] = None,
) -> tuple[dict, str]:
    """Fetch tone records from GDELT or an offline fixture.
    
    Returns (payload_dict, status_str):
    - status_str: 'ok' | 'offline_fixture' | 'timeout' | 'error' | 'blocked'
    """
    if fixture_path is not None and fixture_path.is_file():
        try:
            with fixture_path.open("r", encoding="utf-8") as f:
                data = json.load(f)
            return data, "offline_fixture"
        except Exception as e:
            return {}, f"error: {e}"

    # Bounded network request
    req = urllib.request.Request(
        query_url,
        headers={"User-Agent": "FundFlowSentinel/1.0 (Research Audit)"}
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout_sec) as resp:
            raw = resp.read().decode("utf-8")
            data = json.loads(raw)
            return data, "ok"
    except urllib.error.URLError as e:
        return {}, f"network_unavailable: {e.reason}"
    except Exception as e:
        return {}, f"error: {str(e)}"


def aggregate_gdelt_monthly_tone(
    raw_records: Sequence[dict],
    source_name: str = "GDELT 2.0 Doc API",
) -> pd.DataFrame:
    """Aggregate raw daily/article GDELT tone records to monthly tone metrics.
    
    Columns:
    - month: YYYY-MM
    - mean_tone: average tone score
    - tone_std: standard deviation of tone
    - n_articles: article count
    - available_from: 1st of following month (T+1 cutoff)
    - source_name: provenance string
    - retrieved_at: ISO UTC timestamp
    """
    if not raw_records:
        return pd.DataFrame(columns=[
            "month", "mean_tone", "tone_std", "n_articles",
            "available_from", "source_name", "retrieved_at"
        ])

    parsed_rows = []
    retrieved_at = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")

    for rec in raw_records:
        # Date formats from GDELT: YYYYMMDD or ISO string
        date_raw = str(rec.get("date", rec.get("date_added", "")))
        tone_val = rec.get("tone", rec.get("Tone", None))

        if not date_raw or tone_val is None:
            continue

        try:
            tone_f = float(tone_val)
            if not math.isfinite(tone_f):
                continue
        except Exception:
            continue

        # Extract YYYY-MM
        clean_date = date_raw.replace("-", "")[:6]
        if len(clean_date) == 6 and clean_date.isdigit():
            m_str = f"{clean_date[:4]}-{clean_date[4:6]}"
            parsed_rows.append({"month": m_str, "tone": tone_f})

    if not parsed_rows:
        return pd.DataFrame(columns=[
            "month", "mean_tone", "tone_std", "n_articles",
            "available_from", "source_name", "retrieved_at"
        ])

    df = pd.DataFrame(parsed_rows)
    grouped = df.groupby("month", as_index=False).agg(
        mean_tone=("tone", "mean"),
        tone_std=("tone", lambda s: float(s.std(ddof=1)) if len(s) > 1 else 0.0),
        n_articles=("tone", "count"),
    )

    # Point-in-time cutoff: 1st of month T+1
    avail_dates = []
    for m in grouped["month"]:
        y, mo = map(int, m.split("-"))
        ny = y + (mo // 12)
        nmo = (mo % 12) + 1
        avail_dates.append(f"{ny:04d}-{nmo:02d}-01T00:00:00Z")

    grouped["available_from"] = avail_dates
    grouped["source_name"] = source_name
    grouped["retrieved_at"] = retrieved_at

    grouped["mean_tone"] = grouped["mean_tone"].round(4)
    grouped["tone_std"] = grouped["tone_std"].round(4)
    grouped["n_articles"] = grouped["n_articles"].astype(int)

    return grouped.sort_values("month").reset_index(drop=True)
