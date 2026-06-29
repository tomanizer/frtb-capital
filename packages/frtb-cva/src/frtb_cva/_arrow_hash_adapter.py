"""Columnar Arrow input hashing for CVA Arrow handoffs."""

from __future__ import annotations

import hashlib
from collections.abc import Sequence
from typing import cast

import pyarrow as pa  # type: ignore[import-untyped]
import pyarrow.compute as pc  # type: ignore[import-untyped]
import pyarrow.ipc as pa_ipc  # type: ignore[import-untyped]
from frtb_common import ColumnSpec, TabularLogicalType
from frtb_common.hashing import stable_json_dumps

from frtb_cva.assembly.batch_payloads import INPUT_HASH_ALGORITHM_ARROW_COLUMNAR_V2
from frtb_cva.assembly.payloads import context_payload
from frtb_cva.data_models import CvaCalculationContext
from frtb_cva.registry import (
    CVA_COUNTERPARTY_ARROW_COLUMN_SPECS,
    CVA_HEDGE_ARROW_COLUMN_SPECS,
    CVA_NETTING_SET_ARROW_COLUMN_SPECS,
    SA_CVA_SENSITIVITY_ARROW_COLUMN_SPECS,
)


def cva_arrow_columnar_input_hash(
    context: CvaCalculationContext,
    counterparty_table: pa.Table | None,
    netting_set_table: pa.Table | None,
    *,
    hedge_table: pa.Table | None = None,
    sensitivity_table: pa.Table | None = None,
) -> str:
    """Return the multi-table Arrow IPC columnar input hash for CVA.

    Parameters
    ----------
    context : CvaCalculationContext
        Validated CVA run context included as a stable JSON prefix.
    counterparty_table, netting_set_table : pyarrow.Table or None
        Accepted normalized BA-CVA entity tables, or ``None`` when absent.
    hedge_table, sensitivity_table : pyarrow.Table or None, optional
        Accepted normalized hedge and SA-CVA sensitivity tables, or ``None`` when absent.

    Returns
    -------
    str
        Lowercase SHA-256 hex digest labelled ``arrow-columnar-v2``.
    """

    digest = hashlib.sha256()
    digest.update(INPUT_HASH_ALGORITHM_ARROW_COLUMNAR_V2.encode("utf-8"))
    digest.update(b"\0")
    digest.update(stable_json_dumps(context_payload(context)).encode("utf-8"))
    for table, specs in (
        (counterparty_table, CVA_COUNTERPARTY_ARROW_COLUMN_SPECS),
        (netting_set_table, CVA_NETTING_SET_ARROW_COLUMN_SPECS),
        (hedge_table, CVA_HEDGE_ARROW_COLUMN_SPECS),
        (sensitivity_table, SA_CVA_SENSITIVITY_ARROW_COLUMN_SPECS),
    ):
        if table is None:
            digest.update(b"\0")
            continue
        digest.update(_columnar_ipc_bytes(table, specs))
    return digest.hexdigest()


def _columnar_ipc_bytes(table: pa.Table, column_specs: Sequence[ColumnSpec]) -> bytes:
    canonical = _canonical_hash_table(table, column_specs)
    sink = pa.BufferOutputStream()
    with pa_ipc.new_stream(sink, canonical.schema) as writer:
        writer.write_table(canonical)
    return cast(bytes, sink.getvalue().to_pybytes())


def _canonical_hash_table(table: pa.Table, column_specs: Sequence[ColumnSpec]) -> pa.Table:
    columns = {spec.name: _canonical_hash_column(table, spec) for spec in column_specs}
    return pa.table(columns).combine_chunks()


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


__all__ = ["cva_arrow_columnar_input_hash"]
