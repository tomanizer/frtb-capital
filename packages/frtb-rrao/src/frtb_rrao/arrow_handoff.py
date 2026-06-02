"""Arrow handoff adapter for RRAO residual-risk batches."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

import numpy as np
import numpy.typing as npt
import pyarrow as pa  # type: ignore[import-untyped]
from frtb_common import (
    AdapterDiagnostic,
    ColumnSpec,
    NormalizedTabularHandoff,
    NullPolicy,
    TabularLogicalType,
    normalize_arrow_table,
    normalized_handoff_hash,
    read_handoff_columns,
    resolve_column_name,
)

from frtb_rrao.batch import RraoPositionBatch, build_rrao_batch_from_columns
from frtb_rrao.validation import RraoInputError

HandoffColumnArray = npt.NDArray[Any]

RRAO_HANDOFF_COLUMN_SPECS: tuple[ColumnSpec, ...] = (
    ColumnSpec("position_id", aliases=("positionId",), logical_type=TabularLogicalType.STRING),
    ColumnSpec("source_row_id", aliases=("sourceRowId",), logical_type=TabularLogicalType.STRING),
    ColumnSpec("desk_id", aliases=("deskId",), logical_type=TabularLogicalType.STRING),
    ColumnSpec("legal_entity", aliases=("legalEntity",), logical_type=TabularLogicalType.STRING),
    ColumnSpec(
        "gross_effective_notional",
        aliases=("grossEffectiveNotional", "gross_notional"),
        logical_type=TabularLogicalType.FLOAT,
    ),
    ColumnSpec("currency", logical_type=TabularLogicalType.STRING),
    ColumnSpec(
        "evidence_type",
        aliases=("evidenceType",),
        logical_type=TabularLogicalType.STRING,
    ),
    ColumnSpec(
        "evidence_label",
        aliases=("evidenceLabel",),
        logical_type=TabularLogicalType.STRING,
    ),
    ColumnSpec(
        "classification_hint",
        aliases=("classificationHint",),
        logical_type=TabularLogicalType.STRING,
        required=False,
        null_policy=NullPolicy.ALLOW,
    ),
    ColumnSpec(
        "exclusion_reason",
        aliases=("exclusionReason",),
        logical_type=TabularLogicalType.STRING,
        required=False,
        null_policy=NullPolicy.ALLOW,
    ),
    ColumnSpec(
        "exclusion_evidence_id",
        aliases=("exclusionEvidenceId", "exclusionEvidenceID"),
        logical_type=TabularLogicalType.STRING,
        required=False,
        null_policy=NullPolicy.ALLOW,
    ),
    ColumnSpec(
        "back_to_back_match_group_id",
        aliases=("backToBackMatchGroupId", "backToBackMatchGroupID"),
        logical_type=TabularLogicalType.STRING,
        required=False,
        null_policy=NullPolicy.ALLOW,
    ),
    ColumnSpec(
        "back_to_back_matched_position_id",
        aliases=("backToBackMatchedPositionId", "backToBackMatchedPositionID"),
        logical_type=TabularLogicalType.STRING,
        required=False,
        null_policy=NullPolicy.ALLOW,
    ),
    ColumnSpec(
        "supervisor_directive_id",
        aliases=("supervisorDirectiveId", "supervisorDirectiveID"),
        logical_type=TabularLogicalType.STRING,
        required=False,
        null_policy=NullPolicy.ALLOW,
    ),
    ColumnSpec(
        "underlying_count",
        aliases=("underlyingCount",),
        logical_type=TabularLogicalType.INTEGER,
        required=False,
        null_policy=NullPolicy.ALLOW,
    ),
    ColumnSpec(
        "is_path_dependent",
        aliases=("isPathDependent",),
        logical_type=TabularLogicalType.BOOLEAN,
        required=False,
        null_policy=NullPolicy.ALLOW,
    ),
    ColumnSpec(
        "has_maturity",
        aliases=("hasMaturity",),
        logical_type=TabularLogicalType.BOOLEAN,
        required=False,
        null_policy=NullPolicy.ALLOW,
    ),
    ColumnSpec(
        "has_strike_or_barrier",
        aliases=("hasStrikeOrBarrier",),
        logical_type=TabularLogicalType.BOOLEAN,
        required=False,
        null_policy=NullPolicy.ALLOW,
    ),
    ColumnSpec(
        "has_multiple_strikes_or_barriers",
        aliases=("hasMultipleStrikesOrBarriers",),
        logical_type=TabularLogicalType.BOOLEAN,
        required=False,
        null_policy=NullPolicy.ALLOW,
    ),
    ColumnSpec(
        "is_ctp_hedge",
        aliases=("isCtpHedge",),
        logical_type=TabularLogicalType.BOOLEAN,
        required=False,
        null_policy=NullPolicy.ALLOW,
    ),
    ColumnSpec(
        "is_investment_fund_exposure",
        aliases=("isInvestmentFundExposure",),
        logical_type=TabularLogicalType.BOOLEAN,
        required=False,
        null_policy=NullPolicy.ALLOW,
    ),
    ColumnSpec(
        "investment_fund_id",
        aliases=("investmentFundId", "fund_id", "fundId"),
        logical_type=TabularLogicalType.STRING,
        required=False,
        null_policy=NullPolicy.ALLOW,
    ),
    ColumnSpec(
        "investment_fund_section_205_method",
        aliases=("investmentFundSection205Method", "section_205_method"),
        logical_type=TabularLogicalType.STRING,
        required=False,
        null_policy=NullPolicy.ALLOW,
    ),
    ColumnSpec(
        "investment_fund_included_exposure_type",
        aliases=("investmentFundIncludedExposureType", "included_exposure_type"),
        logical_type=TabularLogicalType.STRING,
        required=False,
        null_policy=NullPolicy.ALLOW,
    ),
    ColumnSpec(
        "investment_fund_mandate_evidence_id",
        aliases=("investmentFundMandateEvidenceId", "mandate_evidence_id"),
        logical_type=TabularLogicalType.STRING,
        required=False,
        null_policy=NullPolicy.ALLOW,
    ),
    ColumnSpec(
        "investment_fund_section_205_evidence_id",
        aliases=("investmentFundSection205EvidenceId", "section_205_evidence_id"),
        logical_type=TabularLogicalType.STRING,
        required=False,
        null_policy=NullPolicy.ALLOW,
    ),
    ColumnSpec(
        "investment_fund_gross_effective_notional",
        aliases=("investmentFundGrossEffectiveNotional", "fund_gross_effective_notional"),
        logical_type=TabularLogicalType.FLOAT,
        required=False,
        null_policy=NullPolicy.ALLOW,
    ),
    ColumnSpec(
        "investment_fund_included_exposure_ratio",
        aliases=("investmentFundIncludedExposureRatio", "included_exposure_ratio"),
        logical_type=TabularLogicalType.FLOAT,
        required=False,
        null_policy=NullPolicy.ALLOW,
    ),
    ColumnSpec(
        "investment_fund_look_through_available",
        aliases=("investmentFundLookThroughAvailable", "look_through_available"),
        logical_type=TabularLogicalType.BOOLEAN,
        required=False,
        null_policy=NullPolicy.ALLOW,
    ),
    ColumnSpec(
        "investment_fund_mandate_allows_rrao_exposures",
        aliases=("investmentFundMandateAllowsRraoExposures", "mandate_allows_rrao_exposures"),
        logical_type=TabularLogicalType.BOOLEAN,
        required=False,
        null_policy=NullPolicy.ALLOW,
    ),
    ColumnSpec(
        "notional_source",
        aliases=("notionalSource",),
        logical_type=TabularLogicalType.STRING,
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
        "lineage_source_row_id",
        aliases=("lineageSourceRowId", "sourceLineageRowId"),
        logical_type=TabularLogicalType.STRING,
        required=False,
        null_policy=NullPolicy.ALLOW,
    ),
    ColumnSpec(
        "citations",
        logical_type=TabularLogicalType.STRING,
        required=False,
        null_policy=NullPolicy.ALLOW,
    ),
    ColumnSpec(
        "unsupported_nested_payload",
        aliases=("investment_fund_descriptor", "back_to_back_match", "nested_payload"),
        logical_type=TabularLogicalType.STRING,
        required=False,
        null_policy=NullPolicy.ALLOW,
    ),
)


_RRAO_BATCH_COLUMN_ARGS: Mapping[str, str] = {
    "position_id": "position_ids",
    "source_row_id": "source_row_ids",
    "desk_id": "desk_ids",
    "legal_entity": "legal_entities",
    "gross_effective_notional": "gross_effective_notionals",
    "currency": "currencies",
    "evidence_type": "evidence_types",
    "evidence_label": "evidence_labels",
    "classification_hint": "classification_hints",
    "exclusion_reason": "exclusion_reasons",
    "exclusion_evidence_id": "exclusion_evidence_ids",
    "back_to_back_match_group_id": "back_to_back_match_group_ids",
    "back_to_back_matched_position_id": "back_to_back_matched_position_ids",
    "supervisor_directive_id": "supervisor_directive_ids",
    "underlying_count": "underlying_counts",
    "is_path_dependent": "is_path_dependents",
    "has_maturity": "has_maturities",
    "has_strike_or_barrier": "has_strike_or_barriers",
    "has_multiple_strikes_or_barriers": "has_multiple_strikes_or_barriers",
    "is_ctp_hedge": "is_ctp_hedges",
    "is_investment_fund_exposure": "is_investment_fund_exposures",
    "investment_fund_id": "investment_fund_ids",
    "investment_fund_section_205_method": "investment_fund_section_205_methods",
    "investment_fund_included_exposure_type": "investment_fund_included_exposure_types",
    "investment_fund_mandate_evidence_id": "investment_fund_mandate_evidence_ids",
    "investment_fund_section_205_evidence_id": "investment_fund_section_205_evidence_ids",
    "investment_fund_gross_effective_notional": "investment_fund_gross_effective_notionals",
    "investment_fund_included_exposure_ratio": "investment_fund_included_exposure_ratios",
    "investment_fund_look_through_available": "investment_fund_look_through_availables",
    "investment_fund_mandate_allows_rrao_exposures": (
        "investment_fund_mandate_allows_rrao_exposures"
    ),
    "notional_source": "notional_sources",
    "lineage_source_system": "lineage_source_systems",
    "lineage_source_file": "lineage_source_files",
    "lineage_source_row_id": "lineage_source_row_ids",
}
_RRAO_COLUMN_SPECS_BY_NAME: Mapping[str, ColumnSpec] = {
    spec.name: spec for spec in RRAO_HANDOFF_COLUMN_SPECS
}

_OPTIONAL_BOOL_OBJECT_COLUMNS = frozenset(
    {
        "is_path_dependent",
        "has_maturity",
        "has_strike_or_barrier",
        "has_multiple_strikes_or_barriers",
    }
)


def _ensure_explicit_logical_types(*spec_groups: Sequence[ColumnSpec]) -> None:
    unknown = tuple(
        spec.name
        for spec_group in spec_groups
        for spec in spec_group
        if spec.logical_type is TabularLogicalType.UNKNOWN
    )
    if unknown:
        raise RuntimeError("RRAO handoff specs must declare logical_type: " + ", ".join(unknown))


_ensure_explicit_logical_types(RRAO_HANDOFF_COLUMN_SPECS)


def normalize_rrao_arrow_table(
    table: pa.Table,
    *,
    diagnostics: Sequence[AdapterDiagnostic] = (),
    metadata: Mapping[str, str] | None = None,
    rejected: pa.Table | None = None,
    source_hash: str | None = None,
) -> NormalizedTabularHandoff:
    """Normalize a raw Arrow table to the RRAO handoff contract."""

    return normalize_arrow_table(
        table,
        column_specs=RRAO_HANDOFF_COLUMN_SPECS,
        rejected=rejected,
        diagnostics=diagnostics,
        metadata={} if metadata is None else metadata,
        source_hash=source_hash,
        require_unique_row_ids=False,
    )


def build_rrao_batch_from_handoff(
    handoff: NormalizedTabularHandoff,
) -> RraoPositionBatch:
    """Build an RRAO-owned residual-risk batch from a normalized Arrow handoff."""

    if not isinstance(handoff, NormalizedTabularHandoff):
        raise RraoInputError("handoff must be NormalizedTabularHandoff", field="handoff")
    table = handoff.accepted
    columns = read_handoff_columns(table, RRAO_HANDOFF_COLUMN_SPECS, error=_rrao_error)
    columns = _rrao_columns_with_package_defaults(table, columns)
    _reject_unsupported_nested_payload(columns.get("unsupported_nested_payload"))
    diagnostics = tuple(diagnostic.as_dict() for diagnostic in handoff.diagnostics)
    return build_rrao_batch_from_columns(
        **_rrao_batch_column_kwargs(columns),
        lineage_present=[True] * table.num_rows,
        citations=_citations_column(columns.get("citations")),
        source_hash=handoff.source_hash,
        handoff_hash=normalized_handoff_hash(handoff),
        diagnostics=diagnostics,
        copy_arrays=False,
    )


def _rrao_batch_column_kwargs(columns: Mapping[str, object]) -> dict[str, Any]:
    return {
        argument_name: columns.get(column_name)
        for column_name, argument_name in _RRAO_BATCH_COLUMN_ARGS.items()
    }


def _rrao_error(message: str, field: str | None) -> RraoInputError:
    return RraoInputError(message, field="" if field is None else field)


def _rrao_columns_with_package_defaults(
    table: pa.Table,
    columns: dict[str, HandoffColumnArray],
) -> dict[str, HandoffColumnArray]:
    updated = columns
    for column_name in _OPTIONAL_BOOL_OBJECT_COLUMNS:
        updated = _restore_null_values(table, updated, column_name, null_value=None)
    return _restore_null_values(
        table,
        updated,
        "investment_fund_mandate_allows_rrao_exposures",
        null_value=True,
    )


def _restore_null_values(
    table: pa.Table,
    columns: dict[str, HandoffColumnArray],
    column_name: str,
    *,
    null_value: object,
) -> dict[str, HandoffColumnArray]:
    values = columns.get(column_name)
    physical_column_name = resolve_column_name(table, _RRAO_COLUMN_SPECS_BY_NAME[column_name])
    if values is None or physical_column_name is None:
        return columns

    column = table.column(physical_column_name)
    if not column.null_count:
        return columns

    array = column.chunk(0) if column.num_chunks == 1 else column.combine_chunks()
    valid = np.asarray(array.is_valid().to_numpy(zero_copy_only=False), dtype=np.bool_)
    restored = values.astype(object)
    restored[~valid] = null_value
    restored.setflags(write=False)
    return columns | {column_name: restored}


def _reject_unsupported_nested_payload(values: HandoffColumnArray | None) -> None:
    if values is None:
        return
    for value in values:
        if value is not None and str(value).strip():
            raise RraoInputError(
                "unsupported nested payload requires flattened RRAO handoff columns",
                field="unsupported_nested_payload",
            )


def _citations_column(values: HandoffColumnArray | None) -> tuple[tuple[str, ...], ...] | None:
    if values is None:
        return None
    groups: list[tuple[str, ...]] = []
    for value in values:
        if value is None or not str(value).strip():
            groups.append(())
            continue
        groups.append(tuple(item.strip() for item in str(value).split(",") if item.strip()))
    return tuple(groups)


__all__ = [
    "RRAO_HANDOFF_COLUMN_SPECS",
    "build_rrao_batch_from_handoff",
    "normalize_rrao_arrow_table",
]
