"""Capture browser screenshots for all 6 pages across desktop, tablet, and mobile.

Saves directly to reports/live_validation/screenshots/
"""
from __future__ import annotations

import os
from pathlib import Path
import subprocess
import time

ROOT = Path(__file__).resolve().parents[1]
SCREENSHOT_DIR = ROOT / "reports" / "live_validation" / "screenshots"
SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)

CHROME_BIN = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"

PAGES = [
    ("command_centre", "http://localhost:8501/"),
    ("forecast_lab", "http://localhost:8501/Forecast_Lab"),
    ("sentiment_monitor", "http://localhost:8501/Sentiment_Monitor"),
    ("fund_research", "http://localhost:8501/Fund_Research"),
    ("stress_lab", "http://localhost:8501/Stress_Lab"),
    ("evidence_limits", "http://localhost:8501/Evidence_and_Limits"),
]

VIEWPORTS = [
    ("desktop", "1440,1100"),
    ("tablet", "768,1024"),
    ("mobile", "390,844"),
]


def capture_all():
    if not os.path.exists(CHROME_BIN):
        print(f"Chrome binary not found at {CHROME_BIN}")
        return

    results = []
    for vp_name, dim in VIEWPORTS:
        for page_name, url in PAGES:
            dest = SCREENSHOT_DIR / f"{page_name}_{vp_name}.png"
            cmd = [
                CHROME_BIN,
                "--headless",
                "--disable-gpu",
                "--virtual-time-budget=5000",
                f"--window-size={dim}",
                f"--screenshot={dest}",
                url,
            ]
            try:
                subprocess.run(cmd, capture_output=True, timeout=20)
                if dest.is_file():
                    sz = dest.stat().st_size
                    print(f"[OK] Captured {page_name} ({vp_name}, {dim}): {sz:,} bytes -> {dest.name}")
                    results.append({"page": page_name, "viewport": vp_name, "size_bytes": sz, "path": str(dest)})
                else:
                    print(f"[FAIL] {page_name} ({vp_name}) screenshot file was not created.")
            except Exception as e:
                print(f"[ERROR] Failed {page_name} ({vp_name}): {e}")

    print(f"\nTotal screenshots captured: {len(results)}/18")


if __name__ == "__main__":
    capture_all()
