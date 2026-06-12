"""Vectorized CRIF accepted/rejected output assembly helpers."""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from typing import cast

import pyarrow as pa  # type: ignore[import-untyped]
import pyarrow.compute as pc  # type: ignore[import-untyped]

from frtb_common.arrow_table import AdapterDiagnostic, TabularLogicalType
from frtb_common.crif_output_adapter import _diagnostic, _mapping_output_logical_type
from frtb_common.crif_types import (
    CRIF_SOURCE_ROW_ID_COLUMN,
    CrifColumnSpec,
    CrifRiskTypeMapping,
    _stringify_record_value,
)
from frtb_common.crif_vectorized_masks_adapter import _true_indices


def _static_mapping_output_arrays(
    risk_type_keys: pa.Array,
    risk_type_mappings: tuple[CrifRiskTypeMapping, ...],
    row_count: int,
) -> dict[str, pa.Array]:
    logical_types = _static_mapping_output_logical_types(risk_type_mappings)
    outputs = {
        column_name: _null_array(row_count, logical_type)
        for column_name, logical_type in logical_types.items()
    }
    for mapping in risk_type_mappings:
        mask = cast(
            pa.Array,
            pc.is_in(risk_type_keys, value_set=pa.array(mapping.source_values)),
        )
        for column_name, value in mapping.output_values.items():
            logical_type = logical_types[column_name]
            outputs[column_name] = cast(
                pa.Array,
                pc.if_else(
                    mask, _scalar_for_logical_type(value, logical_type), outputs[column_name]
                ),
            )
    return outputs


def _static_mapping_output_logical_types(
    risk_type_mappings: tuple[CrifRiskTypeMapping, ...],
) -> dict[str, TabularLogicalType]:
    values_by_column: dict[str, list[object]] = {}
    for mapping in risk_type_mappings:
        for column_name, value in mapping.output_values.items():
            values_by_column.setdefault(column_name, []).append(value)
    return {
        column_name: _mapping_output_logical_type(values, default=TabularLogicalType.STRING)
        for column_name, values in values_by_column.items()
    }


def _scalar_for_logical_type(value: object, logical_type: TabularLogicalType) -> pa.Scalar:
    if logical_type is TabularLogicalType.FLOAT:
        return pa.scalar(cast(float, value), type=pa.float64())
    return pa.scalar(None if value is None else str(value), type=pa.string())


def _null_array(row_count: int, logical_type: TabularLogicalType) -> pa.Array:
    if logical_type is TabularLogicalType.FLOAT:
        return pa.nulls(row_count, type=pa.float64())
    if logical_type is TabularLogicalType.INTEGER:
        return pa.nulls(row_count, type=pa.int64())
    if logical_type is TabularLogicalType.BOOLEAN:
        return pa.nulls(row_count, type=pa.bool_())
    return pa.nulls(row_count, type=pa.string())


def _table_from_arrow_columns(
    columns: Mapping[str, pa.Array],
    accepted_mask: pa.Array,
    *,
    specs: tuple[CrifColumnSpec, ...],
    mapping_outputs: Mapping[str, pa.Array],
) -> pa.Table:
    spec_by_name = {spec.name: spec for spec in specs}
    accepted_columns: dict[str, pa.Array] = {}
    for column_name in sorted(columns):
        values = cast(pa.Array, pc.filter(columns[column_name], accepted_mask))
        logical_type = spec_by_name.get(column_name, CrifColumnSpec(column_name)).logical_type
        if column_name in mapping_outputs:
            logical_type = _logical_type_for_arrow_array(values, default=logical_type)
        accepted_columns[column_name] = _cast_arrow_array(values, logical_type)
    return pa.table(accepted_columns)


def _logical_type_for_arrow_array(
    values: pa.Array,
    *,
    default: TabularLogicalType,
) -> TabularLogicalType:
    if pa.types.is_floating(values.type):
        return TabularLogicalType.FLOAT
    if pa.types.is_integer(values.type):
        return TabularLogicalType.INTEGER
    if pa.types.is_boolean(values.type):
        return TabularLogicalType.BOOLEAN
    return default


def _cast_arrow_array(values: pa.Array, logical_type: TabularLogicalType) -> pa.Array:
    if logical_type is TabularLogicalType.FLOAT:
        return cast(pa.Array, pc.cast(values, pa.float64()))
    if logical_type is TabularLogicalType.INTEGER:
        return cast(pa.Array, pc.cast(values, pa.int64()))
    if logical_type is TabularLogicalType.BOOLEAN:
        return cast(pa.Array, pc.cast(values, pa.bool_()))
    return cast(pa.Array, pc.cast(values, pa.string()))


def _record_vectorized_errors(
    row_error_by_index: dict[int, AdapterDiagnostic],
    mask: pa.Array,
    *,
    code: str,
    column_name: str,
    message: str | None = None,
    message_by_index: Mapping[int, str] | None = None,
    source_row_ids: pa.Array | None,
) -> None:
    for row_index in _true_indices(mask):
        if row_index in row_error_by_index:
            continue
        row_id = None
        if source_row_ids is not None:
            row_id = cast(str, source_row_ids[row_index].as_py())
        row_error_by_index[row_index] = _diagnostic(
            code=code,
            message=message_by_index.get(row_index, "")
            if message_by_index is not None
            else cast(str, message),
            row_id=row_id,
            column_name=column_name,
        )


def _attach_vectorized_source_row_ids(
    row_error_by_index: dict[int, AdapterDiagnostic],
    source_row_ids: pa.Array,
) -> None:
    for row_index, diagnostic in tuple(row_error_by_index.items()):
        if diagnostic.row_id is not None:
            continue
        row_error_by_index[row_index] = AdapterDiagnostic(
            code=diagnostic.code,
            message=diagnostic.message,
            severity=diagnostic.severity,
            row_id=cast(str, source_row_ids[row_index].as_py()),
            column_name=diagnostic.column_name,
        )


def _rejected_table_from_diagnostics(
    raw_table: pa.Table,
    *,
    source_row_ids: pa.Array,
    diagnostics_by_index: Mapping[int, AdapterDiagnostic],
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
        column_name: raw_table.column(column_name) for column_name in raw_table.column_names
    }
    for row_index in rejected_indices:
        diagnostic = diagnostics_by_index[row_index]
        columns[CRIF_SOURCE_ROW_ID_COLUMN].append(cast(str, source_row_ids[row_index].as_py()))
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
