"""Historical Nifty return and India VIX ingestion module.

Fetches and aggregates daily market observations into the frozen market_month contract:
- nifty_return: monthly return in percentage points
- nifty_drawdown_3m: 3-month peak-to-trough percentage drawdown
- vix_mean: monthly mean of closing India VIX
- vix_change: monthly net change in closing India VIX
- available_from: conservative start of month T+1 cutoff

Enforces optional-feature policy: fails gracefully to verified snapshots on network error,
never fills missing features with zero as a shortcut, and records wrapper provenance.
"""
from __future__ import annotations

import csv
import datetime
import json
import math
from pathlib import Path
import urllib.error
import urllib.request
from typing import Any

import pandas as pd

from fundflow.contracts import COLUMNS, validate_table
from fundflow.registry import append_record, _public_url

YAHOO_BASE_URL = "https://query1.finance.yahoo.com/v8/finance/chart"
NIFTY_SYMBOL = "^NSEI"
VIX_SYMBOL = "^INDIAVIX"

SOURCE_NAME_WRAPPER = "yfinance (unofficial wrapper)"
SOURCE_NAME_OFFICIAL = "NSE Indices / India VIX"


def _get_following_month_start(month_str: str) -> str:
    """Return ISO UTC timestamp for 1st of month T+1 at 00:00:00Z."""
    parts = month_str.split("-")
    yr, mo = int(parts[0]), int(parts[1])
    if mo == 12:
        next_yr, next_mo = yr + 1, 1
    else:
        next_yr, next_mo = yr, mo + 1
    dt = datetime.datetime(next_yr, next_mo, 1, 0, 0, 0, tzinfo=datetime.timezone.utc)
    return dt.isoformat().replace("+00:00", "Z")


def fetch_daily_series(
    symbol: str,
    range_str: str = "5y",
    timeout: int = 30,
) -> pd.DataFrame:
    """Fetch daily closing series for a ticker symbol from public market API."""
    url = f"{YAHOO_BASE_URL}/{symbol}?range={range_str}&interval=1d"
    headers = {"User-Agent": "FundFlowSentinel/1.0 (Research Lane; market)"}
    req = urllib.request.Request(url, headers=headers)

    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = json.loads(resp.read().decode("utf-8"))

    chart = data.get("chart", {})
    results = chart.get("result")
    if not results or "timestamp" not in results[0]:
        raise ValueError(f"No chart data returned for {symbol}")

    res = results[0]
    ts = res["timestamp"]
    quotes = res.get("indicators", {}).get("quote", [{}])[0]
    closes = quotes.get("close", [])

    dates = [
        datetime.datetime.fromtimestamp(t, tz=datetime.timezone.utc).strftime("%Y-%m-%d")
        for t in ts
    ]

    df = pd.DataFrame({"date": dates, "close": closes}).dropna().reset_index(drop=True)
    df["close"] = df["close"].astype(float)
    df = df[df["close"] > 0].reset_index(drop=True)
    df["month"] = df["date"].str[:7]
    return df


def aggregate_market_monthly(
    df_nifty: pd.DataFrame,
    df_vix: pd.DataFrame,
    source_name: str = SOURCE_NAME_WRAPPER,
    retrieved_at: str | None = None,
) -> pd.DataFrame:
    """Compute monthly return, 3M drawdown, VIX mean and change from daily series."""
    if df_nifty.empty or df_vix.empty:
        return pd.DataFrame(columns=list(COLUMNS["market_month"]))

    now_utc = retrieved_at or datetime.datetime.now(datetime.timezone.utc).isoformat().replace("+00:00", "Z")

    nifty_months = set(df_nifty["month"])
    vix_months = set(df_vix["month"])
    common_months = sorted(nifty_months & vix_months)

    records = []
    for i, m in enumerate(common_months):
        n_m = df_nifty[df_nifty["month"] == m].sort_values("date")
        v_m = df_vix[df_vix["month"] == m].sort_values("date")

        # Require at least 2 observations in the month
        if len(n_m) < 2 or len(v_m) < 2:
            continue

        # Monthly return: (last - first) / first * 100
        first_nifty = n_m["close"].iloc[0]
        last_nifty = n_m["close"].iloc[-1]
        nifty_ret = ((last_nifty - first_nifty) / first_nifty) * 100.0

        # 3-Month rolling peak-to-trough drawdown of Nifty
        window_months = common_months[max(0, i - 2) : i + 1]
        n_window = df_nifty[df_nifty["month"].isin(window_months)]
        peak_nifty = n_window["close"].max()
        nifty_dd_3m = ((last_nifty - peak_nifty) / peak_nifty) * 100.0

        # VIX mean and change
        vix_mean = float(v_m["close"].mean())
        vix_change = float(v_m["close"].iloc[-1] - v_m["close"].iloc[0])

        avail_from = _get_following_month_start(m)

        records.append({
            "month": m,
            "nifty_return": round(float(nifty_ret), 4),
            "nifty_drawdown_3m": round(float(nifty_dd_3m), 4),
            "vix_mean": round(vix_mean, 4),
            "vix_change": round(vix_change, 4),
            "available_from": avail_from,
            "source_name": source_name,
            "retrieved_at": now_utc,
        })

    if not records:
        return pd.DataFrame(columns=list(COLUMNS["market_month"]))

    df_out = pd.DataFrame(records)[list(COLUMNS["market_month"])].sort_values("month").reset_index(drop=True)
    return validate_table("market_month", df_out)


def fetch_and_build_market_month(
    output_path: str | Path = "data/processed/market_month.csv",
    snapshot_fallback_path: str | Path = "data/snapshots/fixtures/market_month.csv",
    source_name: str = SOURCE_NAME_WRAPPER,
    timeout: int = 30,
    force_snapshot: bool = False,
    registry_path: str | Path | None = None,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Fetch market series, aggregate, and save to processed dataset.

    Implements optional-feature policy: falls back to verified snapshots on failure
    without crashing or returning unlabelled zero fills.
    """
    out_p = Path(output_path)
    snap_p = Path(snapshot_fallback_path)
    now_utc = datetime.datetime.now(datetime.timezone.utc).isoformat().replace("+00:00", "Z")

    provenance: dict[str, Any] = {
        "source": source_name,
        "status": "pending",
        "retrieved_at": now_utc,
        "is_snapshot_fallback": False,
        "records_count": 0,
    }

    df_result = pd.DataFrame(columns=list(COLUMNS["market_month"]))

    if not force_snapshot:
        try:
            df_nifty = fetch_daily_series(NIFTY_SYMBOL, range_str="5y", timeout=timeout)
            df_vix = fetch_daily_series(VIX_SYMBOL, range_str="5y", timeout=timeout)
            df_result = aggregate_market_monthly(df_nifty, df_vix, source_name=source_name, retrieved_at=now_utc)
            provenance["status"] = "success"
        except Exception as e:
            provenance["status"] = f"live_fetch_failed: {e}"

    # If live fetch failed or force_snapshot requested, apply snapshot fallback
    if (df_result.empty or force_snapshot) and snap_p.is_file():
        try:
            snap_df = pd.read_csv(snap_p)
            df_result = validate_table("market_month", snap_df)
            provenance["status"] = "snapshot_fallback"
            provenance["is_snapshot_fallback"] = True
            provenance["snapshot_source"] = str(snap_p)
        except Exception as ex:
            provenance["status"] = f"snapshot_fallback_failed: {ex}"

    # Save to output path if records are present
    if not df_result.empty:
        out_p.parent.mkdir(parents=True, exist_ok=True)
        tmp_p = out_p.with_suffix(".tmp")
        df_result.to_csv(tmp_p, index=False)
        tmp_p.replace(out_p)

    provenance["records_count"] = len(df_result)

    # Optional registry update
    if registry_path and Path(registry_path).is_file():
        record = {
            "source_name": "NSE India VIX",
            "url": "https://www.nseindia.com/static/market-data/nse-data-policy",
            "data_type": "market_daily",
            "frequency": "daily",
            "retrieved_at": now_utc if provenance["status"] == "success" else "",
            "terms_url": "https://www.nseindia.com/static/market-data/nse-data-policy",
            "permitted_use": "Subject to applicable data policy; wrapper used for research.",
            "attribution": "NSE / Yahoo Finance API as wrapper.",
            "redistribution_status": "restricted",
            "source_confidence": "unofficial" if "wrapper" in source_name else "official",
            "sha256": "",
            "last_outcome": "success" if provenance["status"] == "success" else "failed",
            "status": "restricted",
            "checked_on": datetime.date.today().isoformat(),
        }
        try:
            append_record(registry_path, record)
        except Exception:
            pass

    return df_result, provenance
