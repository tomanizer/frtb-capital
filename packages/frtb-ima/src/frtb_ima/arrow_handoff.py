"""Arrow handoff adapters for IMA tabular input lineage."""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from datetime import date, datetime
from typing import cast

import pyarrow as pa  # type: ignore[import-untyped]
from frtb_common import (
    AdapterDiagnostic,
    ColumnSpec,
    NormalizedTabularHandoff,
    NullPolicy,
    TabularLogicalType,
    normalize_arrow_table,
    validate_arrow_table,
)

from frtb_ima.input_manifest import (
    CapitalRunInputManifest,
    InputArtifactLineage,
    InputValidationStatus,
)

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
    if isinstance(value, bool):
        raise ValueError(f"{column_name} must contain integers")
    integer = int(cast(int | float, value))
    if integer < 0:
        raise ValueError(f"{column_name} must be non-negative")
    if isinstance(value, float) and value != integer:
        raise ValueError(f"{column_name} must contain whole-number values")
    return integer


def _messages_at(values: list[object | None] | None, index: int) -> tuple[str, ...]:
    text = _optional_text_at(values, index)
    if text is None:
        return ()
    parsed = json.loads(text) if text.startswith("[") else text
    if isinstance(parsed, list):
        return tuple(str(item) for item in parsed)
    return (str(parsed),)


def _metadata_json_at(values: list[object | None] | None, index: int) -> dict[str, str]:
    text = _optional_text_at(values, index)
    if text is None:
        return {}
    parsed = json.loads(text)
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


__all__ = [
    "IMA_INPUT_MANIFEST_HANDOFF_COLUMN_SPECS",
    "build_capital_run_input_manifest_from_handoff",
    "normalize_ima_input_manifest_arrow_table",
]
