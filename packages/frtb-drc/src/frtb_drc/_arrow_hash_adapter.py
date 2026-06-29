"""Columnar Arrow input hashing for DRC handoffs."""

from __future__ import annotations

import hashlib
from collections.abc import Sequence
from typing import cast

import pyarrow as pa  # type: ignore[import-untyped]
import pyarrow.compute as pc  # type: ignore[import-untyped]
import pyarrow.ipc as pa_ipc  # type: ignore[import-untyped]
from frtb_common import ColumnSpec, TabularLogicalType

from frtb_drc.assembly.hashes import INPUT_HASH_ALGORITHM_ARROW_COLUMNAR_V2


def drc_arrow_columnar_input_hash(
    table: pa.Table,
    column_specs: Sequence[ColumnSpec],
) -> str:
    """Return the Arrow IPC columnar input hash for an accepted table.

    Parameters
    ----------
    table : pyarrow.Table
        Accepted normalized Arrow table for one package-owned ingress path.
    column_specs : Sequence[ColumnSpec]
        Canonical column contract that defines hash column order and types.

    Returns
    -------
    str
        Lowercase SHA-256 hex digest labelled ``arrow-columnar-v2``.
    """

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
        columns[spec.name] = _canonical_hash_column(table, spec)
    canonical = pa.table(columns).combine_chunks()
    if {"position_id", "source_row_id"}.issubset(canonical.column_names):
        return canonical.sort_by([("position_id", "ascending"), ("source_row_id", "ascending")])
    return canonical


def _canonical_hash_column(table: pa.Table, spec: ColumnSpec) -> pa.Array:
    row_count = table.num_rows
    if spec.name not in table.column_names:
        return _default_hash_column(spec, row_count)
    column = table.column(spec.name)
    if spec.logical_type is TabularLogicalType.FLOAT:
        return _combine_cast(column, pa.float64())
    if spec.logical_type is TabularLogicalType.INTEGER:
        return _combine_cast(column, pa.int64())
    if spec.logical_type is TabularLogicalType.BOOLEAN:
        return _combine_cast(column, pa.bool_())
    return _combine_cast(column, pa.string())


def _default_hash_column(spec: ColumnSpec, row_count: int) -> pa.Array:
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


__all__ = ["drc_arrow_columnar_input_hash"]
