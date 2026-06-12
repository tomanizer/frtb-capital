"""Vectorized CRIF Arrow normalization path for static RiskType mappings."""

from __future__ import annotations

from collections.abc import Mapping

import pyarrow as pa  # type: ignore[import-untyped]

from frtb_common.arrow_table import (
    AdapterDiagnostic,
    NormalizedArrowTable,
    arrow_table_content_hash,
)
from frtb_common.crif_output_adapter import _handoff_column_specs
from frtb_common.crif_types import (
    CRIF_RISK_TYPE_COLUMN,
    CRIF_SOURCE_ROW_ID_COLUMN,
    CrifColumnSpec,
    CrifRiskTypeMapping,
)
from frtb_common.crif_vectorized_coercion_adapter import _coerce_column_arrow
from frtb_common.crif_vectorized_masks_adapter import (
    _bool_array,
    _empty_text_mask,
    _mask_and,
    _mask_not,
    _normalise_risk_type_array,
    _source_row_id_array,
    _supported_risk_type_mask,
    _unsupported_risk_type_messages,
)
from frtb_common.crif_vectorized_output_adapter import (
    _attach_vectorized_source_row_ids,
    _record_vectorized_errors,
    _rejected_table_from_diagnostics,
    _static_mapping_output_arrays,
    _table_from_arrow_columns,
)


def _normalize_crif_arrow_table_static_mapping(
    table: pa.Table,
    *,
    specs: tuple[CrifColumnSpec, ...],
    risk_type_mappings: tuple[CrifRiskTypeMapping, ...],
    risk_mapping_by_type: Mapping[str, Mapping[str, object]],
    resolved_columns: Mapping[str, str],
    source_system: str,
    source_file: str,
    metadata: Mapping[str, str] | None,
    source_hash: str | None,
) -> NormalizedArrowTable:
    normalized_columns, row_error_by_index, valid_fields_mask = _coerce_vectorized_fields(
        table, specs, resolved_columns
    )
    source_row_ids = _source_row_id_array(
        normalized_columns.get(CRIF_SOURCE_ROW_ID_COLUMN), table.num_rows
    )
    normalized_columns[CRIF_SOURCE_ROW_ID_COLUMN] = source_row_ids
    _attach_vectorized_source_row_ids(row_error_by_index, source_row_ids)
    risk_type_keys, accepted_mask = _record_vectorized_risk_type_errors(
        normalized_columns,
        row_error_by_index,
        valid_fields_mask,
        source_row_ids,
        risk_mapping_by_type,
        table.num_rows,
    )
    mapping_outputs = _static_mapping_output_arrays(
        risk_type_keys, risk_type_mappings, table.num_rows
    )
    accepted_table = _table_from_arrow_columns(
        {**normalized_columns, **mapping_outputs},
        accepted_mask,
        specs=specs,
        mapping_outputs=mapping_outputs,
    )
    rejected_indices = tuple(sorted(row_error_by_index))
    rejected_table = _rejected_table_from_diagnostics(
        table,
        source_row_ids=source_row_ids,
        diagnostics_by_index=row_error_by_index,
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
        diagnostics=tuple(row_error_by_index[index] for index in rejected_indices),
        metadata=handoff_metadata,
        source_hash=source_hash or arrow_table_content_hash(table),
        require_unique_row_ids=False,
    )


def _coerce_vectorized_fields(
    table: pa.Table,
    specs: tuple[CrifColumnSpec, ...],
    resolved_columns: Mapping[str, str],
) -> tuple[dict[str, pa.Array], dict[int, AdapterDiagnostic], pa.Array]:
    normalized_columns: dict[str, pa.Array] = {}
    row_error_by_index: dict[int, AdapterDiagnostic] = {}
    valid_fields_mask = _bool_array(True, table.num_rows)
    for spec in specs:
        source_name = resolved_columns.get(spec.name)
        vectorized = _coerce_column_arrow(table, source_name, spec)
        normalized_columns[spec.name] = vectorized.values
        for error in vectorized.errors:
            error_mask = _mask_and(valid_fields_mask, error.mask)
            _record_vectorized_errors(
                row_error_by_index,
                error_mask,
                code="crif.invalid_field",
                message=error.message,
                source_row_ids=None,
                column_name=spec.name,
            )
            valid_fields_mask = _mask_and(valid_fields_mask, _mask_not(error.mask))
    return normalized_columns, row_error_by_index, valid_fields_mask


def _record_vectorized_risk_type_errors(
    normalized_columns: Mapping[str, pa.Array],
    row_error_by_index: dict[int, AdapterDiagnostic],
    valid_fields_mask: pa.Array,
    source_row_ids: pa.Array,
    risk_mapping_by_type: Mapping[str, Mapping[str, object]],
    row_count: int,
) -> tuple[pa.Array, pa.Array]:
    risk_type_keys = _normalise_risk_type_array(normalized_columns[CRIF_RISK_TYPE_COLUMN])
    missing_mask = _mask_and(valid_fields_mask, _empty_text_mask(risk_type_keys))
    _record_vectorized_errors(
        row_error_by_index,
        missing_mask,
        code="crif.missing_risk_type",
        message="CRIF RiskType is required",
        source_row_ids=source_row_ids,
        column_name=CRIF_RISK_TYPE_COLUMN,
    )
    candidate_mask = _mask_and(valid_fields_mask, _mask_not(missing_mask))
    supported_mask = _supported_risk_type_mask(risk_type_keys, risk_mapping_by_type, row_count)
    unsupported_mask = _mask_and(candidate_mask, _mask_not(supported_mask))
    _record_vectorized_errors(
        row_error_by_index,
        unsupported_mask,
        code="crif.unsupported_risk_type",
        message_by_index=_unsupported_risk_type_messages(risk_type_keys, unsupported_mask),
        source_row_ids=source_row_ids,
        column_name=CRIF_RISK_TYPE_COLUMN,
    )
    return risk_type_keys, _mask_and(candidate_mask, supported_mask)
