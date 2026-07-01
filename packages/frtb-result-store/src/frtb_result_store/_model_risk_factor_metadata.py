"""Canonical risk-factor metadata snapshot dataclasses.

These result-store-owned records describe fixture-backed risk-factor metadata
for a committed synthetic run. They are read-model contracts, not calculation
inputs and not a production reference-data master. Component packages consume
already-resolved metadata and preserve identifiers; they do not query these
records from capital kernels.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import date, datetime
from enum import StrEnum
from typing import Any, cast

from frtb_common import (
    BucketId,
    CurrencyCode,
    RiskFactorId,
    RiskFactorLineageId,
    RiskFactorMappingVersion,
    RiskFactorPrimitiveError,
    RiskFactorRiskClassCode,
    RiskFactorTypeCode,
    SensitivityTypeCode,
    Tenor,
)

from frtb_result_store.model_enums import ResultStoreContractError
from frtb_result_store.model_validation import (
    _freeze_metadata,
    _require_non_empty_text,
    _require_plain_date,
    _validate_optional_text,
)

__all__ = [
    "RiskFactorEvidenceState",
    "RiskFactorMetadataRecord",
    "RiskFactorMetadataSnapshot",
    "RiskFactorRecordStatus",
    "RiskFactorSourceMapping",
]


class RiskFactorEvidenceState(StrEnum):
    """Availability state for optional risk-factor evidence datasets."""

    AVAILABLE = "available"
    NO_DATA = "no_data"
    UNSUPPORTED = "unsupported"


class RiskFactorRecordStatus(StrEnum):
    """Lifecycle state of a risk-factor metadata record within a snapshot."""

    ACTIVE = "active"
    INACTIVE = "inactive"
    NO_DATA = "no_data"


@dataclass(frozen=True, slots=True)
class RiskFactorMetadataSnapshot:
    """Canonical risk-factor metadata snapshot for one result-store run.

    The snapshot ties risk-factor records to a run, effective date, and mapping
    version. It carries fixture/read-model provenance only; detailed RFET,
    stress-vector, CRIF, or source datasets remain explicit artifacts or
    no-data states unless such data exists.
    """

    run_id: str
    snapshot_id: str
    mapping_version: RiskFactorMappingVersion | str
    effective_date: date
    source_system: str
    created_at: datetime
    metadata: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _require_non_empty_text(self.run_id, "run_id")
        _require_non_empty_text(self.snapshot_id, "snapshot_id")
        object.__setattr__(
            self,
            "mapping_version",
            _coerce_primitive(
                self.mapping_version,
                RiskFactorMappingVersion,
                "mapping_version",
            ),
        )
        _require_plain_date(self.effective_date, "effective_date")
        _require_non_empty_text(self.source_system, "source_system")
        if not isinstance(self.created_at, datetime) or self.created_at.tzinfo is None:
            raise ResultStoreContractError(
                "created_at must be a timezone-aware datetime",
                field="created_at",
            )
        _freeze_metadata(self, self.metadata)


@dataclass(frozen=True, slots=True)
class RiskFactorMetadataRecord:
    """One canonical risk-factor metadata row within a result-store snapshot."""

    run_id: str
    snapshot_id: str
    risk_factor_id: RiskFactorId | str
    display_name: str
    risk_class: RiskFactorRiskClassCode | str
    risk_factor_type: RiskFactorTypeCode | str
    mapping_version: RiskFactorMappingVersion | str
    bucket_id: BucketId | str | None = None
    bucket_label: str | None = None
    sensitivity_type: SensitivityTypeCode | str | None = None
    currency: CurrencyCode | str | None = None
    curve_id: str | None = None
    tenor: Tenor | str | None = None
    issuer_id: str | None = None
    obligor_id: str | None = None
    counterparty_id: str | None = None
    commodity_id: str | None = None
    equity_id: str | None = None
    status: RiskFactorRecordStatus | str = RiskFactorRecordStatus.ACTIVE
    rfet_evidence_state: RiskFactorEvidenceState | str = RiskFactorEvidenceState.NO_DATA
    rfet_evidence_id: RiskFactorLineageId | str | None = None
    modellability_state: RiskFactorEvidenceState | str = RiskFactorEvidenceState.NO_DATA
    liquidity_horizon_days: int | None = None
    nmrf_state: RiskFactorEvidenceState | str = RiskFactorEvidenceState.NO_DATA
    stress_period_id: str | None = None
    source_system: str | None = None
    source_row_id: str | None = None
    metadata: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _validate_record_identity(self)
        _validate_record_dimensions(self)
        _validate_record_ima_evidence_state(self)
        _freeze_metadata(self, self.metadata)


@dataclass(frozen=True, slots=True)
class RiskFactorSourceMapping:
    """Source-system row linked to a canonical risk-factor metadata record."""

    run_id: str
    snapshot_id: str
    risk_factor_id: RiskFactorId | str
    source_system: str
    source_row_id: str
    mapping_version: RiskFactorMappingVersion | str
    relationship: str = "canonical_source"
    source_hash: str | None = None
    metadata: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _require_non_empty_text(self.run_id, "run_id")
        _require_non_empty_text(self.snapshot_id, "snapshot_id")
        object.__setattr__(
            self,
            "risk_factor_id",
            _coerce_primitive(self.risk_factor_id, RiskFactorId, "risk_factor_id"),
        )
        _require_non_empty_text(self.source_system, "source_system")
        _require_non_empty_text(self.source_row_id, "source_row_id")
        object.__setattr__(
            self,
            "mapping_version",
            _coerce_primitive(
                self.mapping_version,
                RiskFactorMappingVersion,
                "mapping_version",
            ),
        )
        _require_non_empty_text(self.relationship, "relationship")
        _validate_optional_text(self.source_hash, "source_hash")
        _freeze_metadata(self, self.metadata)


def _coerce_primitive(value: object, primitive: type[object], field: str) -> object:
    if isinstance(value, primitive):
        return value
    try:
        return cast(Any, primitive)(value)
    except (RiskFactorPrimitiveError, TypeError, ValueError) as exc:
        raise ResultStoreContractError(str(exc), field=field) from exc


def _coerce_optional_primitive(
    value: object | None,
    primitive: type[object],
    field: str,
) -> object | None:
    if value is None:
        return None
    return _coerce_primitive(value, primitive, field)


def _validate_record_identity(record: RiskFactorMetadataRecord) -> None:
    """Validate stable snapshot and taxonomy identity fields for one metadata row."""

    _require_non_empty_text(record.run_id, "run_id")
    _require_non_empty_text(record.snapshot_id, "snapshot_id")
    object.__setattr__(
        record,
        "risk_factor_id",
        _coerce_primitive(record.risk_factor_id, RiskFactorId, "risk_factor_id"),
    )
    _require_non_empty_text(record.display_name, "display_name")
    object.__setattr__(
        record,
        "risk_class",
        _coerce_primitive(record.risk_class, RiskFactorRiskClassCode, "risk_class"),
    )
    object.__setattr__(
        record,
        "risk_factor_type",
        _coerce_primitive(
            record.risk_factor_type,
            RiskFactorTypeCode,
            "risk_factor_type",
        ),
    )
    object.__setattr__(
        record,
        "mapping_version",
        _coerce_primitive(
            record.mapping_version,
            RiskFactorMappingVersion,
            "mapping_version",
        ),
    )


def _validate_record_dimensions(record: RiskFactorMetadataRecord) -> None:
    """Validate optional classification and source dimensions for viewer lookup."""

    object.__setattr__(
        record,
        "bucket_id",
        _coerce_optional_primitive(record.bucket_id, BucketId, "bucket_id"),
    )
    _validate_optional_text(record.bucket_label, "bucket_label")
    object.__setattr__(
        record,
        "sensitivity_type",
        _coerce_optional_primitive(
            record.sensitivity_type,
            SensitivityTypeCode,
            "sensitivity_type",
        ),
    )
    object.__setattr__(
        record,
        "currency",
        _coerce_optional_primitive(record.currency, CurrencyCode, "currency"),
    )
    _validate_optional_text(record.curve_id, "curve_id")
    object.__setattr__(
        record,
        "tenor",
        _coerce_optional_primitive(record.tenor, Tenor, "tenor"),
    )
    for field_name in (
        "issuer_id",
        "obligor_id",
        "counterparty_id",
        "commodity_id",
        "equity_id",
        "stress_period_id",
        "source_system",
        "source_row_id",
    ):
        _validate_optional_text(getattr(record, field_name), field_name)


def _validate_record_ima_evidence_state(record: RiskFactorMetadataRecord) -> None:
    """Validate IMA-adjacent evidence states without fabricating missing evidence."""

    object.__setattr__(record, "status", RiskFactorRecordStatus(record.status))
    object.__setattr__(
        record,
        "rfet_evidence_state",
        RiskFactorEvidenceState(record.rfet_evidence_state),
    )
    object.__setattr__(
        record,
        "rfet_evidence_id",
        _coerce_optional_primitive(
            record.rfet_evidence_id,
            RiskFactorLineageId,
            "rfet_evidence_id",
        ),
    )
    object.__setattr__(
        record,
        "modellability_state",
        RiskFactorEvidenceState(record.modellability_state),
    )
    if record.liquidity_horizon_days is not None:
        if (
            isinstance(record.liquidity_horizon_days, bool)
            or not isinstance(record.liquidity_horizon_days, int)
            or record.liquidity_horizon_days <= 0
        ):
            raise ResultStoreContractError(
                "liquidity_horizon_days must be a positive integer when set",
                field="liquidity_horizon_days",
            )
    object.__setattr__(record, "nmrf_state", RiskFactorEvidenceState(record.nmrf_state))
