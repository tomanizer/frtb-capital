"""Input validation helpers for IMA backtesting trace assembly."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date

import numpy as np
import numpy.typing as npt

from frtb_ima.backtesting_types import BoolVector, FloatVector
from frtb_ima.validation.observation_windows import (
    validate_observation_dates as _validate_observation_dates,
)


@dataclass(frozen=True)
class TraceInputs:
    """Validated APL/HPL, optional dates, holidays, and common history length."""

    apl: npt.NDArray[np.float64]
    hpl: npt.NDArray[np.float64]
    dates: tuple[date, ...] | None
    holiday_mask: npt.NDArray[np.bool_] | None
    min_length: int


def prepare_trace_inputs(
    apl: FloatVector,
    hpl: FloatVector,
    var_estimates_by_confidence: Mapping[float, FloatVector],
    exception_limits: Sequence[tuple[float, int]],
    official_holiday_mask: BoolVector | None,
    observation_dates: Sequence[date] | None,
) -> TraceInputs:
    """Validate aligned APL, HPL, VaR, date, and holiday inputs.
    Parameters
    ----------
    apl : FloatVector
        Apl.
    hpl : FloatVector
        Hpl.
    var_estimates_by_confidence : Mapping[float, FloatVector]
        Var estimates by confidence.
    exception_limits : Sequence[tuple[float, int]]
        Exception limits.
    official_holiday_mask : BoolVector | None
        Official holiday mask.
    observation_dates : Sequence[date] | None
        Observation dates.

    Returns
    -------
    TraceInputs
        Result of the operation.
    """
    apl_arr = as_1d_array_allowing_missing(apl, "apl")
    hpl_arr = as_1d_array_allowing_missing(hpl, "hpl")
    if len(apl_arr) != len(hpl_arr):
        raise ValueError("APL and HPL series must have equal length")
    dates = _validate_observation_dates(
        observation_dates,
        len(apl_arr),
        length_label="APL/HPL",
    )
    holiday_arr = _validated_holiday_mask(official_holiday_mask, expected_length=len(apl_arr))
    min_length = _validated_var_min_length(
        var_estimates_by_confidence,
        exception_limits,
        expected_length=len(apl_arr),
    )
    return TraceInputs(apl_arr, hpl_arr, dates, holiday_arr, min(min_length, len(apl_arr)))


def validated_minimum_history(
    min_length: int,
    minimum_history: int | None,
    allow_prorated_thresholds: bool,
) -> None:
    """Validate minimum history unless prorated thresholds are explicitly allowed.
    Parameters
    ----------
    min_length : int
        Minimum aligned input length.
    minimum_history : int | None
        Required history length.
    allow_prorated_thresholds : bool
        Whether short-history thresholds may be prorated.
    """
    if minimum_history is None or min_length >= minimum_history:
        return
    if not allow_prorated_thresholds:
        raise ValueError(
            "APL, HPL, and VaR series must contain at least "
            f"{minimum_history} observations before windowing"
        )


def as_1d_array_allowing_missing(
    values: FloatVector,
    name: str,
) -> npt.NDArray[np.float64]:
    """Return a one-dimensional float array while preserving NaN as missing.
    Parameters
    ----------
    values : FloatVector
        Values.
    name : str
        Field name for validation errors.

    Returns
    -------
    npt.NDArray[np.float64]
        Result of the operation.
    """
    arr = np.asarray(values, dtype=float)
    if arr.ndim != 1:
        raise ValueError(f"{name} must be one-dimensional")
    if arr.size == 0:
        raise ValueError(f"{name} is empty")
    return arr.astype(np.float64, copy=False)


def float_or_none(value: float) -> float | None:
    """Return finite floats as ``float`` and missing/non-finite values as ``None``.
    Parameters
    ----------
    value : float
        Value.

    Returns
    -------
    float | None
        Result of the operation.
    """
    if np.isfinite(value):
        return float(value)
    return None


def _validated_holiday_mask(
    official_holiday_mask: BoolVector | None,
    *,
    expected_length: int,
) -> npt.NDArray[np.bool_] | None:
    if official_holiday_mask is None:
        return None
    holiday_arr = np.asarray(official_holiday_mask, dtype=bool)
    if holiday_arr.ndim != 1:
        raise ValueError("official_holiday_mask must be one-dimensional")
    if len(holiday_arr) != expected_length:
        raise ValueError("official_holiday_mask length must match APL/HPL")
    return holiday_arr


def _validated_var_min_length(
    var_estimates_by_confidence: Mapping[float, FloatVector],
    exception_limits: Sequence[tuple[float, int]],
    *,
    expected_length: int,
) -> int:
    min_length = expected_length
    for confidence_level, _limit in exception_limits:
        if confidence_level not in var_estimates_by_confidence:
            raise KeyError(f"Missing VaR series for confidence level {confidence_level}")
        var_arr = as_1d_array_allowing_missing(
            var_estimates_by_confidence[confidence_level],
            f"var_estimates[{confidence_level}]",
        )
        if len(var_arr) != expected_length:
            raise ValueError(f"VaR series length for {confidence_level} must match APL/HPL")
        min_length = min(min_length, len(var_arr))
    return min_length


__all__ = (
    "TraceInputs",
    "as_1d_array_allowing_missing",
    "float_or_none",
    "prepare_trace_inputs",
    "validated_minimum_history",
)
