"""Artifact and lineage reference dataclasses."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field

from frtb_result_store.model_enums import ArtifactType, FrtbComponent
from frtb_result_store.model_validation import (
    _coerce_enum,
    _freeze_metadata,
    _require_non_empty_text,
    _require_non_negative_int,
    _require_text_tuple,
    _validate_optional_text,
)


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
