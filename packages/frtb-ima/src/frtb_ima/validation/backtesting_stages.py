"""Backtesting exception classification stage helpers."""

from __future__ import annotations

import math

import numpy as np
import numpy.typing as npt

# Basel MAR32.5 / MAR99 Table 1 traffic-light thresholds over 250 observations.
GREEN_MAX = 4
AMBER_MAX = 9


def _zone(count: int, window_size: int = 250) -> str:
    """Return the Basel MAR32.5 / MAR99 Table 1 traffic-light zone."""
    if window_size <= 0:
        raise ValueError("window_size must be positive")
    green_max = math.floor(GREEN_MAX * window_size / 250)
    amber_max = math.floor(AMBER_MAX * window_size / 250)
    if count <= green_max:
        return "GREEN"
    if count <= amber_max:
        return "AMBER"
    return "RED"


def _count_exceptions_regulatory(
    pnl: npt.NDArray[np.float64],
    var_estimates: npt.NDArray[np.float64],
    official_holiday_mask: npt.NDArray[np.bool_] | None,
) -> int:
    """
    Count exceptions with NPR missing-data treatment.

    Missing P&L or VaR values count as exceptions unless the missing value is
    related to an official holiday. This function assumes inputs have already
    been windowed and length-aligned.
    """
    return int(np.sum(_exception_flags_regulatory(pnl, var_estimates, official_holiday_mask)))


def _exception_flags_regulatory(
    pnl: npt.NDArray[np.float64],
    var_estimates: npt.NDArray[np.float64],
    official_holiday_mask: npt.NDArray[np.bool_] | None,
) -> npt.NDArray[np.bool_]:
    finite_pnl = np.isfinite(pnl)
    finite_var = np.isfinite(var_estimates)
    missing = ~(finite_pnl & finite_var)
    with np.errstate(invalid="ignore"):
        loss_exceeds_var = finite_pnl & finite_var & (-pnl > var_estimates)

    exceptions = missing | loss_exceeds_var
    if official_holiday_mask is not None:
        exceptions = exceptions & ~official_holiday_mask
    return exceptions.astype(np.bool_, copy=False)


def _exception_reason(
    pnl_value: float,
    var_value: float,
    official_holiday: bool,
    is_exception: bool,
) -> str:
    if official_holiday:
        return "official_holiday"
    finite_pnl = math.isfinite(pnl_value)
    finite_var = math.isfinite(var_value)
    if not finite_pnl and not finite_var:
        return "missing_pnl_and_var"
    if not finite_pnl:
        return "missing_pnl"
    if not finite_var:
        return "missing_var"
    if is_exception:
        return "loss_exceeds_var"
    return "none"
