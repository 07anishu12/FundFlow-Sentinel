"""Official AMFI Monthly Flow Report Inspector.

Inspects representative official AMFI monthly reports across FY2018-19 to FY2026-27.
Extracts publication headers, file types, sheet names, table layouts, headers,
units, row counts, category labels, and proves target availability.
"""
import io
import json
import re
import struct
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path

REPRESENTATIVE_REPORTS = [
    {
        "period": "2018-04",
        "url": "https://portal.amfiindia.com/spages/amapr2018repo.xls",
        "notes": "Start of FY2018-19; SEBI categorization transition window"
    },
    {
        "period": "2018-09",
        "url": "https://portal.amfiindia.com/spages/amsep2018repo.xls",
        "notes": "FY2018-19 mid-year; legacy multi-sheet BIFF8 layout"
    },
    {
        "period": "2019-04",
        "url": "https://portal.amfiindia.com/spages/amapr2019repo.xls",
        "notes": "Start of FY2019-20; consolidated single-sheet OOXML layout"
    },
    {
        "period": "2020-09",
        "url": "https://portal.amfiindia.com/spages/amsep2020repo.xls",
        "notes": "Pre-Flexi Cap baseline; COVID recovery period"
    },
    {
        "period": "2021-01",
        "url": "https://portal.amfiindia.com/spages/amjan2021repo.xls",
        "notes": "Flexi Cap introduction structural break (16 Multi Cap funds reclassified)"
    },
    {
        "period": "2022-09",
        "url": "https://portal.amfiindia.com/spages/amsep2022repo.xls",
        "notes": "FY2022-23 established single-sheet OOXML format"
    },
    {
        "period": "2024-09",
        "url": "https://portal.amfiindia.com/spages/amsep2024repo.xls",
        "notes": "FY2024-25 report with explicit in-sheet release date"
    },
    {
        "period": "2026-09",
        "url": "https://portal.amfiindia.com/spages/amsep2026repo.xls",
        "notes": "Current FY2026-27 BIFF8 format with MCR_MonthlyReport sheet naming"
    }
]

def fetch_headers(url: str) -> dict:
    req = urllib.request.Request(url, method="HEAD", headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return dict(resp.headers)
    except Exception as e:
        return {"error": str(e)}

def inspect_report(url: str, period: str) -> dict:
    headers = fetch_headers(url)
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            data = resp.read()
    except Exception as e:
        return {
            "period": period,
            "url": url,
            "headers": headers,
            "error": str(e)
        }

    magic = data[:8].hex()
    is_ooxml = data[:4] == b"PK\x03\x04"
    is_biff8 = data[:8] == b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"

    file_type = "OOXML (.xlsx disguised as .xls)" if is_ooxml else ("BIFF8 (OLE2 Compound .xls)" if is_biff8 else "Unknown/Other")

    sheets = []
    sample_categories = []
    columns_detected = []
    in_file_release = None
    units = "Unknown"
    row_count = 0

    if is_ooxml:
        try:
            import zipfile
            zf = zipfile.ZipFile(io.BytesIO(data))
            if "xl/workbook.xml" in zf.namelist():
                wb_root = ET.fromstring(zf.read("xl/workbook.xml"))
                for s in wb_root.findall("{http://schemas.openxmlformats.org/spreadsheetml/2006/main}sheets/{http://schemas.openxmlformats.org/spreadsheetml/2006/main}sheet"):
                    sheets.append(s.attrib.get("name", ""))

            # Shared strings
            sst = []
            if "xl/sharedStrings.xml" in zf.namelist():
                sst_root = ET.fromstring(zf.read("xl/sharedStrings.xml"))
                for si in sst_root.findall("{http://schemas.openxmlformats.org/spreadsheetml/2006/main}si"):
                    t = si.find("{http://schemas.openxmlformats.org/spreadsheetml/2006/main}t")
                    val = t.text if t is not None else "".join([x.text for x in si.iter() if x.text])
                    sst.append(val or "")

            # Check sheet 1
            if "xl/worksheets/sheet1.xml" in zf.namelist():
                ws_root = ET.fromstring(zf.read("xl/worksheets/sheet1.xml"))
                ns = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
                rows = ws_root.findall(f"{ns}sheetData/{ns}row")
                row_count = len(rows)
                for r in rows:
                    cells = []
                    for c in r.findall(f"{ns}c"):
                        t = c.get("t")
                        v = c.find(f"{ns}v")
                        val = v.text if v is not None else None
                        if t == "s" and val is not None and int(val) < len(sst):
                            val = sst[int(val)]
                        if val:
                            cells.append(val)
                    cell_text = " ".join(cells)
                    if "Crore" in cell_text or "crore" in cell_text or "INR in crore" in cell_text:
                        units = "INR in crore"
                    if "Released on" in cell_text:
                        in_file_release = cell_text
                    if any(h in cell_text for h in ["Funds Mobilized", "Repurchase", "Net Inflow"]):
                        columns_detected = [c for c in cells if any(k in c for k in ["Scheme", "Folios", "Mobilized", "Repurchase", "Inflow", "Assets"])]
                    for cat in ["Large Cap Fund", "Mid Cap Fund", "Small Cap Fund", "Flexi Cap Fund", "Balanced Hybrid Fund/Aggressive Hybrid Fund", "Corporate Bond Fund", "Liquid Fund", "Overnight Fund"]:
                        if any(c == cat for c in cells):
                            if cat not in sample_categories:
                                sample_categories.append(cat)
        except Exception as ex:
            file_type += f" (Parse error: {ex})"

    elif is_biff8:
        # BIFF8 inspection
        try:
            sec_size = 512
            fat = []
            for fat_sec_idx in struct.unpack("<109I", data[76:512]):
                if fat_sec_idx in (0xFFFFFFFE, 0xFFFFFFFF):
                    continue
                fat_data = data[512 + fat_sec_idx * sec_size : 512 + (fat_sec_idx + 1) * sec_size]
                fat.extend(struct.unpack(f"<{sec_size // 4}I", fat_data))

            dir_sec = struct.unpack("<I", data[48:52])[0]
            dir_sectors = []
            cur = dir_sec
            while cur != 0xFFFFFFFE and cur < len(fat):
                dir_sectors.append(cur)
                cur = fat[cur]
            dir_bytes = b"".join(data[512 + s * sec_size : 512 + (s + 1) * sec_size] for s in dir_sectors)

            wb_stream = b""
            for i in range(0, len(dir_bytes), 128):
                entry = dir_bytes[i:i+128]
                name_len = struct.unpack("<H", entry[64:66])[0]
                name = entry[:name_len].decode("utf-16le", errors="ignore").rstrip("\x00")
                if name == "Workbook":
                    start_sec = struct.unpack("<I", entry[116:120])[0]
                    size = struct.unpack("<I", entry[120:124])[0]
                    cur = start_sec
                    wb_sectors = []
                    while cur != 0xFFFFFFFE and cur < len(fat):
                        wb_sectors.append(cur)
                        cur = fat[cur]
                    wb_stream = b"".join(data[512 + s * sec_size : 512 + (s + 1) * sec_size] for s in wb_sectors)[:size]
                    break

            pos = 0
            sst_data = bytearray()
            in_sst = False
            while pos < len(wb_stream) - 4:
                rec_type, rec_len = struct.unpack("<HH", wb_stream[pos:pos+4])
                rec_data = wb_stream[pos+4:pos+4+rec_len]
                pos += 4 + rec_len
                if rec_type == 0x0085: # BOUNDSHEET
                    s_len = rec_data[6]
                    flag = rec_data[7]
                    s_name = rec_data[8:8+s_len].decode("latin1", errors="ignore") if flag == 0 else rec_data[8:8+s_len*2].decode("utf-16le", errors="ignore")
                    sheets.append(s_name)
                elif rec_type == 0x00FC:
                    sst_data.extend(rec_data)
                    in_sst = True
                elif in_sst and rec_type == 0x003C:
                    sst_data.extend(rec_data)
                elif in_sst:
                    in_sst = False

            ascii_strings = [s.decode("latin1", errors="ignore") for s in re.findall(b"[\x20-\x7e]{3,}", sst_data)]
            row_count = len(ascii_strings)
            for s in ascii_strings:
                if "INR in crore" in s or "in Crore" in s or "crore" in s.lower():
                    units = "INR in crore"
                if "Released on" in s:
                    in_file_release = s.strip()
                if any(h in s for h in ["Funds Mobilized", "Repurchase", "Net Inflow"]):
                    columns_detected.append(s.strip())
                for cat in ["Large Cap Fund", "Mid Cap Fund", "Small Cap Fund", "Flexi Cap Fund", "Balanced Hybrid Fund/Aggressive Hybrid Fund", "Corporate Bond Fund", "Liquid Fund", "Overnight Fund", "OPEN END EQUITY", "OPEN END INCOME", "Liquid/ Money Market"]:
                    if cat.lower() in s.lower() and cat not in sample_categories:
                        sample_categories.append(cat)
        except Exception as ex:
            file_type += f" (BIFF8 parse error: {ex})"

    return {
        "period": period,
        "url": url,
        "http_last_modified": headers.get("last-modified") or headers.get("Last-Modified"),
        "in_file_release": in_file_release,
        "content_length": headers.get("content-length") or headers.get("Content-Length"),
        "file_type": file_type,
        "magic_hex": magic,
        "sheets": sheets,
        "units": units,
        "row_count_est": row_count,
        "sample_categories": sample_categories,
        "sample_columns": columns_detected[:6]
    }

def main():
    print("=" * 80)
    print("AMFI MONTHLY FLOW REPORT INSPECTION ENGINE")
    print("=" * 80)
    results = []
    for rep in REPRESENTATIVE_REPORTS:
        print(f"Inspecting {rep['period']} ({rep['url']})...")
        res = inspect_report(rep["url"], rep["period"])
        res["notes"] = rep["notes"]
        results.append(res)
        print(f"  Type: {res.get('file_type')}")
        print(f"  Last-Modified: {res.get('http_last_modified')}")
        print(f"  In-File Release: {res.get('in_file_release')}")
        print(f"  Sheets: {res.get('sheets')}")
        print(f"  Units: {res.get('units')}")
        print(f"  Categories detected: {res.get('sample_categories')}")
        print("-" * 60)

    out_path = Path(__file__).resolve().parents[1] / "docs" / "amfi_inspection_evidence.json"
    out_path.write_text(json.dumps(results, indent=2))
    print(f"\nInspection evidence successfully saved to: {out_path}")

if __name__ == "__main__":
    main()
