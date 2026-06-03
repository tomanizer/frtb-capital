"""
Reduced-set diagnostics for the indirect IMCC stress approach.

Under the NPR 2.0 proposed indirect approach, the current-period LHA ES measure
based on a reduced set of risk factors must explain at least 75 percent of the
variability of the current-period LHA ES measure based on the full set over the
previous 60 business days.

This module implements that variation-explained diagnostic and a deterministic
selector for caller-supplied per-risk-factor current-period LHA ES contribution
series. It does not choose the twelve-month stress period or approve use of the
indirect approach.

Regulatory traceability:
    Supports NPR-MR-IMCC-002 in
    docs/requirements/NPR_2_0_MARKET_RISK.yml.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping, Sequence
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


@dataclass(frozen=True)
class ReducedSetSelectionStep:
    """One iteration in the reduced risk-factor set selection trace."""

    iteration: int
    added_factor: str
    selected_factor_names: tuple[str, ...]
    factor_contribution_sum: float
    factor_contribution_mean: float
    variation_explained: float
    passed: bool

    def as_dict(self) -> dict[str, object]:
        """Return a serialisable dictionary for reporting and notebooks."""
        return {
            "iteration": self.iteration,
            "added_factor": self.added_factor,
            "selected_factor_names": list(self.selected_factor_names),
            "factor_contribution_sum": self.factor_contribution_sum,
            "factor_contribution_mean": self.factor_contribution_mean,
            "variation_explained": self.variation_explained,
            "passed": self.passed,
        }


@dataclass(frozen=True)
class ReducedSetSelectionResult:
    """Audit-friendly reduced risk-factor set selection result."""

    selected_factor_names: tuple[str, ...]
    variation_explained: float
    passed: bool
    threshold: float
    window_size: int
    minimum_history: int | None
    minimum_factors: int
    full_current_lha_es: tuple[float, ...]
    reduced_current_lha_es: tuple[float, ...]
    iteration_trace: tuple[ReducedSetSelectionStep, ...]
    coverage_result: ReducedSetCoverageResult

    def as_dict(self) -> dict[str, object]:
        """Return a serialisable dictionary for reporting and notebooks."""
        return {
            "selected_factor_names": list(self.selected_factor_names),
            "variation_explained": self.variation_explained,
            "passed": self.passed,
            "threshold": self.threshold,
            "window_size": self.window_size,
            "minimum_history": self.minimum_history,
            "minimum_factors": self.minimum_factors,
            "full_current_lha_es": list(self.full_current_lha_es),
            "reduced_current_lha_es": list(self.reduced_current_lha_es),
            "iteration_trace": [step.as_dict() for step in self.iteration_trace],
            "coverage_result": self.coverage_result.as_dict(),
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


def _validate_coverage_parameters(
    *,
    window: int,
    minimum_history: int | None,
    threshold: float,
) -> None:
    if window <= 0:
        raise ValueError(f"window must be positive, got {window}")
    if minimum_history is not None and minimum_history <= 0:
        raise ValueError(f"minimum_history must be positive when provided, got {minimum_history}")
    if not (0.0 <= threshold <= 1.0):
        raise ValueError(f"threshold must be in [0, 1], got {threshold}")


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
    _validate_coverage_parameters(
        window=window,
        minimum_history=minimum_history,
        threshold=threshold,
    )

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


def select_reduced_risk_factor_set(
    full_current_lha_es: FloatVector,
    risk_factor_contributions: Mapping[str, FloatVector],
    *,
    window: int = 60,
    minimum_history: int | None = 60,
    threshold: float = 0.75,
    minimum_factors: int = 1,
) -> ReducedSetSelectionResult:
    """
    Select a deterministic reduced risk-factor set from contribution series.

    Contributions must be aligned to ``full_current_lha_es`` and use the same
    sign convention: positive values are current-period LHA ES contributions.
    The selector ranks factors by descending contribution over the selected
    window, with factor name as the stable secondary key, then accumulates
    factors until the variation-explained threshold and minimum factor count are
    both satisfied.
    """
    _validate_coverage_parameters(
        window=window,
        minimum_history=minimum_history,
        threshold=threshold,
    )
    if minimum_factors <= 0:
        raise ValueError(f"minimum_factors must be positive, got {minimum_factors}")
    if not risk_factor_contributions:
        raise ValueError("risk_factor_contributions must be non-empty")

    full_arr = _as_non_negative_finite_array(full_current_lha_es, "full_current_lha_es")
    if minimum_history is not None and len(full_arr) < minimum_history:
        raise ValueError(
            f"full_current_lha_es must contain at least {minimum_history} observations"
        )

    contribution_arrays: dict[str, npt.NDArray[np.float64]] = {}
    for factor_name, contribution_series in risk_factor_contributions.items():
        if not factor_name:
            raise ValueError("risk factor names must be non-empty")
        arr = _as_non_negative_finite_array(
            contribution_series,
            f"risk_factor_contributions[{factor_name!r}]",
        )
        if len(arr) != len(full_arr):
            raise ValueError("risk factor contribution series must align with full_current_lha_es")
        contribution_arrays[str(factor_name)] = arr

    if minimum_factors > len(contribution_arrays):
        raise ValueError("minimum_factors cannot exceed the number of contribution series")

    window_size = min(window, len(full_arr))
    full_w = full_arr[-window_size:]
    contribution_windows = {
        factor_name: arr[-window_size:] for factor_name, arr in contribution_arrays.items()
    }
    ordered_factor_names = tuple(
        sorted(
            contribution_windows,
            key=lambda factor_name: (
                -float(np.sum(contribution_windows[factor_name])),
                factor_name,
            ),
        )
    )

    selected_factor_names: list[str] = []
    reduced_w = np.zeros(window_size, dtype=np.float64)
    trace: list[ReducedSetSelectionStep] = []
    selected_coverage: ReducedSetCoverageResult | None = None

    for iteration, factor_name in enumerate(ordered_factor_names, start=1):
        contribution_w = contribution_windows[factor_name]
        selected_factor_names.append(factor_name)
        reduced_w = reduced_w + contribution_w
        coverage = reduced_set_variation_explained(
            full_w,
            reduced_w,
            window=window_size,
            minimum_history=None,
            threshold=threshold,
        )
        passed = coverage.passed and len(selected_factor_names) >= minimum_factors
        trace.append(
            ReducedSetSelectionStep(
                iteration=iteration,
                added_factor=factor_name,
                selected_factor_names=tuple(selected_factor_names),
                factor_contribution_sum=float(np.sum(contribution_w)),
                factor_contribution_mean=float(np.mean(contribution_w)),
                variation_explained=coverage.variation_explained,
                passed=passed,
            )
        )
        selected_coverage = coverage
        if passed:
            break

    if selected_coverage is None:
        raise ValueError("risk_factor_contributions must be non-empty")

    return ReducedSetSelectionResult(
        selected_factor_names=tuple(selected_factor_names),
        variation_explained=selected_coverage.variation_explained,
        passed=trace[-1].passed,
        threshold=threshold,
        window_size=window_size,
        minimum_history=minimum_history,
        minimum_factors=minimum_factors,
        full_current_lha_es=tuple(float(value) for value in full_w),
        reduced_current_lha_es=tuple(float(value) for value in reduced_w),
        iteration_trace=tuple(trace),
        coverage_result=selected_coverage,
    )


def select_reduced_risk_factor_set_for_policy(
    full_current_lha_es: FloatVector,
    risk_factor_contributions: Mapping[str, FloatVector],
    policy: RegulatoryPolicy,
    *,
    run_id: str | None = None,
    desk_id: str | None = None,
) -> ReducedSetSelectionResult:
    """Select a reduced risk-factor set using policy defaults."""
    policy.require_capital_runtime_supported()
    result = select_reduced_risk_factor_set(
        full_current_lha_es,
        risk_factor_contributions,
        window=policy.reduced_set_coverage_window_days,
        minimum_history=policy.reduced_set_coverage_window_days,
        threshold=policy.reduced_set_variation_explained_threshold,
        minimum_factors=policy.reduced_set_minimum_factor_count,
    )
    logger.info(
        "reduced_set_selection_complete",
        extra=calculation_log_extra(
            run_id=run_id,
            desk_id=desk_id,
            regime=policy.regime.value,
            selected_factor_count=len(result.selected_factor_names),
            variation_explained=result.variation_explained,
            threshold=result.threshold,
            passed=result.passed,
            window_size=result.window_size,
        ),
    )
    return result


def reduced_set_variation_explained_for_policy(
    full_current_lha_es: FloatVector,
    reduced_current_lha_es: FloatVector,
    policy: RegulatoryPolicy,
    *,
    run_id: str | None = None,
    desk_id: str | None = None,
) -> ReducedSetCoverageResult:
    """Assess reduced-set variation explained using policy defaults."""
    policy.require_capital_runtime_supported()
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
