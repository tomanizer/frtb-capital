"""Shared CRIF output table and diagnostic helpers."""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from typing import cast

import pyarrow as pa  # type: ignore[import-untyped]

from frtb_common.arrow_table import (
    AdapterDiagnostic,
    ColumnSpec,
    DiagnosticSeverity,
    NormalizedTableError,
    NullPolicy,
    TabularLogicalType,
)
from frtb_common.crif_types import CrifColumnSpec


def _mapping_output_logical_type(
    values: Sequence[object | None],
    *,
    default: TabularLogicalType,
) -> TabularLogicalType:
    non_null_values = [value for value in values if value is not None]
    if not non_null_values:
        return default
    if all(isinstance(value, float) for value in non_null_values):
        for value in non_null_values:
            if not math.isfinite(cast(float, value)):
                raise NormalizedTableError("CRIF mapping output float values must be finite")
        return TabularLogicalType.FLOAT
    return default


def _handoff_column_specs(
    table: pa.Table,
    specs: tuple[CrifColumnSpec, ...],
    mapping_outputs: Mapping[str, Sequence[object | None]],
) -> tuple[ColumnSpec, ...]:
    spec_by_name = {spec.name: spec for spec in specs}
    handoff_specs: list[ColumnSpec] = []
    for column_name in table.column_names:
        if column_name in spec_by_name:
            handoff_specs.append(spec_by_name[column_name].as_column_spec())
            continue
        null_policy = NullPolicy.FORBID
        if column_name in mapping_outputs and table[column_name].null_count:
            null_policy = NullPolicy.ALLOW
        handoff_specs.append(ColumnSpec(column_name, null_policy=null_policy))
    return tuple(handoff_specs)


def _diagnostic(
    *,
    code: str,
    message: str,
    row_id: str | None,
    column_name: str,
) -> AdapterDiagnostic:
    return AdapterDiagnostic(
        code=code,
        message=message,
        severity=DiagnosticSeverity.ERROR,
        row_id=row_id,
        column_name=column_name,
    )
