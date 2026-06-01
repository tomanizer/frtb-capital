"""Arrow handoff adapter for RRAO residual-risk batches."""

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

from frtb_rrao.batch import RraoPositionBatch, build_rrao_batch_from_columns
from frtb_rrao.validation import RraoInputError

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
    validate_arrow_table(table, column_specs=RRAO_HANDOFF_COLUMN_SPECS)
    _reject_unsupported_nested_payload(table)
    diagnostics = tuple(diagnostic.as_dict() for diagnostic in handoff.diagnostics)
    return build_rrao_batch_from_columns(
        position_ids=_required_object_column(table, "position_id"),
        source_row_ids=_required_object_column(table, "source_row_id"),
        desk_ids=_required_object_column(table, "desk_id"),
        legal_entities=_required_object_column(table, "legal_entity"),
        gross_effective_notionals=_required_float_column(table, "gross_effective_notional"),
        currencies=_required_object_column(table, "currency"),
        evidence_types=_required_object_column(table, "evidence_type"),
        evidence_labels=_required_object_column(table, "evidence_label"),
        classification_hints=_optional_object_column(table, "classification_hint"),
        exclusion_reasons=_optional_object_column(table, "exclusion_reason"),
        exclusion_evidence_ids=_optional_object_column(table, "exclusion_evidence_id"),
        back_to_back_match_group_ids=_optional_object_column(
            table,
            "back_to_back_match_group_id",
        ),
        back_to_back_matched_position_ids=_optional_object_column(
            table,
            "back_to_back_matched_position_id",
        ),
        supervisor_directive_ids=_optional_object_column(table, "supervisor_directive_id"),
        underlying_counts=_optional_object_column(table, "underlying_count"),
        is_path_dependents=_optional_object_column(table, "is_path_dependent"),
        has_maturities=_optional_object_column(table, "has_maturity"),
        has_strike_or_barriers=_optional_object_column(table, "has_strike_or_barrier"),
        has_multiple_strikes_or_barriers=_optional_object_column(
            table,
            "has_multiple_strikes_or_barriers",
        ),
        is_ctp_hedges=_optional_bool_column(table, "is_ctp_hedge"),
        is_investment_fund_exposures=_optional_bool_column(
            table,
            "is_investment_fund_exposure",
        ),
        investment_fund_ids=_optional_object_column(table, "investment_fund_id"),
        investment_fund_section_205_methods=_optional_object_column(
            table,
            "investment_fund_section_205_method",
        ),
        investment_fund_included_exposure_types=_optional_object_column(
            table,
            "investment_fund_included_exposure_type",
        ),
        investment_fund_mandate_evidence_ids=_optional_object_column(
            table,
            "investment_fund_mandate_evidence_id",
        ),
        investment_fund_section_205_evidence_ids=_optional_object_column(
            table,
            "investment_fund_section_205_evidence_id",
        ),
        investment_fund_gross_effective_notionals=_optional_float_column(
            table,
            "investment_fund_gross_effective_notional",
        ),
        investment_fund_included_exposure_ratios=_optional_float_column(
            table,
            "investment_fund_included_exposure_ratio",
        ),
        investment_fund_look_through_availables=_optional_bool_column(
            table,
            "investment_fund_look_through_available",
        ),
        investment_fund_mandate_allows_rrao_exposures=_optional_bool_column(
            table,
            "investment_fund_mandate_allows_rrao_exposures",
            default=True,
        ),
        notional_sources=_optional_object_column(table, "notional_source"),
        lineage_source_systems=_required_object_column(table, "lineage_source_system"),
        lineage_source_files=_required_object_column(table, "lineage_source_file"),
        lineage_source_row_ids=_optional_object_column(table, "lineage_source_row_id"),
        lineage_present=[True] * table.num_rows,
        citations=_citations_column(table),
        source_hash=handoff.source_hash,
        handoff_hash=normalized_handoff_hash(handoff),
        diagnostics=diagnostics,
        copy_arrays=False,
    )


def _reject_unsupported_nested_payload(table: pa.Table) -> None:
    if "unsupported_nested_payload" not in table.column_names:
        return
    for value in table.column("unsupported_nested_payload").combine_chunks().to_pylist():
        if value is not None and str(value).strip():
            raise RraoInputError(
                "unsupported nested payload requires flattened RRAO handoff columns",
                field="unsupported_nested_payload",
            )


def _required_object_column(table: pa.Table, column_name: str) -> list[object]:
    if column_name not in table.column_names:
        raise RraoInputError(f"column is required: {column_name}", field=column_name)
    return list(table.column(column_name).combine_chunks().to_pylist())


def _optional_object_column(table: pa.Table, column_name: str) -> list[object | None] | None:
    if column_name not in table.column_names:
        return None
    return list(table.column(column_name).combine_chunks().to_pylist())


def _required_float_column(table: pa.Table, column_name: str) -> list[object]:
    if column_name not in table.column_names:
        raise RraoInputError(f"column is required: {column_name}", field=column_name)
    return list(table.column(column_name).combine_chunks().to_pylist())


def _optional_float_column(table: pa.Table, column_name: str) -> list[object | None] | None:
    if column_name not in table.column_names:
        return None
    return [
        math.nan if value is None else value
        for value in table.column(column_name).combine_chunks().to_pylist()
    ]


def _optional_bool_column(
    table: pa.Table,
    column_name: str,
    *,
    default: bool = False,
) -> list[object] | None:
    if column_name not in table.column_names:
        return None
    return [
        default if value is None else value
        for value in table.column(column_name).combine_chunks().to_pylist()
    ]


def _citations_column(table: pa.Table) -> tuple[tuple[str, ...], ...] | None:
    if "citations" not in table.column_names:
        return None
    groups: list[tuple[str, ...]] = []
    for value in table.column("citations").combine_chunks().to_pylist():
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
