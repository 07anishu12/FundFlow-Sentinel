"""Official-source adapters for FundFlow Sentinel.

Only observed source values are returned. An unavailable source is represented by
an explicit error; this module never manufactures market or fund-flow observations.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from io import StringIO
import re
from typing import Any

import pandas as pd
import requests

AMFI_NAV_URL = "https://portal.amfiindia.com/spages/NAVAll.txt"
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
    message: str = ""

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def _now_utc() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def fetch_amfi_nav(timeout: int = DEFAULT_TIMEOUT_SECONDS) -> tuple[pd.DataFrame, SourceStatus]:
    """Fetch AMFI's current NAVAll snapshot and parse dated scheme NAV observations.

    NAVAll is a current snapshot, not a historical time series. The app must not
    use it to claim 36-month scheme performance or historical risk statistics.
    """
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
        lines = response.text.splitlines()
        rows: list[dict[str, Any]] = []
        scheme_code: str | None = None
        scheme_name: str | None = None
        for raw in lines:
            line = raw.strip()
            if not line:
                continue
            # Scheme headers commonly contain a numeric scheme code and name.
            header = re.match(r"^(\d{1,8});(.+)$", line)
            if header and line.count(";") == 1:
                scheme_code, scheme_name = header.group(1), header.group(2).strip()
                continue
            parts = line.split(";")
            if len(parts) < 6 or not scheme_code or not scheme_name:
                continue
            nav_date = pd.to_datetime(parts[5].strip(), format="%d-%b-%Y", errors="coerce")
            nav = pd.to_numeric(parts[4].strip(), errors="coerce")
            if pd.isna(nav_date) or pd.isna(nav) or float(nav) < 0:
                continue
            rows.append({
                "scheme_code": scheme_code,
                "scheme_name": scheme_name,
                "isin_div_payout": parts[0].strip() or None,
                "isin_div_reinvestment": parts[1].strip() or None,
                "nav": float(nav),
                "nav_date": nav_date.date().isoformat(),
            })
        frame = pd.DataFrame(rows)
        status.records_received = len(lines)
        status.records_accepted = len(frame)
        if frame.empty:
            status.status = "invalid"
            status.message = "HTTP succeeded, but no valid dated NAV records matched the expected AMFI schema."
        else:
            status.status = "live"
            status.message = "Live current NAV snapshot received from AMFI. This is not a historical NAV series."
        return frame, status
    except requests.RequestException as exc:
        status.message = f"AMFI NAV request failed: {type(exc).__name__}: {exc}"
    except Exception as exc:  # Keep failures visible to the UI rather than showing fabricated values.
        status.message = f"NAV parsing failed: {type(exc).__name__}: {exc}"
    return pd.DataFrame(columns=[
        "scheme_code", "scheme_name", "isin_div_payout",
        "isin_div_reinvestment", "nav", "nav_date"
    ]), status


def unavailable_flows(reason: str = "No verified AMFI monthly-flow download adapter is configured.") -> tuple[pd.DataFrame, SourceStatus]:
    """Return a typed empty result until a verified monthly report parser is available."""
    status = SourceStatus(
        source="AMFI monthly industry flows",
        url="https://www.amfiindia.com/research-information/amfi-monthly",
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
