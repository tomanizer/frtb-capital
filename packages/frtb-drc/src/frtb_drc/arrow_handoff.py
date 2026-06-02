"""Arrow handoff adapters for DRC batches."""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from typing import cast

import numpy as np
import numpy.typing as npt
import pyarrow as pa  # type: ignore[import-untyped]
import pyarrow.compute as pc  # type: ignore[import-untyped]
from frtb_common import (
    AdapterDiagnostic,
    ColumnSpec,
    NormalizedTabularHandoff,
    NullPolicy,
    TabularLogicalType,
    normalize_arrow_table,
    normalized_handoff_hash,
    validate_arrow_table,
)

from frtb_drc.batch import (
    DrcPositionBatch,
    build_drc_ctp_batch_from_columns,
    build_drc_nonsec_batch_from_columns,
    build_drc_securitisation_non_ctp_batch_from_columns,
)
from frtb_drc.validation import DrcInputError


def _replace_column_spec(
    spec: ColumnSpec,
    *,
    required: bool,
    null_policy: NullPolicy,
) -> ColumnSpec:
    return ColumnSpec(
        spec.name,
        aliases=spec.aliases,
        logical_type=spec.logical_type,
        required=required,
        null_policy=null_policy,
        chunk_policy=spec.chunk_policy,
        dictionary_policy=spec.dictionary_policy,
    )


DRC_NONSEC_HANDOFF_COLUMN_SPECS: tuple[ColumnSpec, ...] = (
    ColumnSpec("position_id", aliases=("positionId",), logical_type=TabularLogicalType.STRING),
    ColumnSpec("source_row_id", aliases=("sourceRowId",), logical_type=TabularLogicalType.STRING),
    ColumnSpec("desk_id", aliases=("deskId",), logical_type=TabularLogicalType.STRING),
    ColumnSpec("legal_entity", aliases=("legalEntity",), logical_type=TabularLogicalType.STRING),
    ColumnSpec("risk_class", aliases=("riskClass",), logical_type=TabularLogicalType.STRING),
    ColumnSpec(
        "instrument_type",
        aliases=("instrumentType",),
        logical_type=TabularLogicalType.STRING,
    ),
    ColumnSpec(
        "default_direction",
        aliases=("defaultDirection",),
        logical_type=TabularLogicalType.STRING,
    ),
    ColumnSpec("issuer_id", aliases=("issuerId",), logical_type=TabularLogicalType.STRING),
    ColumnSpec(
        "tranche_id",
        aliases=("trancheId",),
        logical_type=TabularLogicalType.STRING,
        required=False,
        null_policy=NullPolicy.ALLOW,
    ),
    ColumnSpec(
        "index_series_id",
        aliases=("indexSeriesId",),
        logical_type=TabularLogicalType.STRING,
        required=False,
        null_policy=NullPolicy.ALLOW,
    ),
    ColumnSpec("bucket_key", aliases=("bucketKey",), logical_type=TabularLogicalType.STRING),
    ColumnSpec("seniority", logical_type=TabularLogicalType.STRING),
    ColumnSpec(
        "credit_quality",
        aliases=("creditQuality",),
        logical_type=TabularLogicalType.STRING,
    ),
    ColumnSpec("notional", logical_type=TabularLogicalType.FLOAT),
    ColumnSpec(
        "market_value",
        aliases=("marketValue",),
        logical_type=TabularLogicalType.FLOAT,
        required=False,
        null_policy=NullPolicy.ALLOW,
    ),
    ColumnSpec(
        "cumulative_pnl",
        aliases=("cumulativePnl", "cumulativePnL"),
        logical_type=TabularLogicalType.FLOAT,
        required=False,
        null_policy=NullPolicy.ALLOW,
    ),
    ColumnSpec(
        "maturity_years",
        aliases=("maturityYears",),
        logical_type=TabularLogicalType.FLOAT,
    ),
    ColumnSpec("currency", logical_type=TabularLogicalType.STRING),
    ColumnSpec(
        "lgd_override",
        aliases=("lgdOverride",),
        logical_type=TabularLogicalType.FLOAT,
        required=False,
        null_policy=NullPolicy.ALLOW,
    ),
    ColumnSpec(
        "is_defaulted",
        aliases=("isDefaulted",),
        logical_type=TabularLogicalType.BOOLEAN,
        required=False,
        null_policy=NullPolicy.ALLOW,
    ),
    ColumnSpec(
        "is_gse",
        aliases=("isGse",),
        logical_type=TabularLogicalType.BOOLEAN,
        required=False,
        null_policy=NullPolicy.ALLOW,
    ),
    ColumnSpec(
        "is_pse",
        aliases=("isPse",),
        logical_type=TabularLogicalType.BOOLEAN,
        required=False,
        null_policy=NullPolicy.ALLOW,
    ),
    ColumnSpec(
        "is_covered_bond",
        aliases=("isCoveredBond",),
        logical_type=TabularLogicalType.BOOLEAN,
        required=False,
        null_policy=NullPolicy.ALLOW,
    ),
    ColumnSpec(
        "lineage_source_system",
        aliases=("source_system", "sourceSystem"),
        logical_type=TabularLogicalType.STRING,
    ),
    ColumnSpec(
        "lineage_source_file",
        aliases=("source_file", "sourceFile"),
        logical_type=TabularLogicalType.STRING,
    ),
    ColumnSpec(
        "citation_ids",
        aliases=("citationIds",),
        logical_type=TabularLogicalType.STRING,
        required=False,
        null_policy=NullPolicy.ALLOW,
    ),
)

DRC_SECURITISATION_NON_CTP_HANDOFF_COLUMN_SPECS: tuple[ColumnSpec, ...] = tuple(
    _replace_column_spec(
        spec,
        required=False,
        null_policy=NullPolicy.ALLOW,
    )
    if spec.name in {"seniority", "credit_quality"}
    else _replace_column_spec(spec, required=True, null_policy=NullPolicy.ALLOW)
    if spec.name == "issuer_id"
    else spec
    for spec in DRC_NONSEC_HANDOFF_COLUMN_SPECS
)

DRC_CTP_HANDOFF_COLUMN_SPECS: tuple[ColumnSpec, ...] = tuple(
    _replace_column_spec(
        spec,
        required=False,
        null_policy=NullPolicy.ALLOW,
    )
    if spec.name in {"seniority", "credit_quality", "issuer_id"}
    else spec
    for spec in DRC_NONSEC_HANDOFF_COLUMN_SPECS
)


def normalize_drc_nonsec_arrow_table(
    table: pa.Table,
    *,
    diagnostics: Sequence[AdapterDiagnostic] = (),
    metadata: Mapping[str, str] | None = None,
    rejected: pa.Table | None = None,
    source_hash: str | None = None,
) -> NormalizedTabularHandoff:
    """Normalize a raw Arrow table to the DRC non-securitisation handoff contract."""

    return normalize_arrow_table(
        table,
        column_specs=DRC_NONSEC_HANDOFF_COLUMN_SPECS,
        rejected=rejected,
        diagnostics=diagnostics,
        metadata={} if metadata is None else metadata,
        source_hash=source_hash,
        require_unique_row_ids=False,
    )


def normalize_drc_securitisation_non_ctp_arrow_table(
    table: pa.Table,
    *,
    diagnostics: Sequence[AdapterDiagnostic] = (),
    metadata: Mapping[str, str] | None = None,
    rejected: pa.Table | None = None,
    source_hash: str | None = None,
) -> NormalizedTabularHandoff:
    """Normalize a raw Arrow table to the DRC securitisation non-CTP handoff contract."""

    return normalize_arrow_table(
        table,
        column_specs=DRC_SECURITISATION_NON_CTP_HANDOFF_COLUMN_SPECS,
        rejected=rejected,
        diagnostics=diagnostics,
        metadata={} if metadata is None else metadata,
        source_hash=source_hash,
        require_unique_row_ids=False,
    )


def normalize_drc_ctp_arrow_table(
    table: pa.Table,
    *,
    diagnostics: Sequence[AdapterDiagnostic] = (),
    metadata: Mapping[str, str] | None = None,
    rejected: pa.Table | None = None,
    source_hash: str | None = None,
) -> NormalizedTabularHandoff:
    """Normalize a raw Arrow table to the DRC CTP handoff contract."""

    return normalize_arrow_table(
        table,
        column_specs=DRC_CTP_HANDOFF_COLUMN_SPECS,
        rejected=rejected,
        diagnostics=diagnostics,
        metadata={} if metadata is None else metadata,
        source_hash=source_hash,
        require_unique_row_ids=False,
    )


def build_drc_nonsec_batch_from_handoff(
    handoff: NormalizedTabularHandoff,
) -> DrcPositionBatch:
    """Build a DRC-owned non-securitisation batch from a normalized Arrow handoff."""

    if not isinstance(handoff, NormalizedTabularHandoff):
        raise DrcInputError("handoff must be NormalizedTabularHandoff")
    table = handoff.accepted
    validate_arrow_table(table, column_specs=DRC_NONSEC_HANDOFF_COLUMN_SPECS)
    diagnostics = tuple(diagnostic.as_dict() for diagnostic in handoff.diagnostics)
    return build_drc_nonsec_batch_from_columns(
        position_ids=_required_object_column(table, "position_id"),
        source_row_ids=_required_object_column(table, "source_row_id"),
        desk_ids=_required_object_column(table, "desk_id"),
        legal_entities=_required_object_column(table, "legal_entity"),
        risk_classes=_required_object_column(table, "risk_class"),
        instrument_types=_required_object_column(table, "instrument_type"),
        default_directions=_required_object_column(table, "default_direction"),
        issuer_ids=_required_object_column(table, "issuer_id"),
        tranche_ids=_optional_object_column(table, "tranche_id"),
        index_series_ids=_optional_object_column(table, "index_series_id"),
        bucket_keys=_required_object_column(table, "bucket_key"),
        seniorities=_required_object_column(table, "seniority"),
        credit_qualities=_required_object_column(table, "credit_quality"),
        notionals=_required_float_column(table, "notional"),
        market_values=_optional_float_column(table, "market_value"),
        cumulative_pnls=_optional_float_column(table, "cumulative_pnl"),
        maturity_years=_required_float_column(table, "maturity_years"),
        currencies=_required_object_column(table, "currency"),
        lgd_overrides=_optional_float_column(table, "lgd_override"),
        is_defaulted=_optional_bool_column(table, "is_defaulted"),
        is_gse=_optional_bool_column(table, "is_gse"),
        is_pse=_optional_bool_column(table, "is_pse"),
        is_covered_bond=_optional_bool_column(table, "is_covered_bond"),
        lineage_source_systems=_required_object_column(table, "lineage_source_system"),
        lineage_source_files=_required_object_column(table, "lineage_source_file"),
        lineage_present=np.ones(table.num_rows, dtype=np.bool_),
        citation_ids=_citation_ids_column(table),
        source_hash=handoff.source_hash,
        handoff_hash=normalized_handoff_hash(handoff),
        diagnostics=diagnostics,
        copy_arrays=False,
    )


def build_drc_securitisation_non_ctp_batch_from_handoff(
    handoff: NormalizedTabularHandoff,
) -> DrcPositionBatch:
    """Build a DRC-owned securitisation non-CTP batch from a normalized Arrow handoff."""

    if not isinstance(handoff, NormalizedTabularHandoff):
        raise DrcInputError("handoff must be NormalizedTabularHandoff")
    table = handoff.accepted
    validate_arrow_table(table, column_specs=DRC_SECURITISATION_NON_CTP_HANDOFF_COLUMN_SPECS)
    diagnostics = tuple(diagnostic.as_dict() for diagnostic in handoff.diagnostics)
    return build_drc_securitisation_non_ctp_batch_from_columns(
        position_ids=_required_object_column(table, "position_id"),
        source_row_ids=_required_object_column(table, "source_row_id"),
        desk_ids=_required_object_column(table, "desk_id"),
        legal_entities=_required_object_column(table, "legal_entity"),
        risk_classes=_required_object_column(table, "risk_class"),
        instrument_types=_required_object_column(table, "instrument_type"),
        default_directions=_required_object_column(table, "default_direction"),
        issuer_ids=_required_object_column(table, "issuer_id"),
        tranche_ids=_optional_object_column(table, "tranche_id"),
        index_series_ids=_optional_object_column(table, "index_series_id"),
        bucket_keys=_required_object_column(table, "bucket_key"),
        seniorities=_optional_object_column(table, "seniority"),
        credit_qualities=_optional_object_column(table, "credit_quality"),
        notionals=_required_float_column(table, "notional"),
        market_values=_optional_float_column(table, "market_value"),
        cumulative_pnls=_optional_float_column(table, "cumulative_pnl"),
        maturity_years=_required_float_column(table, "maturity_years"),
        currencies=_required_object_column(table, "currency"),
        lgd_overrides=_optional_float_column(table, "lgd_override"),
        is_defaulted=_optional_bool_column(table, "is_defaulted"),
        is_gse=_optional_bool_column(table, "is_gse"),
        is_pse=_optional_bool_column(table, "is_pse"),
        is_covered_bond=_optional_bool_column(table, "is_covered_bond"),
        lineage_source_systems=_required_object_column(table, "lineage_source_system"),
        lineage_source_files=_required_object_column(table, "lineage_source_file"),
        lineage_present=np.ones(table.num_rows, dtype=np.bool_),
        citation_ids=_citation_ids_column(table),
        source_hash=handoff.source_hash,
        handoff_hash=normalized_handoff_hash(handoff),
        diagnostics=diagnostics,
        copy_arrays=False,
    )


def build_drc_ctp_batch_from_handoff(
    handoff: NormalizedTabularHandoff,
) -> DrcPositionBatch:
    """Build a DRC-owned CTP batch from a normalized Arrow handoff."""

    if not isinstance(handoff, NormalizedTabularHandoff):
        raise DrcInputError("handoff must be NormalizedTabularHandoff")
    table = handoff.accepted
    validate_arrow_table(table, column_specs=DRC_CTP_HANDOFF_COLUMN_SPECS)
    diagnostics = tuple(diagnostic.as_dict() for diagnostic in handoff.diagnostics)
    return build_drc_ctp_batch_from_columns(
        position_ids=_required_object_column(table, "position_id"),
        source_row_ids=_required_object_column(table, "source_row_id"),
        desk_ids=_required_object_column(table, "desk_id"),
        legal_entities=_required_object_column(table, "legal_entity"),
        risk_classes=_required_object_column(table, "risk_class"),
        instrument_types=_required_object_column(table, "instrument_type"),
        default_directions=_required_object_column(table, "default_direction"),
        issuer_ids=_optional_object_column(table, "issuer_id"),
        tranche_ids=_optional_object_column(table, "tranche_id"),
        index_series_ids=_optional_object_column(table, "index_series_id"),
        bucket_keys=_required_object_column(table, "bucket_key"),
        seniorities=_optional_object_column(table, "seniority"),
        credit_qualities=_optional_object_column(table, "credit_quality"),
        notionals=_required_float_column(table, "notional"),
        market_values=_optional_float_column(table, "market_value"),
        cumulative_pnls=_optional_float_column(table, "cumulative_pnl"),
        maturity_years=_required_float_column(table, "maturity_years"),
        currencies=_required_object_column(table, "currency"),
        lgd_overrides=_optional_float_column(table, "lgd_override"),
        is_defaulted=_optional_bool_column(table, "is_defaulted"),
        is_gse=_optional_bool_column(table, "is_gse"),
        is_pse=_optional_bool_column(table, "is_pse"),
        is_covered_bond=_optional_bool_column(table, "is_covered_bond"),
        lineage_source_systems=_required_object_column(table, "lineage_source_system"),
        lineage_source_files=_required_object_column(table, "lineage_source_file"),
        lineage_present=np.ones(table.num_rows, dtype=np.bool_),
        citation_ids=_citation_ids_column(table),
        source_hash=handoff.source_hash,
        handoff_hash=normalized_handoff_hash(handoff),
        diagnostics=diagnostics,
        copy_arrays=False,
    )


def _required_object_column(table: pa.Table, column_name: str) -> npt.NDArray[np.object_]:
    if column_name not in table.column_names:
        raise DrcInputError(f"column is required: {column_name}")
    values = _object_array_from_arrow_column(table.column(column_name))
    values.setflags(write=False)
    return values


def _optional_object_column(table: pa.Table, column_name: str) -> npt.NDArray[np.object_] | None:
    if column_name not in table.column_names:
        return None
    values = _object_array_from_arrow_column(table.column(column_name))
    values.setflags(write=False)
    return values


def _required_float_column(table: pa.Table, column_name: str) -> npt.NDArray[np.float64]:
    if column_name not in table.column_names:
        raise DrcInputError(f"column is required: {column_name}")
    column = table.column(column_name)
    if column.null_count:
        raise DrcInputError(f"{column_name} must be provided")
    values = _float64_array_from_arrow_column(column, field=column_name)
    values.setflags(write=False)
    return values


def _optional_float_column(table: pa.Table, column_name: str) -> npt.NDArray[np.float64] | None:
    if column_name not in table.column_names:
        return None
    column = table.column(column_name)
    if not column.null_count:
        values = _float64_array_from_arrow_column(column, field=column_name)
        values.setflags(write=False)
        return values
    array = column.chunk(0) if column.num_chunks == 1 else column.combine_chunks()
    if not pa.types.is_float64(array.type):
        try:
            array = cast(pa.Array, pc.cast(array, pa.float64()))
        except (pa.ArrowInvalid, TypeError, ValueError) as exc:
            raise DrcInputError(f"{column_name} must be numeric") from exc
    values = np.asarray(
        pc.fill_null(array, pa.scalar(math.nan, type=pa.float64())).to_numpy(zero_copy_only=False),
        dtype=np.float64,
    )
    values.setflags(write=False)
    return values


def _optional_bool_column(table: pa.Table, column_name: str) -> npt.NDArray[np.bool_] | None:
    if column_name not in table.column_names:
        return None
    column = table.column(column_name)
    array = column.chunk(0) if column.num_chunks == 1 else column.combine_chunks()
    values = np.asarray(pc.fill_null(array, False).to_numpy(zero_copy_only=False), dtype=np.bool_)
    values.setflags(write=False)
    return values


def _citation_ids_column(table: pa.Table) -> tuple[tuple[str, ...], ...] | None:
    if "citation_ids" not in table.column_names:
        return None
    groups: list[tuple[str, ...]] = []
    for value in _object_array_from_arrow_column(table.column("citation_ids")):
        if value is None or not str(value).strip():
            groups.append(("US_NPR_210_SCOPE",))
            continue
        groups.append(tuple(item.strip() for item in str(value).split(",") if item.strip()))
    return tuple(groups)


def _object_array_from_arrow_column(column: pa.ChunkedArray) -> npt.NDArray[np.object_]:
    arrays = tuple(_object_array_from_arrow_array(chunk) for chunk in column.chunks)
    if not arrays:
        return np.empty(0, dtype=object)
    if len(arrays) == 1:
        return arrays[0]
    return np.concatenate(arrays).astype(object, copy=False)


def _object_array_from_arrow_array(array: pa.Array) -> npt.NDArray[np.object_]:
    if pa.types.is_dictionary(array.type):
        return _dictionary_array_to_object_array(cast(pa.DictionaryArray, array))
    return np.asarray(array.to_numpy(zero_copy_only=False), dtype=object)


def _dictionary_array_to_object_array(array: pa.DictionaryArray) -> npt.NDArray[np.object_]:
    if len(array) == 0:
        return np.empty(0, dtype=object)
    dictionary = np.asarray(array.dictionary.to_numpy(zero_copy_only=False), dtype=object)
    indices = np.asarray(
        pc.fill_null(array.indices, pa.scalar(0, type=array.indices.type)).to_numpy(
            zero_copy_only=False
        ),
        dtype=np.int64,
    )
    valid = np.asarray(array.is_valid().to_numpy(zero_copy_only=False), dtype=np.bool_)
    values = np.empty(len(array), dtype=object)
    values[valid] = dictionary[indices[valid]]
    values[~valid] = None
    return values


def _float64_array_from_arrow_column(
    column: pa.ChunkedArray,
    *,
    field: str,
) -> npt.NDArray[np.float64]:
    if len(column) == 0:
        return np.empty(0, dtype=np.float64)
    array = column.chunk(0) if column.num_chunks == 1 else column.combine_chunks()
    if not pa.types.is_float64(array.type):
        try:
            array = cast(pa.Array, pc.cast(array, pa.float64()))
        except (pa.ArrowInvalid, TypeError, ValueError) as exc:
            raise DrcInputError(f"{field} must be numeric") from exc
    try:
        return cast(npt.NDArray[np.float64], array.to_numpy(zero_copy_only=True))
    except (pa.ArrowInvalid, TypeError, ValueError):
        return np.asarray(array.to_numpy(zero_copy_only=False), dtype=np.float64)


__all__ = [
    "DRC_CTP_HANDOFF_COLUMN_SPECS",
    "DRC_NONSEC_HANDOFF_COLUMN_SPECS",
    "DRC_SECURITISATION_NON_CTP_HANDOFF_COLUMN_SPECS",
    "build_drc_ctp_batch_from_handoff",
    "build_drc_nonsec_batch_from_handoff",
    "build_drc_securitisation_non_ctp_batch_from_handoff",
    "normalize_drc_ctp_arrow_table",
    "normalize_drc_nonsec_arrow_table",
    "normalize_drc_securitisation_non_ctp_arrow_table",
]
