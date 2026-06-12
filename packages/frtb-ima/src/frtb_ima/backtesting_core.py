"""
Scalar IMA backtesting kernels.

This module owns the single-level exception count and scalar backtest result
calculation. Trading-desk multi-level trace assembly lives in
``backtesting_trace``.
"""

from __future__ import annotations

import numpy as np

from frtb_ima._array_utils import finite_1d_float_array as _as_finite_1d_array
from frtb_ima.backtesting_types import BacktestResult, FloatVector
from frtb_ima.validation.backtesting_stages import _zone
from frtb_ima.validation.observation_windows import (
    require_positive_observation_count as _require_positive_observation_count,
)
from frtb_ima.validation.observation_windows import (
    require_positive_optional_observation_count as _require_positive_optional_observation_count,
)


def count_exceptions(
    pnl: FloatVector,
    var_estimates: FloatVector,
) -> int:
    """Count observations where loss exceeds the VaR estimate.

    P&L uses positive-profit convention. An exception occurs when the loss
    magnitude ``-pnl[i]`` is strictly greater than the VaR estimate.
    Parameters
    ----------
    pnl : FloatVector
        Pnl.
    var_estimates : FloatVector
        Var estimates.

    Returns
    -------
    int
        Result of the operation.
    """
    pnl_arr = _as_finite_1d_array(pnl, "pnl")
    var_arr = _as_finite_1d_array(var_estimates, "var_estimates")

    if len(pnl_arr) != len(var_arr):
        raise ValueError(f"pnl length ({len(pnl_arr)}) != var_estimates length ({len(var_arr)})")
    if np.any(var_arr <= 0.0):
        raise ValueError("var_estimates must contain only positive values")

    return int(np.sum(-pnl_arr > var_arr))


def backtest(
    apl: FloatVector,
    hpl: FloatVector,
    var_estimates: FloatVector,
    window: int = 250,
    minimum_history: int | None = None,
) -> BacktestResult:
    """Run scalar backtesting over the most recent observations.

    APL and HPL use positive-profit convention; VaR values are positive loss
    magnitudes.
    Parameters
    ----------
    apl : FloatVector
        Apl.
    hpl : FloatVector
        Hpl.
    var_estimates : FloatVector
        Var estimates.
    window : int, optional
        Window.
    minimum_history : int | None, optional
        Minimum history.

    Returns
    -------
    BacktestResult
        Result of the operation.
    """
    _require_positive_observation_count(window, field="window")
    _require_positive_optional_observation_count(minimum_history, field="minimum_history")

    apl_arr = _as_finite_1d_array(apl, "apl")
    hpl_arr = _as_finite_1d_array(hpl, "hpl")
    var_arr = _as_finite_1d_array(var_estimates, "var_estimates")

    if minimum_history is not None:
        min_length = min(len(apl_arr), len(hpl_arr), len(var_arr))
        if min_length < minimum_history:
            raise ValueError(
                "APL, HPL, and VaR series must contain at least "
                f"{minimum_history} observations before windowing"
            )

    apl_w = apl_arr[-window:]
    hpl_w = hpl_arr[-window:]
    var_w = var_arr[-window:]

    if len(apl_w) != len(var_w) or len(hpl_w) != len(var_w):
        raise ValueError("After windowing, APL, HPL, and VaR series must have equal length")
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


__all__ = ("backtest", "count_exceptions")
