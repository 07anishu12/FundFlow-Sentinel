"""Capture high-resolution browser screenshots for all 6 pages across desktop, tablet, and mobile.

Saves strictly to reports/final_qa/screenshots/
"""
from __future__ import annotations

import os
from pathlib import Path
import subprocess
import time

ROOT = Path(__file__).resolve().parents[1]
SCREENSHOT_DIR = ROOT / "reports" / "final_qa" / "screenshots"
SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)

CHROME_BIN = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"

PAGES = [
    ("01_command_centre", "http://localhost:8501/"),
    ("02_forecast_lab", "http://localhost:8501/Forecast_Lab"),
    ("03_sentiment_monitor", "http://localhost:8501/Sentiment_Monitor"),
    ("04_fund_research", "http://localhost:8501/Fund_Research"),
    ("05_stress_lab", "http://localhost:8501/Stress_Lab"),
    ("06_evidence_limits", "http://localhost:8501/Evidence_and_Limits"),
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
    print(f"Starting visual capture for 6 pages across 3 viewports (18 screenshots) -> {SCREENSHOT_DIR}")
    for vp_name, dim in VIEWPORTS:
        for page_name, url in PAGES:
            dest = SCREENSHOT_DIR / f"{page_name}_{vp_name}.png"
            cmd = [
                CHROME_BIN,
                "--headless",
                "--disable-gpu",
                "--virtual-time-budget=6000",
                f"--window-size={dim}",
                f"--screenshot={dest}",
                url,
            ]
            try:
                subprocess.run(cmd, capture_output=True, timeout=25)
                if dest.is_file() and dest.stat().st_size > 0:
                    sz = dest.stat().st_size
                    print(f"  [OK] {page_name} ({vp_name}, {dim}): {sz:,} bytes -> {dest.name}")
                    results.append({"page": page_name, "viewport": vp_name, "size_bytes": sz, "path": str(dest)})
                else:
                    print(f"  [FAIL] {page_name} ({vp_name}) screenshot missing or 0 bytes.")
            except Exception as e:
                print(f"  [ERROR] Failed {page_name} ({vp_name}): {e}")

    print(f"\nFinal visual capture complete: {len(results)}/18 screenshots verified.")


if __name__ == "__main__":
    capture_all()
