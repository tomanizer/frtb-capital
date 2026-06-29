"""Columnar Arrow input hashing for RRAO handoffs."""

from __future__ import annotations

import hashlib
from collections.abc import Sequence
from typing import cast

import pyarrow as pa  # type: ignore[import-untyped]
import pyarrow.compute as pc  # type: ignore[import-untyped]
import pyarrow.ipc as pa_ipc  # type: ignore[import-untyped]
from frtb_common import ColumnSpec, TabularLogicalType

from frtb_rrao.assembly.hashes import INPUT_HASH_ALGORITHM_ARROW_COLUMNAR_V2

_HASH_EXCLUDED_COLUMNS = frozenset({"unsupported_nested_payload"})
_OPTIONAL_BOOL_OBJECT_COLUMNS = frozenset(
    {
        "is_path_dependent",
        "has_maturity",
        "has_strike_or_barrier",
        "has_multiple_strikes_or_barriers",
    }
)
_DEFAULT_FALSE_BOOL_COLUMNS = frozenset(
    {
        "is_ctp_hedge",
        "is_investment_fund_exposure",
        "investment_fund_look_through_available",
    }
)


def _rrao_arrow_columnar_input_hash(
    table: pa.Table,
    column_specs: Sequence[ColumnSpec],
) -> str:
    canonical = _canonical_hash_table(table, column_specs)
    sink = pa.BufferOutputStream()
    with pa_ipc.new_stream(sink, canonical.schema) as writer:
        writer.write_table(canonical)
    digest = hashlib.sha256()
    digest.update(INPUT_HASH_ALGORITHM_ARROW_COLUMNAR_V2.encode("utf-8"))
    digest.update(b"\0")
    digest.update(sink.getvalue().to_pybytes())
    return digest.hexdigest()


def _canonical_hash_table(table: pa.Table, column_specs: Sequence[ColumnSpec]) -> pa.Table:
    columns: dict[str, pa.Array] = {}
    for spec in column_specs:
        if spec.name in _HASH_EXCLUDED_COLUMNS:
            continue
        columns[spec.name] = _canonical_hash_column(table, spec)
    return pa.table(columns).combine_chunks()


def _canonical_hash_column(table: pa.Table, spec: ColumnSpec) -> pa.Array:
    row_count = table.num_rows
    if spec.name not in table.column_names:
        return _default_hash_column(table, spec, row_count)
    column = table.column(spec.name)
    logical_type = spec.logical_type
    if logical_type is TabularLogicalType.FLOAT:
        return _combine_cast(column, pa.float64())
    if logical_type is TabularLogicalType.INTEGER:
        return _combine_cast(column, pa.int64())
    if logical_type is TabularLogicalType.BOOLEAN:
        array = _combine_cast(column, pa.bool_())
        default = _bool_default_for_hash(spec.name)
        return array if default is None else _fill_bool_nulls(array, default)
    return _canonical_hash_text_column(table, spec, column)


def _canonical_hash_text_column(
    table: pa.Table,
    spec: ColumnSpec,
    column: pa.ChunkedArray,
) -> pa.Array:
    array = _combine_cast(column, pa.string())
    if spec.name == "notional_source":
        return _fill_string_nulls(array, "reported")
    if spec.name == "lineage_source_row_id" and column.null_count:
        source_rows = _combine_cast(table.column("source_row_id"), pa.string())
        return _fill_nulls_from_column(array, source_rows)
    if spec.name == "citations":
        return _fill_string_nulls(array, "")
    return array


def _default_hash_column(table: pa.Table, spec: ColumnSpec, row_count: int) -> pa.Array:
    if spec.name == "notional_source":
        return pa.array(["reported"] * row_count, type=pa.string())
    if spec.name == "lineage_source_row_id":
        return _combine_cast(table.column("source_row_id"), pa.string())
    if spec.name == "citations":
        return pa.array([""] * row_count, type=pa.string())
    if spec.name in _DEFAULT_FALSE_BOOL_COLUMNS:
        return pa.array([False] * row_count, type=pa.bool_())
    if spec.name == "investment_fund_mandate_allows_rrao_exposures":
        return pa.array([True] * row_count, type=pa.bool_())
    if spec.logical_type is TabularLogicalType.FLOAT:
        return pa.nulls(row_count, type=pa.float64())
    if spec.logical_type is TabularLogicalType.INTEGER:
        return pa.nulls(row_count, type=pa.int64())
    if spec.logical_type is TabularLogicalType.BOOLEAN:
        return pa.nulls(row_count, type=pa.bool_())
    return pa.nulls(row_count, type=pa.string())


def _combine_cast(column: pa.ChunkedArray, data_type: pa.DataType) -> pa.Array:
    array = column.combine_chunks()
    if array.type.equals(data_type):
        return array
    return cast(pa.Array, pc.cast(array, data_type))


def _fill_string_nulls(array: pa.Array, value: str) -> pa.Array:
    return cast(pa.Array, pc.fill_null(array, pa.scalar(value, type=pa.string())))


def _fill_bool_nulls(array: pa.Array, value: bool) -> pa.Array:
    return cast(pa.Array, pc.fill_null(array, pa.scalar(value, type=pa.bool_())))


def _fill_nulls_from_column(array: pa.Array, fallback: pa.Array) -> pa.Array:
    return cast(pa.Array, pc.if_else(pc.is_null(array), fallback, array))


def _bool_default_for_hash(name: str) -> bool | None:
    if name in _OPTIONAL_BOOL_OBJECT_COLUMNS:
        return None
    if name in _DEFAULT_FALSE_BOOL_COLUMNS:
        return False
    if name == "investment_fund_mandate_allows_rrao_exposures":
        return True
    return None
