"""Arrow handoff adapters for CVA batch inputs."""

from __future__ import annotations

import warnings
from collections.abc import Mapping, Sequence
from typing import Any

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

from frtb_cva.batch import (
    CvaCounterpartyBatch,
    CvaHedgeBatch,
    CvaNettingSetBatch,
    SaCvaSensitivityBatch,
    build_cva_counterparty_batch_from_columns,
    build_cva_hedge_batch_from_columns,
    build_cva_netting_set_batch_from_columns,
    build_sa_cva_sensitivity_batch_from_columns,
)
from frtb_cva.validation import CvaInputError

CVA_COUNTERPARTY_ARROW_COLUMN_SPECS: tuple[ColumnSpec, ...] = (
    ColumnSpec(
        "counterparty_id",
        aliases=("counterpartyId", "CounterpartyID"),
        logical_type=TabularLogicalType.STRING,
    ),
    ColumnSpec("desk_id", aliases=("deskId", "DeskID"), logical_type=TabularLogicalType.STRING),
    ColumnSpec(
        "legal_entity",
        aliases=("legalEntity", "LegalEntity"),
        logical_type=TabularLogicalType.STRING,
    ),
    ColumnSpec("sector", logical_type=TabularLogicalType.STRING),
    ColumnSpec(
        "credit_quality", aliases=("creditQuality",), logical_type=TabularLogicalType.STRING
    ),
    ColumnSpec("region", logical_type=TabularLogicalType.STRING),
    ColumnSpec(
        "source_row_id",
        aliases=("sourceRowId", "RowID"),
        logical_type=TabularLogicalType.STRING,
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
        aliases=("lineageSourceRowId",),
        logical_type=TabularLogicalType.STRING,
        required=False,
        null_policy=NullPolicy.ALLOW,
    ),
)

CVA_NETTING_SET_ARROW_COLUMN_SPECS: tuple[ColumnSpec, ...] = (
    ColumnSpec(
        "netting_set_id",
        aliases=("nettingSetId", "NettingSetID"),
        logical_type=TabularLogicalType.STRING,
    ),
    ColumnSpec(
        "counterparty_id",
        aliases=("counterpartyId", "CounterpartyID"),
        logical_type=TabularLogicalType.STRING,
    ),
    ColumnSpec("ead", aliases=("EAD", "exposure"), logical_type=TabularLogicalType.FLOAT),
    ColumnSpec(
        "effective_maturity",
        aliases=("effectiveMaturity", "maturity"),
        logical_type=TabularLogicalType.FLOAT,
    ),
    ColumnSpec(
        "discount_factor", aliases=("discountFactor",), logical_type=TabularLogicalType.FLOAT
    ),
    ColumnSpec("currency", logical_type=TabularLogicalType.STRING),
    ColumnSpec(
        "sign_convention", aliases=("signConvention",), logical_type=TabularLogicalType.STRING
    ),
    ColumnSpec("uses_imm_ead", aliases=("usesImmEad",), logical_type=TabularLogicalType.BOOLEAN),
    ColumnSpec(
        "source_row_id",
        aliases=("sourceRowId", "RowID"),
        logical_type=TabularLogicalType.STRING,
    ),
    ColumnSpec(
        "carved_out_to_ba_cva",
        aliases=("carvedOutToBaCva",),
        logical_type=TabularLogicalType.BOOLEAN,
        required=False,
        null_policy=NullPolicy.ALLOW,
    ),
    ColumnSpec(
        "discount_factor_explicit",
        aliases=("discountFactorExplicit",),
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
        "lineage_source_row_id",
        aliases=("lineageSourceRowId",),
        logical_type=TabularLogicalType.STRING,
        required=False,
        null_policy=NullPolicy.ALLOW,
    ),
)

CVA_HEDGE_ARROW_COLUMN_SPECS: tuple[ColumnSpec, ...] = (
    ColumnSpec("hedge_id", aliases=("hedgeId", "HedgeID"), logical_type=TabularLogicalType.STRING),
    ColumnSpec(
        "source_row_id",
        aliases=("sourceRowId", "RowID"),
        logical_type=TabularLogicalType.STRING,
    ),
    ColumnSpec(
        "counterparty_id",
        aliases=("counterpartyId", "CounterpartyID"),
        logical_type=TabularLogicalType.STRING,
    ),
    ColumnSpec("hedge_type", aliases=("hedgeType",), logical_type=TabularLogicalType.STRING),
    ColumnSpec("notional", logical_type=TabularLogicalType.FLOAT),
    ColumnSpec(
        "remaining_maturity", aliases=("remainingMaturity",), logical_type=TabularLogicalType.FLOAT
    ),
    ColumnSpec(
        "discount_factor", aliases=("discountFactor",), logical_type=TabularLogicalType.FLOAT
    ),
    ColumnSpec(
        "reference_sector", aliases=("referenceSector",), logical_type=TabularLogicalType.STRING
    ),
    ColumnSpec(
        "reference_credit_quality",
        aliases=("referenceCreditQuality",),
        logical_type=TabularLogicalType.STRING,
    ),
    ColumnSpec(
        "reference_region", aliases=("referenceRegion",), logical_type=TabularLogicalType.STRING
    ),
    ColumnSpec(
        "reference_relation", aliases=("referenceRelation",), logical_type=TabularLogicalType.STRING
    ),
    ColumnSpec("eligibility", logical_type=TabularLogicalType.STRING),
    ColumnSpec("is_internal", aliases=("isInternal",), logical_type=TabularLogicalType.BOOLEAN),
    ColumnSpec(
        "discount_factor_explicit",
        aliases=("discountFactorExplicit",),
        logical_type=TabularLogicalType.BOOLEAN,
        required=False,
        null_policy=NullPolicy.ALLOW,
    ),
    ColumnSpec(
        "internal_desk_counterparty_id",
        aliases=("internalDeskCounterpartyId",),
        logical_type=TabularLogicalType.STRING,
        required=False,
        null_policy=NullPolicy.ALLOW,
    ),
    ColumnSpec(
        "sa_cva_risk_class",
        aliases=("saCvaRiskClass",),
        logical_type=TabularLogicalType.STRING,
        required=False,
        null_policy=NullPolicy.ALLOW,
    ),
    ColumnSpec(
        "eligibility_evidence_id",
        aliases=("eligibilityEvidenceId",),
        logical_type=TabularLogicalType.STRING,
        required=False,
        null_policy=NullPolicy.ALLOW,
    ),
    ColumnSpec(
        "rejection_reason",
        aliases=("rejectionReason",),
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
        aliases=("lineageSourceRowId",),
        logical_type=TabularLogicalType.STRING,
        required=False,
        null_policy=NullPolicy.ALLOW,
    ),
)

SA_CVA_SENSITIVITY_ARROW_COLUMN_SPECS: tuple[ColumnSpec, ...] = (
    ColumnSpec(
        "sensitivity_id",
        aliases=("sensitivityId", "SensitivityID", "RiskFactorID"),
        logical_type=TabularLogicalType.STRING,
    ),
    ColumnSpec("risk_class", aliases=("riskClass",), logical_type=TabularLogicalType.STRING),
    ColumnSpec("risk_measure", aliases=("riskMeasure",), logical_type=TabularLogicalType.STRING),
    ColumnSpec(
        "sensitivity_tag", aliases=("sensitivityTag", "tag"), logical_type=TabularLogicalType.STRING
    ),
    ColumnSpec("bucket_id", aliases=("bucketId", "bucket"), logical_type=TabularLogicalType.STRING),
    ColumnSpec(
        "risk_factor_key",
        aliases=("riskFactorKey", "qualifier"),
        logical_type=TabularLogicalType.STRING,
    ),
    ColumnSpec("amount", aliases=("Amount",), logical_type=TabularLogicalType.FLOAT),
    ColumnSpec(
        "amount_currency",
        aliases=("amountCurrency", "currency"),
        logical_type=TabularLogicalType.STRING,
    ),
    ColumnSpec(
        "sign_convention", aliases=("signConvention",), logical_type=TabularLogicalType.STRING
    ),
    ColumnSpec(
        "source_row_id",
        aliases=("sourceRowId", "RowID"),
        logical_type=TabularLogicalType.STRING,
    ),
    ColumnSpec(
        "tenor",
        logical_type=TabularLogicalType.STRING,
        required=False,
        null_policy=NullPolicy.ALLOW,
    ),
    ColumnSpec(
        "volatility_input",
        aliases=("volatilityInput",),
        logical_type=TabularLogicalType.FLOAT,
        required=False,
        null_policy=NullPolicy.ALLOW,
    ),
    ColumnSpec(
        "hedge_id",
        aliases=("hedgeId",),
        logical_type=TabularLogicalType.STRING,
        required=False,
        null_policy=NullPolicy.ALLOW,
    ),
    ColumnSpec(
        "index_treatment",
        aliases=("indexTreatment",),
        logical_type=TabularLogicalType.STRING,
        required=False,
        null_policy=NullPolicy.ALLOW,
    ),
    ColumnSpec(
        "index_max_sector_weight",
        aliases=("indexMaxSectorWeight",),
        logical_type=TabularLogicalType.FLOAT,
        required=False,
        null_policy=NullPolicy.ALLOW,
    ),
    ColumnSpec(
        "index_homogeneous_sector_quality",
        aliases=("indexHomogeneousSectorQuality",),
        logical_type=TabularLogicalType.BOOLEAN,
        required=False,
        null_policy=NullPolicy.ALLOW,
    ),
    ColumnSpec(
        "index_dominant_sector",
        aliases=("indexDominantSector",),
        logical_type=TabularLogicalType.STRING,
        required=False,
        null_policy=NullPolicy.ALLOW,
    ),
    ColumnSpec(
        "index_remap_bucket_id",
        aliases=("indexRemapBucketId",),
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
        aliases=("lineageSourceRowId",),
        logical_type=TabularLogicalType.STRING,
        required=False,
        null_policy=NullPolicy.ALLOW,
    ),
)
CVA_COUNTERPARTY_HANDOFF_COLUMN_SPECS = CVA_COUNTERPARTY_ARROW_COLUMN_SPECS
CVA_NETTING_SET_HANDOFF_COLUMN_SPECS = CVA_NETTING_SET_ARROW_COLUMN_SPECS
CVA_HEDGE_HANDOFF_COLUMN_SPECS = CVA_HEDGE_ARROW_COLUMN_SPECS
SA_CVA_SENSITIVITY_HANDOFF_COLUMN_SPECS = SA_CVA_SENSITIVITY_ARROW_COLUMN_SPECS


_CVA_COUNTERPARTY_BATCH_COLUMN_ARGS: Mapping[str, str] = {
    "counterparty_id": "counterparty_ids",
    "desk_id": "desk_ids",
    "legal_entity": "legal_entities",
    "sector": "sectors",
    "credit_quality": "credit_qualities",
    "region": "regions",
    "source_row_id": "source_row_ids",
    "lineage_source_system": "lineage_source_systems",
    "lineage_source_file": "lineage_source_files",
    "lineage_source_row_id": "lineage_source_row_ids",
}

_CVA_NETTING_SET_BATCH_COLUMN_ARGS: Mapping[str, str] = {
    "netting_set_id": "netting_set_ids",
    "counterparty_id": "counterparty_ids",
    "ead": "eads",
    "effective_maturity": "effective_maturities",
    "discount_factor": "discount_factors",
    "currency": "currencies",
    "sign_convention": "sign_conventions",
    "uses_imm_ead": "uses_imm_eads",
    "source_row_id": "source_row_ids",
    "carved_out_to_ba_cva": "carved_out_to_ba_cva",
    "discount_factor_explicit": "discount_factor_explicit",
    "lineage_source_system": "lineage_source_systems",
    "lineage_source_file": "lineage_source_files",
    "lineage_source_row_id": "lineage_source_row_ids",
}

_CVA_HEDGE_BATCH_COLUMN_ARGS: Mapping[str, str] = {
    "hedge_id": "hedge_ids",
    "source_row_id": "source_row_ids",
    "counterparty_id": "counterparty_ids",
    "hedge_type": "hedge_types",
    "notional": "notionals",
    "remaining_maturity": "remaining_maturities",
    "discount_factor": "discount_factors",
    "reference_sector": "reference_sectors",
    "reference_credit_quality": "reference_credit_qualities",
    "reference_region": "reference_regions",
    "reference_relation": "reference_relations",
    "eligibility": "eligibilities",
    "is_internal": "is_internal",
    "discount_factor_explicit": "discount_factor_explicit",
    "internal_desk_counterparty_id": "internal_desk_counterparty_ids",
    "sa_cva_risk_class": "sa_cva_risk_classes",
    "eligibility_evidence_id": "eligibility_evidence_ids",
    "rejection_reason": "rejection_reasons",
    "lineage_source_system": "lineage_source_systems",
    "lineage_source_file": "lineage_source_files",
    "lineage_source_row_id": "lineage_source_row_ids",
}

_SA_CVA_SENSITIVITY_BATCH_COLUMN_ARGS: Mapping[str, str] = {
    "sensitivity_id": "sensitivity_ids",
    "risk_class": "risk_classes",
    "risk_measure": "risk_measures",
    "sensitivity_tag": "sensitivity_tags",
    "bucket_id": "bucket_ids",
    "risk_factor_key": "risk_factor_keys",
    "amount": "amounts",
    "amount_currency": "amount_currencies",
    "sign_convention": "sign_conventions",
    "source_row_id": "source_row_ids",
    "tenor": "tenors",
    "volatility_input": "volatility_inputs",
    "hedge_id": "hedge_ids",
    "index_treatment": "index_treatments",
    "index_max_sector_weight": "index_max_sector_weights",
    "index_homogeneous_sector_quality": "index_homogeneous_sector_quality",
    "index_dominant_sector": "index_dominant_sectors",
    "index_remap_bucket_id": "index_remap_bucket_ids",
    "lineage_source_system": "lineage_source_systems",
    "lineage_source_file": "lineage_source_files",
    "lineage_source_row_id": "lineage_source_row_ids",
}


def _ensure_explicit_logical_types(*spec_groups: Sequence[ColumnSpec]) -> None:
    unknown = tuple(
        spec.name
        for spec_group in spec_groups
        for spec in spec_group
        if spec.logical_type is TabularLogicalType.UNKNOWN
    )
    if unknown:
        raise RuntimeError("CVA handoff specs must declare logical_type: " + ", ".join(unknown))


_ensure_explicit_logical_types(
    CVA_COUNTERPARTY_ARROW_COLUMN_SPECS,
    CVA_NETTING_SET_ARROW_COLUMN_SPECS,
    CVA_HEDGE_ARROW_COLUMN_SPECS,
    SA_CVA_SENSITIVITY_ARROW_COLUMN_SPECS,
)


def normalize_cva_counterparty_arrow_table(
    table: pa.Table,
    *,
    diagnostics: Sequence[AdapterDiagnostic] = (),
    metadata: Mapping[str, str] | None = None,
    rejected: pa.Table | None = None,
    source_hash: str | None = None,
) -> NormalizedArrowTable:
    return _normalize(
        table, CVA_COUNTERPARTY_ARROW_COLUMN_SPECS, diagnostics, metadata, rejected, source_hash
    )


def normalize_cva_netting_set_arrow_table(
    table: pa.Table,
    *,
    diagnostics: Sequence[AdapterDiagnostic] = (),
    metadata: Mapping[str, str] | None = None,
    rejected: pa.Table | None = None,
    source_hash: str | None = None,
) -> NormalizedArrowTable:
    return _normalize(
        table, CVA_NETTING_SET_ARROW_COLUMN_SPECS, diagnostics, metadata, rejected, source_hash
    )


def normalize_cva_hedge_arrow_table(
    table: pa.Table,
    *,
    diagnostics: Sequence[AdapterDiagnostic] = (),
    metadata: Mapping[str, str] | None = None,
    rejected: pa.Table | None = None,
    source_hash: str | None = None,
) -> NormalizedArrowTable:
    return _normalize(
        table, CVA_HEDGE_ARROW_COLUMN_SPECS, diagnostics, metadata, rejected, source_hash
    )


def normalize_sa_cva_sensitivity_arrow_table(
    table: pa.Table,
    *,
    diagnostics: Sequence[AdapterDiagnostic] = (),
    metadata: Mapping[str, str] | None = None,
    rejected: pa.Table | None = None,
    source_hash: str | None = None,
) -> NormalizedArrowTable:
    return _normalize(
        table, SA_CVA_SENSITIVITY_ARROW_COLUMN_SPECS, diagnostics, metadata, rejected, source_hash
    )


def build_cva_counterparty_batch_from_arrow(
    handoff: NormalizedArrowTable,
) -> CvaCounterpartyBatch:
    if not isinstance(handoff, NormalizedArrowTable):
        raise CvaInputError("handoff must be NormalizedArrowTable", field="handoff")
    table = handoff.accepted
    columns = read_arrow_columns(table, CVA_COUNTERPARTY_ARROW_COLUMN_SPECS, error=_cva_error)
    return build_cva_counterparty_batch_from_columns(
        **_cva_batch_column_kwargs(columns, _CVA_COUNTERPARTY_BATCH_COLUMN_ARGS),
        source_hash=handoff.source_hash,
        handoff_hash=normalized_arrow_table_hash(handoff),
        diagnostics=_diagnostics(handoff),
        copy_arrays=False,
    )


def build_cva_netting_set_batch_from_arrow(
    handoff: NormalizedArrowTable,
) -> CvaNettingSetBatch:
    if not isinstance(handoff, NormalizedArrowTable):
        raise CvaInputError("handoff must be NormalizedArrowTable", field="handoff")
    table = handoff.accepted
    columns = read_arrow_columns(table, CVA_NETTING_SET_ARROW_COLUMN_SPECS, error=_cva_error)
    return build_cva_netting_set_batch_from_columns(
        **_cva_batch_column_kwargs(columns, _CVA_NETTING_SET_BATCH_COLUMN_ARGS),
        source_hash=handoff.source_hash,
        handoff_hash=normalized_arrow_table_hash(handoff),
        diagnostics=_diagnostics(handoff),
        copy_arrays=False,
    )


def build_cva_hedge_batch_from_arrow(handoff: NormalizedArrowTable) -> CvaHedgeBatch:
    if not isinstance(handoff, NormalizedArrowTable):
        raise CvaInputError("handoff must be NormalizedArrowTable", field="handoff")
    table = handoff.accepted
    columns = read_arrow_columns(table, CVA_HEDGE_ARROW_COLUMN_SPECS, error=_cva_error)
    return build_cva_hedge_batch_from_columns(
        **_cva_batch_column_kwargs(columns, _CVA_HEDGE_BATCH_COLUMN_ARGS),
        source_hash=handoff.source_hash,
        handoff_hash=normalized_arrow_table_hash(handoff),
        diagnostics=_diagnostics(handoff),
        copy_arrays=False,
    )


def build_sa_cva_sensitivity_batch_from_arrow(
    handoff: NormalizedArrowTable,
) -> SaCvaSensitivityBatch:
    if not isinstance(handoff, NormalizedArrowTable):
        raise CvaInputError("handoff must be NormalizedArrowTable", field="handoff")
    table = handoff.accepted
    columns = read_arrow_columns(
        table,
        SA_CVA_SENSITIVITY_ARROW_COLUMN_SPECS,
        error=_cva_error,
    )
    return build_sa_cva_sensitivity_batch_from_columns(
        **_cva_batch_column_kwargs(columns, _SA_CVA_SENSITIVITY_BATCH_COLUMN_ARGS),
        source_hash=handoff.source_hash,
        handoff_hash=normalized_arrow_table_hash(handoff),
        diagnostics=_diagnostics(handoff),
        copy_arrays=False,
    )


def build_cva_counterparty_batch_from_handoff(
    handoff: NormalizedArrowTable,
) -> CvaCounterpartyBatch:
    """Deprecated alias for :func:`build_cva_counterparty_batch_from_arrow`."""

    warnings.warn(
        "build_cva_counterparty_batch_from_handoff is deprecated; "
        "use build_cva_counterparty_batch_from_arrow",
        DeprecationWarning,
        stacklevel=2,
    )
    return build_cva_counterparty_batch_from_arrow(handoff)


def build_cva_netting_set_batch_from_handoff(
    handoff: NormalizedArrowTable,
) -> CvaNettingSetBatch:
    """Deprecated alias for :func:`build_cva_netting_set_batch_from_arrow`."""

    warnings.warn(
        "build_cva_netting_set_batch_from_handoff is deprecated; "
        "use build_cva_netting_set_batch_from_arrow",
        DeprecationWarning,
        stacklevel=2,
    )
    return build_cva_netting_set_batch_from_arrow(handoff)


def build_cva_hedge_batch_from_handoff(handoff: NormalizedArrowTable) -> CvaHedgeBatch:
    """Deprecated alias for :func:`build_cva_hedge_batch_from_arrow`."""

    warnings.warn(
        "build_cva_hedge_batch_from_handoff is deprecated; use build_cva_hedge_batch_from_arrow",
        DeprecationWarning,
        stacklevel=2,
    )
    return build_cva_hedge_batch_from_arrow(handoff)


def build_sa_cva_sensitivity_batch_from_handoff(
    handoff: NormalizedArrowTable,
) -> SaCvaSensitivityBatch:
    """Deprecated alias for :func:`build_sa_cva_sensitivity_batch_from_arrow`."""

    warnings.warn(
        "build_sa_cva_sensitivity_batch_from_handoff is deprecated; "
        "use build_sa_cva_sensitivity_batch_from_arrow",
        DeprecationWarning,
        stacklevel=2,
    )
    return build_sa_cva_sensitivity_batch_from_arrow(handoff)


def _normalize(
    table: pa.Table,
    column_specs: tuple[ColumnSpec, ...],
    diagnostics: Sequence[AdapterDiagnostic],
    metadata: Mapping[str, str] | None,
    rejected: pa.Table | None,
    source_hash: str | None,
) -> NormalizedArrowTable:
    return normalize_arrow_table(
        table,
        column_specs=column_specs,
        rejected=rejected,
        diagnostics=diagnostics,
        metadata={} if metadata is None else metadata,
        source_hash=source_hash,
        require_unique_row_ids=False,
    )


def _cva_batch_column_kwargs(
    columns: Mapping[str, object],
    column_args: Mapping[str, str],
) -> dict[str, Any]:
    return {
        argument_name: columns[column_name]
        for column_name, argument_name in column_args.items()
        if column_name in columns
    }


def _cva_error(message: str, field: str | None) -> CvaInputError:
    return CvaInputError(message, field="" if field is None else field)


def _diagnostics(handoff: NormalizedArrowTable) -> tuple[Mapping[str, object], ...]:
    return tuple(diagnostic.as_dict() for diagnostic in handoff.diagnostics)


__all__ = [
    "CVA_COUNTERPARTY_ARROW_COLUMN_SPECS",
    "CVA_COUNTERPARTY_HANDOFF_COLUMN_SPECS",
    "CVA_HEDGE_ARROW_COLUMN_SPECS",
    "CVA_HEDGE_HANDOFF_COLUMN_SPECS",
    "CVA_NETTING_SET_ARROW_COLUMN_SPECS",
    "CVA_NETTING_SET_HANDOFF_COLUMN_SPECS",
    "SA_CVA_SENSITIVITY_ARROW_COLUMN_SPECS",
    "SA_CVA_SENSITIVITY_HANDOFF_COLUMN_SPECS",
    "build_cva_counterparty_batch_from_arrow",
    "build_cva_counterparty_batch_from_handoff",
    "build_cva_hedge_batch_from_arrow",
    "build_cva_hedge_batch_from_handoff",
    "build_cva_netting_set_batch_from_arrow",
    "build_cva_netting_set_batch_from_handoff",
    "build_sa_cva_sensitivity_batch_from_arrow",
    "build_sa_cva_sensitivity_batch_from_handoff",
    "normalize_cva_counterparty_arrow_table",
    "normalize_cva_hedge_arrow_table",
    "normalize_cva_netting_set_arrow_table",
    "normalize_sa_cva_sensitivity_arrow_table",
]
