"""FundFlow anomaly detection and statistical evidence engine.

Computes:
- Historical percentile ranks against prior-only category history.
- Robust Z-scores: (R_t - median_24) / (1.4826 * MAD_24) with zero-MAD safeguards.
- 3-Month Momentum: mean(last 3 rates) / mean(previous 3 rates) - 1.0.
Strictly enforces temporal non-leakage (prior history only).
"""
from __future__ import annotations

import math
from typing import Optional, Sequence
import numpy as np
import pandas as pd


def compute_robust_z(
    rates: Sequence[float],
    current_rate: float,
    window: int = 24,
    min_obs: int = 6,
) -> Optional[float]:
    """Compute robust Z-score using prior-history median and median absolute deviation (MAD).
    
    Formula:
        robust_z = (current_rate - median) / (1.4826 * MAD)
    
    Safeguards:
    - Prior-only observations used (current_rate excluded from median/MAD).
    - Requires at least min_obs observations.
    - If MAD == 0.0, returns 0.0 if current_rate == median, else capped at 3.0 / -3.0.
    """
    clean_rates = [float(r) for r in rates if pd.notna(r) and math.isfinite(float(r))]
    if len(clean_rates) < min_obs:
        return None

    ref_rates = np.array(clean_rates[-window:], dtype=float)
    med = float(np.median(ref_rates))
    mad = float(np.median(np.abs(ref_rates - med)))

    if mad < 1e-6:
        # Zero MAD: distribution has constant values
        diff = current_rate - med
        if abs(diff) < 1e-6:
            return 0.0
        return 3.0 if diff > 0 else -3.0

    denom = 1.4826 * mad
    z = (current_rate - med) / denom
    return round(float(z), 4)


def compute_momentum_3m(
    rates: Sequence[float],
    min_obs: int = 6,
) -> Optional[float]:
    """Compute 3-month momentum: mean(last 3 rates) / mean(previous 3 rates) - 1.0.
    
    Safeguards:
    - Requires at least 6 prior observations.
    - If previous 3-month mean <= 0, returns 0.0 to prevent division by zero.
    """
    clean_rates = [float(r) for r in rates if pd.notna(r) and math.isfinite(float(r))]
    if len(clean_rates) < min_obs:
        return None

    last3 = clean_rates[-3:]
    prev3 = clean_rates[-6:-3]

    m_last = float(np.mean(last3))
    m_prev = float(np.mean(prev3))

    if m_prev <= 1e-6:
        return 0.0

    momentum = (m_last / m_prev) - 1.0
    return round(float(momentum), 4)


def compute_percentile_rank(
    rates: Sequence[float],
    target_value: float,
    min_obs: int = 6,
) -> Optional[float]:
    """Compute empirical percentile rank (0.0 to 100.0) of target_value against prior rates."""
    clean_rates = [float(r) for r in rates if pd.notna(r) and math.isfinite(float(r))]
    if len(clean_rates) < min_obs:
        return None

    arr = np.array(clean_rates)
    pct = float(np.mean(arr <= target_value)) * 100.0
    return round(pct, 2)
