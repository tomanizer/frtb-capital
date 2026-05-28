"""
Vector-friendly data contracts for market-risk calculation runs.

These classes sit at the boundary between upstream risk-engine outputs and the
pure calculation functions in this package. They validate shape, identity, and
metadata early so downstream ES, LHA, IMCC, RFET, PLA, and backtesting code can
stay functional and focused.

Regulatory traceability:
    Supports the NPR 2.0 market-risk workflow described in
    docs/requirements/NPR_2_0_MARKET_RISK.yml and
    docs/REGULATORY_TRACEABILITY.md.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date
from types import MappingProxyType
from typing import cast

import numpy as np
import numpy.typing as npt

from frtb_ima.data_models import (
    DeskCapitalResult,
    LiquidityHorizon,
    RealPriceObservation,
    RiskClass,
)
from frtb_ima.input_manifest import CapitalRunInputManifest
from frtb_ima.regimes import CalculationContext, RegulatoryRegime
from frtb_ima.scenario import ScenarioMetadata

FloatArray = npt.NDArray[np.float64]


def _freeze_mapping(values: Mapping[str, str]) -> Mapping[str, str]:
    return MappingProxyType(dict(values))


def _validate_non_empty_unique(values: Sequence[str], name: str) -> tuple[str, ...]:
    result = tuple(values)
    if not result:
        raise ValueError(f"{name} must be non-empty")
    if any(not value for value in result):
        raise ValueError(f"{name} cannot contain empty values")
    if len(result) != len(set(result)):
        raise ValueError(f"{name} contains duplicates")
    return result


@dataclass(frozen=True)
class RiskFactorBucket:
    """A regulatory or internal bucket used for RFET and LH mapping."""

    bucket_id: str
    risk_class: RiskClass
    liquidity_horizon: LiquidityHorizon
    description: str = ""
    metadata: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.bucket_id:
            raise ValueError("bucket_id must be non-empty")
        object.__setattr__(self, "metadata", _freeze_mapping(self.metadata))


@dataclass(frozen=True)
class RiskFactorDefinition:
    """A risk-factor definition used to align RFET, scenarios, and capital."""

    name: str
    risk_class: RiskClass
    liquidity_horizon: LiquidityHorizon
    bucket: RiskFactorBucket | None = None
    currency: str = ""
    metadata: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("risk factor name must be non-empty")
        if self.bucket is not None:
            if self.bucket.risk_class != self.risk_class:
                raise ValueError("risk factor bucket risk_class does not match definition")
            if self.bucket.liquidity_horizon != self.liquidity_horizon:
                raise ValueError("risk factor bucket liquidity_horizon does not match definition")
        object.__setattr__(self, "metadata", _freeze_mapping(self.metadata))


@dataclass(frozen=True)
class RFETRepresentativenessEvidence:
    """Evidence that RFET observations are representative for a bucket/curve/surface."""

    bucket_id: str
    methodology: str
    passed: bool
    rationale: str = ""
    curve_id: str = ""
    surface_id: str = ""
    metadata: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.bucket_id:
            raise ValueError("bucket_id must be non-empty")
        if not self.methodology:
            raise ValueError("methodology must be non-empty")
        if not isinstance(self.passed, bool):
            raise TypeError("passed must be a bool")
        if not self.passed and not self.rationale:
            raise ValueError("failed representativeness evidence requires a rationale")
        object.__setattr__(self, "metadata", _freeze_mapping(self.metadata))


@dataclass(frozen=True)
class RFETDataPoolEvidence:
    """Vendor/data-pooling evidence for third-party real-price observations."""

    pool_id: str
    vendor_id: str
    independent_audit_evidence_id: str
    description: str = ""
    metadata: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.pool_id:
            raise ValueError("pool_id must be non-empty")
        if not self.vendor_id:
            raise ValueError("vendor_id must be non-empty")
        if not self.independent_audit_evidence_id:
            raise ValueError("independent_audit_evidence_id must be non-empty")
        object.__setattr__(self, "metadata", _freeze_mapping(self.metadata))


@dataclass(frozen=True)
class RFETNewIssuanceEvidence:
    """Policy-governed evidence for new-issuance RFET prorating."""

    issue_date: date
    prorating_approved: bool
    policy_citation: str = ""
    rationale: str = ""
    metadata: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if type(self.issue_date) is not date:
            raise TypeError("issue_date must be a datetime.date")
        if not isinstance(self.prorating_approved, bool):
            raise TypeError("prorating_approved must be a bool")
        if self.prorating_approved and not (self.policy_citation or self.rationale):
            raise ValueError("approved prorating requires a policy_citation or rationale")
        object.__setattr__(self, "metadata", _freeze_mapping(self.metadata))


@dataclass(frozen=True)
class Position:
    """A market-risk covered position as seen by the ex-post capital layer."""

    position_id: str
    desk: str
    instrument_id: str
    fair_value: float
    currency: str
    risk_factor_names: tuple[str, ...]
    notional: float | None = None
    metadata: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.position_id:
            raise ValueError("position_id must be non-empty")
        if not self.desk:
            raise ValueError("desk must be non-empty")
        if not self.instrument_id:
            raise ValueError("instrument_id must be non-empty")
        if not np.isfinite(self.fair_value):
            raise ValueError("fair_value must be finite")
        if self.notional is not None and not np.isfinite(self.notional):
            raise ValueError("notional must be finite when provided")
        object.__setattr__(
            self,
            "risk_factor_names",
            _validate_non_empty_unique(self.risk_factor_names, "risk_factor_names"),
        )
        object.__setattr__(self, "metadata", _freeze_mapping(self.metadata))


@dataclass(frozen=True)
class RFETEvidence:
    """Evidence package used by RFET classification logic."""

    risk_factor_name: str
    as_of_date: date
    observations: tuple[RealPriceObservation, ...]
    qualitative_pass: bool
    bucket_id: str = ""
    representativeness: tuple[RFETRepresentativenessEvidence, ...] = ()
    data_pools: tuple[RFETDataPoolEvidence, ...] = ()
    new_issuance: RFETNewIssuanceEvidence | None = None
    metadata: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.risk_factor_name:
            raise ValueError("risk_factor_name must be non-empty")
        if type(self.as_of_date) is not date:
            raise TypeError("as_of_date must be a datetime.date")
        if any(obs.risk_factor_name != self.risk_factor_name for obs in self.observations):
            raise ValueError("all observations must match risk_factor_name")
        data_pools = tuple(self.data_pools)
        pool_ids = [item.pool_id for item in data_pools]
        if len(pool_ids) != len(set(pool_ids)):
            raise ValueError("data_pools contains duplicate pool_id values")
        object.__setattr__(self, "observations", tuple(self.observations))
        object.__setattr__(self, "representativeness", tuple(self.representativeness))
        object.__setattr__(self, "data_pools", data_pools)
        object.__setattr__(self, "metadata", _freeze_mapping(self.metadata))

    @property
    def observation_count(self) -> int:
        """Raw observation count before RFET eligibility filters."""
        return len(self.observations)


@dataclass(frozen=True)
class ScenarioCube:
    """
    Three-dimensional scenario P&L cube.

    Shape convention:
        axis 0: scenarios
        axis 1: positions
        axis 2: risk factors

    Values use the loss convention for ES/LHA/IMCC paths: positive is loss.
    """

    values: FloatArray
    scenario_metadata: tuple[ScenarioMetadata, ...]
    position_ids: tuple[str, ...]
    risk_factor_names: tuple[str, ...]
    name: str = ""

    def __post_init__(self) -> None:
        source_values = self.values
        arr = np.asarray(source_values, dtype=float)
        if arr.ndim != 3:
            raise ValueError(
                "ScenarioCube values must have shape (scenario, position, risk_factor)"
            )
        if arr.size == 0:
            raise ValueError("ScenarioCube values must be non-empty")
        if not np.all(np.isfinite(arr)):
            raise ValueError("ScenarioCube values must contain only finite values")

        scenario_count, position_count, risk_factor_count = arr.shape
        scenario_metadata = tuple(self.scenario_metadata)
        if len(scenario_metadata) != scenario_count:
            raise ValueError("scenario_metadata length must match ScenarioCube scenario axis")

        position_ids = _validate_non_empty_unique(self.position_ids, "position_ids")
        risk_factor_names = _validate_non_empty_unique(
            self.risk_factor_names,
            "risk_factor_names",
        )
        if len(position_ids) != position_count:
            raise ValueError("position_ids length must match ScenarioCube position axis")
        if len(risk_factor_names) != risk_factor_count:
            raise ValueError("risk_factor_names length must match ScenarioCube risk-factor axis")

        shares_source = isinstance(source_values, np.ndarray) and np.shares_memory(
            arr,
            source_values,
        )
        if shares_source or not arr.flags.owndata:
            arr = arr.copy()
        arr.flags.writeable = False
        object.__setattr__(self, "values", arr)
        object.__setattr__(self, "scenario_metadata", scenario_metadata)
        object.__setattr__(self, "position_ids", position_ids)
        object.__setattr__(self, "risk_factor_names", risk_factor_names)

    @property
    def scenario_count(self) -> int:
        return int(self.values.shape[0])

    @property
    def position_count(self) -> int:
        return int(self.values.shape[1])

    @property
    def risk_factor_count(self) -> int:
        return int(self.values.shape[2])

    @property
    def position_index(self) -> dict[str, int]:
        return {position_id: index for index, position_id in enumerate(self.position_ids)}

    @property
    def risk_factor_index(self) -> dict[str, int]:
        return {
            risk_factor_name: index for index, risk_factor_name in enumerate(self.risk_factor_names)
        }

    def total_scenario_pnl(self) -> FloatArray:
        """Aggregate all positions and risk factors into one scenario vector."""
        return cast(FloatArray, np.sum(self.values, axis=(1, 2)))

    def pnl_for_positions(self, position_ids: Sequence[str]) -> FloatArray:
        """Aggregate selected position IDs across all risk factors."""
        index = self.position_index
        missing = [position_id for position_id in position_ids if position_id not in index]
        if missing:
            raise KeyError(f"Unknown position_ids: {missing}")
        selected = [index[position_id] for position_id in position_ids]
        return cast(FloatArray, np.sum(self.values[:, selected, :], axis=(1, 2)))

    def pnl_for_risk_factors(self, risk_factor_names: Sequence[str]) -> FloatArray:
        """Aggregate selected risk-factor names across all positions."""
        index = self.risk_factor_index
        missing = [name for name in risk_factor_names if name not in index]
        if missing:
            raise KeyError(f"Unknown risk_factor_names: {missing}")
        selected = [index[name] for name in risk_factor_names]
        return cast(FloatArray, np.sum(self.values[:, :, selected], axis=(1, 2)))


@dataclass(frozen=True)
class DeskRun:
    """Inputs for one desk-level capital run."""

    context: CalculationContext
    positions: tuple[Position, ...]
    risk_factors: tuple[RiskFactorDefinition, ...]
    scenario_cube: ScenarioCube | None = None

    def __post_init__(self) -> None:
        positions = tuple(self.positions)
        risk_factors = tuple(self.risk_factors)
        if not positions:
            raise ValueError("DeskRun positions must be non-empty")
        if not risk_factors:
            raise ValueError("DeskRun risk_factors must be non-empty")
        if self.context.desk is not None:
            desks = {position.desk for position in positions}
            if desks != {self.context.desk}:
                raise ValueError("all positions must belong to context.desk")
        object.__setattr__(self, "positions", positions)
        object.__setattr__(self, "risk_factors", risk_factors)


@dataclass(frozen=True)
class CapitalRunResult:
    """Top-level capital run result container for reporting and audit."""

    as_of_date: date
    regime: RegulatoryRegime
    desk_results: Mapping[str, DeskCapitalResult]
    total_market_risk_capital: float | None = None
    notes: tuple[str, ...] = ()
    input_manifest: CapitalRunInputManifest | None = None
    require_input_manifest: bool = field(default=False, kw_only=True)

    def __post_init__(self) -> None:
        if type(self.as_of_date) is not date:
            raise TypeError("as_of_date must be a datetime.date")
        if self.total_market_risk_capital is not None and not np.isfinite(
            self.total_market_risk_capital
        ):
            raise ValueError("total_market_risk_capital must be finite when provided")
        if self.require_input_manifest and self.input_manifest is None:
            raise ValueError("input_manifest is required for production-style capital runs")
        if self.input_manifest is not None and self.input_manifest.as_of_date != self.as_of_date:
            raise ValueError("input_manifest as_of_date must match CapitalRunResult as_of_date")
        object.__setattr__(self, "desk_results", MappingProxyType(dict(self.desk_results)))
        object.__setattr__(self, "notes", tuple(self.notes))

    def as_dict(self) -> dict[str, object]:
        """Return a serialisable dictionary for reporting and audit trails."""
        return {
            "as_of_date": self.as_of_date.isoformat(),
            "regime": self.regime.value,
            "desk_results": {desk: result.as_dict() for desk, result in self.desk_results.items()},
            "total_market_risk_capital": self.total_market_risk_capital,
            "notes": list(self.notes),
            "input_manifest": (
                self.input_manifest.compact_summary() if self.input_manifest is not None else None
            ),
        }
