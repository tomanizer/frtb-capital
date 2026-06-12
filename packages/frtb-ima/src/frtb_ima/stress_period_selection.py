"""
Policy-level stress-period selection and NMRF bridge.

This module applies IMA run policy, optional exact business-calendar windows,
and NMRF stress-period-spec conversion to the lower-level rolling-window
candidate scoring stage.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping, Sequence
from datetime import date

from frtb_ima.calendar import BusinessCalendar, ObservationWindowBasis
from frtb_ima.data_models import RiskClass
from frtb_ima.expected_shortfall import ESEstimator
from frtb_ima.logging import calculation_log_extra
from frtb_ima.nmrf_stress_spec import NMRFStressPeriodSpec
from frtb_ima.regimes import RegulatoryPolicy, RegulatoryRegime
from frtb_ima.stress_period_results import StressPeriodSelectionResult
from frtb_ima.stress_period_types import (
    HistoricalStressSeries,
    StressPeriodCalibrationError,
    StressPeriodCandidate,
    StressPeriodTieBreak,
    StressSeverityMetric,
    _validate_selection_parameters,
)
from frtb_ima.stress_period_windows import select_stress_period_from_history

logger = logging.getLogger(__name__)


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
    """Select one common stress period per risk class.

    Parameters
    ----------
    histories : Sequence[HistoricalStressSeries]
        One validated loss history for each risk class.
    as_of_date : date
        Run calibration date.
    calendar : BusinessCalendar | None, optional
        Required only when exact twelve-month business windows are requested.

    Returns
    -------
    StressPeriodSelectionResult
        Selected windows, candidate counts, and window-basis metadata.
    """
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

    (
        window_observations,
        minimum_observations,
        window_basis,
        calendar_source,
        calendar_version,
        official_holiday_count,
        missing_business_dates,
    ) = _resolve_selection_window(
        as_of_date=as_of_date,
        window_observations=window_observations,
        minimum_observations=minimum_observations,
        calendar=calendar,
        use_exact_twelve_month_window=use_exact_twelve_month_window,
    )
    selected, counts = _select_histories_by_risk_class(
        histories,
        window_observations=window_observations,
        minimum_observations=minimum_observations,
        severity_metric=severity_metric,
        confidence_level=confidence_level,
        es_estimator=es_estimator,
        tie_break=tie_break,
    )

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


def _resolve_selection_window(
    *,
    as_of_date: date,
    window_observations: int,
    minimum_observations: int,
    calendar: BusinessCalendar | None,
    use_exact_twelve_month_window: bool,
) -> tuple[int, int, str, str, str, int, tuple[date, ...]]:
    if not use_exact_twelve_month_window:
        return (
            window_observations,
            minimum_observations,
            ObservationWindowBasis.OBSERVATION_COUNT_PROXY.value,
            "",
            "",
            0,
            (),
        )
    if calendar is None:
        raise ValueError("calendar is required for exact 12-month stress-period windows")
    calendar_window = calendar.exact_twelve_month_window(as_of_date)
    return (
        calendar_window.business_day_count,
        calendar_window.business_day_count,
        calendar_window.basis.value,
        calendar_window.calendar_source,
        calendar_window.calendar_version,
        calendar_window.official_holiday_count,
        calendar_window.missing_business_dates,
    )


def _select_histories_by_risk_class(
    histories: Sequence[HistoricalStressSeries],
    *,
    window_observations: int,
    minimum_observations: int,
    severity_metric: StressSeverityMetric,
    confidence_level: float,
    es_estimator: ESEstimator,
    tie_break: StressPeriodTieBreak,
) -> tuple[dict[RiskClass, StressPeriodCandidate], dict[RiskClass, int]]:
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
    return selected, counts


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
    """Select stress periods using the run-level policy confidence level.
    Parameters
    ----------
    histories : Sequence[HistoricalStressSeries]
        Histories.
    policy : RegulatoryPolicy
        Policy.
    as_of_date : date
        As of date.
    severity_metric : StressSeverityMetric, optional
        Severity metric.
    tie_break : StressPeriodTieBreak, optional
        Tie break.
    calendar : BusinessCalendar | None, optional
        Calendar.
    use_exact_twelve_month_window : bool, optional
        Use exact twelve month window.
    run_id : str | None, optional
        Run id.
    desk_id : str | None, optional
        Desk id.
    metadata : Mapping[str, object] | None, optional
        Metadata.

    Returns
    -------
    StressPeriodSelectionResult
        Result of the operation.
    """
    if not isinstance(policy, RegulatoryPolicy):
        raise TypeError("policy must be a RegulatoryPolicy")
    policy.require_capital_runtime_supported()
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
    """Return NMRF valuation stress-period specs keyed by risk class.
    Parameters
    ----------
    selection_result : StressPeriodSelectionResult
        Selection result.

    Returns
    -------
    dict[RiskClass, NMRFStressPeriodSpec]
        Result of the operation.
    """
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
    """Validate that all required risk classes have selected stress periods.
    Parameters
    ----------
    selection_result : StressPeriodSelectionResult
        Selection result.
    required_risk_classes : Sequence[RiskClass]
        Required risk classes.
    """
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


__all__ = (
    "select_stress_periods_by_risk_class",
    "select_stress_periods_for_policy",
    "stress_period_specs_for_nmrf",
    "validate_selected_stress_periods",
)
