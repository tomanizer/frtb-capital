"""Data contracts for DRC baseline-vs-candidate impact analysis."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field, fields
from enum import StrEnum
from types import MappingProxyType
from typing import TypeVar

from frtb_common import jsonable
from frtb_common.attribution import ReconciliationStatus
from frtb_common.impact import CapitalImpact

from frtb_drc.data_models import BranchMetadata

_TOLERANCE = 1e-9


class DrcImpactMethod(StrEnum):
    """DRC impact method labels separate from analytical Euler attribution."""

    FINITE_DIFFERENCE = "FINITE_DIFFERENCE"
    RESIDUAL = "RESIDUAL"
    UNSUPPORTED = "UNSUPPORTED"


@dataclass(frozen=True)
class DrcImpactRecord:
    """One branch-aware DRC baseline-vs-candidate impact record."""

    impact_id: str
    source_id: str
    source_level: str
    baseline_capital: float | None
    candidate_capital: float | None
    delta: float | None
    method: DrcImpactMethod | str
    reconciliation_status: ReconciliationStatus | str
    reason: str
    baseline_category: str | None = None
    candidate_category: str | None = None
    baseline_bucket_key: str | None = None
    candidate_bucket_key: str | None = None
    baseline_input_hash: str = ""
    candidate_input_hash: str = ""
    baseline_profile_hash: str = ""
    candidate_profile_hash: str = ""
    branch_metadata: tuple[BranchMetadata, ...] = ()
    metadata: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "method", _coerce_enum(self.method, DrcImpactMethod, "method"))
        object.__setattr__(
            self,
            "reconciliation_status",
            _coerce_enum(self.reconciliation_status, ReconciliationStatus, "reconciliation_status"),
        )
        object.__setattr__(self, "branch_metadata", tuple(self.branch_metadata))
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))

    def as_dict(self) -> dict[str, object]:
        """Return a JSON-ready representation of the impact record."""

        return {field.name: jsonable(getattr(self, field.name)) for field in fields(self)}


@dataclass(frozen=True)
class DrcImpactAnalysis:
    """Top-level DRC impact summary plus branch-level records."""

    total_impact: CapitalImpact
    records: tuple[DrcImpactRecord, ...]
    residual: float
    reconciliation_status: ReconciliationStatus | str
    tolerance: float = _TOLERANCE

    def __post_init__(self) -> None:
        object.__setattr__(self, "records", tuple(self.records))
        object.__setattr__(
            self,
            "reconciliation_status",
            _coerce_enum(self.reconciliation_status, ReconciliationStatus, "reconciliation_status"),
        )

    @property
    def baseline_total(self) -> float:
        """Baseline DRC capital total."""

        return self.total_impact.baseline_total

    @property
    def candidate_total(self) -> float:
        """Candidate DRC capital total."""

        return self.total_impact.candidate_total

    @property
    def delta(self) -> float:
        """Candidate minus baseline total DRC."""

        return self.total_impact.delta

    def as_dict(self) -> dict[str, object]:
        """Return a JSON-ready representation of the impact analysis."""

        return {field.name: jsonable(getattr(self, field.name)) for field in fields(self)}


EnumT = TypeVar("EnumT", bound=StrEnum)


def _coerce_enum(value: EnumT | str, enum_type: type[EnumT], field_name: str) -> EnumT:
    if isinstance(value, enum_type):
        return value
    try:
        return enum_type(value)
    except ValueError as exc:
        allowed = ", ".join(item.value for item in enum_type)
        raise ValueError(f"{field_name} must be one of: {allowed}") from exc
