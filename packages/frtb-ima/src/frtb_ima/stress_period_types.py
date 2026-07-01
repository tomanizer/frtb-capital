"""
Stress-period input and result records.

This module owns the immutable record types and shared validation helpers for
IMA stress-period calibration. It does not score rolling windows or select
policy-level stress periods; those physical stages live in
``stress_period_windows`` and ``stress_period_selection``.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from enum import StrEnum
from typing import Literal, cast

import numpy as np
import numpy.typing as npt
from frtb_common import CalculationScope

from frtb_ima.data_models import RiskClass
from frtb_ima.expected_shortfall import ESEstimator
from frtb_ima.nmrf_stress_spec import NMRFStressPeriodSpec
from frtb_ima.org_scope import add_scope_payload, validate_scope_metadata
from frtb_ima.validation.observation_windows import (
    require_positive_observation_count as _require_positive_observation_count,
)
from frtb_ima.validation.observation_windows import (
    require_window_minimum_pair as _require_window_minimum_pair,
)

FloatVector = Sequence[float] | npt.NDArray[np.float64]
StressRiskFactorSet = Literal["FULL", "REDUCED"]

# Basel MAR33.5 / U.S. NPR 2.0 proposed section __.214 require the stressed ES
# observation horizon to include the financial stress period starting 2007-01-01.
REGULATORY_OBSERVATION_HORIZON_START = date(2007, 1, 1)


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
    risk_factor_set: StressRiskFactorSet = "FULL"
    minimum_start_date: date | None = None
    org_scope: CalculationScope | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.risk_class, RiskClass):
            raise TypeError("risk_class must be a RiskClass")
        losses = _as_finite_loss_array(self.losses, "losses")
        dates = _as_strictly_increasing_dates(self.dates)
        if len(dates) != losses.size:
            raise ValueError("dates length must match losses length")
        if not self.source:
            raise ValueError("source must be non-empty")
        risk_factor_set = _validated_risk_factor_set(self.risk_factor_set)
        minimum_start_date = _validated_minimum_start_date(self.minimum_start_date)
        if minimum_start_date is not None and dates[0] > minimum_start_date:
            raise StressPeriodCalibrationError(
                f"HistoricalStressSeries for {self.risk_class.value} starts on "
                f"{dates[0].isoformat()}, which is after the required minimum "
                f"observation horizon of {minimum_start_date.isoformat()} "
                "(Basel MAR33.5 / NPR section __.214)"
            )
        scenario_ids = _validated_scenario_ids(
            self.scenario_ids,
            expected_length=losses.size,
            risk_class=self.risk_class,
            dates=dates,
        )
        object.__setattr__(self, "losses", losses)
        object.__setattr__(self, "dates", dates)
        object.__setattr__(self, "scenario_ids", scenario_ids)
        object.__setattr__(self, "risk_factor_set", risk_factor_set)
        object.__setattr__(self, "minimum_start_date", minimum_start_date)
        object.__setattr__(
            self,
            "org_scope",
            validate_scope_metadata(self.org_scope, field="HistoricalStressSeries.org_scope"),
        )

    @property
    def observation_count(self) -> int:
        """Number of aligned historical observations.

        Returns
        -------
        int
            Count of loss observations aligned to this series' date vector.
        """
        return len(self.dates)

    @property
    def start_date(self) -> date:
        """First observation date.

        Returns
        -------
        date
            Earliest date included in the supplied historical loss series.
        """
        return self.dates[0]

    @property
    def end_date(self) -> date:
        """Last observation date.

        Returns
        -------
        date
            Latest date included in the supplied historical loss series.
        """
        return self.dates[-1]

    def as_dict(self) -> dict[str, object]:
        """Return an audit summary without serialising the loss vector.

        Returns
        -------
        dict[str, object]
            Audit summary with risk class, source, provenance, observation
            count, and date range.
        """
        return add_scope_payload(
            {
                "risk_class": self.risk_class.value,
                "name": self.name,
                "source": self.source,
                "risk_factor_set": self.risk_factor_set,
                "observation_count": self.observation_count,
                "start_date": self.start_date.isoformat(),
                "end_date": self.end_date.isoformat(),
                "minimum_start_date": (
                    None if self.minimum_start_date is None else self.minimum_start_date.isoformat()
                ),
            },
            self.org_scope,
        )


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
    risk_factor_set: StressRiskFactorSet = "FULL"
    org_scope: CalculationScope | None = None

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
        risk_factor_set = _validated_risk_factor_set(self.risk_factor_set)
        object.__setattr__(self, "es_estimator", es_estimator)
        object.__setattr__(self, "risk_factor_set", risk_factor_set)
        object.__setattr__(
            self,
            "org_scope",
            validate_scope_metadata(self.org_scope, field="StressPeriodCandidate.org_scope"),
        )

    def as_dict(self) -> dict[str, object]:
        """Return a serialisable dictionary for reporting and audit trails.

        Returns
        -------
        dict[str, object]
            Candidate stress-window attributes, severity score, scenario ids,
            and risk-factor-set provenance.
        """
        return add_scope_payload(
            {
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
                "risk_factor_set": self.risk_factor_set,
                "notes": self.notes,
            },
            self.org_scope,
        )

    def to_nmrf_stress_period_spec(self) -> NMRFStressPeriodSpec:
        """Convert this selected window into an NMRF valuation stress-period spec.

        Returns
        -------
        NMRFStressPeriodSpec
            Stress-period spec preserving the selected period id, source, and
            start/end dates for downstream NMRF valuation requests.
        """
        return NMRFStressPeriodSpec(
            stress_period_id=self.period_id,
            calibration_source=self.source,
            start_date=self.start_date,
            end_date=self.end_date,
            notes=self.notes,
            org_scope=self.org_scope,
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
    _require_positive_observation_count(
        window_observations,
        field="window_observations",
        include_value=False,
    )
    _require_positive_observation_count(
        minimum_observations,
        field="minimum_observations",
        include_value=False,
    )
    _require_window_minimum_pair(
        window_value=window_observations,
        minimum_value=minimum_observations,
        window_field="window_observations",
        minimum_field="minimum_observations",
    )
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


def _validated_risk_factor_set(value: str) -> StressRiskFactorSet:
    if not isinstance(value, str):
        raise TypeError("risk_factor_set must be 'FULL' or 'REDUCED'")
    if value not in {"FULL", "REDUCED"}:
        raise ValueError("risk_factor_set must be 'FULL' or 'REDUCED'")
    return cast(StressRiskFactorSet, value)


def _validated_minimum_start_date(value: date | None) -> date | None:
    if value is not None and not isinstance(value, date):
        raise TypeError("minimum_start_date must be a datetime.date or None")
    return value


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


__all__ = (
    "REGULATORY_OBSERVATION_HORIZON_START",
    "FloatVector",
    "HistoricalStressSeries",
    "StressPeriodCalibrationError",
    "StressPeriodCandidate",
    "StressPeriodTieBreak",
    "StressRiskFactorSet",
    "StressSeverityMetric",
)
