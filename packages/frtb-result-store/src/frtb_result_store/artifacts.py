"""Strict artifact schemas and streaming Parquet writer helpers."""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from types import MappingProxyType
from urllib.parse import quote, urlparse
from urllib.request import url2pathname

import pyarrow as pa  # type: ignore[import-untyped]
import pyarrow.parquet as pq  # type: ignore[import-untyped]
from frtb_common.hashing import stable_json_hash

from frtb_result_store.model import (
    ArtifactRef,
    ArtifactType,
    CalculationRun,
    CapitalNode,
    FrtbComponent,
    ResultStoreContractError,
)

__all__ = [
    "ARTIFACT_SCHEMA_REGISTRY",
    "ArtifactSchemaEntry",
    "ArtifactWriteRequest",
    "COMMON_SCENARIO_VECTOR_METADATA_SCHEMA_ID",
    "COMMON_SHOCK_DEFINITION_SCHEMA_ID",
    "COMMON_SURFACE_GRID_SCHEMA_ID",
    "COMMON_TIME_SERIES_SCHEMA_ID",
    "IMA_PNL_VECTOR_SCHEMA_ID",
    "RequiredArtifactExpectation",
    "artifact_expectations_for_requests",
    "artifact_schema_fingerprint",
    "artifact_schema_for",
    "stage_artifact_write",
    "validate_artifact_ref_targets",
    "validate_artifact_ref_partitions",
    "validate_required_artifacts",
]

ARTIFACT_COMPRESSION = "zstd"
IMA_PNL_VECTOR_SCHEMA_ID = "ima.pnl_vector.v1"
COMMON_TIME_SERIES_SCHEMA_ID = "common.time_series.v1"
COMMON_SHOCK_DEFINITION_SCHEMA_ID = "common.shock_definition.v1"
COMMON_SCENARIO_VECTOR_METADATA_SCHEMA_ID = "common.scenario_vector_metadata.v1"
COMMON_SURFACE_GRID_SCHEMA_ID = "common.surface_grid.v1"
REQUIRED_ARTIFACTS_BY_COMPONENT: Mapping[FrtbComponent, tuple[ArtifactType, ...]] = {
    FrtbComponent.IMA: (ArtifactType.IMA_PNL_VECTOR,),
    FrtbComponent.SBM: (ArtifactType.SBM_SENSITIVITY_TABLE,),
    FrtbComponent.DRC: (ArtifactType.DRC_JTD_TABLE,),
    FrtbComponent.RRAO: (ArtifactType.RRAO_EXPOSURE_TABLE,),
    FrtbComponent.CVA: (ArtifactType.CVA_EXPOSURE_TABLE,),
}


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
        object.__setattr__(self, "artifact_type", _coerce_artifact_type(self.artifact_type))
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
        """Return the stable fingerprint for the registered Arrow schema.
        Returns
        -------
        str
            Result of the operation.
        """

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
        object.__setattr__(self, "component", _coerce_component(self.component))
        object.__setattr__(self, "artifact_type", _coerce_artifact_type(self.artifact_type))
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
        object.__setattr__(self, "artifact_type", _coerce_artifact_type(self.artifact_type))
        object.__setattr__(self, "component", _coerce_component(self.component))
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


def _coerce_artifact_type(value: ArtifactType | str) -> ArtifactType:
    try:
        return ArtifactType(value)
    except ValueError as exc:
        raise ResultStoreContractError(
            f"invalid artifact_type: {value}",
            field="artifact_type",
        ) from exc


def _coerce_component(value: FrtbComponent | str) -> FrtbComponent:
    try:
        return FrtbComponent(value)
    except ValueError as exc:
        raise ResultStoreContractError(
            f"invalid component: {value}",
            field="component",
        ) from exc


_IMA_PNL_VECTOR_FIELDS = (
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
)

_COMMON_TIME_SERIES_FIELDS = (
    ("run_id", pa.string(), False),
    ("time_series_id", pa.string(), False),
    ("observation_date", pa.date32(), False),
    ("value_name", pa.string(), False),
    ("value", pa.float64(), False),
    ("currency", pa.string(), True),
    ("risk_factor_id", pa.string(), True),
    ("scenario_id", pa.string(), True),
    ("mapping_version", pa.string(), True),
    ("source_row_id", pa.string(), False),
)

_COMMON_SHOCK_DEFINITION_FIELDS = (
    ("run_id", pa.string(), False),
    ("shock_id", pa.string(), False),
    ("shock_direction", pa.string(), False),
    ("shock_type", pa.string(), False),
    ("magnitude", pa.float64(), False),
    ("unit", pa.string(), False),
    ("risk_factor_id", pa.string(), True),
    ("scenario_id", pa.string(), True),
    ("mapping_version", pa.string(), True),
    ("regulatory_rule_id", pa.string(), True),
    ("source_row_id", pa.string(), False),
)

_COMMON_SCENARIO_VECTOR_METADATA_FIELDS = (
    ("run_id", pa.string(), False),
    ("scenario_set_id", pa.string(), False),
    ("scenario_vector_id", pa.string(), False),
    ("scenario_id", pa.string(), False),
    ("observation_date", pa.date32(), False),
    ("scenario_label", pa.string(), False),
    ("mapping_version", pa.string(), True),
    ("source_row_id", pa.string(), False),
)

_COMMON_SURFACE_GRID_FIELDS = (
    ("run_id", pa.string(), False),
    ("surface_id", pa.string(), False),
    ("surface_point_id", pa.string(), False),
    ("axis_1_name", pa.string(), False),
    ("axis_1_value", pa.string(), False),
    ("axis_2_name", pa.string(), False),
    ("axis_2_value", pa.string(), False),
    ("value_name", pa.string(), False),
    ("value", pa.float64(), False),
    ("unit", pa.string(), False),
    ("risk_factor_id", pa.string(), True),
    ("mapping_version", pa.string(), True),
    ("source_row_id", pa.string(), False),
)


def _required_columns(fields: tuple[tuple[str, pa.DataType, bool], ...]) -> tuple[str, ...]:
    return tuple(name for name, _, nullable in fields if not nullable)


def _nullable_columns(fields: tuple[tuple[str, pa.DataType, bool], ...]) -> tuple[str, ...]:
    return tuple(name for name, _, nullable in fields if nullable)

ARTIFACT_SCHEMA_REGISTRY: Mapping[str, ArtifactSchemaEntry] = MappingProxyType(
    {
        IMA_PNL_VECTOR_SCHEMA_ID: ArtifactSchemaEntry(
            schema_id=IMA_PNL_VECTOR_SCHEMA_ID,
            artifact_type=ArtifactType.IMA_PNL_VECTOR,
            schema_version=1,
            arrow_schema=pa.schema(_IMA_PNL_VECTOR_FIELDS),
            required_columns=_required_columns(_IMA_PNL_VECTOR_FIELDS),
            nullable_columns=_nullable_columns(_IMA_PNL_VECTOR_FIELDS),
            partition_columns=("desk_id", "portfolio_id", "book_id"),
        ),
        COMMON_TIME_SERIES_SCHEMA_ID: ArtifactSchemaEntry(
            schema_id=COMMON_TIME_SERIES_SCHEMA_ID,
            artifact_type=ArtifactType.TIME_SERIES,
            schema_version=1,
            arrow_schema=pa.schema(_COMMON_TIME_SERIES_FIELDS),
            required_columns=_required_columns(_COMMON_TIME_SERIES_FIELDS),
            nullable_columns=_nullable_columns(_COMMON_TIME_SERIES_FIELDS),
            partition_columns=("time_series_id",),
        ),
        COMMON_SHOCK_DEFINITION_SCHEMA_ID: ArtifactSchemaEntry(
            schema_id=COMMON_SHOCK_DEFINITION_SCHEMA_ID,
            artifact_type=ArtifactType.SHOCK_DEFINITION,
            schema_version=1,
            arrow_schema=pa.schema(_COMMON_SHOCK_DEFINITION_FIELDS),
            required_columns=_required_columns(_COMMON_SHOCK_DEFINITION_FIELDS),
            nullable_columns=_nullable_columns(_COMMON_SHOCK_DEFINITION_FIELDS),
            partition_columns=("shock_id",),
        ),
        COMMON_SCENARIO_VECTOR_METADATA_SCHEMA_ID: ArtifactSchemaEntry(
            schema_id=COMMON_SCENARIO_VECTOR_METADATA_SCHEMA_ID,
            artifact_type=ArtifactType.SCENARIO_VECTOR_METADATA,
            schema_version=1,
            arrow_schema=pa.schema(_COMMON_SCENARIO_VECTOR_METADATA_FIELDS),
            required_columns=_required_columns(_COMMON_SCENARIO_VECTOR_METADATA_FIELDS),
            nullable_columns=_nullable_columns(_COMMON_SCENARIO_VECTOR_METADATA_FIELDS),
            partition_columns=("scenario_set_id", "scenario_vector_id"),
        ),
        COMMON_SURFACE_GRID_SCHEMA_ID: ArtifactSchemaEntry(
            schema_id=COMMON_SURFACE_GRID_SCHEMA_ID,
            artifact_type=ArtifactType.SURFACE_GRID,
            schema_version=1,
            arrow_schema=pa.schema(_COMMON_SURFACE_GRID_FIELDS),
            required_columns=_required_columns(_COMMON_SURFACE_GRID_FIELDS),
            nullable_columns=_nullable_columns(_COMMON_SURFACE_GRID_FIELDS),
            partition_columns=("surface_id",),
        ),
    }
)


def artifact_schema_for(schema_id: str) -> ArtifactSchemaEntry:
    """Return a registered artifact schema or fail closed.
    Parameters
    ----------
    schema_id : str
        Schema id.

    Returns
    -------
    ArtifactSchemaEntry
        Result of the operation.
    """

    try:
        return ARTIFACT_SCHEMA_REGISTRY[schema_id]
    except KeyError as exc:
        raise ResultStoreContractError(f"unknown artifact schema: {schema_id}") from exc


def artifact_schema_fingerprint(entry: ArtifactSchemaEntry) -> str:
    """Generate a stable fingerprint for an artifact schema registry entry.
    Parameters
    ----------
    entry : ArtifactSchemaEntry
        Entry.

    Returns
    -------
    str
        Result of the operation.
    """

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


def artifact_expectations_for_requests(
    artifact_requests: Sequence[ArtifactWriteRequest],
) -> tuple[RequiredArtifactExpectation, ...]:
    return tuple(
        expectation
        for request in artifact_requests
        for expectation in request.conditional_expectations
    )


def validate_required_artifacts(
    nodes: Sequence[CapitalNode],
    artifacts: Sequence[ArtifactRef],
    artifact_expectations: Sequence[RequiredArtifactExpectation],
) -> None:
    present = {
        (FrtbComponent(artifact.component), ArtifactType(artifact.artifact_type))
        for artifact in artifacts
    }
    missing = [
        f"{component.value}:{artifact_type.value}"
        for component in sorted(_components_requiring_artifacts(nodes), key=lambda item: item.value)
        for artifact_type in REQUIRED_ARTIFACTS_BY_COMPONENT[component]
        if (component, artifact_type) not in present
    ]
    missing.extend(
        (
            f"{expectation.trigger_name}:{FrtbComponent(expectation.component).value}:"
            f"{ArtifactType(expectation.artifact_type).value}"
        )
        for expectation in artifact_expectations
        if expectation.required
        and (FrtbComponent(expectation.component), ArtifactType(expectation.artifact_type))
        not in present
    )
    if missing:
        raise ResultStoreContractError(
            f"missing required artifacts: {', '.join(missing)}",
            field="artifacts",
        )


def validate_artifact_ref_targets(artifacts: Sequence[ArtifactRef]) -> None:
    for artifact in artifacts:
        parsed = urlparse(artifact.uri)
        if parsed.scheme == "file":
            path = Path(url2pathname(parsed.path))
            if not path.is_file():
                raise ResultStoreContractError(
                    f"artifact ref points to missing local file: {artifact.artifact_id}",
                    field="uri",
                )



_METADATA_PARTITIONED_ARTIFACT_TYPES = frozenset(
    {
        ArtifactType.TIME_SERIES,
        ArtifactType.SHOCK_DEFINITION,
        ArtifactType.SCENARIO_VECTOR_METADATA,
        ArtifactType.SURFACE_GRID,
    }
)

def validate_artifact_ref_partitions(artifacts: Sequence[ArtifactRef]) -> None:
    """Reject duplicate semantic artifact partitions within one committed run."""

    seen: dict[tuple[str, tuple[tuple[str, str], ...]], str] = {}
    for artifact in artifacts:
        if not artifact.partition_keys:
            continue
        artifact_type = ArtifactType(artifact.artifact_type)
        if artifact_type not in _METADATA_PARTITIONED_ARTIFACT_TYPES:
            continue
        raw_partition_values = artifact.metadata.get("partition_values")
        if not isinstance(raw_partition_values, Mapping):
            continue
        key = (
            artifact_type.value,
            tuple(
                sorted((name, str(raw_partition_values[name])) for name in artifact.partition_keys)
            ),
        )
        prior = seen.get(key)
        if prior is not None:
            raise ResultStoreContractError(
                f"duplicate artifact partition for {artifact.artifact_id}: {prior}",
                field="artifacts",
            )
        seen[key] = artifact.artifact_id


def stage_artifact_write(
    *,
    run: CalculationRun,
    request: ArtifactWriteRequest,
    staging_dir: Path,
    final_root: Path,
    final_uri: str | None = None,
) -> StagedArtifact:
    """Validate and stage one artifact without materializing all chunks.
    Parameters
    ----------
    run : CalculationRun
        Run.
    request : ArtifactWriteRequest
        Request.
    staging_dir : Path
        Staging dir.
    final_root : Path
        Final root.
    final_uri : str | None, optional
        Final uri.

    Returns
    -------
    StagedArtifact
        Result of the operation.
    """

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
            uri=final_uri if final_uri is not None else final_path.resolve().as_uri(),
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


def _components_requiring_artifacts(nodes: Sequence[CapitalNode]) -> set[FrtbComponent]:
    return {
        component
        for node in nodes
        if (component := FrtbComponent(node.component)) in REQUIRED_ARTIFACTS_BY_COMPONENT
    }


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
