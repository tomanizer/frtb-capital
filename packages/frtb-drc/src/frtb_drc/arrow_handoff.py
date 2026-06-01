"""Arrow handoff adapter for DRC non-securitisation batches."""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence

import pyarrow as pa  # type: ignore[import-untyped]
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

from frtb_drc.batch import DrcPositionBatch, build_drc_nonsec_batch_from_columns
from frtb_drc.validation import DrcInputError

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
        lineage_present=[True] * table.num_rows,
        citation_ids=_citation_ids_column(table),
        source_hash=handoff.source_hash,
        handoff_hash=normalized_handoff_hash(handoff),
        diagnostics=diagnostics,
        copy_arrays=False,
    )


def _required_object_column(table: pa.Table, column_name: str) -> list[object]:
    if column_name not in table.column_names:
        raise DrcInputError(f"column is required: {column_name}")
    values = table.column(column_name).combine_chunks().to_pylist()
    return list(values)


def _optional_object_column(table: pa.Table, column_name: str) -> list[object | None] | None:
    if column_name not in table.column_names:
        return None
    return list(table.column(column_name).combine_chunks().to_pylist())


def _required_float_column(table: pa.Table, column_name: str) -> list[object]:
    if column_name not in table.column_names:
        raise DrcInputError(f"column is required: {column_name}")
    return list(table.column(column_name).combine_chunks().to_pylist())


def _optional_float_column(table: pa.Table, column_name: str) -> list[object | None] | None:
    if column_name not in table.column_names:
        return None
    values = [
        math.nan if value is None else value
        for value in table.column(column_name).combine_chunks().to_pylist()
    ]
    return values


def _optional_bool_column(table: pa.Table, column_name: str) -> list[object] | None:
    if column_name not in table.column_names:
        return None
    values: list[object] = [
        False if value is None else bool(value)
        for value in table.column(column_name).combine_chunks().to_pylist()
    ]
    return values


def _citation_ids_column(table: pa.Table) -> tuple[tuple[str, ...], ...] | None:
    if "citation_ids" not in table.column_names:
        return None
    groups: list[tuple[str, ...]] = []
    for value in table.column("citation_ids").combine_chunks().to_pylist():
        if value is None or not str(value).strip():
            groups.append(("US_NPR_210_SCOPE",))
            continue
        groups.append(tuple(item.strip() for item in str(value).split(",") if item.strip()))
    return tuple(groups)


__all__ = [
    "DRC_NONSEC_HANDOFF_COLUMN_SPECS",
    "build_drc_nonsec_batch_from_handoff",
    "normalize_drc_nonsec_arrow_table",
]
