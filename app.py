"""FundFlow Sentinel - Institutional Dashboard Application Entry Point.

Delegates directly to app.components.command_centre for the full 6-page suite.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
for directory in (ROOT, ROOT / "src"):
    if str(directory) not in sys.path:
        sys.path.insert(0, str(directory))

from app.components import command_centre

if __name__ == "__main__" or True:
    command_centre()
