"""Artifact and lineage reference dataclasses."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from urllib.parse import urlparse

from frtb_result_store.model_enums import ArtifactType, FrtbComponent, ResultStoreContractError
from frtb_result_store.model_validation import (
    _coerce_enum,
    _freeze_metadata,
    _require_non_empty_text,
    _require_non_negative_int,
    _require_text_tuple,
    _validate_optional_text,
)


class ArtifactAvailabilityStatus(StrEnum):
    """Availability status for a stored artifact reference."""

    AVAILABLE = "AVAILABLE"
    NO_DATA = "NO_DATA"
    UNSUPPORTED = "UNSUPPORTED"


@dataclass(frozen=True, slots=True)
class ArtifactRef:
    """Reference to a large drillthrough artifact such as an IMA P&L vector."""

    run_id: str
    artifact_id: str
    component: FrtbComponent | str
    artifact_type: ArtifactType | str
    uri: str
    format: str
    row_count: int
    schema_fingerprint: str | None = None
    partition_keys: tuple[str, ...] = ()
    metadata: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _require_non_empty_text(self.run_id, "run_id")
        _require_non_empty_text(self.artifact_id, "artifact_id")
        object.__setattr__(
            self, "component", _coerce_enum(self.component, FrtbComponent, "component")
        )
        object.__setattr__(
            self,
            "artifact_type",
            _coerce_enum(self.artifact_type, ArtifactType, "artifact_type"),
        )
        _require_non_empty_text(self.uri, "uri")
        _require_non_empty_text(self.format, "format")
        _require_non_negative_int(self.row_count, "row_count")
        _validate_optional_text(self.schema_fingerprint, "schema_fingerprint")
        object.__setattr__(
            self,
            "partition_keys",
            _require_text_tuple(self.partition_keys, "partition_keys"),
        )
        _validate_artifact_availability(
            metadata=self.metadata,
            row_count=self.row_count,
            uri=self.uri,
            format=self.format,
        )
        _validate_partition_values(
            metadata=self.metadata,
            partition_keys=self.partition_keys,
        )
        _freeze_metadata(self, self.metadata)


@dataclass(frozen=True, slots=True)
class LineageRef:
    """Trace one stored result object back to an input, policy, or source hash."""

    run_id: str
    result_id: str
    source_type: str
    source_id: str
    relationship: str = "derived_from"
    source_hash: str | None = None
    metadata: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _require_non_empty_text(self.run_id, "run_id")
        _require_non_empty_text(self.result_id, "result_id")
        _require_non_empty_text(self.source_type, "source_type")
        _require_non_empty_text(self.source_id, "source_id")
        _require_non_empty_text(self.relationship, "relationship")
        _validate_optional_text(self.source_hash, "source_hash")
        _freeze_metadata(self, self.metadata)


def _validate_artifact_availability(
    *,
    metadata: Mapping[str, object],
    row_count: int,
    uri: str,
    format: str,
) -> None:
    raw_status = metadata.get("artifact_status", ArtifactAvailabilityStatus.AVAILABLE.value)
    try:
        status = ArtifactAvailabilityStatus(raw_status)
    except ValueError as exc:
        raise ResultStoreContractError(
            f"invalid artifact_status: {raw_status}",
            field="artifact_status",
        ) from exc
    reason = metadata.get("status_reason", "")
    if status is not ArtifactAvailabilityStatus.AVAILABLE:
        _require_non_empty_text(reason, "status_reason")
        if row_count != 0:
            raise ResultStoreContractError(
                "unavailable artifact refs must have row_count=0",
                field="row_count",
            )
        if format != "none":
            raise ResultStoreContractError(
                "unavailable artifact refs must use format='none'",
                field="format",
            )
        required_scheme = "no-data" if status is ArtifactAvailabilityStatus.NO_DATA else "unsupported"
        if urlparse(uri).scheme != required_scheme:
            raise ResultStoreContractError(
                f"{status.value} artifact refs must use {required_scheme}:// URIs",
                field="uri",
            )


def _validate_partition_values(
    *,
    metadata: Mapping[str, object],
    partition_keys: tuple[str, ...],
) -> None:
    if not partition_keys:
        return
    raw_partition_values = metadata.get("partition_values")
    if not isinstance(raw_partition_values, Mapping):
        raise ResultStoreContractError(
            "artifact refs with partition_keys require metadata.partition_values",
            field="metadata",
        )
    missing = sorted(key for key in partition_keys if key not in raw_partition_values)
    if missing:
        raise ResultStoreContractError(
            f"artifact partition value missing: {', '.join(missing)}",
            field="metadata",
        )
    for key in partition_keys:
        _require_non_empty_text(key, "partition_keys")
        _require_non_empty_text(raw_partition_values[key], "partition_values")
