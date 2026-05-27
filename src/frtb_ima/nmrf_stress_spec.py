"""
NMRF valuation-run specifications.

This module converts post-RFET NMRF method instructions into concrete
requirements for an upstream valuation or pricing engine. It does not generate
stress losses, select market data, or price instruments.

Regulatory traceability:
    Basel MAR33 NMRF stress-scenario capital; U.S. NPR 2.0 SES working
    assumptions for Type A / Type B NMRFs; EU CRR Article 325bk stress scenario
    risk measure. Specifications here are prototype run contracts for upstream
    valuation artifacts, not regulatory calibration approval.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from enum import StrEnum
from typing import ClassVar

import numpy as np
import numpy.typing as npt

from frtb_ima.data_models import LiquidityHorizon, ModellabilityStatus, RiskClass
from frtb_ima.nmrf import NMRFStressMethod
from frtb_ima.nmrf_method_selection import NMRFValuationInstruction
from frtb_ima.regimes import RegulatoryPolicy


class NMRFStressSpecError(ValueError):
    """Raised when an NMRF valuation specification cannot be built."""


class NMRFShockDirection(StrEnum):
    """Direction of the calibrated NMRF shock supplied to valuation."""

    UP = "UP"
    DOWN = "DOWN"
    TWO_SIDED = "TWO_SIDED"


@dataclass(frozen=True)
class NMRFStressPeriodSpec:
    """Stress-period identifier and optional date range used for calibration."""

    stress_period_id: str
    calibration_source: str
    start_date: date | None = None
    end_date: date | None = None
    notes: str = ""

    def __post_init__(self) -> None:
        if not self.stress_period_id:
            raise ValueError("stress_period_id must be non-empty")
        if not self.calibration_source:
            raise ValueError("calibration_source must be non-empty")
        if self.start_date is not None and not isinstance(self.start_date, date):
            raise TypeError("start_date must be a datetime.date when provided")
        if self.end_date is not None and not isinstance(self.end_date, date):
            raise TypeError("end_date must be a datetime.date when provided")
        if (
            self.start_date is not None
            and self.end_date is not None
            and self.start_date > self.end_date
        ):
            raise ValueError("start_date cannot be after end_date")

    def as_dict(self) -> dict[str, object]:
        """Return a serialisable dictionary for reporting and audit trails."""
        return {
            "stress_period_id": self.stress_period_id,
            "calibration_source": self.calibration_source,
            "start_date": self.start_date.isoformat() if self.start_date is not None else None,
            "end_date": self.end_date.isoformat() if self.end_date is not None else None,
            "notes": self.notes,
        }


@dataclass(frozen=True)
class NMRFDirectShockSpec:
    """Calibrated direct NMRF shock requirement for upstream valuation."""

    shock_size: float
    shock_unit: str
    direction: NMRFShockDirection
    calibration_source: str
    confidence_level: float = 0.975
    notes: str = ""

    def __post_init__(self) -> None:
        if not math.isfinite(self.shock_size) or self.shock_size <= 0.0:
            raise ValueError("shock_size must be finite and positive")
        if not self.shock_unit:
            raise ValueError("shock_unit must be non-empty")
        if not isinstance(self.direction, NMRFShockDirection):
            raise TypeError("direction must be an NMRFShockDirection")
        if not self.calibration_source:
            raise ValueError("calibration_source must be non-empty")
        if not (0.0 < self.confidence_level < 1.0):
            raise ValueError("confidence_level must be in (0, 1)")

    def as_dict(self) -> dict[str, object]:
        """Return a serialisable dictionary for reporting and audit trails."""
        return {
            "shock_size": self.shock_size,
            "shock_unit": self.shock_unit,
            "direction": self.direction.value,
            "calibration_source": self.calibration_source,
            "confidence_level": self.confidence_level,
            "notes": self.notes,
        }


@dataclass(frozen=True)
class NMRFStepwiseShockGrid:
    """Ordered shock grid or path for stepwise NMRF valuation."""

    shock_points: Sequence[float] | npt.NDArray[np.float64]
    shock_unit: str
    calibration_source: str
    path_dependent: bool = False
    require_monotonic_loss_check: bool = True
    notes: str = ""

    def __post_init__(self) -> None:
        points = _as_finite_tuple(self.shock_points, "shock_points")
        if len(points) < 2:
            raise ValueError("shock_points must contain at least two points")
        if len(points) != len(set(points)):
            raise ValueError("shock_points contains duplicates")
        if not self.shock_unit:
            raise ValueError("shock_unit must be non-empty")
        if not self.calibration_source:
            raise ValueError("calibration_source must be non-empty")
        object.__setattr__(self, "shock_points", points)

    @property
    def shock_count(self) -> int:
        """Number of shock points in the valuation grid/path."""
        return len(self.shock_points)

    def as_dict(self) -> dict[str, object]:
        """Return a serialisable dictionary for reporting and audit trails."""
        return {
            "shock_points": list(self.shock_points),
            "shock_unit": self.shock_unit,
            "calibration_source": self.calibration_source,
            "path_dependent": self.path_dependent,
            "require_monotonic_loss_check": self.require_monotonic_loss_check,
            "shock_count": self.shock_count,
            "notes": self.notes,
        }


@dataclass(frozen=True)
class NMRFFullRevaluationSpec:
    """Market-state requirements for full revaluation."""

    scenario_set_id: str
    market_state_ids: Sequence[str]
    calibration_source: str
    require_full_trade_repricing: bool = True
    notes: str = ""

    def __post_init__(self) -> None:
        if not self.scenario_set_id:
            raise ValueError("scenario_set_id must be non-empty")
        market_state_ids = _validate_non_empty_unique(
            self.market_state_ids,
            "market_state_ids",
        )
        if not self.calibration_source:
            raise ValueError("calibration_source must be non-empty")
        object.__setattr__(self, "market_state_ids", market_state_ids)

    def as_dict(self) -> dict[str, object]:
        """Return a serialisable audit summary without expanding large state lists."""
        return {
            "scenario_set_id": self.scenario_set_id,
            "market_state_count": len(self.market_state_ids),
            "calibration_source": self.calibration_source,
            "require_full_trade_repricing": self.require_full_trade_repricing,
            "notes": self.notes,
        }


@dataclass(frozen=True)
class NMRFMaxLossFallbackSpec:
    """
    Candidate scenarios for the conservative max-loss fallback path.

    The fallback selection rule is fixed: the upstream valuation run must return
    candidate losses and the capital layer uses the maximum loss.
    """

    SELECTION_RULE: ClassVar[str] = "MAXIMUM_LOSS"

    candidate_scenario_ids: Sequence[str]
    loss_source: str
    notes: str = ""

    def __post_init__(self) -> None:
        candidate_scenario_ids = _validate_non_empty_unique(
            self.candidate_scenario_ids,
            "candidate_scenario_ids",
        )
        if not self.loss_source:
            raise ValueError("loss_source must be non-empty")
        object.__setattr__(self, "candidate_scenario_ids", candidate_scenario_ids)

    def as_dict(self) -> dict[str, object]:
        """Return a serialisable dictionary for reporting and audit trails."""
        return {
            "candidate_scenario_ids": list(self.candidate_scenario_ids),
            "candidate_scenario_count": len(self.candidate_scenario_ids),
            "loss_source": self.loss_source,
            "selection_rule": self.SELECTION_RULE,
            "notes": self.notes,
        }


@dataclass(frozen=True)
class NMRFValuationSpec:
    """Complete upstream valuation requirement for one NMRF."""

    risk_factor_name: str
    modellability_status: ModellabilityStatus
    risk_class: RiskClass
    method: NMRFStressMethod
    required_liquidity_horizon: LiquidityHorizon
    stress_period: NMRFStressPeriodSpec
    direct_shock: NMRFDirectShockSpec | None = None
    stepwise_grid: NMRFStepwiseShockGrid | None = None
    full_revaluation: NMRFFullRevaluationSpec | None = None
    max_loss_fallback: NMRFMaxLossFallbackSpec | None = None
    source: str = ""
    notes: str = ""

    def __post_init__(self) -> None:
        if not self.risk_factor_name:
            raise ValueError("risk_factor_name must be non-empty")
        if self.modellability_status not in {
            ModellabilityStatus.TYPE_A_NMRF,
            ModellabilityStatus.TYPE_B_NMRF,
        }:
            raise ValueError("NMRF valuation specs are only valid for NMRFs")
        if not isinstance(self.risk_class, RiskClass):
            raise TypeError("risk_class must be a RiskClass")
        if not isinstance(self.method, NMRFStressMethod):
            raise TypeError("method must be an NMRFStressMethod")
        if not isinstance(self.required_liquidity_horizon, LiquidityHorizon):
            raise TypeError("required_liquidity_horizon must be a LiquidityHorizon")
        if self.required_liquidity_horizon.value < LiquidityHorizon.LH20.value:
            raise ValueError("required_liquidity_horizon must be at least 20 days")
        if not isinstance(self.stress_period, NMRFStressPeriodSpec):
            raise TypeError("stress_period must be an NMRFStressPeriodSpec")
        if not self.source:
            raise ValueError("source must be non-empty")
        self._validate_method_payload()

    def _validate_method_payload(self) -> None:
        if self.method == NMRFStressMethod.LINEAR_SENSITIVITY:
            raise ValueError("LINEAR_SENSITIVITY is not a valuation-run specification")

        payloads = {
            NMRFStressMethod.DIRECT: self.direct_shock,
            NMRFStressMethod.STEPWISE: self.stepwise_grid,
            NMRFStressMethod.FULL_REVALUATION: self.full_revaluation,
            NMRFStressMethod.MAX_LOSS_FALLBACK: self.max_loss_fallback,
        }
        required_payload = payloads[self.method]
        if required_payload is None:
            raise ValueError(f"{self.method.value} requires its matching spec payload")

        unexpected = [
            method.value
            for method, payload in payloads.items()
            if method != self.method and payload is not None
        ]
        if unexpected:
            raise ValueError(
                f"{self.method.value} valuation spec has unexpected payloads: {unexpected}"
            )

    def as_dict(self) -> dict[str, object]:
        """Return a serialisable dictionary for reporting and audit trails."""
        return {
            "risk_factor_name": self.risk_factor_name,
            "modellability_status": self.modellability_status.value,
            "risk_class": self.risk_class.value,
            "method": self.method.value,
            "required_liquidity_horizon": self.required_liquidity_horizon.value,
            "stress_period": self.stress_period.as_dict(),
            "direct_shock": self.direct_shock.as_dict() if self.direct_shock is not None else None,
            "stepwise_grid": self.stepwise_grid.as_dict()
            if self.stepwise_grid is not None
            else None,
            "full_revaluation": self.full_revaluation.as_dict()
            if self.full_revaluation is not None
            else None,
            "max_loss_fallback": self.max_loss_fallback.as_dict()
            if self.max_loss_fallback is not None
            else None,
            "source": self.source,
            "notes": self.notes,
        }


def _as_finite_tuple(
    values: Sequence[float] | npt.NDArray[np.float64],
    name: str,
) -> tuple[float, ...]:
    arr = np.asarray(values, dtype=float)
    if arr.ndim != 1:
        raise ValueError(f"{name} must be one-dimensional")
    if arr.size == 0:
        raise ValueError(f"{name} must be non-empty")
    if not np.all(np.isfinite(arr)):
        raise ValueError(f"{name} must contain only finite values")
    return tuple(float(value) for value in arr)


def _validate_non_empty_unique(values: Sequence[str], name: str) -> tuple[str, ...]:
    result = tuple(values)
    if not result:
        raise ValueError(f"{name} must be non-empty")
    if any(not isinstance(value, str) for value in result):
        raise TypeError(f"{name} must contain only strings")
    if any(not value for value in result):
        raise ValueError(f"{name} cannot contain empty values")
    if len(result) != len(set(result)):
        raise ValueError(f"{name} contains duplicates")
    return result


def build_nmrf_valuation_spec(
    instruction: NMRFValuationInstruction,
    risk_class: RiskClass,
    stress_period: NMRFStressPeriodSpec,
    policy: RegulatoryPolicy,
    *,
    direct_shock: NMRFDirectShockSpec | None = None,
    stepwise_grid: NMRFStepwiseShockGrid | None = None,
    full_revaluation: NMRFFullRevaluationSpec | None = None,
    max_loss_fallback: NMRFMaxLossFallbackSpec | None = None,
    source: str = "",
    notes: str = "",
) -> NMRFValuationSpec:
    """Build one upstream valuation spec from a method-selection instruction."""
    policy.require_supported("type_a_type_b_nmrf_taxonomy")
    if not isinstance(instruction, NMRFValuationInstruction):
        raise TypeError("instruction must be an NMRFValuationInstruction")

    return NMRFValuationSpec(
        risk_factor_name=instruction.risk_factor_name,
        modellability_status=instruction.modellability_status,
        risk_class=risk_class,
        method=instruction.method,
        required_liquidity_horizon=instruction.required_liquidity_horizon,
        stress_period=stress_period,
        direct_shock=direct_shock,
        stepwise_grid=stepwise_grid,
        full_revaluation=full_revaluation,
        max_loss_fallback=max_loss_fallback,
        source=source or instruction.source or "nmrf valuation specification",
        notes=notes or instruction.notes,
    )


def build_nmrf_valuation_specs(
    instructions: Sequence[NMRFValuationInstruction],
    risk_classes: Mapping[str, RiskClass],
    stress_periods_by_risk_class: Mapping[RiskClass, NMRFStressPeriodSpec],
    policy: RegulatoryPolicy,
    *,
    stress_periods_by_risk_factor: Mapping[str, NMRFStressPeriodSpec] | None = None,
    direct_shocks: Mapping[str, NMRFDirectShockSpec] | None = None,
    stepwise_grids: Mapping[str, NMRFStepwiseShockGrid] | None = None,
    full_revaluations: Mapping[str, NMRFFullRevaluationSpec] | None = None,
    max_loss_fallbacks: Mapping[str, NMRFMaxLossFallbackSpec] | None = None,
    source: str = "nmrf valuation specification builder",
) -> tuple[NMRFValuationSpec, ...]:
    """Build deterministic valuation specs for a sequence of NMRF instructions."""
    if not instructions:
        raise ValueError("instructions must be non-empty")

    seen_risk_factors: set[str] = set()
    specs: list[NMRFValuationSpec] = []
    for instruction in instructions:
        risk_factor_name = instruction.risk_factor_name
        if risk_factor_name in seen_risk_factors:
            raise NMRFStressSpecError(f"duplicate instruction for risk factor {risk_factor_name}")
        seen_risk_factors.add(risk_factor_name)

        risk_class = risk_classes.get(risk_factor_name)
        if risk_class is None:
            raise NMRFStressSpecError(f"missing risk class for {risk_factor_name}")

        stress_period = None
        if stress_periods_by_risk_factor is not None:
            stress_period = stress_periods_by_risk_factor.get(risk_factor_name)
        if stress_period is None:
            stress_period = stress_periods_by_risk_class.get(risk_class)
        if stress_period is None:
            raise NMRFStressSpecError(
                f"missing stress period for {risk_factor_name} / {risk_class.value}"
            )

        direct_shock = None if direct_shocks is None else direct_shocks.get(risk_factor_name)
        stepwise_grid = None if stepwise_grids is None else stepwise_grids.get(risk_factor_name)
        full_revaluation = (
            None if full_revaluations is None else full_revaluations.get(risk_factor_name)
        )
        max_loss_fallback = (
            None if max_loss_fallbacks is None else max_loss_fallbacks.get(risk_factor_name)
        )

        try:
            specs.append(
                build_nmrf_valuation_spec(
                    instruction,
                    risk_class,
                    stress_period,
                    policy,
                    direct_shock=direct_shock,
                    stepwise_grid=stepwise_grid,
                    full_revaluation=full_revaluation,
                    max_loss_fallback=max_loss_fallback,
                    source=source,
                )
            )
        except (TypeError, ValueError) as exc:
            raise NMRFStressSpecError(
                f"invalid valuation spec for {risk_factor_name}: {exc}"
            ) from exc

    return tuple(specs)


def required_methods_from_valuation_specs(
    specs: Sequence[NMRFValuationSpec],
) -> dict[str, NMRFStressMethod]:
    """Return the required method mapping expected by NMRF capital validation."""
    if not specs:
        raise ValueError("specs must be non-empty")
    return {spec.risk_factor_name: spec.method for spec in specs}


def required_liquidity_horizons_from_valuation_specs(
    specs: Sequence[NMRFValuationSpec],
) -> dict[str, LiquidityHorizon]:
    """Return the required LH mapping expected by NMRF capital validation."""
    if not specs:
        raise ValueError("specs must be non-empty")
    return {spec.risk_factor_name: spec.required_liquidity_horizon for spec in specs}
