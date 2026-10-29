"""Streamlit page entry point."""
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
for directory in (ROOT, ROOT / "src"):
    if str(directory) not in sys.path:
        sys.path.insert(0, str(directory))
from app.components import fund_research

fund_research()
