"""
Rolling-window stress-period scoring.

This module contains the NumPy window-scoring stage for IMA stress-period
calibration. It consumes validated ``HistoricalStressSeries`` records and
returns deterministic ``StressPeriodCandidate`` records without applying
run-level policy dispatch.
"""

from __future__ import annotations

from datetime import date

import numpy as np
import numpy.typing as npt
from numpy.lib.stride_tricks import sliding_window_view

from frtb_ima.data_models import RiskClass
from frtb_ima.expected_shortfall import ESEstimator, expected_shortfall_from_sorted_losses_desc
from frtb_ima.stress_period_types import (
    FloatVector,
    HistoricalStressSeries,
    StressPeriodCandidate,
    StressPeriodTieBreak,
    StressSeverityMetric,
    _as_finite_loss_array,
    _validate_selection_parameters,
)


def rolling_window_severity_scores(
    losses: FloatVector,
    *,
    window_observations: int = 250,
    minimum_observations: int = 250,
    severity_metric: StressSeverityMetric = StressSeverityMetric.EXPECTED_SHORTFALL,
    confidence_level: float,
    es_estimator: ESEstimator,
) -> npt.NDArray[np.float64]:
    """Return one severity score per rolling window.

    ``severity_score`` is derived from the supplied positive-loss history using
    the selected metric. ``EXPECTED_SHORTFALL`` returns the empirical mean of
    the largest tail losses in each window, ``MAX_LOSS`` returns the single
    largest loss, and ``CUMULATIVE_LOSS`` returns the sum of losses.

    The numeric path is NumPy-native. ``CUMULATIVE_LOSS`` uses prefix sums, which
    is the add-one/remove-one rolling-window optimisation. ``EXPECTED_SHORTFALL``
    uses a strided rolling-window view plus ``np.partition`` to avoid full
    sorting of each window.
    Parameters
    ----------
    losses : FloatVector
        Losses.
    window_observations : int, optional
        Window observations.
    minimum_observations : int, optional
        Minimum observations.
    severity_metric : StressSeverityMetric, optional
        Severity metric.
    confidence_level : float
        Confidence level.
    es_estimator : ESEstimator
        Es estimator.

    Returns
    -------
    npt.NDArray[np.float64]
        Result of the operation.
    """
    _validate_selection_parameters(
        window_observations=window_observations,
        minimum_observations=minimum_observations,
        severity_metric=severity_metric,
        confidence_level=confidence_level,
        es_estimator=es_estimator,
    )
    loss_arr = _as_finite_loss_array(losses, "losses")
    if loss_arr.size < minimum_observations:
        raise ValueError(f"losses must contain at least {minimum_observations} observations")
    if loss_arr.size < window_observations:
        raise ValueError("losses must contain at least window_observations observations")

    if severity_metric == StressSeverityMetric.CUMULATIVE_LOSS:
        cumulative = np.empty(loss_arr.size + 1, dtype=np.float64)
        cumulative[0] = 0.0
        np.cumsum(loss_arr, out=cumulative[1:])
        return cumulative[window_observations:] - cumulative[:-window_observations]

    windows = sliding_window_view(loss_arr, window_shape=window_observations)

    if severity_metric == StressSeverityMetric.MAX_LOSS:
        max_scores: npt.NDArray[np.float64] = np.asarray(
            np.max(windows, axis=1),
            dtype=np.float64,
        )
        return max_scores

    if severity_metric == StressSeverityMetric.EXPECTED_SHORTFALL:
        sorted_windows = np.sort(windows, axis=1)[:, ::-1]
        es_scores: npt.NDArray[np.float64] = np.asarray(
            [
                expected_shortfall_from_sorted_losses_desc(
                    window,
                    alpha=confidence_level,
                    estimator=es_estimator,
                )
                for window in sorted_windows
            ],
            dtype=np.float64,
        )
        return es_scores

    raise ValueError(f"Unsupported severity metric: {severity_metric}")


def stress_period_candidates_from_history(
    series: HistoricalStressSeries,
    *,
    window_observations: int = 250,
    minimum_observations: int = 250,
    severity_metric: StressSeverityMetric = StressSeverityMetric.EXPECTED_SHORTFALL,
    confidence_level: float,
    es_estimator: ESEstimator,
) -> tuple[StressPeriodCandidate, ...]:
    """Build all candidate stress windows for audit or diagnostics.
    Parameters
    ----------
    series : HistoricalStressSeries
        Series.
    window_observations : int, optional
        Window observations.
    minimum_observations : int, optional
        Minimum observations.
    severity_metric : StressSeverityMetric, optional
        Severity metric.
    confidence_level : float
        Confidence level.
    es_estimator : ESEstimator
        Es estimator.

    Returns
    -------
    tuple[StressPeriodCandidate, ...]
        Result of the operation.
    """
    if not isinstance(series, HistoricalStressSeries):
        raise TypeError("series must be a HistoricalStressSeries")
    scores = rolling_window_severity_scores(
        series.losses,
        window_observations=window_observations,
        minimum_observations=minimum_observations,
        severity_metric=severity_metric,
        confidence_level=confidence_level,
        es_estimator=es_estimator,
    )
    return tuple(
        _candidate_from_window_index(
            series,
            scores,
            window_index,
            window_observations=window_observations,
            severity_metric=severity_metric,
            confidence_level=confidence_level,
            es_estimator=es_estimator,
        )
        for window_index in range(scores.size)
    )


def select_stress_period_from_history(
    series: HistoricalStressSeries,
    *,
    window_observations: int = 250,
    minimum_observations: int = 250,
    severity_metric: StressSeverityMetric = StressSeverityMetric.EXPECTED_SHORTFALL,
    confidence_level: float,
    es_estimator: ESEstimator,
    tie_break: StressPeriodTieBreak = StressPeriodTieBreak.LATEST_START_DATE,
) -> StressPeriodCandidate:
    """Select the highest-severity stress period from one risk-class history.

    Ties are resolved by the requested start-date rule. The default selects the
    most recent start date; candidate period IDs are deterministic and provide a
    stable tertiary ordering if a caller later supplies duplicate date ranges.
    Parameters
    ----------
    series : HistoricalStressSeries
        Series.
    window_observations : int, optional
        Window observations.
    minimum_observations : int, optional
        Minimum observations.
    severity_metric : StressSeverityMetric, optional
        Severity metric.
    confidence_level : float
        Confidence level.
    es_estimator : ESEstimator
        Es estimator.
    tie_break : StressPeriodTieBreak, optional
        Tie break.

    Returns
    -------
    StressPeriodCandidate
        Result of the operation.
    """
    if not isinstance(series, HistoricalStressSeries):
        raise TypeError("series must be a HistoricalStressSeries")
    scores = rolling_window_severity_scores(
        series.losses,
        window_observations=window_observations,
        minimum_observations=minimum_observations,
        severity_metric=severity_metric,
        confidence_level=confidence_level,
        es_estimator=es_estimator,
    )
    window_index = _select_window_index(scores, tie_break)
    return _candidate_from_window_index(
        series,
        scores,
        window_index,
        window_observations=window_observations,
        severity_metric=severity_metric,
        confidence_level=confidence_level,
        es_estimator=es_estimator,
    )


def _select_window_index(
    scores: npt.NDArray[np.float64],
    tie_break: StressPeriodTieBreak,
) -> int:
    max_score = float(np.max(scores))
    tied = np.flatnonzero(scores == max_score)
    if tie_break == StressPeriodTieBreak.EARLIEST_START_DATE:
        return int(tied[0])
    if tie_break == StressPeriodTieBreak.LATEST_START_DATE:
        return int(tied[-1])
    raise ValueError(f"Unsupported tie-break rule: {tie_break}")


def _candidate_from_window_index(
    series: HistoricalStressSeries,
    scores: npt.NDArray[np.float64],
    window_index: int,
    *,
    window_observations: int,
    severity_metric: StressSeverityMetric,
    confidence_level: float,
    es_estimator: ESEstimator,
) -> StressPeriodCandidate:
    start_index = window_index
    end_index_exclusive = window_index + window_observations
    end_index = end_index_exclusive - 1
    start_date = series.dates[start_index]
    end_date = series.dates[end_index]
    period_id = _stress_period_id(
        series.risk_class,
        start_date,
        end_date,
        severity_metric,
    )
    return StressPeriodCandidate(
        risk_class=series.risk_class,
        period_id=period_id,
        start_date=start_date,
        end_date=end_date,
        start_index=start_index,
        end_index_exclusive=end_index_exclusive,
        observation_count=window_observations,
        severity_score=float(scores[window_index]),
        severity_metric=severity_metric,
        confidence_level=confidence_level,
        es_estimator=es_estimator,
        source=series.source,
        start_scenario_id=series.scenario_ids[start_index],
        end_scenario_id=series.scenario_ids[end_index],
        notes=(
            "Selected from provided historical loss series; "
            "window basis is recorded on the StressPeriodSelectionResult."
        ),
    )


def _stress_period_id(
    risk_class: RiskClass,
    start_date: date,
    end_date: date,
    metric: StressSeverityMetric,
) -> str:
    metric_label = metric.value.lower().replace("_", "-")
    return f"{risk_class.value.lower()}-{start_date:%Y%m%d}-{end_date:%Y%m%d}-{metric_label}"


__all__ = (
    "rolling_window_severity_scores",
    "select_stress_period_from_history",
    "stress_period_candidates_from_history",
)
