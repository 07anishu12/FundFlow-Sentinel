"""Capture high-fidelity browser screenshots for all 6 pages across desktop, tablet, and mobile.

Uses Chrome DevTools Protocol (CDP) over WebSocket via Tornado to guarantee that
the Streamlit WebSocket connection has completed and the DOM is fully rendered.
Saves directly to reports/live_validation/screenshots/
"""
from __future__ import annotations

import asyncio
import base64
import json
import os
from pathlib import Path
import subprocess
import time
import urllib.request
from tornado.websocket import websocket_connect

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
    ("desktop", 1440, 1100, False),
    ("tablet", 768, 1024, True),
    ("mobile", 390, 844, True),
]


async def capture_page(ws_url: str, width: int, height: int, is_mobile: bool, out_path: Path):
    ws = await websocket_connect(ws_url)
    try:
        # Set viewport metrics
        await ws.write_message(json.dumps({
            "id": 1,
            "method": "Emulation.setDeviceMetricsOverride",
            "params": {
                "width": width,
                "height": height,
                "deviceScaleFactor": 1,
                "mobile": is_mobile,
            }
        }))
        await ws.read_message()

        # Wait for Streamlit rendering
        await asyncio.sleep(2.5)

        # Trigger screenshot
        await ws.write_message(json.dumps({
            "id": 2,
            "method": "Page.captureScreenshot",
            "params": {"format": "png"}
        }))

        while True:
            raw_msg = await ws.read_message()
            if raw_msg is None:
                break
            msg = json.loads(raw_msg)
            if msg.get("id") == 2:
                img_bytes = base64.b64decode(msg["result"]["data"])
                out_path.write_bytes(img_bytes)
                print(f"[OK] Captured {out_path.name}: {len(img_bytes):,} bytes ({width}x{height})")
                break
    finally:
        ws.close()


def main():
    if not os.path.exists(CHROME_BIN):
        print(f"Chrome binary not found at {CHROME_BIN}")
        return

    print("Launching Chrome headless with CDP...")
    chrome_proc = subprocess.Popen([
        CHROME_BIN,
        "--headless=new",
        "--remote-debugging-port=9222",
        "--disable-gpu",
        "--no-sandbox",
    ])
    time.sleep(2.0)

    try:
        total = 0
        for vp_name, width, height, is_mobile in VIEWPORTS:
            print(f"\n=== Viewport: {vp_name} ({width}x{height}) ===")
            for page_name, url in PAGES:
                dest = SCREENSHOT_DIR / f"{page_name}_{vp_name}.png"
                # Open tab
                req = urllib.request.Request(f"http://localhost:9222/json/new?{url}", method="PUT")
                try:
                    with urllib.request.urlopen(req) as resp:
                        tab_info = json.loads(resp.read())
                    ws_url = tab_info["webSocketDebuggerUrl"]
                    tab_id = tab_info["id"]

                    asyncio.run(capture_page(ws_url, width, height, is_mobile, dest))
                    total += 1

                    # Close tab to free memory
                    close_req = urllib.request.Request(f"http://localhost:9222/json/close/{tab_id}", method="PUT")
                    try:
                        with urllib.request.urlopen(close_req):
                            pass
                    except Exception:
                        pass
                except Exception as e:
                    print(f"[ERROR] Failed {page_name}_{vp_name}: {e}")

        print(f"\nCapture complete! Total screenshots captured: {total}/{len(VIEWPORTS) * len(PAGES)}")
    finally:
        chrome_proc.terminate()


if __name__ == "__main__":
    main()
