"""
Expected shortfall calculation.

Convention throughout this package: scenario values represent losses,
so larger positive numbers are worse. ES is the average of the worst
(1 - alpha) tail — i.e. the average loss beyond the alpha quantile.

Working assumption: 97.5% one-tailed ES per NPR 2.0 / Basel FRTB IMA.

Regulatory traceability:
    Basel MAR33 expected shortfall; U.S. NPR 2.0 expected-shortfall-based
    measures; EU CRR Article 325bc partial expected shortfall. See
    docs/REGULATORY_TRACEABILITY.md.
"""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np
import numpy.typing as npt


def expected_shortfall(
    losses: Sequence[float] | npt.NDArray[np.float64],
    alpha: float = 0.975,
) -> float:
    """
    Compute expected shortfall (average of tail losses beyond alpha quantile).

    Args:
        losses: Scenario loss values. Positive = loss, negative = gain.
        alpha:  Confidence level. Default 0.975 (97.5%) per NPR 2.0.

    Returns:
        ES as the mean of the non-empty worst-loss tail. The result can be
        negative when all selected tail scenarios are gains.

    Raises:
        ValueError: on empty input or invalid alpha.
    """
    if not (0.0 < alpha < 1.0):
        raise ValueError(f"alpha must be in (0, 1), got {alpha}")

    arr = np.asarray(losses, dtype=float)
    if arr.ndim != 1:
        raise ValueError("losses must be a one-dimensional sequence")
    if arr.size == 0:
        raise ValueError("losses must be a non-empty sequence")
    if not np.all(np.isfinite(arr)):
        raise ValueError("losses must contain only finite values")

    arr_sorted = np.sort(arr)[::-1]  # descending: worst losses first

    n = len(arr_sorted)
    # Number of scenarios in the tail: at least 1
    tail_count = max(1, int(np.ceil(n * (1.0 - alpha))))
    tail = arr_sorted[:tail_count]

    return float(np.mean(tail))
