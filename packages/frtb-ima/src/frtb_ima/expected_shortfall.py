"""
Expected shortfall calculation.

Convention throughout this package: scenario values represent losses,
so larger positive numbers are worse. ES is the average of the worst
(1 - alpha) tail — i.e. the average loss beyond the alpha quantile.

Callers must provide the ES confidence level explicitly. Policy-aware
calculation wrappers source the level from ``RegulatoryPolicy``.

Regulatory traceability:
    Basel MAR33 expected shortfall; U.S. NPR 2.0 expected-shortfall-based
    measures; EU CRR Article 325bc partial expected shortfall. See
    docs/REGULATORY_TRACEABILITY.md.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from enum import StrEnum

import numpy as np
import numpy.typing as npt


class ESEstimator(StrEnum):
    """Expected shortfall tail estimator."""

    DISCRETE_CEIL = "DISCRETE_CEIL"
    WEIGHTED_INTERPOLATED = "WEIGHTED_INTERPOLATED"


def expected_shortfall(
    losses: Sequence[float] | npt.NDArray[np.float64],
    alpha: float,
    estimator: ESEstimator,
) -> float:
    """Compute expected shortfall (average of tail losses beyond alpha quantile).

    Args:
        losses: Scenario loss values. Positive = loss, negative = gain.
        alpha:  Confidence level sourced from the applicable run policy.
        estimator: Tail estimator used to average losses beyond alpha.

    Returns:
        ES as the mean of the non-empty worst-loss tail. The result can be
        negative when all selected tail scenarios are gains.

    Raises:
        ValueError: on empty input or invalid alpha.
    Parameters
    ----------
    losses : Sequence[float] | npt.NDArray[np.float64]
        Losses.
    alpha : float
        Alpha.
    estimator : ESEstimator
        Estimator.

    Returns
    -------
    float
        Result of the operation.
    """
    if not (0.0 < alpha < 1.0):
        raise ValueError(f"alpha must be in (0, 1), got {alpha}")
    estimator = ESEstimator(estimator)

    arr = np.asarray(losses, dtype=float)
    if arr.ndim != 1:
        raise ValueError("losses must be a one-dimensional sequence")
    if arr.size == 0:
        raise ValueError("losses must be a non-empty sequence")
    if not np.all(np.isfinite(arr)):
        raise ValueError("losses must contain only finite values")

    return expected_shortfall_from_sorted_losses_desc(
        np.sort(arr)[::-1],
        alpha=alpha,
        estimator=estimator,
    )


def expected_shortfall_from_sorted_losses_desc(
    sorted_losses_desc: Sequence[float] | npt.NDArray[np.float64],
    alpha: float,
    estimator: ESEstimator,
) -> float:
    """Compute ES from losses already sorted descending, worst losses first.
    Parameters
    ----------
    sorted_losses_desc : Sequence[float] | npt.NDArray[np.float64]
        Sorted losses desc.
    alpha : float
        Alpha.
    estimator : ESEstimator
        Estimator.

    Returns
    -------
    float
        Result of the operation.
    """
    if not (0.0 < alpha < 1.0):
        raise ValueError(f"alpha must be in (0, 1), got {alpha}")
    estimator = ESEstimator(estimator)
    arr = np.asarray(sorted_losses_desc, dtype=float)
    if arr.ndim != 1:
        raise ValueError("sorted_losses_desc must be a one-dimensional sequence")
    if arr.size == 0:
        raise ValueError("sorted_losses_desc must be a non-empty sequence")
    if not np.all(np.isfinite(arr)):
        raise ValueError("sorted_losses_desc must contain only finite values")

    if estimator == ESEstimator.DISCRETE_CEIL:
        tail_count = max(1, math.ceil(arr.size * (1.0 - alpha)))
        return float(np.mean(arr[:tail_count]))

    tail_mass = arr.size * (1.0 - alpha)
    full_count = math.floor(tail_mass)
    fractional_weight = tail_mass - full_count
    weighted_sum = float(np.sum(arr[:full_count])) if full_count else 0.0
    if fractional_weight > 0.0:
        weighted_sum += fractional_weight * float(arr[full_count])
    return weighted_sum / tail_mass
