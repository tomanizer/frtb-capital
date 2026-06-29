"""Fast Arrow ingress for canonical RRAO batches."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from enum import StrEnum

import numpy as np
import pyarrow as pa  # type: ignore[import-untyped]
import pyarrow.compute as pc  # type: ignore[import-untyped]
from frtb_common import (
    ColumnSpec,
    NormalizedArrowTable,
    read_arrow_columns,
)

from frtb_rrao._arrow_batch_columns_adapter import (
    ArrowColumnArray,
    _batch_from_arrow_columns,
    _optional_text_array,
    _required_text_column,
)
from frtb_rrao._arrow_hash_adapter import (
    _combine_cast,
    _fill_string_nulls,
    _rrao_arrow_columnar_input_hash,
)
from frtb_rrao.batch import RraoPositionBatch
from frtb_rrao.data_models import (
    RraoClassification,
    RraoEvidenceType,
    RraoExclusionReason,
    RraoInvestmentFundExposureType,
    RraoInvestmentFundMethod,
)
from frtb_rrao.validation._errors import RraoInputError
from frtb_rrao.validation.batch import validate_rrao_batch


def _build_rrao_batch_from_arrow_fast(
    handoff: NormalizedArrowTable,
    *,
    column_specs: Sequence[ColumnSpec],
    null_defaults: Mapping[str, object],
) -> RraoPositionBatch:
    """Build an RRAO batch from Arrow without row-payload hashing."""

    if not isinstance(handoff, NormalizedArrowTable):
        raise RraoInputError("handoff must be NormalizedArrowTable", field="handoff")
    table = handoff.accepted.combine_chunks()
    row_count = table.num_rows
    _reject_unsupported_nested_payload_arrow(table)
    columns = read_arrow_columns(
        table,
        column_specs,
        error=_rrao_error,
        null_defaults=null_defaults,
    )
    if row_count == 0:
        raise RraoInputError("RRAO batch requires at least one position", field="positions")
    _validate_required_text_columns(columns)
    _validate_enum_columns(columns)
    batch = _batch_from_arrow_columns(
        columns,
        row_count=row_count,
        source_hash=handoff.source_hash,
        handoff_hash=_normalized_arrow_envelope_hash(handoff),
        diagnostics=tuple(diagnostic.as_dict() for diagnostic in handoff.diagnostics),
        input_hash=_rrao_arrow_columnar_input_hash(table, column_specs),
    )
    validate_rrao_batch(batch)
    return batch


def _normalized_arrow_envelope_hash(handoff: NormalizedArrowTable) -> str:
    from frtb_common import normalized_arrow_table_hash

    return normalized_arrow_table_hash(handoff)


def _validate_required_text_columns(columns: Mapping[str, ArrowColumnArray]) -> None:
    required = (
        "position_id",
        "source_row_id",
        "desk_id",
        "legal_entity",
        "currency",
        "evidence_type",
        "evidence_label",
        "lineage_source_system",
        "lineage_source_file",
    )
    for field in required:
        _required_text_column(columns, field)


def _validate_enum_columns(columns: Mapping[str, ArrowColumnArray]) -> None:
    _required_enum_column(columns, "evidence_type", RraoEvidenceType)
    _optional_enum_column(columns, "classification_hint", RraoClassification)
    _optional_enum_column(columns, "exclusion_reason", RraoExclusionReason)
    _optional_enum_column(
        columns,
        "investment_fund_section_205_method",
        RraoInvestmentFundMethod,
        field="investment_fund_descriptor.section_205_method",
    )
    _optional_enum_column(
        columns,
        "investment_fund_included_exposure_type",
        RraoInvestmentFundExposureType,
        field="investment_fund_descriptor.included_exposure_type",
        message="invalid investment fund exposure type",
    )


def _required_enum_column(
    columns: Mapping[str, ArrowColumnArray],
    name: str,
    enum_type: type[StrEnum],
) -> None:
    values = _required_text_column(columns, name)
    valid = {item.value for item in enum_type}
    invalid = ~np.isin(values, tuple(valid))
    if bool(np.any(invalid)):
        raise RraoInputError(f"invalid {name}", field=name)


def _optional_enum_column(
    columns: Mapping[str, ArrowColumnArray],
    name: str,
    enum_type: type[StrEnum],
    *,
    field: str | None = None,
    message: str | None = None,
) -> None:
    values = columns.get(name)
    if values is None:
        return
    optional = _optional_text_array(values)
    present = optional != None  # noqa: E711
    valid = {item.value for item in enum_type}
    invalid = present & ~np.isin(optional, tuple(valid))
    if bool(np.any(invalid)):
        raise RraoInputError(message or f"invalid {field or name}", field=field or name)


def _reject_unsupported_nested_payload_arrow(table: pa.Table) -> None:
    if "unsupported_nested_payload" not in table.column_names:
        return
    column = _combine_cast(table.column("unsupported_nested_payload"), pa.string())
    if column.null_count == len(column):
        return
    filled = _fill_string_nulls(column, "")
    non_empty = pc.not_equal(pc.utf8_trim_whitespace(filled), "")
    if bool(pc.any(non_empty).as_py()):
        raise RraoInputError(
            "unsupported nested payload requires flattened RRAO Arrow columns",
            field="unsupported_nested_payload",
        )


def _rrao_error(message: str, field: str | None) -> RraoInputError:
    return RraoInputError(message, field="" if field is None else field)
