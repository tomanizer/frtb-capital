"""
Stress-period calibration from provided historical loss series.

This module selects common stress windows by risk class before valuation runs.
It consumes historical scenario loss/severity vectors supplied by upstream
market-data and risk-engine processes; it does not download market data, build
shocks, price trades, or approve regulatory calibration.
The selection result is a cross-cutting governance input: it directly supplies
NMRF valuation stress-period specs and can inform upstream IMCC stressed-ES
scenario preparation, while ``imcc.py`` itself still consumes numeric ES inputs.
Window length is observation-count based by default. Callers may also supply a
BusinessCalendar so the selection result records an exact 12-month
business-calendar interpretation.

Sign convention: input historical values are positive = loss.

Regulatory traceability:
    Basel MAR33 stress-period and NMRF stress-scenario concepts; U.S. NPR 2.0
    proposed-rule stressed ES / SES calibration basis; EU CRR
    Article 325bc and 325bk comparison concepts. See
    docs/REGULATORY_TRACEABILITY.md.
"""

from __future__ import annotations

import logging
import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date
from enum import StrEnum
from types import MappingProxyType

import numpy as np
import numpy.typing as npt
from numpy.lib.stride_tricks import sliding_window_view

from frtb_ima.audit import _jsonable
from frtb_ima.calendar import BusinessCalendar, ObservationWindowBasis
from frtb_ima.data_models import RiskClass
from frtb_ima.expected_shortfall import ESEstimator, expected_shortfall_from_sorted_losses_desc
from frtb_ima.logging import calculation_log_extra
from frtb_ima.nmrf_stress_spec import NMRFStressPeriodSpec
from frtb_ima.regimes import RegulatoryPolicy, RegulatoryRegime

FloatVector = Sequence[float] | npt.NDArray[np.float64]
logger = logging.getLogger(__name__)


class StressPeriodCalibrationError(ValueError):
    """Raised when a stress-period calibration input or result is invalid."""


class StressSeverityMetric(StrEnum):
    """Window-severity statistic used to select the stress period."""

    EXPECTED_SHORTFALL = "EXPECTED_SHORTFALL"
    MAX_LOSS = "MAX_LOSS"
    CUMULATIVE_LOSS = "CUMULATIVE_LOSS"


class StressPeriodTieBreak(StrEnum):
    """Deterministic tie-break rule when multiple windows have equal severity."""

    LATEST_START_DATE = "LATEST_START_DATE"
    EARLIEST_START_DATE = "EARLIEST_START_DATE"


@dataclass(frozen=True)
class HistoricalStressSeries:
    """
    Historical risk-class loss series used for stress-period selection.

    Losses must be aligned one-to-one with strictly increasing dates.
    """

    risk_class: RiskClass
    losses: FloatVector
    dates: Sequence[date]
    source: str
    scenario_ids: Sequence[str] = ()
    name: str = ""

    def __post_init__(self) -> None:
        if not isinstance(self.risk_class, RiskClass):
            raise TypeError("risk_class must be a RiskClass")
        losses = _as_finite_loss_array(self.losses, "losses")
        dates = _as_strictly_increasing_dates(self.dates)
        if len(dates) != losses.size:
            raise ValueError("dates length must match losses length")
        if not self.source:
            raise ValueError("source must be non-empty")
        scenario_ids = _validated_scenario_ids(
            self.scenario_ids,
            expected_length=losses.size,
            risk_class=self.risk_class,
            dates=dates,
        )
        object.__setattr__(self, "losses", losses)
        object.__setattr__(self, "dates", dates)
        object.__setattr__(self, "scenario_ids", scenario_ids)

    @property
    def observation_count(self) -> int:
        """Number of aligned historical observations."""
        return len(self.dates)

    @property
    def start_date(self) -> date:
        """First observation date."""
        return self.dates[0]

    @property
    def end_date(self) -> date:
        """Last observation date."""
        return self.dates[-1]

    def as_dict(self) -> dict[str, object]:
        """Return an audit summary without serialising the loss vector."""
        return {
            "risk_class": self.risk_class.value,
            "name": self.name,
            "source": self.source,
            "observation_count": self.observation_count,
            "start_date": self.start_date.isoformat(),
            "end_date": self.end_date.isoformat(),
        }


@dataclass(frozen=True)
class StressPeriodCandidate:
    """
    One candidate stress window and its derived severity score.

    ``severity_score`` follows the positive-loss convention. Its scale is the
    selected metric: ES tail mean, maximum loss, or cumulative window loss.
    """

    risk_class: RiskClass
    period_id: str
    start_date: date
    end_date: date
    start_index: int
    end_index_exclusive: int
    observation_count: int
    severity_score: float
    severity_metric: StressSeverityMetric
    confidence_level: float
    es_estimator: ESEstimator
    source: str
    start_scenario_id: str
    end_scenario_id: str
    notes: str = ""

    def __post_init__(self) -> None:
        if not isinstance(self.risk_class, RiskClass):
            raise TypeError("risk_class must be a RiskClass")
        if not self.period_id:
            raise ValueError("period_id must be non-empty")
        if self.start_date > self.end_date:
            raise ValueError("start_date cannot be after end_date")
        if self.start_index < 0:
            raise ValueError("start_index must be non-negative")
        if self.end_index_exclusive <= self.start_index:
            raise ValueError("end_index_exclusive must be greater than start_index")
        if self.observation_count <= 0:
            raise ValueError("observation_count must be positive")
        if self.observation_count != self.end_index_exclusive - self.start_index:
            raise ValueError("observation_count must match index span")
        if not math.isfinite(self.severity_score):
            raise ValueError("severity_score must be finite")
        if not isinstance(self.severity_metric, StressSeverityMetric):
            raise TypeError("severity_metric must be a StressSeverityMetric")
        if not (0.0 < self.confidence_level < 1.0):
            raise ValueError("confidence_level must be in (0, 1)")
        es_estimator = ESEstimator(self.es_estimator)
        if not self.source:
            raise ValueError("source must be non-empty")
        if not self.start_scenario_id or not self.end_scenario_id:
            raise ValueError("start_scenario_id and end_scenario_id must be non-empty")
        object.__setattr__(self, "es_estimator", es_estimator)

    def as_dict(self) -> dict[str, object]:
        """Return a serialisable dictionary for reporting and audit trails."""
        return {
            "risk_class": self.risk_class.value,
            "period_id": self.period_id,
            "start_date": self.start_date.isoformat(),
            "end_date": self.end_date.isoformat(),
            "start_index": self.start_index,
            "end_index_exclusive": self.end_index_exclusive,
            "observation_count": self.observation_count,
            "severity_score": self.severity_score,
            "severity_metric": self.severity_metric.value,
            "confidence_level": self.confidence_level,
            "es_estimator": self.es_estimator.value,
            "source": self.source,
            "start_scenario_id": self.start_scenario_id,
            "end_scenario_id": self.end_scenario_id,
            "notes": self.notes,
        }

    def to_nmrf_stress_period_spec(self) -> NMRFStressPeriodSpec:
        """Convert this selected window into an NMRF valuation stress-period spec."""
        return NMRFStressPeriodSpec(
            stress_period_id=self.period_id,
            calibration_source=self.source,
            start_date=self.start_date,
            end_date=self.end_date,
            notes=self.notes,
        )


def _empty_mapping() -> Mapping[str, object]:
    return MappingProxyType({})


@dataclass(frozen=True)
class StressPeriodSelectionResult:
    """Selected stress periods for a run-level calibration pass."""

    as_of_date: date
    regime: str
    window_observations: int
    minimum_observations: int
    severity_metric: StressSeverityMetric
    confidence_level: float
    es_estimator: ESEstimator
    tie_break: StressPeriodTieBreak
    selected_by_risk_class: Mapping[RiskClass, StressPeriodCandidate]
    candidate_counts: Mapping[RiskClass, int]
    window_basis: str = ObservationWindowBasis.OBSERVATION_COUNT_PROXY.value
    calendar_source: str = ""
    calendar_version: str = ""
    official_holiday_count: int = 0
    missing_business_dates: tuple[date, ...] = ()
    metadata: Mapping[str, object] = field(default_factory=_empty_mapping)

    def __post_init__(self) -> None:
        if not isinstance(self.as_of_date, date):
            raise TypeError("as_of_date must be a datetime.date")
        if not self.regime:
            raise ValueError("regime must be non-empty")
        _validate_selection_parameters(
            window_observations=self.window_observations,
            minimum_observations=self.minimum_observations,
            severity_metric=self.severity_metric,
            confidence_level=self.confidence_level,
            es_estimator=self.es_estimator,
            tie_break=self.tie_break,
        )
        es_estimator = ESEstimator(self.es_estimator)
        selected = dict(self.selected_by_risk_class)
        counts = dict(self.candidate_counts)
        if not selected:
            raise ValueError("selected_by_risk_class must be non-empty")
        if set(selected) != set(counts):
            raise ValueError("candidate_counts keys must match selected_by_risk_class")
        for risk_class, candidate in selected.items():
            if not isinstance(risk_class, RiskClass):
                raise TypeError("selected_by_risk_class keys must be RiskClass values")
            if candidate.risk_class != risk_class:
                raise ValueError("candidate risk_class must match mapping key")
            count = counts[risk_class]
            if count <= 0:
                raise ValueError("candidate_counts values must be positive")
        object.__setattr__(self, "selected_by_risk_class", MappingProxyType(selected))
        object.__setattr__(self, "candidate_counts", MappingProxyType(counts))
        object.__setattr__(self, "es_estimator", es_estimator)
        object.__setattr__(self, "window_basis", str(self.window_basis))
        object.__setattr__(self, "missing_business_dates", tuple(self.missing_business_dates))
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))

    @property
    def risk_class_count(self) -> int:
        """Number of risk classes with selected stress periods."""
        return len(self.selected_by_risk_class)

    def as_dict(self) -> dict[str, object]:
        """Return a serialisable dictionary for reporting and audit trails."""
        selected = {
            risk_class.value: self.selected_by_risk_class[risk_class].as_dict()
            for risk_class in sorted(self.selected_by_risk_class, key=lambda item: item.value)
        }
        counts = {
            risk_class.value: self.candidate_counts[risk_class]
            for risk_class in sorted(self.candidate_counts, key=lambda item: item.value)
        }
        return {
            "as_of_date": self.as_of_date.isoformat(),
            "regime": self.regime,
            "selection_parameters": {
                "window_observations": self.window_observations,
                "minimum_observations": self.minimum_observations,
                "severity_metric": self.severity_metric.value,
                "confidence_level": self.confidence_level,
                "es_estimator": self.es_estimator.value,
                "tie_break": self.tie_break.value,
                "window_basis": self.window_basis,
                "calendar_source": self.calendar_source,
                "calendar_version": self.calendar_version,
                "official_holiday_count": self.official_holiday_count,
                "missing_business_dates": [
                    item.isoformat() for item in self.missing_business_dates
                ],
            },
            "risk_class_count": self.risk_class_count,
            "selected_by_risk_class": selected,
            "candidate_counts": counts,
            "metadata": _jsonable(self.metadata),
        }


def rolling_window_severity_scores(
    losses: FloatVector,
    *,
    window_observations: int = 250,
    minimum_observations: int = 250,
    severity_metric: StressSeverityMetric = StressSeverityMetric.EXPECTED_SHORTFALL,
    confidence_level: float,
    es_estimator: ESEstimator,
) -> npt.NDArray[np.float64]:
    """
    Return one severity score per rolling window.

    ``severity_score`` is derived from the supplied positive-loss history using
    the selected metric. ``EXPECTED_SHORTFALL`` returns the empirical mean of
    the largest tail losses in each window, ``MAX_LOSS`` returns the single
    largest loss, and ``CUMULATIVE_LOSS`` returns the sum of losses.

    The numeric path is NumPy-native. ``CUMULATIVE_LOSS`` uses prefix sums, which
    is the add-one/remove-one rolling-window optimisation. ``EXPECTED_SHORTFALL``
    uses a strided rolling-window view plus ``np.partition`` to avoid full
    sorting of each window.
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
    """Build all candidate stress windows for audit or diagnostics."""
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
    """
    Select the highest-severity stress period from one risk-class history.

    Ties are resolved by the requested start-date rule. The default selects the
    most recent start date; candidate period IDs are deterministic and provide a
    stable tertiary ordering if a caller later supplies duplicate date ranges.
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


def select_stress_periods_by_risk_class(
    histories: Sequence[HistoricalStressSeries],
    *,
    as_of_date: date,
    window_observations: int = 250,
    minimum_observations: int = 250,
    severity_metric: StressSeverityMetric = StressSeverityMetric.EXPECTED_SHORTFALL,
    confidence_level: float,
    es_estimator: ESEstimator,
    tie_break: StressPeriodTieBreak = StressPeriodTieBreak.LATEST_START_DATE,
    regime: RegulatoryRegime | str = RegulatoryRegime.FED_NPR_2_0,
    calendar: BusinessCalendar | None = None,
    use_exact_twelve_month_window: bool = False,
    metadata: Mapping[str, object] | None = None,
) -> StressPeriodSelectionResult:
    """Select one common stress period per risk class from supplied histories."""
    if not histories:
        raise ValueError("histories must be non-empty")
    if not isinstance(as_of_date, date):
        raise TypeError("as_of_date must be a datetime.date")
    _validate_selection_parameters(
        window_observations=window_observations,
        minimum_observations=minimum_observations,
        severity_metric=severity_metric,
        confidence_level=confidence_level,
        es_estimator=es_estimator,
        tie_break=tie_break,
    )

    window_basis = ObservationWindowBasis.OBSERVATION_COUNT_PROXY.value
    calendar_source = ""
    calendar_version = ""
    official_holiday_count = 0
    missing_business_dates: tuple[date, ...] = ()
    if use_exact_twelve_month_window:
        if calendar is None:
            raise ValueError("calendar is required for exact 12-month stress-period windows")
        calendar_window = calendar.exact_twelve_month_window(as_of_date)
        window_observations = calendar_window.business_day_count
        minimum_observations = calendar_window.business_day_count
        window_basis = calendar_window.basis.value
        calendar_source = calendar_window.calendar_source
        calendar_version = calendar_window.calendar_version
        official_holiday_count = calendar_window.official_holiday_count
        missing_business_dates = calendar_window.missing_business_dates

    selected: dict[RiskClass, StressPeriodCandidate] = {}
    counts: dict[RiskClass, int] = {}
    for series in histories:
        if not isinstance(series, HistoricalStressSeries):
            raise TypeError("histories must contain HistoricalStressSeries values")
        if series.risk_class in selected:
            raise ValueError(f"duplicate history for risk class {series.risk_class.value}")
        selected[series.risk_class] = select_stress_period_from_history(
            series,
            window_observations=window_observations,
            minimum_observations=minimum_observations,
            severity_metric=severity_metric,
            confidence_level=confidence_level,
            es_estimator=es_estimator,
            tie_break=tie_break,
        )
        counts[series.risk_class] = series.observation_count - window_observations + 1

    regime_value = regime.value if isinstance(regime, RegulatoryRegime) else str(regime)
    return StressPeriodSelectionResult(
        as_of_date=as_of_date,
        regime=regime_value,
        window_observations=window_observations,
        minimum_observations=minimum_observations,
        severity_metric=severity_metric,
        confidence_level=confidence_level,
        es_estimator=es_estimator,
        tie_break=tie_break,
        selected_by_risk_class=selected,
        candidate_counts=counts,
        window_basis=window_basis,
        calendar_source=calendar_source,
        calendar_version=calendar_version,
        official_holiday_count=official_holiday_count,
        missing_business_dates=missing_business_dates,
        metadata={} if metadata is None else metadata,
    )


def select_stress_periods_for_policy(
    histories: Sequence[HistoricalStressSeries],
    policy: RegulatoryPolicy,
    *,
    as_of_date: date,
    severity_metric: StressSeverityMetric = StressSeverityMetric.EXPECTED_SHORTFALL,
    tie_break: StressPeriodTieBreak = StressPeriodTieBreak.LATEST_START_DATE,
    calendar: BusinessCalendar | None = None,
    use_exact_twelve_month_window: bool = False,
    run_id: str | None = None,
    desk_id: str | None = None,
    metadata: Mapping[str, object] | None = None,
) -> StressPeriodSelectionResult:
    """Select stress periods using the run-level policy confidence level."""
    if not isinstance(policy, RegulatoryPolicy):
        raise TypeError("policy must be a RegulatoryPolicy")
    result = select_stress_periods_by_risk_class(
        histories,
        as_of_date=as_of_date,
        window_observations=policy.stress_period_window_observations,
        minimum_observations=policy.stress_period_minimum_observations,
        severity_metric=severity_metric,
        confidence_level=policy.es_confidence_level,
        es_estimator=policy.es_estimator,
        tie_break=tie_break,
        regime=policy.regime,
        calendar=calendar,
        use_exact_twelve_month_window=use_exact_twelve_month_window,
        metadata=metadata,
    )
    logger.info(
        "stress_period_selection_complete",
        extra=calculation_log_extra(
            run_id=run_id,
            desk_id=desk_id,
            regime=policy.regime.value,
            risk_class_count=result.risk_class_count,
            window_observations=result.window_observations,
            severity_metric=result.severity_metric.value,
        ),
    )
    return result


def stress_period_specs_for_nmrf(
    selection_result: StressPeriodSelectionResult,
) -> dict[RiskClass, NMRFStressPeriodSpec]:
    """Return NMRF valuation stress-period specs keyed by risk class."""
    if not isinstance(selection_result, StressPeriodSelectionResult):
        raise TypeError("selection_result must be a StressPeriodSelectionResult")
    return {
        risk_class: selection_result.selected_by_risk_class[risk_class].to_nmrf_stress_period_spec()
        for risk_class in sorted(
            selection_result.selected_by_risk_class,
            key=lambda item: item.value,
        )
    }


def validate_selected_stress_periods(
    selection_result: StressPeriodSelectionResult,
    required_risk_classes: Sequence[RiskClass],
) -> None:
    """Validate that all required risk classes have selected stress periods."""
    if not isinstance(selection_result, StressPeriodSelectionResult):
        raise TypeError("selection_result must be a StressPeriodSelectionResult")
    required = tuple(required_risk_classes)
    if not required:
        raise ValueError("required_risk_classes must be non-empty")
    if any(not isinstance(risk_class, RiskClass) for risk_class in required):
        raise TypeError("required_risk_classes must contain only RiskClass values")
    missing = sorted(
        set(required) - set(selection_result.selected_by_risk_class),
        key=lambda item: item.value,
    )
    if missing:
        labels = ", ".join(risk_class.value for risk_class in missing)
        raise StressPeriodCalibrationError(
            f"missing selected stress period for risk classes: {labels}"
        )


def _validate_selection_parameters(
    *,
    window_observations: int,
    minimum_observations: int,
    severity_metric: StressSeverityMetric,
    confidence_level: float,
    es_estimator: ESEstimator,
    tie_break: StressPeriodTieBreak | None = None,
) -> None:
    if window_observations <= 0:
        raise ValueError("window_observations must be positive")
    if minimum_observations <= 0:
        raise ValueError("minimum_observations must be positive")
    if minimum_observations < window_observations:
        raise ValueError("minimum_observations cannot be less than window_observations")
    if not isinstance(severity_metric, StressSeverityMetric):
        raise TypeError("severity_metric must be a StressSeverityMetric")
    if not (0.0 < confidence_level < 1.0):
        raise ValueError("confidence_level must be in (0, 1)")
    ESEstimator(es_estimator)
    if tie_break is not None and not isinstance(tie_break, StressPeriodTieBreak):
        raise TypeError("tie_break must be a StressPeriodTieBreak")


def _as_finite_loss_array(
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
    copied = arr.astype(np.float64, copy=True)
    copied.flags.writeable = False
    return copied


def _as_strictly_increasing_dates(values: Sequence[date]) -> tuple[date, ...]:
    dates = tuple(values)
    if not dates:
        raise ValueError("dates must be non-empty")
    if any(not isinstance(item, date) for item in dates):
        raise TypeError("dates must contain only datetime.date values")
    ordinals = np.fromiter((item.toordinal() for item in dates), dtype=np.int64)
    if np.any(np.diff(ordinals) <= 0):
        raise ValueError("dates must be strictly increasing with no duplicates")
    return dates


def _validated_scenario_ids(
    values: Sequence[str],
    *,
    expected_length: int,
    risk_class: RiskClass,
    dates: Sequence[date],
) -> tuple[str, ...]:
    if not values:
        prefix = risk_class.value.lower()
        return tuple(f"{prefix}-{item.isoformat()}" for item in dates)

    scenario_ids = tuple(values)
    if len(scenario_ids) != expected_length:
        raise ValueError("scenario_ids length must match losses length")
    if any(not isinstance(item, str) for item in scenario_ids):
        raise TypeError("scenario_ids must contain only strings")
    if any(not item for item in scenario_ids):
        raise ValueError("scenario_ids cannot contain empty values")
    if len(scenario_ids) != len(set(scenario_ids)):
        raise ValueError("scenario_ids contains duplicates")
    return scenario_ids


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
