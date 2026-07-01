"""
Stress-period selection result records.

This module contains the run-level stress-period selection result type. It is
kept separate from input/candidate records so the stress-period stages remain
small and reviewable.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import date

from frtb_common.serialization import jsonable

from frtb_ima._mapping_utils import empty_mapping as _empty_mapping
from frtb_ima._mapping_utils import freeze_mapping as _freeze_mapping
from frtb_ima.calendar import ObservationWindowBasis
from frtb_ima.data_models import RiskClass
from frtb_ima.expected_shortfall import ESEstimator
from frtb_ima.stress_period_types import (
    StressPeriodCandidate,
    StressPeriodTieBreak,
    StressSeverityMetric,
    _validate_selection_parameters,
)


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
    series_start_dates: Mapping[RiskClass, date] = field(default_factory=dict)
    risk_factor_sets: Mapping[RiskClass, str] = field(default_factory=dict)
    scenario_set_ids: Mapping[RiskClass, str] = field(default_factory=dict)
    loss_time_series_ids: Mapping[RiskClass, str] = field(default_factory=dict)
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
        start_dates = dict(self.series_start_dates)
        if start_dates:
            if set(start_dates) != set(selected):
                raise ValueError("series_start_dates keys must match selected_by_risk_class")
            for risk_class, start_date in start_dates.items():
                if not isinstance(risk_class, RiskClass):
                    raise TypeError("series_start_dates keys must be RiskClass values")
                if not isinstance(start_date, date):
                    raise TypeError("series_start_dates values must be datetime.date values")
        risk_factor_sets = dict(self.risk_factor_sets)
        if risk_factor_sets:
            if set(risk_factor_sets) != set(selected):
                raise ValueError("risk_factor_sets keys must match selected_by_risk_class")
            for risk_class, risk_factor_set in risk_factor_sets.items():
                if not isinstance(risk_class, RiskClass):
                    raise TypeError("risk_factor_sets keys must be RiskClass values")
                if risk_factor_set not in {"FULL", "REDUCED"}:
                    raise ValueError("risk_factor_sets values must be 'FULL' or 'REDUCED'")
        scenario_set_ids = dict(self.scenario_set_ids)
        if scenario_set_ids:
            if set(scenario_set_ids) != set(selected):
                raise ValueError("scenario_set_ids keys must match selected_by_risk_class")
            for risk_class, scenario_set_id in scenario_set_ids.items():
                if not isinstance(risk_class, RiskClass):
                    raise TypeError("scenario_set_ids keys must be RiskClass values")
                if not scenario_set_id:
                    raise ValueError("scenario_set_ids values must be non-empty")
        loss_time_series_ids = dict(self.loss_time_series_ids)
        if loss_time_series_ids:
            if set(loss_time_series_ids) != set(selected):
                raise ValueError("loss_time_series_ids keys must match selected_by_risk_class")
            for risk_class, time_series_id in loss_time_series_ids.items():
                if not isinstance(risk_class, RiskClass):
                    raise TypeError("loss_time_series_ids keys must be RiskClass values")
                if not time_series_id:
                    raise ValueError("loss_time_series_ids values must be non-empty")
        object.__setattr__(self, "selected_by_risk_class", _freeze_mapping(selected))
        object.__setattr__(self, "candidate_counts", _freeze_mapping(counts))
        object.__setattr__(self, "es_estimator", es_estimator)
        object.__setattr__(self, "window_basis", str(self.window_basis))
        object.__setattr__(self, "missing_business_dates", tuple(self.missing_business_dates))
        object.__setattr__(self, "series_start_dates", _freeze_mapping(start_dates))
        object.__setattr__(self, "risk_factor_sets", _freeze_mapping(risk_factor_sets))
        object.__setattr__(self, "scenario_set_ids", _freeze_mapping(scenario_set_ids))
        object.__setattr__(self, "loss_time_series_ids", _freeze_mapping(loss_time_series_ids))
        object.__setattr__(self, "metadata", _freeze_mapping(self.metadata))

    @property
    def risk_class_count(self) -> int:
        """Number of risk classes with selected stress periods.

        Returns
        -------
        int
            Count of risk classes represented in ``selected_by_risk_class``.
        """
        return len(self.selected_by_risk_class)

    def as_dict(self) -> dict[str, object]:
        """Return a serialisable dictionary for reporting and audit trails.

        Returns
        -------
        dict[str, object]
            Serialisable dictionary with selection parameters, per-risk-class
            selected windows, candidate counts, and series coverage evidence.
        """
        selected = {
            risk_class.value: self.selected_by_risk_class[risk_class].as_dict()
            for risk_class in sorted(self.selected_by_risk_class, key=lambda item: item.value)
        }
        counts = {
            risk_class.value: self.candidate_counts[risk_class]
            for risk_class in sorted(self.candidate_counts, key=lambda item: item.value)
        }
        series_start_dates = {
            risk_class.value: self.series_start_dates[risk_class].isoformat()
            for risk_class in sorted(self.series_start_dates, key=lambda item: item.value)
        }
        risk_factor_sets = {
            risk_class.value: self.risk_factor_sets[risk_class]
            for risk_class in sorted(self.risk_factor_sets, key=lambda item: item.value)
        }
        scenario_set_ids = {
            risk_class.value: self.scenario_set_ids[risk_class]
            for risk_class in sorted(self.scenario_set_ids, key=lambda item: item.value)
        }
        loss_time_series_ids = {
            risk_class.value: self.loss_time_series_ids[risk_class]
            for risk_class in sorted(self.loss_time_series_ids, key=lambda item: item.value)
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
            "series_start_dates": series_start_dates,
            "risk_factor_sets": risk_factor_sets,
            "scenario_set_ids": scenario_set_ids,
            "loss_time_series_ids": loss_time_series_ids,
            "metadata": jsonable(self.metadata),
        }


__all__ = ("StressPeriodSelectionResult",)
