"""Arrow handoff adapters for IMA tabular input lineage."""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from datetime import UTC, date, datetime
from typing import cast

import numpy as np
import numpy.typing as npt
import pyarrow as pa  # type: ignore[import-untyped]
import pyarrow.compute as pc  # type: ignore[import-untyped]
from frtb_common import (
    AdapterDiagnostic,
    ColumnSpec,
    NormalizedTabularHandoff,
    NullPolicy,
    TabularLogicalType,
    normalize_arrow_table,
    normalized_handoff_hash,
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

IMA_INPUT_MANIFEST_HANDOFF_COLUMN_SPECS: tuple[ColumnSpec, ...] = (
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

IMA_SCENARIO_METADATA_HANDOFF_COLUMN_SPECS: tuple[ColumnSpec, ...] = (
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

IMA_RFET_OBSERVATION_HANDOFF_COLUMN_SPECS: tuple[ColumnSpec, ...] = (
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


def normalize_ima_input_manifest_arrow_table(
    table: pa.Table,
    *,
    diagnostics: Sequence[AdapterDiagnostic] = (),
    metadata: Mapping[str, str] | None = None,
    rejected: pa.Table | None = None,
    source_hash: str | None = None,
) -> NormalizedTabularHandoff:
    """Normalize an Arrow artifact-lineage table for IMA input manifest construction."""

    return normalize_arrow_table(
        table,
        column_specs=IMA_INPUT_MANIFEST_HANDOFF_COLUMN_SPECS,
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
) -> NormalizedTabularHandoff:
    """Normalize an Arrow scenario metadata table for IMA scenario-axis handoff."""

    return normalize_arrow_table(
        table,
        column_specs=IMA_SCENARIO_METADATA_HANDOFF_COLUMN_SPECS,
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
) -> NormalizedTabularHandoff:
    """Normalize an Arrow real-price observation table for RFET handoff."""

    return normalize_arrow_table(
        table,
        column_specs=IMA_RFET_OBSERVATION_HANDOFF_COLUMN_SPECS,
        rejected=rejected,
        diagnostics=diagnostics,
        metadata={} if metadata is None else metadata,
        source_hash=source_hash,
        require_unique_row_ids=False,
    )


def build_scenario_metadata_batch_from_handoff(
    handoff: NormalizedTabularHandoff,
) -> ScenarioMetadataBatch:
    """Build a columnar IMA scenario metadata batch from a normalized Arrow handoff."""

    if not isinstance(handoff, NormalizedTabularHandoff):
        raise ValueError("handoff must be NormalizedTabularHandoff")
    table = handoff.accepted
    validate_arrow_table(table, column_specs=IMA_SCENARIO_METADATA_HANDOFF_COLUMN_SPECS)
    return ScenarioMetadataBatch(
        scenario_ids=_string_column(table, "scenario_id"),
        scenario_dates=_date_column(table, "scenario_date"),
        scenario_sets=_string_column(
            table,
            "scenario_set",
            default=ScenarioSetType.CURRENT.value,
        ),
        calibration_windows=_string_column(table, "calibration_window", default=""),
        sources=_string_column(table, "source", default=""),
        provenance_json=_string_column(table, "provenance_json", default=""),
        source_row_ids=_string_column(table, "source_row_id", default=""),
        source_hash=handoff.source_hash,
        handoff_hash=normalized_handoff_hash(handoff),
    )


def build_rfet_observation_batch_from_handoff(
    handoff: NormalizedTabularHandoff,
) -> RFETObservationBatch:
    """Build a columnar RFET observation batch from a normalized Arrow handoff."""

    if not isinstance(handoff, NormalizedTabularHandoff):
        raise ValueError("handoff must be NormalizedTabularHandoff")
    table = handoff.accepted
    validate_arrow_table(table, column_specs=IMA_RFET_OBSERVATION_HANDOFF_COLUMN_SPECS)
    return RFETObservationBatch(
        risk_factor_names=_string_column(table, "risk_factor_name"),
        observation_dates=_date_column(table, "observation_date"),
        sources=_string_column(table, "source", default=""),
        vendor_ids=_string_column(table, "vendor_id", default=""),
        venues=_string_column(table, "venue", default=""),
        feeds=_string_column(table, "feed", default=""),
        observation_timestamps=_timestamp_column(table, "observation_timestamp"),
        date_normalization_evidence=_string_column(
            table,
            "date_normalization_evidence",
            default="",
        ),
        verifiable=_bool_column(table, "verifiable", default=True),
        verifiability_reasons=_string_column(table, "verifiability_reason", default=""),
        data_pool_ids=_string_column(table, "data_pool_id", default=""),
        vendor_audit_evidence_ids=_string_column(
            table,
            "vendor_audit_evidence_id",
            default="",
        ),
        source_row_ids=_string_column(table, "source_row_id", default=""),
        source_hash=handoff.source_hash,
        handoff_hash=normalized_handoff_hash(handoff),
    )


def build_capital_run_input_manifest_from_handoff(
    handoff: NormalizedTabularHandoff,
    *,
    run_id: str | None = None,
    as_of_date: date | datetime | str | None = None,
    schema_version: str | None = None,
    metadata: Mapping[str, str] | None = None,
) -> CapitalRunInputManifest:
    """Build an IMA capital-run input manifest from a normalized Arrow handoff."""

    if not isinstance(handoff, NormalizedTabularHandoff):
        raise ValueError("handoff must be NormalizedTabularHandoff")
    table = handoff.accepted
    validate_arrow_table(table, column_specs=IMA_INPUT_MANIFEST_HANDOFF_COLUMN_SPECS)

    artifacts = _artifact_lineages_from_table(table)
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


def _artifact_lineages_from_table(table: pa.Table) -> tuple[InputArtifactLineage, ...]:
    optional_statuses = _optional_column(table, "validation_status")
    optional_messages = _optional_column(table, "validation_messages")
    optional_metadata = _optional_column(table, "metadata_json")
    optional_source_rows = _optional_column(table, "source_row_id")
    artifacts: list[InputArtifactLineage] = []
    for index in range(table.num_rows):
        row_metadata = _metadata_json_at(optional_metadata, index)
        source_row_id = _optional_text_at(optional_source_rows, index)
        if source_row_id is not None:
            row_metadata["source_row_id"] = source_row_id
        artifacts.append(
            InputArtifactLineage(
                artifact_name=_required_text_at(table, "artifact_name", index),
                artifact_type=_required_text_at(table, "artifact_type", index),
                schema_version=_required_text_at(table, "schema_version", index),
                source_system=_required_text_at(table, "source_system", index),
                source_version=_required_text_at(table, "source_version", index),
                extraction_timestamp=_datetime_at(table, "extraction_timestamp", index),
                as_of_date=_date_at(table, "as_of_date", index),
                record_count=_non_negative_int_at(table, "record_count", index),
                vector_count=_non_negative_int_at(table, "vector_count", index),
                checksum=_required_text_at(table, "checksum", index),
                sign_convention=_required_text_at(table, "sign_convention", index),
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


def _required_column(table: pa.Table, column_name: str) -> list[object]:
    if column_name not in table.column_names:
        raise ValueError(f"column is required: {column_name}")
    return cast(list[object], table.column(column_name).to_pylist())


def _optional_column(table: pa.Table, column_name: str) -> list[object | None] | None:
    if column_name not in table.column_names:
        return None
    return cast(list[object | None], table.column(column_name).to_pylist())


def _required_text_at(table: pa.Table, column_name: str, index: int) -> str:
    value = _required_column(table, column_name)[index]
    if not isinstance(value, str) or not value:
        raise ValueError(f"{column_name} must contain non-empty text")
    return value


def _optional_text_at(values: list[object | None] | None, index: int) -> str | None:
    if values is None:
        return None
    value = values[index]
    if value is None:
        return None
    text = str(value)
    return text or None


def _datetime_at(table: pa.Table, column_name: str, index: int) -> datetime:
    value = _required_column(table, column_name)[index]
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    raise ValueError(f"{column_name} must contain datetimes or ISO-8601 datetime text")


def _date_at(table: pa.Table, column_name: str, index: int) -> date:
    value = _required_column(table, column_name)[index]
    return _parse_date(value, column_name)


def _parse_date(value: object, field: str) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        return date.fromisoformat(value)
    raise ValueError(f"{field} must contain dates or ISO-8601 date text")


def _non_negative_int_at(table: pa.Table, column_name: str, index: int) -> int:
    value = _required_column(table, column_name)[index]
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{column_name} must contain integers")
    integer = int(value)
    if integer < 0:
        raise ValueError(f"{column_name} must be non-negative")
    if isinstance(value, float) and value != integer:
        raise ValueError(f"{column_name} must contain whole-number values")
    return integer


def _messages_at(values: list[object | None] | None, index: int) -> tuple[str, ...]:
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


def _metadata_json_at(values: list[object | None] | None, index: int) -> dict[str, str]:
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


def _string_column(table: pa.Table, column_name: str, *, default: str | None = None) -> StringArray:
    if column_name not in table.column_names:
        if default is None:
            raise ValueError(f"column is required: {column_name}")
        return np.asarray([default] * table.num_rows, dtype=np.str_)
    values = _object_array_from_column(table.column(column_name), default=default)
    return np.asarray(values, dtype=np.str_)


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


def _bool_column(table: pa.Table, column_name: str, *, default: bool) -> BooleanArray:
    if column_name not in table.column_names:
        return np.full(table.num_rows, default, dtype=np.bool_)
    array = _single_array(table.column(column_name))
    if pa.types.is_boolean(array.type):
        return np.asarray(
            pc.fill_null(array, default).to_numpy(zero_copy_only=False), dtype=np.bool_
        )
    values = array.to_pylist()
    return np.asarray(
        [default if value is None else bool(value) for value in values], dtype=np.bool_
    )


def _timestamp_to_utc_naive(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value
    return value.astimezone(UTC).replace(tzinfo=None)


def _single_array(column: pa.ChunkedArray) -> pa.Array:
    return column.chunk(0) if column.num_chunks == 1 else column.combine_chunks()


def _object_array_from_column(
    column: pa.ChunkedArray,
    *,
    default: str | None,
) -> npt.NDArray[np.object_]:
    chunks = [_object_array_from_array(chunk, default=default) for chunk in column.chunks]
    if not chunks:
        return np.asarray([], dtype=object)
    if len(chunks) == 1:
        return chunks[0]
    return np.concatenate(chunks).astype(object, copy=False)


def _object_array_from_array(
    array: pa.Array,
    *,
    default: str | None,
) -> npt.NDArray[np.object_]:
    if pa.types.is_dictionary(array.type):
        return _dictionary_array_to_object_array(cast(pa.DictionaryArray, array), default=default)
    values = np.asarray(array.to_numpy(zero_copy_only=False), dtype=object)
    if array.null_count:
        fill = "" if default is None else default
        valid = np.asarray(array.is_valid().to_numpy(zero_copy_only=False), dtype=np.bool_)
        values = values.copy()
        values[~valid] = fill
    return values


def _dictionary_array_to_object_array(
    array: pa.DictionaryArray,
    *,
    default: str | None,
) -> npt.NDArray[np.object_]:
    dictionary = np.asarray(array.dictionary.to_numpy(zero_copy_only=False), dtype=object)
    if dictionary.size == 0:
        return np.full(len(array), "" if default is None else default, dtype=object)
    indices = np.asarray(
        pc.fill_null(array.indices, pa.scalar(0, type=array.indices.type)).to_numpy(
            zero_copy_only=False
        ),
        dtype=np.int64,
    )
    values = dictionary[indices]
    if array.null_count:
        fill = "" if default is None else default
        valid = np.asarray(array.is_valid().to_numpy(zero_copy_only=False), dtype=np.bool_)
        values = values.astype(object, copy=True)
        values[~valid] = fill
    return values


__all__ = [
    "IMA_INPUT_MANIFEST_HANDOFF_COLUMN_SPECS",
    "IMA_RFET_OBSERVATION_HANDOFF_COLUMN_SPECS",
    "IMA_SCENARIO_METADATA_HANDOFF_COLUMN_SPECS",
    "build_capital_run_input_manifest_from_handoff",
    "build_rfet_observation_batch_from_handoff",
    "build_scenario_metadata_batch_from_handoff",
    "normalize_ima_input_manifest_arrow_table",
    "normalize_ima_rfet_observation_arrow_table",
    "normalize_ima_scenario_metadata_arrow_table",
]
