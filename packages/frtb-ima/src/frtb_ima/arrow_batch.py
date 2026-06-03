"""Arrow batch adapters for IMA tabular input lineage."""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from datetime import UTC, date, datetime
from typing import Any, cast

import numpy as np
import numpy.typing as npt
import pyarrow as pa  # type: ignore[import-untyped]
from frtb_common import (
    AdapterDiagnostic,
    ColumnSpec,
    NormalizedArrowTable,
    NullPolicy,
    TabularLogicalType,
    normalize_arrow_table,
    normalized_arrow_table_hash,
    read_arrow_columns,
    validate_arrow_table,
)

from frtb_ima.input_manifest import (
    CapitalRunInputManifest,
    InputArtifactLineage,
    InputValidationStatus,
)
from frtb_ima.rfet_evidence import RFETObservationBatch
from frtb_ima.scenario import ScenarioMetadataBatch, ScenarioSetType

BooleanArray = npt.NDArray[np.bool_]
DateArray = npt.NDArray[np.datetime64]
DatetimeArray = npt.NDArray[np.datetime64]
StringArray = npt.NDArray[np.str_]

IMA_INPUT_MANIFEST_ARROW_COLUMN_SPECS: tuple[ColumnSpec, ...] = (
    ColumnSpec("artifact_name", aliases=("artifactName",), logical_type=TabularLogicalType.STRING),
    ColumnSpec("artifact_type", aliases=("artifactType",), logical_type=TabularLogicalType.STRING),
    ColumnSpec(
        "schema_version",
        aliases=("schemaVersion",),
        logical_type=TabularLogicalType.STRING,
    ),
    ColumnSpec("source_system", aliases=("sourceSystem",), logical_type=TabularLogicalType.STRING),
    ColumnSpec(
        "source_version",
        aliases=("sourceVersion",),
        logical_type=TabularLogicalType.STRING,
    ),
    ColumnSpec(
        "extraction_timestamp",
        aliases=("extractionTimestamp",),
        logical_type=TabularLogicalType.TIMESTAMP,
    ),
    ColumnSpec("as_of_date", aliases=("asOfDate",), logical_type=TabularLogicalType.DATE),
    ColumnSpec("record_count", aliases=("recordCount",), logical_type=TabularLogicalType.INTEGER),
    ColumnSpec("vector_count", aliases=("vectorCount",), logical_type=TabularLogicalType.INTEGER),
    ColumnSpec("checksum", logical_type=TabularLogicalType.STRING),
    ColumnSpec(
        "sign_convention",
        aliases=("signConvention",),
        logical_type=TabularLogicalType.STRING,
    ),
    ColumnSpec(
        "validation_status",
        aliases=("validationStatus",),
        logical_type=TabularLogicalType.STRING,
        required=False,
        null_policy=NullPolicy.ALLOW,
    ),
    ColumnSpec(
        "validation_messages",
        aliases=("validationMessages",),
        logical_type=TabularLogicalType.STRING,
        required=False,
        null_policy=NullPolicy.ALLOW,
    ),
    ColumnSpec(
        "metadata_json",
        aliases=("metadataJson",),
        logical_type=TabularLogicalType.STRING,
        required=False,
        null_policy=NullPolicy.ALLOW,
    ),
    ColumnSpec(
        "source_row_id",
        aliases=("sourceRowId",),
        logical_type=TabularLogicalType.STRING,
        required=False,
        null_policy=NullPolicy.ALLOW,
    ),
)

IMA_SCENARIO_METADATA_ARROW_COLUMN_SPECS: tuple[ColumnSpec, ...] = (
    ColumnSpec("scenario_id", aliases=("scenarioId",), logical_type=TabularLogicalType.STRING),
    ColumnSpec(
        "scenario_date",
        aliases=("scenarioDate",),
        logical_type=TabularLogicalType.DATE,
    ),
    ColumnSpec(
        "scenario_set",
        aliases=("scenarioSet", "set_type", "setType"),
        logical_type=TabularLogicalType.STRING,
        required=False,
        null_policy=NullPolicy.ALLOW,
    ),
    ColumnSpec(
        "calibration_window",
        aliases=("calibrationWindow",),
        logical_type=TabularLogicalType.STRING,
        required=False,
        null_policy=NullPolicy.ALLOW,
    ),
    ColumnSpec(
        "source",
        logical_type=TabularLogicalType.STRING,
        required=False,
        null_policy=NullPolicy.ALLOW,
    ),
    ColumnSpec(
        "provenance_json",
        aliases=("provenanceJson",),
        logical_type=TabularLogicalType.STRING,
        required=False,
        null_policy=NullPolicy.ALLOW,
    ),
    ColumnSpec(
        "source_row_id",
        aliases=("sourceRowId",),
        logical_type=TabularLogicalType.STRING,
        required=False,
        null_policy=NullPolicy.ALLOW,
    ),
)

IMA_RFET_OBSERVATION_ARROW_COLUMN_SPECS: tuple[ColumnSpec, ...] = (
    ColumnSpec(
        "risk_factor_name",
        aliases=("riskFactorName",),
        logical_type=TabularLogicalType.STRING,
    ),
    ColumnSpec(
        "observation_date",
        aliases=("observationDate",),
        logical_type=TabularLogicalType.DATE,
    ),
    ColumnSpec(
        "source",
        logical_type=TabularLogicalType.STRING,
        required=False,
        null_policy=NullPolicy.ALLOW,
    ),
    ColumnSpec(
        "vendor_id",
        aliases=("vendorId",),
        logical_type=TabularLogicalType.STRING,
        required=False,
        null_policy=NullPolicy.ALLOW,
    ),
    ColumnSpec(
        "venue",
        logical_type=TabularLogicalType.STRING,
        required=False,
        null_policy=NullPolicy.ALLOW,
    ),
    ColumnSpec(
        "feed",
        logical_type=TabularLogicalType.STRING,
        required=False,
        null_policy=NullPolicy.ALLOW,
    ),
    ColumnSpec(
        "observation_timestamp",
        aliases=("observationTimestamp",),
        logical_type=TabularLogicalType.TIMESTAMP,
        required=False,
        null_policy=NullPolicy.ALLOW,
    ),
    ColumnSpec(
        "date_normalization_evidence",
        aliases=("dateNormalizationEvidence",),
        logical_type=TabularLogicalType.STRING,
        required=False,
        null_policy=NullPolicy.ALLOW,
    ),
    ColumnSpec(
        "verifiable",
        logical_type=TabularLogicalType.BOOLEAN,
        required=False,
        null_policy=NullPolicy.ALLOW,
    ),
    ColumnSpec(
        "verifiability_reason",
        aliases=("verifiabilityReason",),
        logical_type=TabularLogicalType.STRING,
        required=False,
        null_policy=NullPolicy.ALLOW,
    ),
    ColumnSpec(
        "data_pool_id",
        aliases=("dataPoolId",),
        logical_type=TabularLogicalType.STRING,
        required=False,
        null_policy=NullPolicy.ALLOW,
    ),
    ColumnSpec(
        "vendor_audit_evidence_id",
        aliases=("vendorAuditEvidenceId",),
        logical_type=TabularLogicalType.STRING,
        required=False,
        null_policy=NullPolicy.ALLOW,
    ),
    ColumnSpec(
        "source_row_id",
        aliases=("sourceRowId",),
        logical_type=TabularLogicalType.STRING,
        required=False,
        null_policy=NullPolicy.ALLOW,
    ),
)
_IMA_SCENARIO_METADATA_BATCH_COLUMN_ARGS: Mapping[str, str] = {
    "scenario_id": "scenario_ids",
    "scenario_set": "scenario_sets",
    "calibration_window": "calibration_windows",
    "source": "sources",
    "provenance_json": "provenance_json",
    "source_row_id": "source_row_ids",
}

_IMA_RFET_OBSERVATION_BATCH_COLUMN_ARGS: Mapping[str, str] = {
    "risk_factor_name": "risk_factor_names",
    "source": "sources",
    "vendor_id": "vendor_ids",
    "venue": "venues",
    "feed": "feeds",
    "date_normalization_evidence": "date_normalization_evidence",
    "verifiable": "verifiable",
    "verifiability_reason": "verifiability_reasons",
    "data_pool_id": "data_pool_ids",
    "vendor_audit_evidence_id": "vendor_audit_evidence_ids",
    "source_row_id": "source_row_ids",
}

_IMA_SCENARIO_METADATA_DEFAULTS: Mapping[str, object] = {
    "scenario_set": ScenarioSetType.CURRENT.value,
    "calibration_window": "",
    "source": "",
    "provenance_json": "",
    "source_row_id": "",
}

_IMA_RFET_OBSERVATION_DEFAULTS: Mapping[str, object] = {
    "source": "",
    "vendor_id": "",
    "venue": "",
    "feed": "",
    "date_normalization_evidence": "",
    "verifiable": True,
    "verifiability_reason": "",
    "data_pool_id": "",
    "vendor_audit_evidence_id": "",
    "source_row_id": "",
}

_IMA_LOCAL_LOGICAL_TYPES = frozenset(
    {
        TabularLogicalType.DATE,
        TabularLogicalType.TIMESTAMP,
    }
)


def _ensure_explicit_logical_types(*spec_groups: Sequence[ColumnSpec]) -> None:
    unknown = tuple(
        spec.name
        for spec_group in spec_groups
        for spec in spec_group
        if spec.logical_type is TabularLogicalType.UNKNOWN
    )
    if unknown:
        raise RuntimeError("IMA Arrow specs must declare logical_type: " + ", ".join(unknown))


_ensure_explicit_logical_types(
    IMA_INPUT_MANIFEST_ARROW_COLUMN_SPECS,
    IMA_SCENARIO_METADATA_ARROW_COLUMN_SPECS,
    IMA_RFET_OBSERVATION_ARROW_COLUMN_SPECS,
)


def normalize_ima_input_manifest_arrow_table(
    table: pa.Table,
    *,
    diagnostics: Sequence[AdapterDiagnostic] = (),
    metadata: Mapping[str, str] | None = None,
    rejected: pa.Table | None = None,
    source_hash: str | None = None,
) -> NormalizedArrowTable:
    """Normalize an Arrow artifact-lineage table for IMA input manifest construction."""

    return normalize_arrow_table(
        table,
        column_specs=IMA_INPUT_MANIFEST_ARROW_COLUMN_SPECS,
        rejected=rejected,
        diagnostics=diagnostics,
        metadata={} if metadata is None else metadata,
        source_hash=source_hash,
        require_unique_row_ids=False,
    )


def normalize_ima_scenario_metadata_arrow_table(
    table: pa.Table,
    *,
    diagnostics: Sequence[AdapterDiagnostic] = (),
    metadata: Mapping[str, str] | None = None,
    rejected: pa.Table | None = None,
    source_hash: str | None = None,
) -> NormalizedArrowTable:
    """Normalize an Arrow scenario metadata table for IMA scenario-axis tables."""

    return normalize_arrow_table(
        table,
        column_specs=IMA_SCENARIO_METADATA_ARROW_COLUMN_SPECS,
        rejected=rejected,
        diagnostics=diagnostics,
        metadata={} if metadata is None else metadata,
        source_hash=source_hash,
        require_unique_row_ids=False,
    )


def normalize_ima_rfet_observation_arrow_table(
    table: pa.Table,
    *,
    diagnostics: Sequence[AdapterDiagnostic] = (),
    metadata: Mapping[str, str] | None = None,
    rejected: pa.Table | None = None,
    source_hash: str | None = None,
) -> NormalizedArrowTable:
    """Normalize an Arrow real-price observation table for RFET input tables."""

    return normalize_arrow_table(
        table,
        column_specs=IMA_RFET_OBSERVATION_ARROW_COLUMN_SPECS,
        rejected=rejected,
        diagnostics=diagnostics,
        metadata={} if metadata is None else metadata,
        source_hash=source_hash,
        require_unique_row_ids=False,
    )


def build_scenario_metadata_batch_from_arrow(
    handoff: NormalizedArrowTable,
) -> ScenarioMetadataBatch:
    """Build a columnar IMA scenario metadata batch from a normalized Arrow table."""

    if not isinstance(handoff, NormalizedArrowTable):
        raise ValueError("handoff must be NormalizedArrowTable")
    table = handoff.accepted
    columns = _read_ima_arrow_columns(table, IMA_SCENARIO_METADATA_ARROW_COLUMN_SPECS)
    return ScenarioMetadataBatch(
        scenario_dates=_date_column(table, "scenario_date"),
        **_ima_batch_column_kwargs(
            columns,
            _IMA_SCENARIO_METADATA_BATCH_COLUMN_ARGS,
            row_count=table.num_rows,
            defaults=_IMA_SCENARIO_METADATA_DEFAULTS,
        ),
        source_hash=handoff.source_hash,
        handoff_hash=normalized_arrow_table_hash(handoff),
    )


def build_rfet_observation_batch_from_arrow(
    handoff: NormalizedArrowTable,
) -> RFETObservationBatch:
    """Build a columnar RFET observation batch from a normalized Arrow table."""

    if not isinstance(handoff, NormalizedArrowTable):
        raise ValueError("handoff must be NormalizedArrowTable")
    table = handoff.accepted
    columns = _read_ima_arrow_columns(table, IMA_RFET_OBSERVATION_ARROW_COLUMN_SPECS)
    return RFETObservationBatch(
        observation_dates=_date_column(table, "observation_date"),
        observation_timestamps=_timestamp_column(table, "observation_timestamp"),
        **_ima_batch_column_kwargs(
            columns,
            _IMA_RFET_OBSERVATION_BATCH_COLUMN_ARGS,
            row_count=table.num_rows,
            defaults=_IMA_RFET_OBSERVATION_DEFAULTS,
        ),
        source_hash=handoff.source_hash,
        handoff_hash=normalized_arrow_table_hash(handoff),
    )


def build_capital_run_input_manifest_from_arrow(
    handoff: NormalizedArrowTable,
    *,
    run_id: str | None = None,
    as_of_date: date | datetime | str | None = None,
    schema_version: str | None = None,
    metadata: Mapping[str, str] | None = None,
) -> CapitalRunInputManifest:
    """Build an IMA capital-run input manifest from a normalized Arrow table."""

    if not isinstance(handoff, NormalizedArrowTable):
        raise ValueError("handoff must be NormalizedArrowTable")
    table = handoff.accepted
    columns = _read_ima_arrow_columns(table, IMA_INPUT_MANIFEST_ARROW_COLUMN_SPECS)

    artifacts = _artifact_lineages_from_table(table, columns)
    manifest_as_of = _manifest_as_of_date(
        as_of_date,
        metadata_value=handoff.metadata.get("as_of_date"),
        artifacts=artifacts,
    )
    manifest_metadata = {
        key: value
        for key, value in handoff.metadata.items()
        if key not in {"run_id", "as_of_date", "manifest_schema_version"}
    }
    if handoff.source_hash is not None:
        manifest_metadata["source_hash"] = handoff.source_hash
    if metadata is not None:
        manifest_metadata.update(metadata)

    manifest_schema_version = schema_version or handoff.metadata.get("manifest_schema_version")
    if manifest_schema_version is None:
        return CapitalRunInputManifest(
            run_id=_manifest_run_id(run_id, handoff.metadata.get("run_id")),
            as_of_date=manifest_as_of,
            artifacts=tuple(sorted(artifacts, key=lambda artifact: artifact.artifact_name)),
            metadata=manifest_metadata,
        )

    return CapitalRunInputManifest(
        run_id=_manifest_run_id(run_id, handoff.metadata.get("run_id")),
        as_of_date=manifest_as_of,
        artifacts=tuple(sorted(artifacts, key=lambda artifact: artifact.artifact_name)),
        metadata=manifest_metadata,
        schema_version=manifest_schema_version,
    )


def _artifact_lineages_from_table(
    table: pa.Table,
    columns: Mapping[str, object],
) -> tuple[InputArtifactLineage, ...]:
    optional_statuses = _optional_column_values(columns, "validation_status")
    optional_messages = _optional_column_values(columns, "validation_messages")
    optional_metadata = _optional_column_values(columns, "metadata_json")
    optional_source_rows = _optional_column_values(columns, "source_row_id")
    artifacts: list[InputArtifactLineage] = []
    for index in range(table.num_rows):
        row_metadata = _metadata_json_at(optional_metadata, index)
        source_row_id = _optional_text_at(optional_source_rows, index)
        if source_row_id is not None:
            row_metadata["source_row_id"] = source_row_id
        artifacts.append(
            InputArtifactLineage(
                artifact_name=_required_text_at(columns, "artifact_name", index),
                artifact_type=_required_text_at(columns, "artifact_type", index),
                schema_version=_required_text_at(columns, "schema_version", index),
                source_system=_required_text_at(columns, "source_system", index),
                source_version=_required_text_at(columns, "source_version", index),
                extraction_timestamp=_datetime_at(table, "extraction_timestamp", index),
                as_of_date=_date_at(table, "as_of_date", index),
                record_count=_non_negative_int_at(columns, "record_count", index),
                vector_count=_non_negative_int_at(columns, "vector_count", index),
                checksum=_required_text_at(columns, "checksum", index),
                sign_convention=_required_text_at(columns, "sign_convention", index),
                validation_status=InputValidationStatus(
                    _optional_text_at(optional_statuses, index)
                    or InputValidationStatus.PASSED.value
                ),
                validation_messages=_messages_at(optional_messages, index),
                metadata=row_metadata,
            )
        )
    return tuple(artifacts)


def _manifest_run_id(explicit: str | None, metadata_value: str | None) -> str:
    run_id = explicit or metadata_value
    if run_id is None or not run_id:
        raise ValueError("run_id must be supplied or present in handoff metadata")
    return run_id


def _manifest_as_of_date(
    explicit: date | datetime | str | None,
    *,
    metadata_value: str | None,
    artifacts: tuple[InputArtifactLineage, ...],
) -> date:
    if explicit is not None:
        return _parse_date(explicit, "as_of_date")
    if metadata_value is not None:
        return _parse_date(metadata_value, "as_of_date")
    artifact_dates = {artifact.as_of_date for artifact in artifacts}
    if len(artifact_dates) == 1:
        return next(iter(artifact_dates))
    raise ValueError("as_of_date must be supplied when artifact rows have multiple dates")


def _read_ima_arrow_columns(
    table: pa.Table,
    column_specs: tuple[ColumnSpec, ...],
) -> Mapping[str, object]:
    validate_arrow_table(table, column_specs=column_specs)
    columns: Mapping[str, object] = read_arrow_columns(
        table,
        _ima_reader_specs(column_specs),
        error=_ima_error,
        null_defaults=_ima_null_defaults(column_specs),
    )
    return columns


def _ima_reader_specs(column_specs: tuple[ColumnSpec, ...]) -> tuple[ColumnSpec, ...]:
    return tuple(spec for spec in column_specs if spec.logical_type not in _IMA_LOCAL_LOGICAL_TYPES)


def _ima_null_defaults(column_specs: Sequence[ColumnSpec]) -> Mapping[str, object]:
    spec_names = {spec.name for spec in column_specs}
    if "risk_factor_name" in spec_names:
        defaults = _IMA_RFET_OBSERVATION_DEFAULTS
    elif "scenario_id" in spec_names:
        defaults = _IMA_SCENARIO_METADATA_DEFAULTS
    else:
        defaults = {}
    return {name: default for name, default in defaults.items() if name in spec_names}


def _ima_batch_column_kwargs(
    columns: Mapping[str, object],
    column_args: Mapping[str, str],
    *,
    row_count: int,
    defaults: Mapping[str, object],
) -> dict[str, Any]:
    kwargs: dict[str, Any] = {}
    for column_name, argument_name in column_args.items():
        default = defaults.get(column_name)
        if isinstance(default, bool):
            kwargs[argument_name] = _bool_column_from_columns(
                columns,
                column_name,
                row_count=row_count,
                default=default,
            )
        else:
            kwargs[argument_name] = _string_column_from_columns(
                columns,
                column_name,
                row_count=row_count,
                default=cast(str | None, default),
            )
    return kwargs


def _string_column_from_columns(
    columns: Mapping[str, object],
    column_name: str,
    *,
    row_count: int,
    default: str | None = None,
) -> StringArray:
    values = columns.get(column_name)
    if values is None:
        if default is None:
            raise ValueError(f"column is required: {column_name}")
        return np.full(row_count, default, dtype=f"<U{max(1, len(default))}")
    fill = "" if default is None else default
    array = np.asarray(values, dtype=object)
    mask = np.equal(array, np.array(None, dtype=object))
    if bool(np.any(mask)):
        array = array.copy()
        array[mask] = fill
    return cast(StringArray, array.astype(np.str_))


def _bool_column_from_columns(
    columns: Mapping[str, object],
    column_name: str,
    *,
    row_count: int,
    default: bool,
) -> BooleanArray:
    values = columns.get(column_name)
    if values is None:
        return np.full(row_count, default, dtype=np.bool_)
    return cast(BooleanArray, np.asarray(values, dtype=np.bool_))


def _required_column_value(columns: Mapping[str, object], column_name: str, index: int) -> object:
    values = columns.get(column_name)
    if values is None:
        raise ValueError(f"column is required: {column_name}")
    return cast(Sequence[object], values)[index]


def _optional_column_values(
    columns: Mapping[str, object],
    column_name: str,
) -> Sequence[object | None] | None:
    values = columns.get(column_name)
    if values is None:
        return None
    return cast(Sequence[object | None], values)


def _required_text_at(columns: Mapping[str, object], column_name: str, index: int) -> str:
    value = _required_column_value(columns, column_name, index)
    if not isinstance(value, str) or not value:
        raise ValueError(f"{column_name} must contain non-empty text")
    return value


def _optional_text_at(values: Sequence[object | None] | None, index: int) -> str | None:
    if values is None:
        return None
    value = values[index]
    if value is None:
        return None
    text = str(value)
    return text or None


def _datetime_at(table: pa.Table, column_name: str, index: int) -> datetime:
    value = _required_table_column(table, column_name)[index]
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    raise ValueError(f"{column_name} must contain datetimes or ISO-8601 datetime text")


def _date_at(table: pa.Table, column_name: str, index: int) -> date:
    value = _required_table_column(table, column_name)[index]
    return _parse_date(value, column_name)


def _parse_date(value: object, field: str) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        return date.fromisoformat(value)
    raise ValueError(f"{field} must contain dates or ISO-8601 date text")


def _non_negative_int_at(columns: Mapping[str, object], column_name: str, index: int) -> int:
    value = _required_column_value(columns, column_name, index)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{column_name} must contain integers")
    integer = int(value)
    if integer < 0:
        raise ValueError(f"{column_name} must be non-negative")
    if isinstance(value, float) and value != integer:
        raise ValueError(f"{column_name} must contain whole-number values")
    return integer


def _messages_at(values: Sequence[object | None] | None, index: int) -> tuple[str, ...]:
    text = _optional_text_at(values, index)
    if text is None:
        return ()
    stripped = text.lstrip()
    if not stripped.startswith("["):
        return (text,)
    try:
        parsed = json.loads(stripped)
    except json.JSONDecodeError as err:
        raise ValueError(f"validation_messages contains invalid JSON: {err}") from err
    if isinstance(parsed, list):
        return tuple(str(item) for item in parsed)
    return (str(parsed),)


def _metadata_json_at(values: Sequence[object | None] | None, index: int) -> dict[str, str]:
    text = _optional_text_at(values, index)
    if text is None:
        return {}
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError as err:
        raise ValueError(f"metadata_json contains invalid JSON: {err}") from err
    if not isinstance(parsed, dict):
        raise ValueError("metadata_json must contain a JSON object")
    metadata: dict[str, str] = {}
    for key, value in parsed.items():
        if not isinstance(key, str) or not key:
            raise ValueError("metadata_json keys must be non-empty strings")
        if not isinstance(value, str):
            raise ValueError("metadata_json values must be strings")
        metadata[key] = value
    return metadata


def _required_table_column(table: pa.Table, column_name: str) -> list[object]:
    if column_name not in table.column_names:
        raise ValueError(f"column is required: {column_name}")
    return cast(list[object], table.column(column_name).to_pylist())


def _date_column(table: pa.Table, column_name: str) -> DateArray:
    if column_name not in table.column_names:
        raise ValueError(f"column is required: {column_name}")
    array = _single_array(table.column(column_name))
    if pa.types.is_date(array.type) or pa.types.is_timestamp(array.type):
        return np.asarray(array.to_numpy(zero_copy_only=False), dtype="datetime64[D]")
    values = array.to_pylist()
    return np.asarray([_parse_date(value, column_name) for value in values], dtype="datetime64[D]")


def _timestamp_column(table: pa.Table, column_name: str) -> DatetimeArray:
    if column_name not in table.column_names:
        return np.full(table.num_rows, np.datetime64("NaT", "us"), dtype="datetime64[us]")
    array = _single_array(table.column(column_name))
    if pa.types.is_timestamp(array.type):
        return np.asarray(array.to_numpy(zero_copy_only=False), dtype="datetime64[us]")
    values = array.to_pylist()
    timestamps: list[np.datetime64] = []
    for value in values:
        if value is None:
            timestamps.append(np.datetime64("NaT", "us"))
        elif isinstance(value, datetime):
            timestamps.append(np.datetime64(_timestamp_to_utc_naive(value), "us"))
        elif isinstance(value, str):
            timestamps.append(
                np.datetime64(
                    _timestamp_to_utc_naive(datetime.fromisoformat(value.replace("Z", "+00:00"))),
                    "us",
                )
            )
        else:
            raise ValueError(f"{column_name} must contain timestamps or ISO-8601 text")
    return np.asarray(timestamps, dtype="datetime64[us]")


def _timestamp_to_utc_naive(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value
    return value.astimezone(UTC).replace(tzinfo=None)


def _single_array(column: pa.ChunkedArray) -> pa.Array:
    return column.chunk(0) if column.num_chunks == 1 else column.combine_chunks()


def _ima_error(message: str, _field: str | None) -> ValueError:
    return ValueError(message)


__all__ = [
    "IMA_INPUT_MANIFEST_ARROW_COLUMN_SPECS",
    "IMA_RFET_OBSERVATION_ARROW_COLUMN_SPECS",
    "IMA_SCENARIO_METADATA_ARROW_COLUMN_SPECS",
    "build_capital_run_input_manifest_from_arrow",
    "build_rfet_observation_batch_from_arrow",
    "build_scenario_metadata_batch_from_arrow",
    "normalize_ima_input_manifest_arrow_table",
    "normalize_ima_rfet_observation_arrow_table",
    "normalize_ima_scenario_metadata_arrow_table",
]
