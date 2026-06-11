"""GIRR delta CRIF Arrow normalization for SBM adapters."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

import pyarrow as pa  # type: ignore[import-untyped]
import pyarrow.compute as pc  # type: ignore[import-untyped]
from frtb_common import (
    CRIF_SOURCE_ROW_ID_COLUMN,
    NormalizedArrowTable,
    normalize_crif_arrow_table,
    normalize_crif_records,
)

from frtb_sbm.adapters.arrow import normalize_sbm_arrow_table
from frtb_sbm.adapters.crif_constants import (
    _GIRR_DELTA_CRIF_COLUMN_SPECS,
    _GIRR_DELTA_CRIF_RISK_TYPE_MAPPINGS,
)
from frtb_sbm.data_models import SbmRiskClass, SbmRiskMeasure, SbmSignConvention
from frtb_sbm.validation import SbmInputError


def normalize_girr_delta_crif_records(
    records: object,
    *,
    source_file: str = "crif.csv",
    desk_id: str = "UNKNOWN",
    legal_entity: str = "UNKNOWN",
    sign_convention: SbmSignConvention = SbmSignConvention.RECEIVE,
    source_hash: str | None = None,
) -> NormalizedArrowTable:
    """Normalize CRIF-like row dictionaries into the GIRR delta Arrow table.
    Parameters
    ----------
    records, source_file, desk_id, legal_entity, sign_convention, source_hash :
        See function signature for types and defaults.

    Returns
    -------
    NormalizedArrowTable
    """

    if not isinstance(records, Sequence) or isinstance(records, str | bytes):
        raise SbmInputError("records must be a sequence of mapping rows", field="records")
    rows: list[Mapping[str, object]] = []
    for index, record in enumerate(records):
        if not isinstance(record, Mapping):
            raise SbmInputError(
                "records must be a sequence of mapping rows",
                field=f"records[{index}]",
            )
        rows.append(record)
    crif_handoff = normalize_crif_records(
        rows,
        column_specs=_GIRR_DELTA_CRIF_COLUMN_SPECS,
        risk_type_mappings=_GIRR_DELTA_CRIF_RISK_TYPE_MAPPINGS,
        source_file=source_file,
        source_hash=source_hash,
    )
    return _girr_delta_handoff_from_normalized_crif(
        crif_handoff,
        desk_id=desk_id,
        legal_entity=legal_entity,
        sign_convention=sign_convention,
    )


def normalize_girr_delta_crif_arrow_table(
    table: pa.Table,
    *,
    source_file: str = "crif.csv",
    desk_id: str = "UNKNOWN",
    legal_entity: str = "UNKNOWN",
    sign_convention: SbmSignConvention = SbmSignConvention.RECEIVE,
    source_hash: str | None = None,
) -> NormalizedArrowTable:
    """Normalize a CRIF-like Arrow table into the GIRR delta Arrow table.
    Parameters
    ----------
    table, source_file, desk_id, legal_entity, sign_convention, source_hash :
        See function signature for types and defaults.

    Returns
    -------
    NormalizedArrowTable
    """

    crif_handoff = normalize_crif_arrow_table(
        table,
        column_specs=_GIRR_DELTA_CRIF_COLUMN_SPECS,
        risk_type_mappings=_GIRR_DELTA_CRIF_RISK_TYPE_MAPPINGS,
        source_file=source_file,
        source_hash=source_hash,
    )
    return _girr_delta_handoff_from_normalized_crif(
        crif_handoff,
        desk_id=desk_id,
        legal_entity=legal_entity,
        sign_convention=sign_convention,
    )


def _girr_delta_handoff_from_normalized_crif(
    crif_handoff: NormalizedArrowTable,
    *,
    desk_id: str,
    legal_entity: str,
    sign_convention: SbmSignConvention,
) -> NormalizedArrowTable:
    table = crif_handoff.accepted
    amount_currency = _text_column(table, "amount_currency", "USD")
    source_row_ids = _text_column(table, CRIF_SOURCE_ROW_ID_COLUMN, "")
    girr_table = pa.table(
        {
            "sensitivity_id": _coalesce_text_columns(
                _text_column(table, "sensitivity_id", ""),
                source_row_ids,
            ),
            "source_row_id": source_row_ids,
            "desk_id": _text_column(table, "desk_id", desk_id),
            "legal_entity": _text_column(table, "legal_entity", legal_entity),
            "risk_class": _text_column(table, "risk_class", SbmRiskClass.GIRR.value),
            "risk_measure": _text_column(table, "risk_measure", SbmRiskMeasure.DELTA.value),
            "bucket": _text_column(table, "bucket", "1"),
            "risk_factor": _coalesce_text_columns(
                _text_column(table, "qualifier", ""),
                amount_currency,
            ),
            "amount": _required_column(table, "amount"),
            "amount_currency": amount_currency,
            "sign_convention": _constant_text_column(sign_convention.value, table.num_rows),
            "tenor": _text_column(table, "label1", ""),
            "lineage_source_system": _constant_text_column(
                crif_handoff.metadata.get("source_system", "crif"),
                table.num_rows,
            ),
            "lineage_source_file": _constant_text_column(
                crif_handoff.metadata.get("source_file", "crif.csv"),
                table.num_rows,
            ),
        }
    )
    return normalize_sbm_arrow_table(
        girr_table,
        SbmRiskClass.GIRR,
        SbmRiskMeasure.DELTA,
        diagnostics=crif_handoff.diagnostics,
        metadata=crif_handoff.metadata,
        rejected=crif_handoff.rejected,
        source_hash=crif_handoff.source_hash,
    )


def _required_column(table: pa.Table, column_name: str) -> pa.ChunkedArray:
    if column_name not in table.column_names:
        raise SbmInputError(f"required column {column_name!r} is missing", field=column_name)
    return table.column(column_name)


def _text_column(table: pa.Table, column_name: str, default: str) -> pa.Array:
    if table.num_rows == 0:
        return pa.array([], type=pa.string())
    if column_name not in table.column_names:
        return _constant_text_column(default, table.num_rows)
    column = table.column(column_name).combine_chunks()
    if not pa.types.is_string(column.type):
        column = pc.cast(column, pa.string())
    trimmed = pc.utf8_trim_whitespace(column)
    filled = pc.fill_null(trimmed, "")
    has_text = pc.not_equal(filled, "")
    return pc.if_else(has_text, trimmed, _constant_text_column(default, table.num_rows))


def _coalesce_text_columns(primary: pa.Array, fallback: pa.Array) -> pa.Array:
    if len(primary) != len(fallback):
        raise SbmInputError("coalesced CRIF columns must have matching lengths", field="crif")
    if len(primary) == 0:
        return pa.array([], type=pa.string())
    trimmed = pc.utf8_trim_whitespace(primary)
    filled = pc.fill_null(trimmed, "")
    has_text = pc.not_equal(filled, "")
    return pc.if_else(has_text, trimmed, fallback)


def _constant_text_column(value: str, row_count: int) -> pa.Array:
    return pa.repeat(pa.scalar(value, type=pa.string()), row_count)


__all__ = ["normalize_girr_delta_crif_arrow_table", "normalize_girr_delta_crif_records"]
