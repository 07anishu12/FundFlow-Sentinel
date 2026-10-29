"""Capture browser-level screenshots of all 6 FundFlow Sentinel pages across desktop, tablet, and mobile.
Uses Google Chrome headless mode with virtual time budget to allow full rendering.
"""
from __future__ import annotations

import os
from pathlib import Path
import subprocess
import time

ROOT = Path(__file__).resolve().parents[1]
SCREENSHOT_DIR = ROOT / "reports" / "screenshots"
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


def capture():
    if not os.path.exists(CHROME_BIN):
        print(f"Chrome binary not found at {CHROME_BIN}")
        return

    for page_name, url in PAGES:
        # Capture desktop for all pages
        dest_desktop = SCREENSHOT_DIR / f"{page_name}_desktop.png"
        cmd = [
            CHROME_BIN,
            "--headless",
            "--disable-gpu",
            "--virtual-time-budget=4000",
            f"--window-size=1440,1100",
            f"--screenshot={dest_desktop}",
            url,
        ]
        try:
            res = subprocess.run(cmd, capture_output=True, timeout=15)
            if dest_desktop.is_file():
                sz = dest_desktop.stat().st_size
                print(f"Captured {page_name} desktop: {sz} bytes")
        except Exception as e:
            print(f"Failed {page_name} desktop: {e}")

    # Capture tablet & mobile for Command Centre and Forecast Lab
    for vp_name, dim in [("tablet", "768,1024"), ("mobile", "390,844")]:
        for page_name, url in [("command_centre", "http://localhost:8501/"), ("forecast_lab", "http://localhost:8501/Forecast_Lab")]:
            dest = SCREENSHOT_DIR / f"{page_name}_{vp_name}.png"
            cmd = [
                CHROME_BIN,
                "--headless",
                "--disable-gpu",
                "--virtual-time-budget=4000",
                f"--window-size={dim}",
                f"--screenshot={dest}",
                url,
            ]
            try:
                res = subprocess.run(cmd, capture_output=True, timeout=15)
                if dest.is_file():
                    sz = dest.stat().st_size
                    print(f"Captured {page_name} {vp_name}: {sz} bytes")
            except Exception as e:
                print(f"Failed {page_name} {vp_name}: {e}")


if __name__ == "__main__":
    capture()
