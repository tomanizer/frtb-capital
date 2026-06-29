"""Types for v1 RFET observation mapping adapters."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType

from frtb_ima.adapters._daily_pnl_mapping_types import FieldMapping, MappingFinding, MappingSpecError

IMA_RFET_OBSERVATION_TARGET = "ima_rfet_observations"
RFET_OBSERVATION_TARGET_FIELDS = frozenset(
    {
        "risk_factor_name",
        "observation_date",
        "source",
        "vendor_id",
        "venue",
        "feed",
        "observation_timestamp",
        "date_normalization_evidence",
        "verifiable",
        "verifiability_reason",
        "data_pool_id",
        "vendor_audit_evidence_id",
        "source_row_id",
    }
)
REQUIRED_RFET_OBSERVATION_FIELDS = frozenset({"risk_factor_name", "observation_date"})


@dataclass(frozen=True)
class RfetObservationTableMapping:
    """Mapping configuration for v1 RFET observation source rows."""

    source: str
    target: str
    fields: Mapping[str, FieldMapping]

    def __post_init__(self) -> None:
        if not self.source:
            raise MappingSpecError("rfet_observations.source must be non-empty")
        if self.target != IMA_RFET_OBSERVATION_TARGET:
            raise MappingSpecError(
                f"rfet_observations.target must be {IMA_RFET_OBSERVATION_TARGET!r}, got {self.target!r}"
            )
        unknown = sorted(set(self.fields) - RFET_OBSERVATION_TARGET_FIELDS)
        if unknown:
            raise MappingSpecError("unknown rfet_observations target fields: " + ", ".join(unknown))
        missing = sorted(REQUIRED_RFET_OBSERVATION_FIELDS - set(self.fields))
        if missing:
            raise MappingSpecError("missing rfet_observations required fields: " + ", ".join(missing))
        object.__setattr__(self, "fields", MappingProxyType(dict(self.fields)))


@dataclass(frozen=True)
class RfetObservationValidationReport:
    """Generated validation and reconciliation report for RFET observation mapping."""

    target_schema: str
    source_system: str
    source_file: str
    mapping_hash: str
    source_hash: str
    row_count_read: int
    row_count_mapped: int
    row_count_rejected: int
    findings: tuple[MappingFinding, ...] = ()

    @property
    def passed(self) -> bool:
        return all(finding.severity != "ERROR" for finding in self.findings)

    def as_dict(self) -> dict[str, object]:
        return {
            "target_schema": self.target_schema,
            "source_system": self.source_system,
            "source_file": self.source_file,
            "mapping_hash": self.mapping_hash,
            "source_hash": self.source_hash,
            "row_count_read": self.row_count_read,
            "row_count_mapped": self.row_count_mapped,
            "row_count_rejected": self.row_count_rejected,
            "passed": self.passed,
            "findings": [finding.as_dict() for finding in self.findings],
        }
