"""
Backtesting prototype.

Working assumption (NPR 2.0 / Basel FRTB IMA):

    Count VaR exceptions over the most recent 250 business days.
    An exception occurs when the actual loss exceeds the VaR estimate.

    Two exception series are counted separately:
        - APL exceptions: Actual P&L (APL) vs VaR
        - HPL exceptions: Hypothetical P&L (HPL) vs VaR

    VaR convention used here: 99%, 1-day (simplification).
    The 250-day window is the Basel / NPR 2.0 standard backtesting window.

    Exception count thresholds (Basel traffic-light):
        Green:  0-4  exceptions
        Amber:  5-9  exceptions
        Red:   10+     exceptions

    These thresholds are prototype working assumptions.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np
import numpy.typing as npt

# Basel backtesting traffic-light thresholds
GREEN_MAX = 4
AMBER_MAX = 9


@dataclass(frozen=True)
class BacktestResult:
    apl_exceptions: int
    hpl_exceptions: int
    apl_zone: str   # "GREEN", "AMBER", "RED"
    hpl_zone: str
    window_size: int


def _as_finite_1d_array(values: Sequence[float], name: str) -> npt.NDArray[np.float64]:
    arr = np.asarray(values, dtype=float)
    if arr.ndim != 1:
        raise ValueError(f"{name} must be one-dimensional")
    if arr.size == 0:
        raise ValueError(f"{name} is empty")
    if not np.all(np.isfinite(arr)):
        raise ValueError(f"{name} must contain only finite values")
    return arr.astype(np.float64, copy=False)


def _zone(count: int) -> str:
    if count <= GREEN_MAX:
        return "GREEN"
    elif count <= AMBER_MAX:
        return "AMBER"
    return "RED"


def count_exceptions(
    pnl: Sequence[float],
    var_estimates: Sequence[float],
) -> int:
    """
    Count observations where loss exceeds the VaR estimate.

    Convention:
        pnl values:        positive = profit, negative = loss.
        var_estimates:     positive scalar (the magnitude of the VaR threshold).

    An exception occurs when -pnl[i] > var_estimates[i],
    i.e. actual loss exceeds estimated VaR.

    Args:
        pnl:           P&L observations (positive = profit).
        var_estimates: Corresponding daily VaR values (positive magnitude).

    Returns:
        Number of exceptions.

    Raises:
        ValueError: if lengths differ or inputs are empty.
    """
    pnl_arr = _as_finite_1d_array(pnl, "pnl")
    var_arr = _as_finite_1d_array(var_estimates, "var_estimates")

    if len(pnl_arr) != len(var_arr):
        raise ValueError(
            f"pnl length ({len(pnl_arr)}) != var_estimates length ({len(var_arr)})"
        )
    if np.any(var_arr <= 0.0):
        raise ValueError("var_estimates must contain only positive values")

    return int(np.sum(-pnl_arr > var_arr))


def backtest(
    apl: Sequence[float],
    hpl: Sequence[float],
    var_estimates: Sequence[float],
    window: int = 250,
) -> BacktestResult:
    """
    Run backtesting over the most recent `window` observations.

    Args:
        apl:            Actual P&L series (positive = profit).
        hpl:            Hypothetical P&L series (positive = profit).
        var_estimates:  Daily VaR magnitudes (positive scalars).
        window:         Number of most recent business days to evaluate.
                        Default 250 per Basel / NPR 2.0.

    Returns:
        BacktestResult with exception counts and zone classifications.
    """
    if window <= 0:
        raise ValueError(f"window must be positive, got {window}")

    apl_w = _as_finite_1d_array(apl, "apl")[-window:]
    hpl_w = _as_finite_1d_array(hpl, "hpl")[-window:]
    var_w = _as_finite_1d_array(var_estimates, "var_estimates")[-window:]

    if len(apl_w) != len(var_w) or len(hpl_w) != len(var_w):
        raise ValueError(
            "After windowing, APL, HPL, and VaR series must have equal length"
        )
    if np.any(var_w <= 0.0):
        raise ValueError("var_estimates must contain only positive values")

    n_apl = int(np.sum(-apl_w > var_w))
    n_hpl = int(np.sum(-hpl_w > var_w))

    return BacktestResult(
        apl_exceptions=n_apl,
        hpl_exceptions=n_hpl,
        apl_zone=_zone(n_apl),
        hpl_zone=_zone(n_hpl),
        window_size=len(var_w),
    )
