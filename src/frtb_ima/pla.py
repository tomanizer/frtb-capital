"""
Profit and Loss Attribution (PLA) prototype.

Working assumption: use Kolmogorov-Smirnov (KS) statistic to compare
Hypothetical P&L (HPL) and Risk-Theoretical P&L (RTPL) vectors.

A large KS statistic indicates the two distributions differ significantly,
which under NPR 2.0 / Basel FRTB IMA would trigger a PLA add-on or
model failure.

Zone thresholds:
    Green (pass):  KS <= GREEN_THRESHOLD
    Amber:         GREEN_THRESHOLD < KS <= AMBER_THRESHOLD
    Red (fail):    KS > AMBER_THRESHOLD

Thresholds are placeholders — NPR 2.0 working assumption only.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np
import numpy.typing as npt

# Placeholder zone thresholds — replace with final NPR 2.0 values when published
GREEN_THRESHOLD: float = 0.09
AMBER_THRESHOLD: float = 0.12


@dataclass(frozen=True)
class PlaResult:
    ks_statistic: float
    zone: str        # "GREEN", "AMBER", or "RED"
    n_hpl: int
    n_rtpl: int


def _as_finite_1d_array(values: Sequence[float], name: str) -> npt.NDArray[np.float64]:
    arr = np.asarray(values, dtype=float)
    if arr.ndim != 1:
        raise ValueError(f"{name} vector must be one-dimensional")
    if arr.size == 0:
        raise ValueError(f"{name} vector is empty")
    if not np.all(np.isfinite(arr)):
        raise ValueError(f"{name} vector must contain only finite values")
    return arr.astype(np.float64, copy=False)


def ks_statistic(hpl: Sequence[float], rtpl: Sequence[float]) -> float:
    """
    Compute the two-sample Kolmogorov-Smirnov statistic between HPL and RTPL.

    KS = max|F_HPL(x) - F_RTPL(x)| over all x.

    Args:
        hpl:  Hypothetical P&L vector (sign convention: positive = profit).
        rtpl: Risk-Theoretical P&L vector (same convention).

    Returns:
        KS statistic in [0, 1].

    Raises:
        ValueError: if either vector is empty.
    """
    return _ks_statistic_arrays(
        np.sort(_as_finite_1d_array(hpl, "hpl")),
        np.sort(_as_finite_1d_array(rtpl, "rtpl")),
    )


def _ks_statistic_arrays(
    hpl_arr: npt.NDArray[np.float64],
    rtpl_arr: npt.NDArray[np.float64],
) -> float:
    """Compute KS for already validated, sorted arrays."""

    # Merge all unique values for evaluation points
    all_values = np.unique(np.concatenate([hpl_arr, rtpl_arr]))

    n_hpl = len(hpl_arr)
    n_rtpl = len(rtpl_arr)

    # Empirical CDFs evaluated at each merged point
    cdf_hpl = np.searchsorted(hpl_arr, all_values, side="right") / n_hpl
    cdf_rtpl = np.searchsorted(rtpl_arr, all_values, side="right") / n_rtpl

    return float(np.max(np.abs(cdf_hpl - cdf_rtpl)))


def pla_assessment(
    hpl: Sequence[float],
    rtpl: Sequence[float],
    green_threshold: float = GREEN_THRESHOLD,
    amber_threshold: float = AMBER_THRESHOLD,
) -> PlaResult:
    """
    Run PLA assessment and return the KS statistic with zone classification.

    Args:
        hpl:              Hypothetical P&L vector.
        rtpl:             Risk-Theoretical P&L vector.
        green_threshold:  KS <= this -> GREEN.
        amber_threshold:  green < KS <= this -> AMBER; above -> RED.

    Returns:
        PlaResult with ks_statistic, zone, and vector lengths.
    """
    if not (0.0 <= green_threshold <= amber_threshold <= 1.0):
        raise ValueError(
            "PLA thresholds must satisfy 0 <= green_threshold <= amber_threshold <= 1"
        )

    hpl_arr = _as_finite_1d_array(hpl, "hpl")
    rtpl_arr = _as_finite_1d_array(rtpl, "rtpl")
    ks = _ks_statistic_arrays(np.sort(hpl_arr), np.sort(rtpl_arr))

    if ks <= green_threshold:
        zone = "GREEN"
    elif ks <= amber_threshold:
        zone = "AMBER"
    else:
        zone = "RED"

    return PlaResult(
        ks_statistic=ks,
        zone=zone,
        n_hpl=len(hpl_arr),
        n_rtpl=len(rtpl_arr),
    )
