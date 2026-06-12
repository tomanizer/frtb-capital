"""Scalar CRIF value coercion and rejected-row table helpers."""

from __future__ import annotations

import json
import math
from collections.abc import Mapping, Sequence
from typing import cast

import pyarrow as pa  # type: ignore[import-untyped]

from frtb_common.arrow_table import AdapterDiagnostic, NormalizedTableError, TabularLogicalType
from frtb_common.crif_output_adapter import _diagnostic, _mapping_output_logical_type
from frtb_common.crif_types import (
    CRIF_SOURCE_ROW_ID_COLUMN,
    CrifColumnSpec,
    CrifRiskTypeMapper,
    _normalise_risk_type,
    _stringify_record_value,
)


def _source_values(table: pa.Table, column_name: str | None) -> list[object | None]:
    if column_name is None:
        return [None] * table.num_rows
    return cast(list[object | None], table.column(column_name).combine_chunks().to_pylist())


def _coerce_column(
    values: Sequence[object | None],
    spec: CrifColumnSpec,
    *,
    row_errors: list[list[AdapterDiagnostic]],
) -> list[object | None]:
    coerced: list[object | None] = []
    missing_column = (
        all(value is None for value in values) and spec.required and spec.default is None
    )
    for row_index, value in enumerate(values):
        try:
            candidate = spec.default if value is None and spec.default is not None else value
            coerced.append(_coerce_value(candidate, spec))
        except NormalizedTableError as exc:
            coerced.append(None)
            row_errors[row_index].append(
                _diagnostic(
                    code="crif.invalid_field",
                    message=(
                        f"required CRIF column {spec.name!r} is missing"
                        if missing_column
                        else str(exc)
                    ),
                    row_id=None,
                    column_name=spec.name,
                )
            )
    return coerced


def _coerce_value(value: object | None, spec: CrifColumnSpec) -> object | None:
    if value is None:
        if spec.required:
            raise NormalizedTableError(f"CRIF field {spec.name!r} is required")
        return None
    if spec.logical_type is TabularLogicalType.FLOAT:
        return _coerce_float(value, spec)
    if spec.logical_type is TabularLogicalType.INTEGER:
        return _coerce_integer(value, spec)
    if spec.logical_type is TabularLogicalType.BOOLEAN:
        return _coerce_boolean(value, spec)
    text = str(value).strip()
    if not text:
        if spec.required:
            raise NormalizedTableError(f"CRIF field {spec.name!r} is required")
        return None
    return text


def _coerce_float(value: object, spec: CrifColumnSpec) -> float | None:
    text = str(value).strip()
    if not text:
        if spec.required:
            raise NormalizedTableError(f"CRIF field {spec.name!r} is required")
        return None
    try:
        float_value = float(text)
    except (TypeError, ValueError) as exc:
        raise NormalizedTableError(f"CRIF field {spec.name!r} must be numeric") from exc
    if not math.isfinite(float_value):
        raise NormalizedTableError(f"CRIF field {spec.name!r} must be finite")
    return float_value


def _coerce_integer(value: object, spec: CrifColumnSpec) -> int | None:
    text = str(value).strip()
    if not text:
        if spec.required:
            raise NormalizedTableError(f"CRIF field {spec.name!r} is required")
        return None
    try:
        return int(text)
    except (TypeError, ValueError) as exc:
        raise NormalizedTableError(f"CRIF field {spec.name!r} must be an integer") from exc


def _coerce_boolean(value: object, spec: CrifColumnSpec) -> bool | None:
    text = str(value).strip().lower()
    if not text:
        if spec.required:
            raise NormalizedTableError(f"CRIF field {spec.name!r} is required")
        return None
    if text in {"1", "true", "yes", "y"}:
        return True
    if text in {"0", "false", "no", "n"}:
        return False
    raise NormalizedTableError(f"CRIF field {spec.name!r} must be boolean")


def _source_row_ids(values: Sequence[object | None] | None, row_count: int) -> list[str]:
    if values is None:
        return [str(index) for index in range(row_count)]
    row_ids: list[str] = []
    for index, value in enumerate(values):
        text = "" if value is None else str(value).strip()
        row_ids.append(text or str(index))
    return row_ids


def _attach_source_row_ids(
    row_errors: Sequence[list[AdapterDiagnostic]],
    source_row_ids: Sequence[str],
) -> None:
    for row_index, errors in enumerate(row_errors):
        for error_index, diagnostic in enumerate(errors):
            if diagnostic.row_id is not None:
                continue
            errors[error_index] = AdapterDiagnostic(
                code=diagnostic.code,
                message=diagnostic.message,
                severity=diagnostic.severity,
                row_id=source_row_ids[row_index],
                column_name=diagnostic.column_name,
            )


def _risk_mapping_output(
    risk_type: str,
    row: Mapping[str, object],
    risk_mapping_by_type: Mapping[str, Mapping[str, object]],
    risk_type_mapper: CrifRiskTypeMapper | None,
) -> Mapping[str, object] | None:
    if risk_type_mapper is not None:
        return risk_type_mapper(risk_type, row)
    if not risk_mapping_by_type:
        return {}
    return risk_mapping_by_type.get(_normalise_risk_type(risk_type))


def _table_from_columns(
    columns: Mapping[str, Sequence[object | None]],
    indices: Sequence[int],
    *,
    specs: tuple[CrifColumnSpec, ...],
    mapping_outputs: Mapping[str, Sequence[object | None]],
) -> pa.Table:
    spec_by_name = {spec.name: spec for spec in specs}
    accepted_columns: dict[str, pa.Array] = {}
    for column_name in sorted(columns):
        values = [columns[column_name][index] for index in indices]
        logical_type = spec_by_name.get(column_name, CrifColumnSpec(column_name)).logical_type
        if column_name in mapping_outputs:
            logical_type = _mapping_output_logical_type(values, default=logical_type)
        accepted_columns[column_name] = _arrow_array(values, logical_type)
    return pa.table(accepted_columns)


def _arrow_array(values: Sequence[object | None], logical_type: TabularLogicalType) -> pa.Array:
    if logical_type is TabularLogicalType.FLOAT:
        return pa.array(values, type=pa.float64())
    if logical_type is TabularLogicalType.INTEGER:
        return pa.array(values, type=pa.int64())
    if logical_type is TabularLogicalType.BOOLEAN:
        return pa.array(values, type=pa.bool_())
    return pa.array([None if value is None else str(value) for value in values], type=pa.string())


def _rejected_table(
    raw_table: pa.Table,
    *,
    source_row_ids: Sequence[str],
    row_errors: Sequence[Sequence[AdapterDiagnostic]],
    rejected_indices: Sequence[int],
) -> pa.Table | None:
    if not rejected_indices:
        return None
    columns: dict[str, list[str]] = {
        CRIF_SOURCE_ROW_ID_COLUMN: [],
        "rejection_code": [],
        "rejection_column": [],
        "rejection_reason": [],
        "source_row_json": [],
    }
    raw_columns = {
        column_name: raw_table.column(column_name).combine_chunks()
        for column_name in raw_table.column_names
    }
    for row_index in rejected_indices:
        diagnostic = row_errors[row_index][0]
        columns[CRIF_SOURCE_ROW_ID_COLUMN].append(source_row_ids[row_index])
        columns["rejection_code"].append(diagnostic.code)
        columns["rejection_column"].append(diagnostic.column_name or "")
        columns["rejection_reason"].append(diagnostic.message)
        source_row = {
            column_name: _stringify_record_value(values[row_index].as_py())
            for column_name, values in raw_columns.items()
        }
        columns["source_row_json"].append(
            json.dumps(source_row, sort_keys=True, separators=(",", ":"))
        )
    return pa.table(columns)
