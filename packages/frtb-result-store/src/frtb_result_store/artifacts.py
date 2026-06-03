"""Strict artifact schemas and streaming Parquet writer helpers."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from types import MappingProxyType
from urllib.parse import quote

import pyarrow as pa  # type: ignore[import-untyped]
import pyarrow.parquet as pq  # type: ignore[import-untyped]
from frtb_common.hashing import stable_json_hash

from frtb_result_store.model import (
    ArtifactRef,
    ArtifactType,
    CalculationRun,
    FrtbComponent,
    ResultStoreContractError,
)

__all__ = [
    "ARTIFACT_SCHEMA_REGISTRY",
    "ArtifactSchemaEntry",
    "ArtifactWriteRequest",
    "RequiredArtifactExpectation",
    "artifact_schema_fingerprint",
    "artifact_schema_for",
    "stage_artifact_write",
]

ARTIFACT_COMPRESSION = "zstd"
IMA_PNL_VECTOR_SCHEMA_ID = "ima.pnl_vector.v1"


@dataclass(frozen=True, slots=True)
class ArtifactSchemaEntry:
    """Strict schema registry entry for one artifact type/version."""

    schema_id: str
    artifact_type: ArtifactType | str
    schema_version: int
    arrow_schema: pa.Schema
    required_columns: tuple[str, ...]
    nullable_columns: tuple[str, ...] = ()
    partition_columns: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _require_non_empty_text(self.schema_id, "schema_id")
        object.__setattr__(self, "artifact_type", ArtifactType(self.artifact_type))
        if not isinstance(self.schema_version, int) or self.schema_version < 1:
            raise ResultStoreContractError(
                "schema_version must be a positive integer",
                field="schema_version",
            )
        if not isinstance(self.arrow_schema, pa.Schema):
            raise ResultStoreContractError("arrow_schema must be a pyarrow schema")
        field_names = tuple(self.arrow_schema.names)
        for field_name in self.required_columns + self.nullable_columns + self.partition_columns:
            if field_name not in field_names:
                raise ResultStoreContractError(
                    f"schema column not found: {field_name}",
                    field=field_name,
                )

    @property
    def schema_fingerprint(self) -> str:
        """Return the stable fingerprint for the registered Arrow schema."""

        return artifact_schema_fingerprint(self)


@dataclass(frozen=True, slots=True)
class RequiredArtifactExpectation:
    """Declared trigger for later required-artifact validation."""

    component: FrtbComponent | str
    artifact_type: ArtifactType | str
    trigger_name: str
    required: bool
    reason: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "component", FrtbComponent(self.component))
        object.__setattr__(self, "artifact_type", ArtifactType(self.artifact_type))
        _require_non_empty_text(self.trigger_name, "trigger_name")
        if not isinstance(self.required, bool):
            raise ResultStoreContractError("required must be boolean", field="required")
        _require_non_empty_text(self.reason, "reason")


@dataclass(frozen=True, slots=True)
class ArtifactWriteRequest:
    """Streaming request to write one strict Parquet artifact."""

    artifact_id_hint: str
    artifact_type: ArtifactType | str
    component: FrtbComponent | str
    schema_id: str
    chunks: Iterable[pa.Table]
    partition_values: Mapping[str, object]
    required: bool = True
    metadata: Mapping[str, object] = field(default_factory=dict)
    conditional_expectations: tuple[RequiredArtifactExpectation, ...] = ()

    def __post_init__(self) -> None:
        _require_non_empty_text(self.artifact_id_hint, "artifact_id_hint")
        object.__setattr__(self, "artifact_type", ArtifactType(self.artifact_type))
        object.__setattr__(self, "component", FrtbComponent(self.component))
        _require_non_empty_text(self.schema_id, "schema_id")
        if not isinstance(self.partition_values, Mapping):
            raise ResultStoreContractError("partition_values must be a mapping")
        if not isinstance(self.required, bool):
            raise ResultStoreContractError("required must be boolean", field="required")
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))
        object.__setattr__(
            self,
            "conditional_expectations",
            tuple(self.conditional_expectations),
        )


@dataclass(frozen=True, slots=True)
class StagedArtifact:
    """Artifact data staged before run commit finalization."""

    ref: ArtifactRef
    staged_path: Path
    final_path: Path


def _require_non_empty_text(value: object, field: str) -> None:
    if not isinstance(value, str) or not value:
        raise ResultStoreContractError(f"{field} must be non-empty text", field=field)


ARTIFACT_SCHEMA_REGISTRY: Mapping[str, ArtifactSchemaEntry] = MappingProxyType(
    {
        IMA_PNL_VECTOR_SCHEMA_ID: ArtifactSchemaEntry(
            schema_id=IMA_PNL_VECTOR_SCHEMA_ID,
            artifact_type=ArtifactType.IMA_PNL_VECTOR,
            schema_version=1,
            arrow_schema=pa.schema(
                [
                    ("run_id", pa.string(), False),
                    ("desk_id", pa.string(), False),
                    ("portfolio_id", pa.string(), False),
                    ("book_id", pa.string(), False),
                    ("position_id", pa.string(), False),
                    ("risk_factor_id", pa.string(), False),
                    ("risk_factor_set_id", pa.string(), True),
                    ("scenario_id", pa.string(), False),
                    ("observation_date", pa.date32(), False),
                    ("liquidity_horizon", pa.int32(), False),
                    ("pnl_amount", pa.float64(), False),
                    ("currency", pa.string(), False),
                    ("tail_flag", pa.bool_(), False),
                    ("source_row_id", pa.string(), False),
                ]
            ),
            required_columns=(
                "run_id",
                "desk_id",
                "portfolio_id",
                "book_id",
                "position_id",
                "risk_factor_id",
                "scenario_id",
                "observation_date",
                "liquidity_horizon",
                "pnl_amount",
                "currency",
                "tail_flag",
                "source_row_id",
            ),
            nullable_columns=("risk_factor_set_id",),
            partition_columns=("desk_id", "portfolio_id", "book_id"),
        )
    }
)


def artifact_schema_for(schema_id: str) -> ArtifactSchemaEntry:
    """Return a registered artifact schema or fail closed."""

    try:
        return ARTIFACT_SCHEMA_REGISTRY[schema_id]
    except KeyError as exc:
        raise ResultStoreContractError(f"unknown artifact schema: {schema_id}") from exc


def artifact_schema_fingerprint(entry: ArtifactSchemaEntry) -> str:
    """Generate a stable fingerprint for an artifact schema registry entry."""

    payload = {
        "schema_id": entry.schema_id,
        "artifact_type": ArtifactType(entry.artifact_type).value,
        "schema_version": entry.schema_version,
        "fields": [
            {
                "name": field.name,
                "type": str(field.type),
                "nullable": field.nullable,
            }
            for field in entry.arrow_schema
        ],
        "required_columns": entry.required_columns,
        "nullable_columns": entry.nullable_columns,
        "partition_columns": entry.partition_columns,
    }
    return stable_json_hash(payload)


def stage_artifact_write(
    *,
    run: CalculationRun,
    request: ArtifactWriteRequest,
    staging_dir: Path,
    final_root: Path,
) -> StagedArtifact:
    """Validate and stage one artifact without materializing all chunks."""

    entry = artifact_schema_for(request.schema_id)
    _validate_request_matches_schema(request, entry)
    artifact_id = _artifact_id(run, request, entry)
    staged_path = staging_dir / "artifacts" / f"{_safe_path_name(artifact_id)}.parquet"
    final_path = (
        final_root
        / f"artifact_type={ArtifactType(request.artifact_type).value}"
        / f"run_id={_safe_path_name(run.run_id)}"
        / f"artifact_id={_safe_path_name(artifact_id)}"
        / "data.parquet"
    )
    staged_path.parent.mkdir(parents=True, exist_ok=True)
    row_count, chunk_count = _write_validated_chunks(request.chunks, entry, staged_path)
    metadata = {
        **dict(request.metadata),
        "byte_count": staged_path.stat().st_size,
        "compression": ARTIFACT_COMPRESSION,
        "schema_id": entry.schema_id,
        "schema_version": entry.schema_version,
        "chunk_count": chunk_count,
        "partition_values": dict(request.partition_values),
        "required": request.required,
    }
    return StagedArtifact(
        ref=ArtifactRef(
            run_id=run.run_id,
            artifact_id=artifact_id,
            component=request.component,
            artifact_type=request.artifact_type,
            uri=final_path.resolve().as_uri(),
            format="parquet",
            row_count=row_count,
            schema_fingerprint=entry.schema_fingerprint,
            partition_keys=entry.partition_columns,
            metadata=metadata,
        ),
        staged_path=staged_path,
        final_path=final_path,
    )


def _validate_request_matches_schema(
    request: ArtifactWriteRequest,
    entry: ArtifactSchemaEntry,
) -> None:
    if request.artifact_type != entry.artifact_type:
        raise ResultStoreContractError(
            "artifact_type does not match schema registry entry",
            field="artifact_type",
        )
    missing_partitions = sorted(
        column for column in entry.partition_columns if column not in request.partition_values
    )
    if missing_partitions:
        raise ResultStoreContractError(
            f"missing artifact partition values: {', '.join(missing_partitions)}",
            field="partition_values",
        )


def _write_validated_chunks(
    chunks: Iterable[pa.Table],
    entry: ArtifactSchemaEntry,
    path: Path,
) -> tuple[int, int]:
    writer: pq.ParquetWriter | None = None
    row_count = 0
    chunk_count = 0
    try:
        for chunk in chunks:
            _validate_chunk(chunk, entry)
            if writer is None:
                writer = pq.ParquetWriter(
                    path,
                    entry.arrow_schema,
                    compression=ARTIFACT_COMPRESSION,
                )
            writer.write_table(chunk)
            row_count += chunk.num_rows
            chunk_count += 1
    finally:
        if writer is not None:
            writer.close()
    if chunk_count == 0:
        raise ResultStoreContractError("artifact chunks must be non-empty", field="chunks")
    return row_count, chunk_count


def _validate_chunk(chunk: object, entry: ArtifactSchemaEntry) -> None:
    if not isinstance(chunk, pa.Table):
        raise ResultStoreContractError("artifact chunk must be a pyarrow Table")
    if not chunk.schema.equals(entry.arrow_schema, check_metadata=False):
        raise ResultStoreContractError(
            "artifact chunk schema does not match registry schema",
            field="chunks",
        )


def _artifact_id(
    run: CalculationRun,
    request: ArtifactWriteRequest,
    entry: ArtifactSchemaEntry,
) -> str:
    payload = {
        "run_id": run.run_id,
        "artifact_id_hint": request.artifact_id_hint,
        "artifact_type": ArtifactType(request.artifact_type).value,
        "schema_fingerprint": entry.schema_fingerprint,
        "partition_values": dict(request.partition_values),
    }
    return f"{ArtifactType(request.artifact_type).value}:{stable_json_hash(payload)}"


def _safe_path_name(value: str) -> str:
    return quote(value, safe="")
