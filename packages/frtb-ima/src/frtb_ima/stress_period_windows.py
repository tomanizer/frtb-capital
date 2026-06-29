"""
Rolling-window stress-period scoring.

This module contains the NumPy window-scoring stage for IMA stress-period
calibration. It consumes validated ``HistoricalStressSeries`` records and
returns deterministic ``StressPeriodCandidate`` records without applying
run-level policy dispatch.
"""

from __future__ import annotations

import math
from datetime import date

import numpy as np
import numpy.typing as npt
from numpy.lib.stride_tricks import sliding_window_view

from frtb_ima.data_models import RiskClass
from frtb_ima.expected_shortfall import ESEstimator
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
    uses a strided rolling-window view, partitions out the largest tail losses,
    and computes every window tail mean in one vectorized operation.

    Parameters
    ----------
    losses : FloatVector
        Positive-loss observations sorted by observation date.
    window_observations : int, optional
        Observation count in each rolling window.
    minimum_observations : int, optional
        Minimum observations required before scoring.
    severity_metric : StressSeverityMetric, optional
        Statistic used to score each candidate window.
    confidence_level : float
        ES confidence level sourced from the applicable policy.
    es_estimator : ESEstimator
        Tail-mean estimator used for expected-shortfall scoring.

    Returns
    -------
    npt.NDArray[np.float64]
        Array of shape ``(N - window_observations + 1,)`` with one severity
        score per rolling window start position.
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
        return _expected_shortfall_scores_from_windows(
            windows,
            confidence_level=confidence_level,
            es_estimator=es_estimator,
        )

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
        Validated historical loss series to score.
    window_observations : int, optional
        Observation count in each candidate stress window.
    minimum_observations : int, optional
        Minimum observations required before scoring.
    severity_metric : StressSeverityMetric, optional
        Statistic used to score each candidate window.
    confidence_level : float
        ES confidence level sourced from the applicable policy.
    es_estimator : ESEstimator
        Tail-mean estimator used for expected-shortfall scoring.

    Returns
    -------
    tuple[StressPeriodCandidate, ...]
        Candidate records, one per valid window start, in chronological order.
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
        Validated historical loss series to score.
    window_observations : int, optional
        Observation count in each candidate stress window.
    minimum_observations : int, optional
        Minimum observations required before scoring.
    severity_metric : StressSeverityMetric, optional
        Statistic used to score each candidate window.
    confidence_level : float
        ES confidence level sourced from the applicable policy.
    es_estimator : ESEstimator
        Tail-mean estimator used for expected-shortfall scoring.
    tie_break : StressPeriodTieBreak, optional
        Deterministic rule used when windows have equal severity.

    Returns
    -------
    StressPeriodCandidate
        Highest-severity candidate, ties resolved by ``tie_break``.
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
        risk_factor_set=series.risk_factor_set,
        notes=(
            "Selected from provided historical loss series; "
            "window basis is recorded on the StressPeriodSelectionResult."
        ),
    )


def _expected_shortfall_scores_from_windows(
    windows: npt.NDArray[np.float64],
    *,
    confidence_level: float,
    es_estimator: ESEstimator,
) -> npt.NDArray[np.float64]:
    window_observations = int(windows.shape[1])
    tail_mass = window_observations * (1.0 - confidence_level)
    estimator = ESEstimator(es_estimator)
    if estimator == ESEstimator.DISCRETE_CEIL:
        tail_count = max(1, math.ceil(tail_mass))
        tail_losses = _largest_losses_desc(windows, tail_count)
        scores: npt.NDArray[np.float64] = np.asarray(
            np.mean(tail_losses, axis=1),
            dtype=np.float64,
        )
        return scores

    full_count = math.floor(tail_mass)
    fractional_weight = tail_mass - full_count
    selected_count = full_count + (1 if fractional_weight > 0.0 else 0)
    tail_losses = _largest_losses_desc(windows, max(1, selected_count))
    weighted_sum = (
        np.sum(tail_losses[:, :full_count], axis=1)
        if full_count
        else np.zeros(windows.shape[0], dtype=np.float64)
    )
    if fractional_weight > 0.0:
        weighted_sum = weighted_sum + fractional_weight * tail_losses[:, full_count]
    scores = np.asarray(weighted_sum / tail_mass, dtype=np.float64)
    return scores


def _largest_losses_desc(
    windows: npt.NDArray[np.float64],
    count: int,
) -> npt.NDArray[np.float64]:
    kth = int(windows.shape[1] - count)
    tail = np.partition(windows, kth=kth, axis=1)[:, kth:]
    sorted_tail: npt.NDArray[np.float64] = np.asarray(np.sort(tail, axis=1)[:, ::-1])
    return sorted_tail


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
