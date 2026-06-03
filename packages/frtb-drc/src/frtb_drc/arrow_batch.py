"""Arrow batch adapters for DRC batches."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

import numpy as np
import numpy.typing as npt
import pyarrow as pa  # type: ignore[import-untyped]
from frtb_common import (
    AdapterDiagnostic,
    ColumnSpec,
    NormalizedArrowTable,
    NullPolicy,
    TabularLogicalType,
    normalize_arrow_table,
    normalized_arrow_table_hash,
    read_arrow_columns,
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


DRC_NONSEC_ARROW_COLUMN_SPECS: tuple[ColumnSpec, ...] = (
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

DRC_SECURITISATION_NON_CTP_ARROW_COLUMN_SPECS: tuple[ColumnSpec, ...] = tuple(
    _replace_column_spec(
        spec,
        required=False,
        null_policy=NullPolicy.ALLOW,
    )
    if spec.name in {"seniority", "credit_quality"}
    else _replace_column_spec(spec, required=True, null_policy=NullPolicy.ALLOW)
    if spec.name == "issuer_id"
    else spec
    for spec in DRC_NONSEC_ARROW_COLUMN_SPECS
)

DRC_CTP_ARROW_COLUMN_SPECS: tuple[ColumnSpec, ...] = tuple(
    _replace_column_spec(
        spec,
        required=False,
        null_policy=NullPolicy.ALLOW,
    )
    if spec.name in {"seniority", "credit_quality", "issuer_id"}
    else spec
    for spec in DRC_NONSEC_ARROW_COLUMN_SPECS
)
_DRC_BATCH_COLUMN_ARGS: Mapping[str, str] = {
    "position_id": "position_ids",
    "source_row_id": "source_row_ids",
    "desk_id": "desk_ids",
    "legal_entity": "legal_entities",
    "risk_class": "risk_classes",
    "instrument_type": "instrument_types",
    "default_direction": "default_directions",
    "issuer_id": "issuer_ids",
    "tranche_id": "tranche_ids",
    "index_series_id": "index_series_ids",
    "bucket_key": "bucket_keys",
    "seniority": "seniorities",
    "credit_quality": "credit_qualities",
    "notional": "notionals",
    "market_value": "market_values",
    "cumulative_pnl": "cumulative_pnls",
    "maturity_years": "maturity_years",
    "currency": "currencies",
    "lgd_override": "lgd_overrides",
    "is_defaulted": "is_defaulted",
    "is_gse": "is_gse",
    "is_pse": "is_pse",
    "is_covered_bond": "is_covered_bond",
    "lineage_source_system": "lineage_source_systems",
    "lineage_source_file": "lineage_source_files",
}


def _ensure_explicit_logical_types(*spec_groups: Sequence[ColumnSpec]) -> None:
    unknown = tuple(
        spec.name
        for spec_group in spec_groups
        for spec in spec_group
        if spec.logical_type is TabularLogicalType.UNKNOWN
    )
    if unknown:
        raise RuntimeError("DRC Arrow specs must declare logical_type: " + ", ".join(unknown))


_ensure_explicit_logical_types(
    DRC_NONSEC_ARROW_COLUMN_SPECS,
    DRC_SECURITISATION_NON_CTP_ARROW_COLUMN_SPECS,
    DRC_CTP_ARROW_COLUMN_SPECS,
)


def normalize_drc_nonsec_arrow_table(
    table: pa.Table,
    *,
    diagnostics: Sequence[AdapterDiagnostic] = (),
    metadata: Mapping[str, str] | None = None,
    rejected: pa.Table | None = None,
    source_hash: str | None = None,
) -> NormalizedArrowTable:
    """Normalize a raw Arrow table to the DRC non-securitisation batch contract."""

    return normalize_arrow_table(
        table,
        column_specs=DRC_NONSEC_ARROW_COLUMN_SPECS,
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
) -> NormalizedArrowTable:
    """Normalize a raw Arrow table to the DRC securitisation non-CTP batch contract."""

    return normalize_arrow_table(
        table,
        column_specs=DRC_SECURITISATION_NON_CTP_ARROW_COLUMN_SPECS,
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
) -> NormalizedArrowTable:
    """Normalize a raw Arrow table to the DRC CTP batch contract."""

    return normalize_arrow_table(
        table,
        column_specs=DRC_CTP_ARROW_COLUMN_SPECS,
        rejected=rejected,
        diagnostics=diagnostics,
        metadata={} if metadata is None else metadata,
        source_hash=source_hash,
        require_unique_row_ids=False,
    )


def build_drc_nonsec_batch_from_arrow(
    handoff: NormalizedArrowTable,
) -> DrcPositionBatch:
    """Build a DRC-owned non-securitisation batch from a normalized Arrow batch."""

    if not isinstance(handoff, NormalizedArrowTable):
        raise DrcInputError("handoff must be NormalizedArrowTable")
    table = handoff.accepted
    columns = read_arrow_columns(table, DRC_NONSEC_ARROW_COLUMN_SPECS, error=_drc_error)
    diagnostics = tuple(diagnostic.as_dict() for diagnostic in handoff.diagnostics)
    return build_drc_nonsec_batch_from_columns(
        **_drc_batch_column_kwargs(columns),
        lineage_present=np.ones(table.num_rows, dtype=np.bool_),
        citation_ids=_citation_ids_column(columns.get("citation_ids")),
        source_hash=handoff.source_hash,
        handoff_hash=normalized_arrow_table_hash(handoff),
        diagnostics=diagnostics,
        copy_arrays=False,
    )


def build_drc_securitisation_non_ctp_batch_from_arrow(
    handoff: NormalizedArrowTable,
) -> DrcPositionBatch:
    """Build a DRC-owned securitisation non-CTP batch from a normalized Arrow batch."""

    if not isinstance(handoff, NormalizedArrowTable):
        raise DrcInputError("handoff must be NormalizedArrowTable")
    table = handoff.accepted
    columns = read_arrow_columns(
        table,
        DRC_SECURITISATION_NON_CTP_ARROW_COLUMN_SPECS,
        error=_drc_error,
    )
    diagnostics = tuple(diagnostic.as_dict() for diagnostic in handoff.diagnostics)
    return build_drc_securitisation_non_ctp_batch_from_columns(
        **_drc_batch_column_kwargs(columns),
        lineage_present=np.ones(table.num_rows, dtype=np.bool_),
        citation_ids=_citation_ids_column(columns.get("citation_ids")),
        source_hash=handoff.source_hash,
        handoff_hash=normalized_arrow_table_hash(handoff),
        diagnostics=diagnostics,
        copy_arrays=False,
    )


def build_drc_ctp_batch_from_arrow(
    handoff: NormalizedArrowTable,
) -> DrcPositionBatch:
    """Build a DRC-owned CTP batch from a normalized Arrow batch."""

    if not isinstance(handoff, NormalizedArrowTable):
        raise DrcInputError("handoff must be NormalizedArrowTable")
    table = handoff.accepted
    columns = read_arrow_columns(table, DRC_CTP_ARROW_COLUMN_SPECS, error=_drc_error)
    diagnostics = tuple(diagnostic.as_dict() for diagnostic in handoff.diagnostics)
    return build_drc_ctp_batch_from_columns(
        **_drc_batch_column_kwargs(columns),
        lineage_present=np.ones(table.num_rows, dtype=np.bool_),
        citation_ids=_citation_ids_column(columns.get("citation_ids")),
        source_hash=handoff.source_hash,
        handoff_hash=normalized_arrow_table_hash(handoff),
        diagnostics=diagnostics,
        copy_arrays=False,
    )


def _drc_batch_column_kwargs(columns: Mapping[str, object]) -> dict[str, Any]:
    return {
        argument_name: columns.get(column_name)
        for column_name, argument_name in _DRC_BATCH_COLUMN_ARGS.items()
    }


def _drc_error(message: str, _field: str | None) -> DrcInputError:
    return DrcInputError(message)


def _citation_ids_column(values: npt.NDArray[Any] | None) -> tuple[tuple[str, ...], ...] | None:
    if values is None:
        return None
    groups: list[tuple[str, ...]] = []
    for value in values:
        if value is None or not str(value).strip():
            groups.append(("US_NPR_210_SCOPE",))
            continue
        groups.append(tuple(item.strip() for item in str(value).split(",") if item.strip()))
    return tuple(groups)


__all__ = [
    "DRC_CTP_ARROW_COLUMN_SPECS",
    "DRC_NONSEC_ARROW_COLUMN_SPECS",
    "DRC_SECURITISATION_NON_CTP_ARROW_COLUMN_SPECS",
    "build_drc_ctp_batch_from_arrow",
    "build_drc_nonsec_batch_from_arrow",
    "build_drc_securitisation_non_ctp_batch_from_arrow",
    "normalize_drc_ctp_arrow_table",
    "normalize_drc_nonsec_arrow_table",
    "normalize_drc_securitisation_non_ctp_arrow_table",
]
