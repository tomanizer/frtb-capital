"""Input-manifest row parsing for IMA Arrow handoffs."""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from datetime import date, datetime

import pyarrow as pa  # type: ignore[import-untyped]

from frtb_ima.adapters._arrow_columns import (
    _date_at,
    _datetime_at,
    _non_negative_int_at,
    _optional_column_values,
    _optional_text_at,
    _parse_date,
    _required_text_at,
)
from frtb_ima.input_manifest import InputArtifactLineage, InputValidationStatus


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
