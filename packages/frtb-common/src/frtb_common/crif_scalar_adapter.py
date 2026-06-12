"""Scalar CRIF normalization fallback for callback-based RiskType mapping."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

import pyarrow as pa  # type: ignore[import-untyped]

from frtb_common.arrow_table import (
    AdapterDiagnostic,
    NormalizedArrowTable,
    arrow_table_content_hash,
)
from frtb_common.crif_output_adapter import _diagnostic, _handoff_column_specs
from frtb_common.crif_scalar_coercion_adapter import (
    _attach_source_row_ids,
    _coerce_column,
    _rejected_table,
    _risk_mapping_output,
    _source_row_ids,
    _source_values,
    _table_from_columns,
)
from frtb_common.crif_types import (
    CRIF_RISK_TYPE_COLUMN,
    CRIF_SOURCE_ROW_ID_COLUMN,
    CrifColumnSpec,
    CrifRiskTypeMapper,
    _normalise_risk_type,
)


def _normalize_crif_arrow_table_scalar_mapping(
    table: pa.Table,
    *,
    specs: tuple[CrifColumnSpec, ...],
    risk_mapping_by_type: Mapping[str, Mapping[str, object]],
    resolved_columns: Mapping[str, str],
    risk_type_mapper: CrifRiskTypeMapper | None,
    source_system: str,
    source_file: str,
    metadata: Mapping[str, str] | None,
    source_hash: str | None,
) -> NormalizedArrowTable:
    normalized_columns, row_errors = _coerce_scalar_columns(table, specs, resolved_columns)
    source_row_ids = _source_row_ids(
        normalized_columns.get(CRIF_SOURCE_ROW_ID_COLUMN),
        table.num_rows,
    )
    normalized_columns[CRIF_SOURCE_ROW_ID_COLUMN] = list(source_row_ids)
    _attach_source_row_ids(row_errors, source_row_ids)
    mapping_outputs = _map_scalar_risk_types(
        normalized_columns,
        row_errors,
        source_row_ids,
        risk_mapping_by_type,
        risk_type_mapper,
        table.num_rows,
    )
    return _build_scalar_handoff(
        table,
        normalized_columns=normalized_columns,
        mapping_outputs=mapping_outputs,
        row_errors=row_errors,
        source_row_ids=source_row_ids,
        specs=specs,
        source_system=source_system,
        source_file=source_file,
        metadata=metadata,
        source_hash=source_hash,
    )


def _coerce_scalar_columns(
    table: pa.Table,
    specs: tuple[CrifColumnSpec, ...],
    resolved_columns: Mapping[str, str],
) -> tuple[dict[str, list[object | None]], list[list[AdapterDiagnostic]]]:
    normalized_columns: dict[str, list[object | None]] = {}
    row_errors: list[list[AdapterDiagnostic]] = [[] for _ in range(table.num_rows)]
    for spec in specs:
        source_name = resolved_columns.get(spec.name)
        values = _source_values(table, source_name)
        normalized_columns[spec.name] = _coerce_column(values, spec, row_errors=row_errors)
    return normalized_columns, row_errors


def _map_scalar_risk_types(
    normalized_columns: Mapping[str, Sequence[object | None]],
    row_errors: list[list[AdapterDiagnostic]],
    source_row_ids: Sequence[str],
    risk_mapping_by_type: Mapping[str, Mapping[str, object]],
    risk_type_mapper: CrifRiskTypeMapper | None,
    row_count: int,
) -> dict[str, list[object | None]]:
    mapping_outputs: dict[str, list[object | None]] = {}
    risk_types = normalized_columns.get(CRIF_RISK_TYPE_COLUMN, [None] * row_count)
    for row_index in range(row_count):
        if row_errors[row_index]:
            continue
        risk_type = risk_types[row_index]
        if not isinstance(risk_type, str) or not risk_type.strip():
            row_errors[row_index].append(
                _diagnostic(
                    code="crif.missing_risk_type",
                    message="CRIF RiskType is required",
                    row_id=source_row_ids[row_index],
                    column_name=CRIF_RISK_TYPE_COLUMN,
                )
            )
            continue
        output_values = _risk_mapping_output(
            risk_type,
            {name: values[row_index] for name, values in normalized_columns.items()},
            risk_mapping_by_type,
            risk_type_mapper,
        )
        if output_values is None:
            row_errors[row_index].append(
                _diagnostic(
                    code="crif.unsupported_risk_type",
                    message=f"unsupported CRIF RiskType {_normalise_risk_type(risk_type)!r}",
                    row_id=source_row_ids[row_index],
                    column_name=CRIF_RISK_TYPE_COLUMN,
                )
            )
            continue
        for column_name, value in output_values.items():
            mapping_outputs.setdefault(column_name, [None] * row_count)[row_index] = value
    return mapping_outputs


def _build_scalar_handoff(
    raw_table: pa.Table,
    *,
    normalized_columns: Mapping[str, Sequence[object | None]],
    mapping_outputs: Mapping[str, Sequence[object | None]],
    row_errors: Sequence[Sequence[AdapterDiagnostic]],
    source_row_ids: Sequence[str],
    specs: tuple[CrifColumnSpec, ...],
    source_system: str,
    source_file: str,
    metadata: Mapping[str, str] | None,
    source_hash: str | None,
) -> NormalizedArrowTable:
    accepted_indices = tuple(index for index, errors in enumerate(row_errors) if not errors)
    rejected_indices = tuple(index for index, errors in enumerate(row_errors) if errors)
    accepted_table = _table_from_columns(
        {**normalized_columns, **mapping_outputs},
        accepted_indices,
        specs=specs,
        mapping_outputs=mapping_outputs,
    )
    rejected_table = _rejected_table(
        raw_table,
        source_row_ids=source_row_ids,
        row_errors=row_errors,
        rejected_indices=rejected_indices,
    )
    handoff_metadata = {
        "adapter": "crif",
        "source_file": source_file,
        "source_system": source_system,
    }
    if metadata is not None:
        handoff_metadata.update(metadata)
    return NormalizedArrowTable(
        accepted=accepted_table,
        column_specs=_handoff_column_specs(accepted_table, specs, mapping_outputs),
        row_id_column=CRIF_SOURCE_ROW_ID_COLUMN,
        rejected=rejected_table,
        diagnostics=tuple(errors[0] for errors in row_errors if errors),
        metadata=handoff_metadata,
        source_hash=source_hash or arrow_table_content_hash(raw_table),
        require_unique_row_ids=False,
    )
