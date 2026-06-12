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
        object.__setattr__(self, "selected_by_risk_class", _freeze_mapping(selected))
        object.__setattr__(self, "candidate_counts", _freeze_mapping(counts))
        object.__setattr__(self, "es_estimator", es_estimator)
        object.__setattr__(self, "window_basis", str(self.window_basis))
        object.__setattr__(self, "missing_business_dates", tuple(self.missing_business_dates))
        object.__setattr__(self, "metadata", _freeze_mapping(self.metadata))

    @property
    def risk_class_count(self) -> int:
        """Number of risk classes with selected stress periods.
        Returns
        -------
        int
            Result of the operation.
        """
        return len(self.selected_by_risk_class)

    def as_dict(self) -> dict[str, object]:
        """Return a serialisable dictionary for reporting and audit trails.
        Returns
        -------
        dict[str, object]
            Result of the operation.
        """
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
            "metadata": jsonable(self.metadata),
        }


__all__ = ("StressPeriodSelectionResult",)
