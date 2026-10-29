"""Official-source adapters for FundFlow Sentinel.

Only observed source values are returned. An unavailable source is represented by
an explicit error; this module never manufactures market or fund-flow observations.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import re
from typing import Any

import pandas as pd
import requests

AMFI_NAV_URL = "https://portal.amfiindia.com/spages/NAVAll.txt"
AMFI_MONTHLY_URL = "https://www.amfiindia.com/research-information/amfi-monthly"
DEFAULT_TIMEOUT_SECONDS = 20


@dataclass
class SourceStatus:
    source: str
    url: str
    status: str
    retrieved_at_utc: str
    http_status: int | None = None
    records_received: int = 0
    records_accepted: int = 0
    latest_observation_date: str | None = None
    message: str = ""

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def _now_utc() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def parse_amfi_nav_text(text: str) -> tuple[pd.DataFrame, int]:
    """Parse AMFI's 6- or 8-column NAVAll layouts.

    Scheme rows contain a numeric scheme code; section/AMC/header lines are
    ignored. The value is a latest-snapshot observation, not a historical series.
    """
    rows: list[dict[str, Any]] = []
    rejected = 0
    current_amc: str | None = None
    current_category: str | None = None

    for raw in text.splitlines():
        line = raw.strip().lstrip("\ufeff")
        if not line:
            continue
        parts = [part.strip() for part in line.split(";")]
        normalized = [re.sub(r"\s+", " ", part).casefold() for part in parts]

        # Both official layouts have a column header row, so skip it explicitly.
        if normalized and "scheme code" in normalized[0] and "date" in normalized:
            continue
        if not re.fullmatch(r"\d{1,8}", parts[0] if parts else ""):
            # Carry visible context from section/AMC headings for auditing.
            if ";" not in line:
                if "scheme" in line.casefold() and "(" in line:
                    current_category = line
                elif "mutual fund" in line.casefold():
                    current_amc = line
            continue

        # Layout A: Scheme Code;ISIN1;ISIN2;Scheme Name;NAV;Date
        # Layout B: Scheme Code;ISIN1;ISIN2;Scheme Name;Plan;Option;NAV;Date
        if len(parts) == 6:
            code, isin1, isin2, name, nav_text, date_text = parts
        elif len(parts) == 8:
            code, isin1, isin2, name, plan, option, nav_text, date_text = parts
            name = " ".join(part for part in (name, plan, option) if part and part != "-")
        else:
            rejected += 1
            continue

        nav_date = pd.to_datetime(date_text, format="%d-%b-%Y", errors="coerce")
        nav_value = pd.to_numeric(nav_text, errors="coerce")
        if pd.isna(nav_date) or pd.isna(nav_value) or float(nav_value) < 0 or not name:
            rejected += 1
            continue

        rows.append({
            "scheme_code": code,
            "scheme_name": name,
            "isin_div_payout": None if isin1 in ("", "-") else isin1,
            "isin_div_reinvestment": None if isin2 in ("", "-") else isin2,
            "nav": float(nav_value),
            "nav_date": nav_date.date().isoformat(),
            "amc": current_amc,
            "scheme_category": current_category,
        })

    columns = [
        "scheme_code", "scheme_name", "isin_div_payout",
        "isin_div_reinvestment", "nav", "nav_date", "amc", "scheme_category",
    ]
    return pd.DataFrame(rows, columns=columns), rejected


def fetch_amfi_nav(timeout: int = DEFAULT_TIMEOUT_SECONDS) -> tuple[pd.DataFrame, SourceStatus]:
    """Fetch AMFI's current NAVAll snapshot; fail visibly instead of fabricating data."""
    status = SourceStatus(
        source="AMFI NAVAll",
        url=AMFI_NAV_URL,
        status="unavailable",
        retrieved_at_utc=_now_utc(),
    )
    try:
        response = requests.get(
            AMFI_NAV_URL,
            timeout=timeout,
            headers={"User-Agent": "FundFlowSentinel/1.0 (research dashboard)"},
        )
        status.http_status = response.status_code
        response.raise_for_status()
        status.records_received = len(response.text.splitlines())
        frame, rejected = parse_amfi_nav_text(response.text)
        status.records_accepted = len(frame)
        status.latest_observation_date = frame["nav_date"].max() if not frame.empty else None
        if frame.empty:
            status.status = "invalid"
            status.message = (
                f"HTTP succeeded but no valid dated rows matched AMFI's supported 6/8-column schema; "
                f"rejected candidate rows={rejected}."
            )
        else:
            status.status = "live"
            status.message = (
                f"Parsed current NAV snapshot; accepted={len(frame)}, rejected={rejected}. "
                "This feed is not a historical NAV time series, and some schemes may have stale last NAV dates."
            )
        return frame, status
    except requests.RequestException as exc:
        status.message = f"AMFI NAV request failed: {type(exc).__name__}: {exc}"
    except Exception as exc:
        status.message = f"NAV parsing failed: {type(exc).__name__}: {exc}"
    columns = [
        "scheme_code", "scheme_name", "isin_div_payout",
        "isin_div_reinvestment", "nav", "nav_date", "amc", "scheme_category",
    ]
    return pd.DataFrame(columns=columns), status


def unavailable_flows(reason: str = "Official AMFI monthly-flow parser is not configured.") -> tuple[pd.DataFrame, SourceStatus]:
    """Return typed empty data until the monthly workbook schema is verified."""
    status = SourceStatus(
        source="AMFI monthly industry flows",
        url=AMFI_MONTHLY_URL,
        status="unavailable",
        retrieved_at_utc=_now_utc(),
        message=reason,
    )
    columns = [
        "observation_month", "category", "gross_redemption_cr",
        "net_flow_cr", "aum_close_cr", "source_url",
    ]
    return pd.DataFrame(columns=columns), status


def frame_is_observed(frame: pd.DataFrame) -> bool:
    """True only when at least one real row is present."""
    return not frame.empty
