"""
Reduced-set diagnostics for the indirect IMCC stress approach.

Under the NPR 2.0 proposed indirect approach, the current-period LHA ES measure
based on a reduced set of risk factors must explain at least 75 percent of the
variability of the current-period LHA ES measure based on the full set over the
previous 60 business days.

This module implements only that variation-explained diagnostic. It does not
select the reduced risk-factor set, choose the twelve-month stress period, or
approve use of the indirect approach.

Regulatory traceability:
    Supports NPR-MR-IMCC-002 in
    docs/requirements/NPR_2_0_MARKET_RISK.yml.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np
import numpy.typing as npt

from frtb_ima.logging import calculation_log_extra
from frtb_ima.regimes import RegulatoryPolicy

FloatVector = Sequence[float] | npt.NDArray[np.float64]
logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ReducedSetCoverageResult:
    """Audit-friendly reduced-set variation-explained diagnostic."""

    window_size: int
    minimum_history: int | None
    threshold: float
    variation_explained: float
    passed: bool
    full_mean: float
    sum_squared_residuals: float
    total_sum_squares: float
    degenerate_full_series: bool

    def as_dict(self) -> dict[str, object]:
        """Return a serialisable dictionary for reporting and notebooks."""
        return {
            "window_size": self.window_size,
            "minimum_history": self.minimum_history,
            "threshold": self.threshold,
            "variation_explained": self.variation_explained,
            "passed": self.passed,
            "full_mean": self.full_mean,
            "sum_squared_residuals": self.sum_squared_residuals,
            "total_sum_squares": self.total_sum_squares,
            "degenerate_full_series": self.degenerate_full_series,
        }


def _as_non_negative_finite_array(
    values: FloatVector,
    name: str,
) -> npt.NDArray[np.float64]:
    arr = np.asarray(values, dtype=float)
    if arr.ndim != 1:
        raise ValueError(f"{name} must be one-dimensional")
    if arr.size == 0:
        raise ValueError(f"{name} must be non-empty")
    if not np.all(np.isfinite(arr)):
        raise ValueError(f"{name} must contain only finite values")
    if np.any(arr < 0.0):
        raise ValueError(f"{name} must contain only non-negative ES values")
    return arr.astype(np.float64, copy=False)


def reduced_set_variation_explained(
    full_current_lha_es: FloatVector,
    reduced_current_lha_es: FloatVector,
    *,
    window: int = 60,
    minimum_history: int | None = 60,
    threshold: float = 0.75,
) -> ReducedSetCoverageResult:
    """
    Assess whether the reduced set explains enough full-set ES variability.

    The statistic is the out-of-sample R-squared style measure:

        1 - sum((ES_full - ES_reduced)^2) / sum((ES_full - mean(ES_full))^2)

    over the most recent ``window`` observations.
    """
    if window <= 0:
        raise ValueError(f"window must be positive, got {window}")
    if minimum_history is not None and minimum_history <= 0:
        raise ValueError(f"minimum_history must be positive when provided, got {minimum_history}")
    if not (0.0 <= threshold <= 1.0):
        raise ValueError(f"threshold must be in [0, 1], got {threshold}")

    full_arr = _as_non_negative_finite_array(full_current_lha_es, "full_current_lha_es")
    reduced_arr = _as_non_negative_finite_array(
        reduced_current_lha_es,
        "reduced_current_lha_es",
    )
    if len(full_arr) != len(reduced_arr):
        raise ValueError("full and reduced current LHA ES series must have equal length")
    if minimum_history is not None and len(full_arr) < minimum_history:
        raise ValueError(
            "full and reduced current LHA ES series must contain at least "
            f"{minimum_history} observations"
        )

    window_size = min(window, len(full_arr))
    full_w = full_arr[-window_size:]
    reduced_w = reduced_arr[-window_size:]

    full_mean = float(np.mean(full_w))
    residuals = full_w - reduced_w
    sum_squared_residuals = float(np.dot(residuals, residuals))
    centred_full = full_w - full_mean
    total_sum_squares = float(np.dot(centred_full, centred_full))

    degenerate_full_series = total_sum_squares == 0.0
    if degenerate_full_series:
        variation_explained = 1.0 if sum_squared_residuals == 0.0 else 0.0
    else:
        variation_explained = 1.0 - (sum_squared_residuals / total_sum_squares)

    return ReducedSetCoverageResult(
        window_size=window_size,
        minimum_history=minimum_history,
        threshold=threshold,
        variation_explained=variation_explained,
        passed=variation_explained >= threshold,
        full_mean=full_mean,
        sum_squared_residuals=sum_squared_residuals,
        total_sum_squares=total_sum_squares,
        degenerate_full_series=degenerate_full_series,
    )


def reduced_set_variation_explained_for_policy(
    full_current_lha_es: FloatVector,
    reduced_current_lha_es: FloatVector,
    policy: RegulatoryPolicy,
    *,
    run_id: str | None = None,
    desk_id: str | None = None,
) -> ReducedSetCoverageResult:
    """Assess reduced-set variation explained using policy defaults."""
    result = reduced_set_variation_explained(
        full_current_lha_es,
        reduced_current_lha_es,
        window=policy.reduced_set_coverage_window_days,
        minimum_history=policy.reduced_set_coverage_window_days,
        threshold=policy.reduced_set_variation_explained_threshold,
    )
    logger.info(
        "reduced_set_variation_explained_complete",
        extra=calculation_log_extra(
            run_id=run_id,
            desk_id=desk_id,
            regime=policy.regime.value,
            variation_explained=result.variation_explained,
            threshold=result.threshold,
            passed=result.passed,
            window_size=result.window_size,
        ),
    )
    return result
