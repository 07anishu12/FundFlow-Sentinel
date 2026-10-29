"""Official AMFI monthly flow ingestion and parsing module.

Extracts category-level flows from official AMFI monthly reports across
all historical layouts (FY2018-19 to FY2026-27). Guarantees untouched raw
storage, provenance tracking, layout error checking, and exact contract compliance.
"""
from __future__ import annotations

import csv
import datetime
import hashlib
import io
import json
import math
import os
from pathlib import Path
import re
import shutil
import tempfile
import time
import urllib.error
import urllib.request
from typing import Any

import openpyxl
import pandas as pd
import xlrd

from fundflow.contracts import COLUMNS, validate_table
from fundflow.registry import file_sha256, _public_url, append_record

MONTH_NAME_MAP = {
    "january": "01", "jan": "01",
    "february": "02", "feb": "02",
    "march": "03", "mar": "03",
    "april": "04", "apr": "04",
    "may": "05",
    "june": "06", "jun": "06",
    "july": "07", "jul": "07",
    "august": "08", "aug": "08",
    "september": "09", "sep": "09", "sept": "09",
    "october": "10", "oct": "10",
    "november": "11", "nov": "11",
    "december": "12", "dec": "12",
}

OOXML_MAGIC = b"PK\x03\x04"
BIFF8_MAGIC = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"


def detect_file_format(path: str | Path) -> str:
    """Detect binary format of an AMFI spreadsheet report by magic bytes."""
    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError(f"Report file not found: {path}")
    if path.stat().st_size == 0:
        raise ValueError(f"Report file is empty (0 bytes): {path}")

    with path.open("rb") as stream:
        header = stream.read(8)

    if header.startswith(OOXML_MAGIC):
        return "OOXML"
    if header.startswith(BIFF8_MAGIC):
        return "BIFF8"
    raise ValueError(
        f"Unrecognized file format for {path.name}: magic bytes {header.hex()} "
        f"match neither OOXML (PK..) nor BIFF8 (d0cf..)"
    )


def _clean_numeric(value: Any) -> float | None:
    """Parse numeric cell value; handles formatted strings, commas, and dashes."""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        if math.isnan(value) or not math.isfinite(value):
            return None
        return float(value)
    text = str(value).strip().replace(",", "")
    if text in {"-", "", "N.A.", "NA", "NIL", "Nil", "@"}:
        return None
    try:
        val = float(text)
        return val if math.isfinite(val) else None
    except ValueError:
        return None


def _parse_month_string(text: str) -> str | None:
    """Extract YYYY-MM from text such as 'September 2024' or 'amsep2024repo.xls'."""
    # Pattern 1: 'Month Year' e.g. 'September 2024' or 'Apr 2019'
    m = re.search(r"\b(january|february|march|april|may|june|july|august|september|sept|october|november|december|jan|feb|mar|apr|jun|jul|aug|sep|oct|nov|dec)\b[\s_-]*(\d{4}|\d{2})", text, re.IGNORECASE)
    if m:
        mon_str = m.group(1).lower()
        yr_str = m.group(2)
        if len(yr_str) == 2:
            yr_str = "20" + yr_str
        mon = MONTH_NAME_MAP.get(mon_str)
        if mon:
            return f"{yr_str}-{mon}"

    # Pattern 2: 'amsep2024' or 'amapr19'
    m2 = re.search(r"am(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)(\d{2,4})", text, re.IGNORECASE)
    if m2:
        mon_str = m2.group(1).lower()
        yr_str = m2.group(2)
        if len(yr_str) == 2:
            yr_str = "20" + yr_str
        mon = MONTH_NAME_MAP.get(mon_str)
        if mon:
            return f"{yr_str}-{mon}"
    return None


def _parse_release_date_to_iso(date_str: str) -> str | None:
    """Parse 'Released on DD-Mon-YYYY' or similar into ISO UTC string."""
    m = re.search(r"Released\s+on\s+([0-9]{1,2})[-./]([A-Za-z0-9]+)[-./]([0-9]{2,4})", date_str, re.IGNORECASE)
    if not m:
        # Try DD-Mon-YYYY without 'Released on'
        m = re.search(r"\b([0-9]{1,2})[-./]([A-Za-z]{3,9})[-./]([0-9]{4})\b", date_str)
    if not m:
        return None

    day_s, mon_s, yr_s = m.group(1), m.group(2).lower(), m.group(3)
    if len(yr_s) == 2:
        yr_s = "20" + yr_s
    mon_num = MONTH_NAME_MAP.get(mon_s)
    if not mon_num:
        # maybe mon_s is numeric
        if mon_s.isdigit() and 1 <= int(mon_s) <= 12:
            mon_num = f"{int(mon_s):02d}"
        else:
            return None
    try:
        dt = datetime.datetime(int(yr_s), int(mon_num), int(day_s), 0, 0, 0, tzinfo=datetime.timezone.utc)
        return dt.isoformat().replace("+00:00", "Z")
    except ValueError:
        return None


def download_report(
    url: str,
    dest_dir: str | Path = "data/raw/amfi",
    timeout: int = 30,
    max_retries: int = 3,
    min_delay: float = 1.0,
    max_bytes: int = 15_000_000,
    registry_path: str | Path | None = None,
) -> tuple[Path, dict[str, Any]]:
    """Download an official AMFI monthly flow report with bounded safety and hash registration."""
    _public_url(url)
    dest_path_dir = Path(dest_dir)
    dest_path_dir.mkdir(parents=True, exist_ok=True)

    filename = Path(urllib.parse.urlsplit(url).path).name
    if not filename:
        filename = "amfi_report.xls"
    final_file_path = dest_path_dir / filename
    meta_file_path = dest_path_dir / f"{filename}.meta.json"

    # Request with polite retries
    headers = {
        "User-Agent": "FundFlowSentinel/1.0 (Research Ingestion; polite)",
        "Accept": "*/*",
    }
    req = urllib.request.Request(url, headers=headers)

    attempts = 0
    last_err: Exception | None = None
    data = bytearray()
    resp_headers: dict[str, str] = {}

    while attempts < max_retries:
        attempts += 1
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                resp_headers = dict(resp.headers)
                # Check declared content length if available
                content_len = resp.headers.get("Content-Length")
                if content_len and int(content_len) > max_bytes:
                    raise ValueError(f"Report exceeds size limit ({content_len} > {max_bytes} bytes)")

                # Bounded chunk read
                data = bytearray()
                while True:
                    chunk = resp.read(65536)
                    if not chunk:
                        break
                    data.extend(chunk)
                    if len(data) > max_bytes:
                        raise ValueError(f"Report downloaded bytes exceeded limit of {max_bytes}")
                break
        except (urllib.error.URLError, TimeoutError, ConnectionResetError) as e:
            last_err = e
            if attempts < max_retries:
                time.sleep(min_delay * (2 ** (attempts - 1)))
            continue

    if not data and last_err is not None:
        raise ConnectionError(f"Failed downloading {url} after {max_retries} attempts: {last_err}") from last_err

    # Compute SHA-256 hash
    sha256 = hashlib.sha256(data).hexdigest()
    retrieved_at = datetime.datetime.now(datetime.timezone.utc).isoformat().replace("+00:00", "Z")
    http_last_modified = resp_headers.get("Last-Modified") or resp_headers.get("last-modified")

    # Atomic write to destination
    with tempfile.NamedTemporaryFile(dir=dest_path_dir, delete=False) as tmp:
        tmp.write(data)
        tmp_path = Path(tmp.name)

    shutil.move(str(tmp_path), str(final_file_path))

    metadata: dict[str, Any] = {
        "url": url,
        "filename": filename,
        "sha256": sha256,
        "size_bytes": len(data),
        "retrieved_at": retrieved_at,
        "http_last_modified": http_last_modified,
        "status": "success",
    }

    # Write sidecar metadata
    meta_file_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")

    # Optional registry update
    if registry_path:
        registry_rec = {
            "source_name": "AMFI monthly flows",
            "url": url,
            "data_type": "category_month_flows",
            "frequency": "monthly",
            "retrieved_at": retrieved_at,
            "terms_url": "https://www.amfiindia.com/terms-of-use",
            "permitted_use": "Personal non-commercial access only; broader ingestion/publication requires permission.",
            "attribution": "AMFI; retain notices if permitted.",
            "redistribution_status": "restricted",
            "source_confidence": "official",
            "sha256": sha256,
            "last_outcome": "success",
            "status": "restricted",
            "checked_on": datetime.date.today().isoformat(),
        }
        append_record(registry_path, registry_rec)

    return final_file_path, metadata


def _load_category_map(map_path: str | Path | None = None) -> list[dict[str, str]]:
    """Load valid category mappings with validity date ranges."""
    if map_path is None:
        map_path = Path(__file__).resolve().parents[3] / "config" / "category_map.csv"
    map_path = Path(map_path)
    if not map_path.is_file():
        raise FileNotFoundError(f"category_map.csv not found at {map_path}")

    with map_path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        return list(reader)


def parse_report(
    path: str | Path,
    source_url: str = "",
    retrieved_at: str = "",
    available_from: str = "",
    category_map_path: str | Path | None = None,
) -> pd.DataFrame:
    """Parse an official AMFI monthly flow report into flows_category_month schema.

    Enforces layout verification, units confirmation, and availability lag evidence.
    Never infers gross redemption from net flows.
    """
    path = Path(path)
    fmt = detect_file_format(path)

    # Check for companion sidecar metadata if parameters are omitted
    meta_path = path.parent / f"{path.name}.meta.json"
    meta: dict[str, Any] = {}
    if meta_path.is_file():
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
        except Exception:
            meta = {}

    if not source_url:
        source_url = meta.get("url") or f"https://portal.amfiindia.com/spages/{path.name}"
    if not retrieved_at:
        retrieved_at = meta.get("retrieved_at") or datetime.datetime.now(datetime.timezone.utc).isoformat().replace("+00:00", "Z")

    # Extract all sheet data into simple Python rows
    sheets_data: dict[str, list[list[Any]]] = {}
    if fmt == "OOXML":
        with path.open("rb") as f:
            wb = openpyxl.load_workbook(f, data_only=True)
            for sname in wb.sheetnames:
                ws = wb[sname]
                sheet_rows = []
                for r in ws.iter_rows(values_only=True):
                    sheet_rows.append(list(r))
                sheets_data[sname] = sheet_rows
    else:  # BIFF8
        wb_biff = xlrd.open_workbook(filename=str(path))
        for sname in wb_biff.sheet_names():
            ws = wb_biff.sheet_by_name(sname)
            sheet_rows = []
            for r in range(ws.nrows):
                sheet_rows.append(ws.row_values(r))
            sheets_data[sname] = sheet_rows

    if not sheets_data:
        raise ValueError(f"Report has no sheets or rows: {path.name}")

    # Inspect for layout style: Modern (2019-04 to present) vs Legacy (2018 multi-sheet)
    sheet_names = list(sheets_data.keys())
    is_legacy = "sales" in sheet_names and "red+assets" in sheet_names

    if is_legacy:
        return _parse_legacy_report(
            sheets_data,
            path=path,
            source_url=source_url,
            retrieved_at=retrieved_at,
            available_from=available_from,
            meta=meta,
            category_map_path=category_map_path,
        )
    return _parse_modern_report(
        sheets_data,
        path=path,
        source_url=source_url,
        retrieved_at=retrieved_at,
        available_from=available_from,
        meta=meta,
        category_map_path=category_map_path,
    )


def _parse_modern_report(
    sheets_data: dict[str, list[list[Any]]],
    path: Path,
    source_url: str,
    retrieved_at: str,
    available_from: str,
    meta: dict[str, Any],
    category_map_path: str | Path | None,
) -> pd.DataFrame:
    """Parse modern consolidated AMFI monthly report layout (2019-04 to present)."""
    # Select target sheet: first sheet matching Month name or MCR_MonthlyReport, or sheet 0
    target_sheet_name = None
    for sname in sheets_data:
        if re.search(r"(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[\s_]?\d{2,4}", sname, re.IGNORECASE) or "MCR" in sname:
            target_sheet_name = sname
            break
    if not target_sheet_name:
        target_sheet_name = list(sheets_data.keys())[0]

    rows = sheets_data[target_sheet_name]
    if not rows:
        raise ValueError(f"Target sheet '{target_sheet_name}' in {path.name} is empty")

    # 1. Locate Header Row (scan first 15 rows)
    header_row_idx = -1
    col_inflow = -1
    col_redemption = -1
    col_net = -1
    col_aum_close = -1
    col_aaum = -1
    col_category = -1

    units_confirmed = False
    in_file_release = None
    report_month = None

    # Search title and all rows for release date, units, and report month
    for idx, r in enumerate(rows[:30]):
        text_row = " ".join(str(c) for c in r if c is not None)
        if not report_month:
            report_month = _parse_month_string(text_row)
        if "Released on" in text_row or re.search(r"\bReleased\s+\d", text_row, re.IGNORECASE):
            in_file_release = text_row
        if any(u in text_row.lower() for u in ["in crore", "in rs. crore", "inr in crore", "(inr in crore)", "(` in crore)"]):
            units_confirmed = True

    # Check footer rows for release date as well
    for r in rows[-20:]:
        text_row = " ".join(str(c) for c in r if c is not None)
        if "Released on" in text_row or re.search(r"\bReleased\s+\d", text_row, re.IGNORECASE):
            in_file_release = text_row

    for idx, r in enumerate(rows[:15]):
        str_cells = [str(c).strip() if c is not None else "" for c in r]
        row_str = " ".join(str_cells).lower()
        if ("funds mobilized" in row_str or "fund mobilized" in row_str) and ("repurchase" in row_str or "redemption" in row_str):
            header_row_idx = idx
            for c_idx, cell_val in enumerate(str_cells):
                c_low = cell_val.lower()
                if ("scheme" in c_low or "category" in c_low) and "no. of" not in c_low and "no.of" not in c_low:
                    if col_category == -1:
                        col_category = c_idx
                if "mobilized" in c_low:
                    col_inflow = c_idx
                if "repurchase" in c_low or "redemption" in c_low:
                    col_redemption = c_idx
                if "net inflow" in c_low or "net outflow" in c_low or ("net" in c_low and ("inflow" in c_low or "outflow" in c_low)):
                    col_net = c_idx
                if ("average" in c_low and ("assets" in c_low or "aum" in c_low)) or "aaum" in c_low:
                    col_aaum = c_idx
                elif (
                    ("net assets" in c_low or "assets under management" in c_low or c_low.startswith("aum as") or "aum as on" in c_low)
                    and "average" not in c_low
                    and "aaum" not in c_low
                    and "segregated" not in c_low
                ):
                    col_aum_close = c_idx
            break

    if header_row_idx == -1:
        raise ValueError(
            f"Unknown AMFI report layout in {path.name}: header keywords "
            f"('funds mobilized' and 'repurchase/redemption') missing from sheet '{target_sheet_name}'"
        )

    if not units_confirmed:
        # Check header cells themselves
        for c in rows[header_row_idx]:
            if any(u in str(c).lower() for u in ["crore", "inr"]):
                units_confirmed = True
                break

    if not units_confirmed:
        # Check other sheets in the workbook (e.g. New Schemes companion sheet)
        for sname, srows in sheets_data.items():
            for r in srows[:20]:
                text_row = " ".join(str(c) for c in r if c is not None).lower()
                if any(u in text_row for u in ["in crore", "in rs. crore", "inr in crore", "(inr in crore)", "(` in crore)", "rs. in crore"]):
                    units_confirmed = True
                    break
            if units_confirmed:
                break

    if not units_confirmed:
        raise ValueError(f"Unconfirmed units in {path.name}; expected INR in crore")

    if any(col == -1 for col in [col_category, col_inflow, col_redemption, col_net, col_aum_close]):
        missing = []
        if col_category == -1: missing.append("category")
        if col_inflow == -1: missing.append("gross_inflow")
        if col_redemption == -1: missing.append("gross_redemption")
        if col_net == -1: missing.append("net_flow")
        if col_aum_close == -1: missing.append("aum_close")
        raise ValueError(f"Ambiguous layout in {path.name}: unable to resolve columns: {', '.join(missing)}")

    # Derive report month if not yet resolved
    if not report_month:
        report_month = _parse_month_string(target_sheet_name) or _parse_month_string(path.name)
    if not report_month:
        raise ValueError(f"Could not determine report month for {path.name}")

    # Determine available_from timestamp (strictly non-leakage)
    final_available_from = available_from
    if not final_available_from and in_file_release:
        final_available_from = _parse_release_date_to_iso(in_file_release) or ""
    if not final_available_from and meta.get("http_last_modified"):
        try:
            # Parse HTTP Date header e.g. "Thu, 10 Oct 2024 08:57:53 GMT"
            dt = datetime.datetime.strptime(meta["http_last_modified"], "%a, %d %b %Y %H:%M:%S %Z")
            final_available_from = dt.replace(tzinfo=datetime.timezone.utc).isoformat().replace("+00:00", "Z")
        except Exception:
            pass

    if not final_available_from:
        raise ValueError(
            f"Missing required publication lag evidence for {path.name}; "
            f"under no circumstances may month-end be assumed as available_from"
        )

    # Load category map
    cat_mappings = _load_category_map(category_map_path)

    # Build category lookup: raw_category -> target category (for valid date window)
    active_map: dict[str, str] = {}
    for m in cat_mappings:
        if m["valid_from"] <= report_month <= m["valid_to"]:
            active_map[m["raw_category"].strip().lower()] = m["category"]

    parsed_records = []
    for r_idx in range(header_row_idx + 1, len(rows)):
        r = rows[r_idx]
        if col_category >= len(r) or r[col_category] is None:
            continue
        raw_cat_name = str(r[col_category]).strip()
        raw_cat_clean = re.sub(r"\s+", " ", raw_cat_name).lower()

        if raw_cat_clean not in active_map:
            # Handle common minor variations in punctuation or whitespace
            matched = False
            for cand, target in active_map.items():
                if cand.replace(" ", "") == raw_cat_clean.replace(" ", ""):
                    canonical_cat = target
                    matched = True
                    break
            if not matched:
                continue
        else:
            canonical_cat = active_map[raw_cat_clean]

        # Extract numerical values
        inflow_val = _clean_numeric(r[col_inflow] if col_inflow < len(r) else None)
        redemption_val = _clean_numeric(r[col_redemption] if col_redemption < len(r) else None)
        net_val = _clean_numeric(r[col_net] if col_net < len(r) else None)
        aum_close_val = _clean_numeric(r[col_aum_close] if col_aum_close < len(r) else None)
        aaum_val = _clean_numeric(r[col_aaum] if col_aaum != -1 and col_aaum < len(r) else None)

        # Invariant: gross redemption must NEVER be inferred from net flows
        if redemption_val is None or inflow_val is None:
            raise ValueError(
                f"Missing observed gross flow values for '{raw_cat_name}' in {path.name}; "
                f"gross redemptions cannot be inferred"
            )

        if net_val is None:
            net_val = inflow_val - redemption_val
        if aum_close_val is None:
            raise ValueError(f"Missing closing AUM for '{raw_cat_name}' in {path.name}")
        if aaum_val is None:
            aaum_val = aum_close_val

        parsed_records.append({
            "month": report_month,
            "category": canonical_cat,
            "gross_inflow_cr": float(inflow_val),
            "gross_redemption_cr": float(redemption_val),
            "net_flow_cr": float(net_val),
            "aum_close_cr": float(aum_close_val),
            "aaum_cr": float(aaum_val),
            "available_from": final_available_from,
            "source_url": source_url,
            "retrieved_at": retrieved_at,
        })

    if not parsed_records:
        raise ValueError(f"No valid category rows extracted from {path.name}")

    df = pd.DataFrame(parsed_records)[list(COLUMNS["flows_category_month"])]
    # De-duplicate any repeated category rows if sheet had multiple sections
    df = df.drop_duplicates(subset=["month", "category"]).reset_index(drop=True)
    return validate_table("flows_category_month", df)


def _parse_legacy_report(
    sheets_data: dict[str, list[list[Any]]],
    path: Path,
    source_url: str,
    retrieved_at: str,
    available_from: str,
    meta: dict[str, Any],
    category_map_path: str | Path | None,
) -> pd.DataFrame:
    """Parse legacy multi-sheet AMFI monthly report layout (2018-04 to 2019-03)."""
    sales_rows = sheets_data["sales"]
    red_rows = sheets_data["red+assets"]

    # Locate report month
    report_month = None
    for r in sales_rows[:10] + red_rows[:10]:
        text_row = " ".join(str(c) for c in r if c is not None)
        if not report_month:
            report_month = _parse_month_string(text_row)
    if not report_month:
        report_month = _parse_month_string(path.name)
    if not report_month:
        raise ValueError(f"Could not determine legacy report month for {path.name}")

    # Publication release evidence
    final_available_from = available_from
    if not final_available_from and meta.get("http_last_modified"):
        try:
            dt = datetime.datetime.strptime(meta["http_last_modified"], "%a, %d %b %Y %H:%M:%S %Z")
            final_available_from = dt.replace(tzinfo=datetime.timezone.utc).isoformat().replace("+00:00", "Z")
        except Exception:
            pass

    if not final_available_from:
        raise ValueError(f"Missing required publication lag evidence for legacy report {path.name}")

    # Extract sales (inflows)
    cat_inflows: dict[str, float] = {}
    in_total_section = False
    for r in sales_rows:
        text_row = " ".join(str(c) for c in r if c is not None)
        if "TOTAL OF ALL SCHEMES" in text_row.upper() or "TOTAL SALES" in text_row.upper():
            in_total_section = True
            continue
        if in_total_section and len(r) >= 2 and r[0]:
            name = str(r[0]).strip().lower()
            if name.startswith("total"):
                in_total_section = False
                continue
            # Find amount (col 3 or col 12 or col 2)
            amt = None
            if len(r) > 3 and _clean_numeric(r[3]) is not None:
                amt = _clean_numeric(r[3])
            elif len(r) > 12 and _clean_numeric(r[12]) is not None:
                amt = _clean_numeric(r[12])
            elif len(r) > 2 and _clean_numeric(r[2]) is not None:
                amt = _clean_numeric(r[2])
            if amt is not None:
                cat_inflows[name] = amt

    # Fallback to general scan if total section was not demarcated
    if not cat_inflows:
        for r in sales_rows[4:]:
            if len(r) >= 4 and r[0]:
                name = str(r[0]).strip().lower()
                amt = _clean_numeric(r[3]) or _clean_numeric(r[1])
                if amt is not None:
                    cat_inflows[name] = amt

    # Extract redemptions & assets
    cat_records: list[dict[str, Any]] = []
    cat_mappings = _load_category_map(category_map_path)
    active_map = {m["raw_category"].strip().lower(): m["category"] for m in cat_mappings if m["valid_from"] <= report_month <= m["valid_to"]}

    # Search red_rows for Table 3 (redemptions) and Table 4 (AUM)
    in_red = False
    in_aum = False
    redemptions: dict[str, float] = {}
    net_flows: dict[str, float] = {}
    aums: dict[str, float] = {}

    for r in red_rows:
        col0 = str(r[0]).strip().upper() if r and r[0] else ""
        text_row = " ".join(str(c) for c in r if c is not None)
        if "REDEMPTIONS" in text_row.upper():
            in_red = True
            in_aum = False
            continue
        if "ASSETS UNDER MANAGEMENT" in text_row.upper():
            in_aum = True
            in_red = False
            continue
        if col0 == "TOTAL":
            in_red = False
            in_aum = False
            continue

        if in_red and len(r) >= 6 and r[0] and "CATEGORY" not in col0 and "OPEN END" not in col0:
            name = str(r[0]).strip().lower()
            red_val = _clean_numeric(r[4]) or _clean_numeric(r[1])
            net_val = _clean_numeric(r[5]) if len(r) > 5 else None
            if red_val is not None:
                redemptions[name] = red_val
            if net_val is not None:
                net_flows[name] = net_val

        if in_aum and len(r) >= 2 and r[0] and "CATEGORY" not in col0 and "OPEN END" not in col0 and "NOTE" not in col0:
            name = str(r[0]).strip().lower()
            aum_val = _clean_numeric(r[1])
            if aum_val is not None:
                aums[name] = aum_val

    # Match against category map
    for raw_name, canonical_cat in active_map.items():
        matched_key = None
        for k in redemptions:
            if k == raw_name or raw_name in k or k in raw_name:
                matched_key = k
                break
        if matched_key and matched_key in redemptions and matched_key in aums:
            red_val = redemptions[matched_key]
            inflow_val = cat_inflows.get(matched_key, 0.0)
            net_val = net_flows.get(matched_key, inflow_val - red_val)
            aum_val = aums[matched_key]

            cat_records.append({
                "month": report_month,
                "category": canonical_cat,
                "gross_inflow_cr": float(inflow_val),
                "gross_redemption_cr": float(red_val),
                "net_flow_cr": float(net_val),
                "aum_close_cr": float(aum_val),
                "aaum_cr": float(aum_val),
                "available_from": final_available_from,
                "source_url": source_url,
                "retrieved_at": retrieved_at,
            })

    if not cat_records:
        raise ValueError(f"No categories matched in legacy report {path.name}")

    df = pd.DataFrame(cat_records)[list(COLUMNS["flows_category_month"])]
    df = df.drop_duplicates(subset=["month", "category"]).reset_index(drop=True)
    return validate_table("flows_category_month", df)
