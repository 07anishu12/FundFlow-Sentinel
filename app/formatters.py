"""Institutional financial data formatting utilities for FundFlow Sentinel.

Enforces:
- Consistent currency formatting in INR crore with true minus signs (−).
- Tabular numeral precision policies (no floating-point tails like 254594.79049813).
- Clean date and period representations (e.g. 'Sep 2024', '30 Sep 2024').
- Clear distinction between 0.0 and unavailable (N/A).
"""
from __future__ import annotations

import datetime
import math
from typing import Any, Optional


def format_currency_crore(value: Any, precision: int = 2) -> str:
    """Format monetary amount in Indian Rupee crore (₹ crore).
    
    Examples:
        254594.79049813 -> "₹254,594.79 crore"
        -125.4          -> "−₹125.40 crore"
        None / NaN      -> "N/A"
    """
    if value is None:
        return "N/A"
    try:
        val_f = float(value)
        if not math.isfinite(val_f):
            return "N/A"
    except (ValueError, TypeError):
        return "N/A"

    is_negative = val_f < -1e-9
    abs_val = abs(val_f)

    # Format with commas and exact precision
    formatted_num = f"{abs_val:,.{precision}f}"
    if is_negative:
        return f"−₹{formatted_num} crore"
    return f"₹{formatted_num} crore"


def format_rate_pct(value: Any, precision: int = 2, show_sign: bool = False) -> str:
    """Format financial rate or percentage.
    
    Examples:
        0.7486     -> "0.75%"
        -1.25      -> "−1.25%"
        None / NaN -> "N/A"
    """
    if value is None:
        return "N/A"
    try:
        val_f = float(value)
        if not math.isfinite(val_f):
            return "N/A"
    except (ValueError, TypeError):
        return "N/A"

    is_negative = val_f < -1e-9
    abs_val = abs(val_f)
    num_str = f"{abs_val:.{precision}f}"

    if is_negative:
        return f"−{num_str}%"
    if show_sign and val_f > 1e-9:
        return f"+{num_str}%"
    return f"{num_str}%"


def format_number(value: Any, precision: int = 2) -> str:
    """Format general numeric value with tabular thousands commas.
    
    Examples:
        1234567.89 -> "1,234,567.89"
        None       -> "N/A"
    """
    if value is None:
        return "N/A"
    try:
        val_f = float(value)
        if not math.isfinite(val_f):
            return "N/A"
    except (ValueError, TypeError):
        return "N/A"

    is_negative = val_f < -1e-9
    abs_val = abs(val_f)
    num_str = f"{abs_val:,.{precision}f}"
    return f"−{num_str}" if is_negative else num_str


def format_period(period_str: Any) -> str:
    """Format YYYY-MM into human-readable financial period (e.g., '2024-09' -> 'Sep 2024')."""
    if not period_str or not isinstance(period_str, str):
        return str(period_str or "N/A")

    clean = period_str.strip()
    if len(clean) == 7 and clean[4] == "-":
        try:
            dt = datetime.datetime.strptime(clean, "%Y-%m")
            return dt.strftime("%b %Y")
        except ValueError:
            pass
    elif len(clean) == 10 and clean[4] == "-" and clean[7] == "-":
        try:
            dt = datetime.datetime.strptime(clean, "%Y-%m-%d")
            return dt.strftime("%d %b %Y")
        except ValueError:
            pass

    return clean


def format_timestamp(iso_str: Any) -> str:
    """Format ISO UTC timestamp into compact readable date/time string."""
    if not iso_str or not isinstance(iso_str, str):
        return "Unavailable"

    clean = iso_str.strip().replace("Z", "+00:00")
    try:
        dt = datetime.datetime.fromisoformat(clean)
        return dt.strftime("%d %b %Y, %H:%M UTC")
    except Exception:
        return iso_str[:16].replace("T", " ")


def format_provenance_label(source_url_or_name: Any) -> str:
    """Convert raw source URL or internal ID to a clean, readable provenance label."""
    if not source_url_or_name or not isinstance(source_url_or_name, str):
        return "Internal Engine"

    s = source_url_or_name.strip()
    if "amfiindia.com" in s:
        return "AMFI Official"
    if "nseindia.com" in s:
        return "NSE Indices"
    if "mfapi.in" in s:
        return "mfapi (AMFI Wrapper)"
    if "economictimes" in s:
        return "Economic Times MF"
    if "synthetic:" in s or "fixture" in s.lower():
        return "Synthetic Demo"
    if "walk-forward" in s or "ridge" in s:
        return "Walk-Forward Ridge"
    if "lag0" in s or "persistence" in s:
        return "Persistence Proxy"

    # Truncate long URLs
    if "://" in s:
        domain = s.split("://", 1)[1].split("/", 1)[0]
        return domain
    return s[:30]
