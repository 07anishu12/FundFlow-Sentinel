"""NAV history and scheme master metadata ingestion module.

Independent research data lane supporting both official AMFI endpoints and
labelled, cached unofficial wrappers (mfapi.in). Enforces survivorship bias
disclosures, chunked date-window pagination, duplicate removal, and contract compliance.
"""
from __future__ import annotations

import csv
import datetime
import hashlib
import json
import math
import os
from pathlib import Path
import re
import time
import urllib.error
import urllib.request
from typing import Any

import pandas as pd

from fundflow.contracts import COLUMNS, validate_table
from fundflow.registry import _public_url

AMFI_NAVALL_URL = "https://www.amfiindia.com/spages/NAVAll.txt"
AMFI_NAV_HISTORY_URL = "https://portal.amfiindia.com/DownloadNAVHistoryReport_Po.aspx"
MFAPI_BASE_URL = "https://api.mfapi.in/mf"

SURVIVORSHIP_BIAS_DISCLOSURE = (
    "Survivorship Bias Warning: Scheme lists sourced from current AMFI or API feeds "
    "reflect currently operational schemes and may exclude merged, closed, or "
    "discontinued historical schemes. Performance rankings and analyses using "
    "this lane must disclose survivorship bias."
)


def _parse_amfi_date_to_iso(date_str: str) -> str | None:
    """Convert DD-Mon-YYYY or DD-MM-YYYY to ISO YYYY-MM-DD."""
    date_str = date_str.strip()
    # Try DD-Mon-YYYY (e.g. 01-Jan-2024 or 27-Oct-2026)
    for fmt in ("%d-%b-%Y", "%d-%B-%Y", "%d-%m-%Y", "%Y-%m-%d"):
        try:
            dt = datetime.datetime.strptime(date_str, fmt)
            return dt.strftime("%Y-%m-%d")
        except ValueError:
            continue
    return None


def _format_date_for_amfi(iso_date: str) -> str:
    """Convert YYYY-MM-DD to DD-Mon-YYYY for AMFI URL query parameters."""
    dt = datetime.datetime.strptime(iso_date.strip(), "%Y-%m-%d")
    return dt.strftime("%d-%b-%Y")


def _chunk_date_range(start_date: str, end_date: str, chunk_days: int = 90) -> list[tuple[str, str]]:
    """Split [start_date, end_date] into consecutive windows of at most chunk_days."""
    start_dt = datetime.datetime.strptime(start_date, "%Y-%m-%d")
    end_dt = datetime.datetime.strptime(end_date, "%Y-%m-%d")
    if start_dt > end_dt:
        raise ValueError(f"start_date ({start_date}) cannot be after end_date ({end_date})")

    chunks = []
    current_start = start_dt
    while current_start <= end_dt:
        current_end = min(current_start + datetime.timedelta(days=chunk_days - 1), end_dt)
        chunks.append((current_start.strftime("%Y-%m-%d"), current_end.strftime("%Y-%m-%d")))
        current_start = current_end + datetime.timedelta(days=1)
    return chunks


def fetch_scheme_master(
    source_url: str = AMFI_NAVALL_URL,
    cache_dir: str | Path = "data/raw/nav",
    raw_text: str | None = None,
    timeout: int = 30,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Fetch and parse official AMFI scheme metadata into scheme_master schema.

    Never infers riskometer values from scheme names; missing fields remain null.
    """
    cache_path = Path(cache_dir)
    cache_path.mkdir(parents=True, exist_ok=True)

    provenance_meta = {
        "source_url": source_url,
        "lane": "research_scheme_master",
        "survivorship_bias_disclosure": SURVIVORSHIP_BIAS_DISCLOSURE,
        "retrieved_at": datetime.datetime.now(datetime.timezone.utc).isoformat().replace("+00:00", "Z"),
        "status": "pending",
        "scheme_count": 0,
    }

    content = ""
    if raw_text is not None:
        content = raw_text
        provenance_meta["status"] = "success_from_fixture"
    else:
        _public_url(source_url)
        headers = {"User-Agent": "FundFlowSentinel/1.0 (Research Lane; polite)"}
        req = urllib.request.Request(source_url, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                raw_bytes = resp.read()
                content = raw_bytes.decode("utf-8", errors="ignore")
                provenance_meta["status"] = "success"
                provenance_meta["sha256"] = hashlib.sha256(raw_bytes).hexdigest()
                # Cache raw copy
                today_str = datetime.date.today().isoformat()
                cache_file = cache_path / f"amfi_navall_{today_str}.txt"
                cache_file.write_bytes(raw_bytes)
        except Exception as e:
            provenance_meta["status"] = f"failed: {e}"
            # Graceful degradation: return empty DataFrame with valid schema
            empty_df = pd.DataFrame(columns=list(COLUMNS["scheme_master"]))
            return validate_table("scheme_master", empty_df), provenance_meta

    lines = content.splitlines()
    current_category = "Other"
    current_fund_house = "Unknown AMC"
    records: list[dict[str, Any]] = []

    for line in lines:
        line_clean = line.strip()
        if not line_clean:
            continue

        # Check for Category header, e.g., 'Open Ended Schemes ( Equity Scheme - Large Cap Fund )'
        if line_clean.startswith("Open Ended Schemes") or line_clean.startswith("Close Ended Schemes") or line_clean.startswith("Interval Fund"):
            # Extract category name inside parentheses if available
            m = re.search(r"\(([^)]+)\)", line_clean)
            if m:
                cat_sub = m.group(1).strip()
                if " - " in cat_sub:
                    current_category = cat_sub.split(" - ", 1)[1].strip()
                else:
                    current_category = cat_sub
            else:
                current_category = line_clean
            continue

        # Check for Fund House header (lines without semicolons that aren't headers)
        if ";" not in line_clean:
            if not line_clean.startswith("Scheme Code") and not line_clean.startswith("Note"):
                current_fund_house = line_clean
            continue

        parts = line_clean.split(";")
        if len(parts) >= 6:
            code = parts[0].strip()
            if not code.isdigit():
                continue  # Header row like 'Scheme Code;...'

            scheme_name = parts[3].strip() if len(parts) > 3 else ""
            plan_type = parts[4].strip() if len(parts) > 4 else ""
            option_type = parts[5].strip() if len(parts) > 5 else ""

            # Normalize plan_type / option_type if in scheme_name
            if not plan_type:
                if "direct" in scheme_name.lower():
                    plan_type = "Direct"
                elif "regular" in scheme_name.lower():
                    plan_type = "Regular"
                else:
                    plan_type = "Regular"

            if not option_type:
                if "growth" in scheme_name.lower():
                    option_type = "Growth"
                elif "idcw" in scheme_name.lower() or "dividend" in scheme_name.lower():
                    option_type = "IDCW"
                else:
                    option_type = "Growth"

            # Invariant: do not infer riskometer from names! Riskometer remains null.
            riskometer = ""

            records.append({
                "scheme_code": code,
                "scheme_name": scheme_name,
                "fund_house": current_fund_house,
                "category": current_category,
                "plan_type": plan_type,
                "option_type": option_type,
                "riskometer": riskometer,
            })

    if not records:
        df = pd.DataFrame(columns=list(COLUMNS["scheme_master"]))
    else:
        df = pd.DataFrame(records)[list(COLUMNS["scheme_master"])]
        df = df.drop_duplicates(subset=["scheme_code"]).reset_index(drop=True)

    provenance_meta["scheme_count"] = len(df)
    return validate_table("scheme_master", df), provenance_meta


def fetch_nav_history(
    scheme_codes: list[str],
    start_date: str,
    end_date: str,
    source: str = "amfi",
    cache_dir: str | Path = "data/cache/nav",
    timeout: int = 30,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Fetch daily NAV history chunking by date windows and deduplicating overlaps.

    Supports 'amfi' (official) and 'mfapi' (labelled unofficial wrapper).
    Fails gracefully on bad responses without crashing caller.
    """
    cache_path = Path(cache_dir)
    cache_path.mkdir(parents=True, exist_ok=True)

    date_chunks = _chunk_date_range(start_date, end_date, chunk_days=90)
    provenance_meta: dict[str, Any] = {
        "source": source,
        "start_date": start_date,
        "end_date": end_date,
        "chunks_requested": len(date_chunks),
        "schemes_requested": len(scheme_codes),
        "failures": [],
        "retrieved_at": datetime.datetime.now(datetime.timezone.utc).isoformat().replace("+00:00", "Z"),
        "survivorship_bias_disclosure": SURVIVORSHIP_BIAS_DISCLOSURE,
    }

    all_nav_records: list[dict[str, Any]] = []

    if source.lower() == "mfapi":
        # Unofficial wrapper: query mfapi.in per scheme
        for sc in scheme_codes:
            url = f"{MFAPI_BASE_URL}/{sc}"
            cache_file = cache_path / f"mfapi_{sc}.json"
            data_json = None

            # Check cache first
            if cache_file.is_file():
                try:
                    data_json = json.loads(cache_file.read_text(encoding="utf-8"))
                except Exception:
                    data_json = None

            if data_json is None:
                headers = {"User-Agent": "FundFlowSentinel/1.0 (Research Lane; mfapi wrapper)"}
                req = urllib.request.Request(url, headers=headers)
                try:
                    with urllib.request.urlopen(req, timeout=timeout) as resp:
                        raw = resp.read()
                        data_json = json.loads(raw.decode("utf-8"))
                        cache_file.write_text(json.dumps(data_json, indent=2), encoding="utf-8")
                except Exception as e:
                    provenance_meta["failures"].append({"scheme_code": sc, "url": url, "error": str(e)})
                    continue

            if not data_json or "data" not in data_json:
                provenance_meta["failures"].append({"scheme_code": sc, "url": url, "error": "Invalid JSON response"})
                continue

            for row in data_json["data"]:
                raw_d = row.get("date")
                raw_nav = row.get("nav")
                if not raw_d or not raw_nav:
                    continue
                iso_d = _parse_amfi_date_to_iso(raw_d)
                if not iso_d or not (start_date <= iso_d <= end_date):
                    continue
                try:
                    nav_val = float(raw_nav)
                    if math.isfinite(nav_val) and nav_val > 0:
                        all_nav_records.append({
                            "date": iso_d,
                            "scheme_code": str(sc),
                            "nav": nav_val,
                            "source_url": url,
                        })
                except ValueError:
                    continue

    else:
        # Official AMFI historical NAV query
        target_schemes = set(str(s) for s in scheme_codes)
        base_url = AMFI_NAV_HISTORY_URL

        for c_start, c_end in date_chunks:
            amfi_start = _format_date_for_amfi(c_start)
            amfi_end = _format_date_for_amfi(c_end)
            query_url = f"{base_url}?frmdt={amfi_start}&todt={amfi_end}"

            # Public URL check for base URL
            _public_url(base_url)

            cache_file = cache_path / f"amfi_nav_{c_start}_{c_end}.txt"
            content = ""

            if cache_file.is_file():
                try:
                    content = cache_file.read_text(encoding="utf-8")
                except Exception:
                    content = ""

            if not content:
                headers = {"User-Agent": "FundFlowSentinel/1.0 (Research Lane; polite)"}
                req = urllib.request.Request(query_url, headers=headers)
                try:
                    with urllib.request.urlopen(req, timeout=timeout) as resp:
                        raw = resp.read()
                        content = raw.decode("utf-8", errors="ignore")
                        cache_file.write_text(content, encoding="utf-8")
                except Exception as e:
                    provenance_meta["failures"].append({
                        "chunk": f"{c_start}..{c_end}",
                        "url": query_url,
                        "error": str(e)
                    })
                    continue

            # Parse AMFI semicolon output
            for line in content.splitlines():
                line = line.strip()
                if not line or ";" not in line:
                    continue
                parts = line.split(";")
                if len(parts) >= 8:
                    sc = parts[0].strip()
                    if target_schemes and sc not in target_schemes:
                        continue
                    nav_str = parts[6].strip()
                    dt_str = parts[7].strip()
                    iso_d = _parse_amfi_date_to_iso(dt_str)
                    if not iso_d or not (start_date <= iso_d <= end_date):
                        continue
                    try:
                        nav_val = float(nav_str)
                        if math.isfinite(nav_val) and nav_val > 0:
                            all_nav_records.append({
                                "date": iso_d,
                                "scheme_code": sc,
                                "nav": nav_val,
                                "source_url": base_url,
                            })
                    except ValueError:
                        continue

    if not all_nav_records:
        df = pd.DataFrame(columns=list(COLUMNS["nav_daily"]))
    else:
        df = pd.DataFrame(all_nav_records)[list(COLUMNS["nav_daily"])]
        # Deduplicate overlaps across chunks / repeated fetches
        df = df.drop_duplicates(subset=["date", "scheme_code"]).sort_values(["date", "scheme_code"]).reset_index(drop=True)

    provenance_meta["record_count"] = len(df)
    return validate_table("nav_daily", df), provenance_meta
