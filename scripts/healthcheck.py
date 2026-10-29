"""Production healthcheck probe for FundFlow Sentinel Streamlit service."""
from __future__ import annotations

import sys
import urllib.request
import urllib.error


def check_health(url: str = "http://localhost:8501/_stcore/health", timeout: int = 5) -> int:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "FundFlowSentinel-Healthcheck/1.0"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            if resp.status == 200:
                print(f"[Healthcheck] Status 200 OK from {url}")
                return 0
            else:
                print(f"[Healthcheck] Unexpected status code: {resp.status}", file=sys.stderr)
                return 1
    except urllib.error.URLError as err:
        # Fallback to base URL if _stcore/health is unrouted
        try:
            with urllib.request.urlopen("http://localhost:8501/", timeout=timeout) as resp:
                if resp.status == 200:
                    print("[Healthcheck] Status 200 OK from root endpoint")
                    return 0
        except Exception:
            pass
        print(f"[Healthcheck] Connection failed: {err}", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"[Healthcheck] Exception during probe: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(check_health())
