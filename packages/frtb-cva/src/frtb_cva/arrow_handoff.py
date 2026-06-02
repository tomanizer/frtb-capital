"""Arrow handoff adapters for CVA batch inputs."""

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
    arrow_object_array,
    normalize_arrow_table,
    normalized_handoff_hash,
    validate_arrow_table,
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

ObjectArray = npt.NDArray[np.object_]
FloatArray = npt.NDArray[np.float64]
BoolArray = npt.NDArray[np.bool_]
_ARROW_CONVERSION_ERRORS = (pa.ArrowException, TypeError, ValueError)

CVA_COUNTERPARTY_HANDOFF_COLUMN_SPECS: tuple[ColumnSpec, ...] = (
    ColumnSpec("counterparty_id", aliases=("counterpartyId", "CounterpartyID")),
    ColumnSpec("desk_id", aliases=("deskId", "DeskID")),
    ColumnSpec("legal_entity", aliases=("legalEntity", "LegalEntity")),
    ColumnSpec("sector", logical_type=TabularLogicalType.STRING),
    ColumnSpec(
        "credit_quality", aliases=("creditQuality",), logical_type=TabularLogicalType.STRING
    ),
    ColumnSpec("region", logical_type=TabularLogicalType.STRING),
    ColumnSpec("source_row_id", aliases=("sourceRowId", "RowID")),
    ColumnSpec("lineage_source_system", aliases=("source_system", "sourceSystem")),
    ColumnSpec("lineage_source_file", aliases=("source_file", "sourceFile")),
    ColumnSpec(
        "lineage_source_row_id",
        aliases=("lineageSourceRowId",),
        required=False,
        null_policy=NullPolicy.ALLOW,
    ),
)

CVA_NETTING_SET_HANDOFF_COLUMN_SPECS: tuple[ColumnSpec, ...] = (
    ColumnSpec("netting_set_id", aliases=("nettingSetId", "NettingSetID")),
    ColumnSpec("counterparty_id", aliases=("counterpartyId", "CounterpartyID")),
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
    ColumnSpec("source_row_id", aliases=("sourceRowId", "RowID")),
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
    ColumnSpec("lineage_source_system", aliases=("source_system", "sourceSystem")),
    ColumnSpec("lineage_source_file", aliases=("source_file", "sourceFile")),
    ColumnSpec(
        "lineage_source_row_id",
        aliases=("lineageSourceRowId",),
        required=False,
        null_policy=NullPolicy.ALLOW,
    ),
)

CVA_HEDGE_HANDOFF_COLUMN_SPECS: tuple[ColumnSpec, ...] = (
    ColumnSpec("hedge_id", aliases=("hedgeId", "HedgeID")),
    ColumnSpec("source_row_id", aliases=("sourceRowId", "RowID")),
    ColumnSpec("counterparty_id", aliases=("counterpartyId", "CounterpartyID")),
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
        required=False,
        null_policy=NullPolicy.ALLOW,
    ),
    ColumnSpec(
        "sa_cva_risk_class",
        aliases=("saCvaRiskClass",),
        required=False,
        null_policy=NullPolicy.ALLOW,
    ),
    ColumnSpec(
        "eligibility_evidence_id",
        aliases=("eligibilityEvidenceId",),
        required=False,
        null_policy=NullPolicy.ALLOW,
    ),
    ColumnSpec(
        "rejection_reason",
        aliases=("rejectionReason",),
        required=False,
        null_policy=NullPolicy.ALLOW,
    ),
    ColumnSpec("lineage_source_system", aliases=("source_system", "sourceSystem")),
    ColumnSpec("lineage_source_file", aliases=("source_file", "sourceFile")),
    ColumnSpec(
        "lineage_source_row_id",
        aliases=("lineageSourceRowId",),
        required=False,
        null_policy=NullPolicy.ALLOW,
    ),
)

SA_CVA_SENSITIVITY_HANDOFF_COLUMN_SPECS: tuple[ColumnSpec, ...] = (
    ColumnSpec("sensitivity_id", aliases=("sensitivityId", "SensitivityID", "RiskFactorID")),
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
    ColumnSpec("source_row_id", aliases=("sourceRowId", "RowID")),
    ColumnSpec("tenor", required=False, null_policy=NullPolicy.ALLOW),
    ColumnSpec(
        "volatility_input",
        aliases=("volatilityInput",),
        logical_type=TabularLogicalType.FLOAT,
        required=False,
        null_policy=NullPolicy.ALLOW,
    ),
    ColumnSpec("hedge_id", aliases=("hedgeId",), required=False, null_policy=NullPolicy.ALLOW),
    ColumnSpec(
        "index_treatment",
        aliases=("indexTreatment",),
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
        required=False,
        null_policy=NullPolicy.ALLOW,
    ),
    ColumnSpec(
        "index_remap_bucket_id",
        aliases=("indexRemapBucketId",),
        required=False,
        null_policy=NullPolicy.ALLOW,
    ),
    ColumnSpec("lineage_source_system", aliases=("source_system", "sourceSystem")),
    ColumnSpec("lineage_source_file", aliases=("source_file", "sourceFile")),
    ColumnSpec(
        "lineage_source_row_id",
        aliases=("lineageSourceRowId",),
        required=False,
        null_policy=NullPolicy.ALLOW,
    ),
)


def normalize_cva_counterparty_arrow_table(
    table: pa.Table,
    *,
    diagnostics: Sequence[AdapterDiagnostic] = (),
    metadata: Mapping[str, str] | None = None,
    rejected: pa.Table | None = None,
    source_hash: str | None = None,
) -> NormalizedTabularHandoff:
    return _normalize(
        table, CVA_COUNTERPARTY_HANDOFF_COLUMN_SPECS, diagnostics, metadata, rejected, source_hash
    )


def normalize_cva_netting_set_arrow_table(
    table: pa.Table,
    *,
    diagnostics: Sequence[AdapterDiagnostic] = (),
    metadata: Mapping[str, str] | None = None,
    rejected: pa.Table | None = None,
    source_hash: str | None = None,
) -> NormalizedTabularHandoff:
    return _normalize(
        table, CVA_NETTING_SET_HANDOFF_COLUMN_SPECS, diagnostics, metadata, rejected, source_hash
    )


def normalize_cva_hedge_arrow_table(
    table: pa.Table,
    *,
    diagnostics: Sequence[AdapterDiagnostic] = (),
    metadata: Mapping[str, str] | None = None,
    rejected: pa.Table | None = None,
    source_hash: str | None = None,
) -> NormalizedTabularHandoff:
    return _normalize(
        table, CVA_HEDGE_HANDOFF_COLUMN_SPECS, diagnostics, metadata, rejected, source_hash
    )


def normalize_sa_cva_sensitivity_arrow_table(
    table: pa.Table,
    *,
    diagnostics: Sequence[AdapterDiagnostic] = (),
    metadata: Mapping[str, str] | None = None,
    rejected: pa.Table | None = None,
    source_hash: str | None = None,
) -> NormalizedTabularHandoff:
    return _normalize(
        table, SA_CVA_SENSITIVITY_HANDOFF_COLUMN_SPECS, diagnostics, metadata, rejected, source_hash
    )


def build_cva_counterparty_batch_from_handoff(
    handoff: NormalizedTabularHandoff,
) -> CvaCounterpartyBatch:
    if not isinstance(handoff, NormalizedTabularHandoff):
        raise CvaInputError("handoff must be NormalizedTabularHandoff", field="handoff")
    table = handoff.accepted
    validate_arrow_table(table, column_specs=CVA_COUNTERPARTY_HANDOFF_COLUMN_SPECS)
    return build_cva_counterparty_batch_from_columns(
        counterparty_ids=_required_object_column(table, "counterparty_id"),
        desk_ids=_required_object_column(table, "desk_id"),
        legal_entities=_required_object_column(table, "legal_entity"),
        sectors=_required_object_column(table, "sector"),
        credit_qualities=_required_object_column(table, "credit_quality"),
        regions=_required_object_column(table, "region"),
        source_row_ids=_required_object_column(table, "source_row_id"),
        lineage_source_systems=_required_object_column(table, "lineage_source_system"),
        lineage_source_files=_required_object_column(table, "lineage_source_file"),
        lineage_source_row_ids=_optional_object_column(table, "lineage_source_row_id"),
        source_hash=handoff.source_hash,
        handoff_hash=normalized_handoff_hash(handoff),
        diagnostics=_diagnostics(handoff),
        copy_arrays=False,
    )


def build_cva_netting_set_batch_from_handoff(
    handoff: NormalizedTabularHandoff,
) -> CvaNettingSetBatch:
    if not isinstance(handoff, NormalizedTabularHandoff):
        raise CvaInputError("handoff must be NormalizedTabularHandoff", field="handoff")
    table = handoff.accepted
    validate_arrow_table(table, column_specs=CVA_NETTING_SET_HANDOFF_COLUMN_SPECS)
    return build_cva_netting_set_batch_from_columns(
        netting_set_ids=_required_object_column(table, "netting_set_id"),
        counterparty_ids=_required_object_column(table, "counterparty_id"),
        eads=_required_float_column(table, "ead"),
        effective_maturities=_required_float_column(table, "effective_maturity"),
        discount_factors=_required_float_column(table, "discount_factor"),
        currencies=_required_object_column(table, "currency"),
        sign_conventions=_required_object_column(table, "sign_convention"),
        uses_imm_eads=_required_bool_column(table, "uses_imm_ead"),
        source_row_ids=_required_object_column(table, "source_row_id"),
        carved_out_to_ba_cva=_optional_bool_column(table, "carved_out_to_ba_cva"),
        discount_factor_explicit=_optional_bool_column(table, "discount_factor_explicit"),
        lineage_source_systems=_required_object_column(table, "lineage_source_system"),
        lineage_source_files=_required_object_column(table, "lineage_source_file"),
        lineage_source_row_ids=_optional_object_column(table, "lineage_source_row_id"),
        source_hash=handoff.source_hash,
        handoff_hash=normalized_handoff_hash(handoff),
        diagnostics=_diagnostics(handoff),
        copy_arrays=False,
    )


def build_cva_hedge_batch_from_handoff(handoff: NormalizedTabularHandoff) -> CvaHedgeBatch:
    if not isinstance(handoff, NormalizedTabularHandoff):
        raise CvaInputError("handoff must be NormalizedTabularHandoff", field="handoff")
    table = handoff.accepted
    validate_arrow_table(table, column_specs=CVA_HEDGE_HANDOFF_COLUMN_SPECS)
    return build_cva_hedge_batch_from_columns(
        hedge_ids=_required_object_column(table, "hedge_id"),
        source_row_ids=_required_object_column(table, "source_row_id"),
        counterparty_ids=_required_object_column(table, "counterparty_id"),
        hedge_types=_required_object_column(table, "hedge_type"),
        notionals=_required_float_column(table, "notional"),
        remaining_maturities=_required_float_column(table, "remaining_maturity"),
        discount_factors=_required_float_column(table, "discount_factor"),
        reference_sectors=_required_object_column(table, "reference_sector"),
        reference_credit_qualities=_required_object_column(table, "reference_credit_quality"),
        reference_regions=_required_object_column(table, "reference_region"),
        reference_relations=_required_object_column(table, "reference_relation"),
        eligibilities=_required_object_column(table, "eligibility"),
        is_internal=_required_bool_column(table, "is_internal"),
        discount_factor_explicit=_optional_bool_column(table, "discount_factor_explicit"),
        internal_desk_counterparty_ids=_optional_object_column(
            table, "internal_desk_counterparty_id"
        ),
        sa_cva_risk_classes=_optional_object_column(table, "sa_cva_risk_class"),
        eligibility_evidence_ids=_optional_object_column(table, "eligibility_evidence_id"),
        rejection_reasons=_optional_object_column(table, "rejection_reason"),
        lineage_source_systems=_required_object_column(table, "lineage_source_system"),
        lineage_source_files=_required_object_column(table, "lineage_source_file"),
        lineage_source_row_ids=_optional_object_column(table, "lineage_source_row_id"),
        source_hash=handoff.source_hash,
        handoff_hash=normalized_handoff_hash(handoff),
        diagnostics=_diagnostics(handoff),
        copy_arrays=False,
    )


def build_sa_cva_sensitivity_batch_from_handoff(
    handoff: NormalizedTabularHandoff,
) -> SaCvaSensitivityBatch:
    if not isinstance(handoff, NormalizedTabularHandoff):
        raise CvaInputError("handoff must be NormalizedTabularHandoff", field="handoff")
    table = handoff.accepted
    validate_arrow_table(table, column_specs=SA_CVA_SENSITIVITY_HANDOFF_COLUMN_SPECS)
    return build_sa_cva_sensitivity_batch_from_columns(
        sensitivity_ids=_required_object_column(table, "sensitivity_id"),
        risk_classes=_required_object_column(table, "risk_class"),
        risk_measures=_required_object_column(table, "risk_measure"),
        sensitivity_tags=_required_object_column(table, "sensitivity_tag"),
        bucket_ids=_required_object_column(table, "bucket_id"),
        risk_factor_keys=_required_object_column(table, "risk_factor_key"),
        amounts=_required_float_column(table, "amount"),
        amount_currencies=_required_object_column(table, "amount_currency"),
        sign_conventions=_required_object_column(table, "sign_convention"),
        source_row_ids=_required_object_column(table, "source_row_id"),
        tenors=_optional_object_column(table, "tenor"),
        volatility_inputs=_optional_float_column(table, "volatility_input"),
        hedge_ids=_optional_object_column(table, "hedge_id"),
        index_treatments=_optional_object_column(table, "index_treatment"),
        index_max_sector_weights=_optional_float_column(table, "index_max_sector_weight"),
        index_homogeneous_sector_quality=_optional_bool_column(
            table,
            "index_homogeneous_sector_quality",
        ),
        index_dominant_sectors=_optional_object_column(table, "index_dominant_sector"),
        index_remap_bucket_ids=_optional_object_column(table, "index_remap_bucket_id"),
        lineage_source_systems=_required_object_column(table, "lineage_source_system"),
        lineage_source_files=_required_object_column(table, "lineage_source_file"),
        lineage_source_row_ids=_optional_object_column(table, "lineage_source_row_id"),
        source_hash=handoff.source_hash,
        handoff_hash=normalized_handoff_hash(handoff),
        diagnostics=_diagnostics(handoff),
        copy_arrays=False,
    )


def _normalize(
    table: pa.Table,
    column_specs: tuple[ColumnSpec, ...],
    diagnostics: Sequence[AdapterDiagnostic],
    metadata: Mapping[str, str] | None,
    rejected: pa.Table | None,
    source_hash: str | None,
) -> NormalizedTabularHandoff:
    return normalize_arrow_table(
        table,
        column_specs=column_specs,
        rejected=rejected,
        diagnostics=diagnostics,
        metadata={} if metadata is None else metadata,
        source_hash=source_hash,
        require_unique_row_ids=False,
    )


def _required_object_column(table: pa.Table, column_name: str) -> ObjectArray:
    if column_name not in table.column_names:
        raise CvaInputError(f"column is required: {column_name}", field=column_name)
    values = _object_array_from_arrow_column(table.column(column_name), field=column_name)
    values.setflags(write=False)
    return values


def _optional_object_column(table: pa.Table, column_name: str) -> ObjectArray | None:
    if column_name not in table.column_names:
        return None
    values = _object_array_from_arrow_column(table.column(column_name), field=column_name)
    values.setflags(write=False)
    return values


def _required_float_column(table: pa.Table, column_name: str) -> FloatArray:
    if column_name not in table.column_names:
        raise CvaInputError(f"column is required: {column_name}", field=column_name)
    column = table.column(column_name)
    if column.null_count:
        raise CvaInputError(f"{column_name} must be provided", field=column_name)
    values = _float64_array_from_arrow_column(column, field=column_name)
    values.setflags(write=False)
    return values


def _optional_float_column(table: pa.Table, column_name: str) -> FloatArray | None:
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
        except _ARROW_CONVERSION_ERRORS as exc:
            raise CvaInputError(f"{column_name} must be numeric", field=column_name) from exc
    try:
        values = np.asarray(
            pc.fill_null(array, pa.scalar(math.nan, type=pa.float64())).to_numpy(
                zero_copy_only=False
            ),
            dtype=np.float64,
        )
    except _ARROW_CONVERSION_ERRORS as exc:
        raise CvaInputError(f"{column_name} must be numeric", field=column_name) from exc
    values.setflags(write=False)
    return values


def _required_bool_column(table: pa.Table, column_name: str) -> ObjectArray | BoolArray:
    if column_name not in table.column_names:
        raise CvaInputError(f"column is required: {column_name}", field=column_name)
    column = table.column(column_name)
    if column.null_count:
        raise CvaInputError(f"{column_name} must be provided", field=column_name)
    values = _bool_array_from_arrow_column(column, field=column_name, default=False)
    values.setflags(write=False)
    return values


def _optional_bool_column(table: pa.Table, column_name: str) -> ObjectArray | BoolArray | None:
    if column_name not in table.column_names:
        return None
    values = _bool_array_from_arrow_column(
        table.column(column_name),
        field=column_name,
        default=False,
    )
    values.setflags(write=False)
    return values


def _bool_array_from_arrow_column(
    column: pa.ChunkedArray,
    *,
    field: str,
    default: bool,
) -> ObjectArray | BoolArray:
    array = column.chunk(0) if column.num_chunks == 1 else column.combine_chunks()
    if not pa.types.is_boolean(array.type):
        values = _object_array_from_arrow_column(column, field=field)
        if column.null_count:
            values = values.copy()
            values[values == None] = default  # noqa: E711
        return values
    try:
        return np.asarray(
            pc.fill_null(array, default).to_numpy(zero_copy_only=False),
            dtype=np.bool_,
        )
    except _ARROW_CONVERSION_ERRORS as exc:
        raise CvaInputError("Arrow column conversion failed", field=field) from exc


def _object_array_from_arrow_column(column: pa.ChunkedArray, *, field: str) -> ObjectArray:
    try:
        return arrow_object_array(column)
    except _ARROW_CONVERSION_ERRORS as exc:
        raise CvaInputError("Arrow column conversion failed", field=field) from exc


def _float64_array_from_arrow_column(
    column: pa.ChunkedArray,
    *,
    field: str,
) -> FloatArray:
    if len(column) == 0:
        return np.empty(0, dtype=np.float64)
    array = column.chunk(0) if column.num_chunks == 1 else column.combine_chunks()
    if not pa.types.is_float64(array.type):
        try:
            array = cast(pa.Array, pc.cast(array, pa.float64()))
        except _ARROW_CONVERSION_ERRORS as exc:
            raise CvaInputError(f"{field} must be numeric", field=field) from exc
    try:
        return cast(FloatArray, array.to_numpy(zero_copy_only=True))
    except _ARROW_CONVERSION_ERRORS:
        pass

    try:
        return np.asarray(array.to_numpy(zero_copy_only=False), dtype=np.float64)
    except _ARROW_CONVERSION_ERRORS as exc:
        raise CvaInputError(f"{field} must be numeric", field=field) from exc


def _diagnostics(handoff: NormalizedTabularHandoff) -> tuple[Mapping[str, object], ...]:
    return tuple(diagnostic.as_dict() for diagnostic in handoff.diagnostics)


__all__ = [
    "CVA_COUNTERPARTY_HANDOFF_COLUMN_SPECS",
    "CVA_HEDGE_HANDOFF_COLUMN_SPECS",
    "CVA_NETTING_SET_HANDOFF_COLUMN_SPECS",
    "SA_CVA_SENSITIVITY_HANDOFF_COLUMN_SPECS",
    "build_cva_counterparty_batch_from_handoff",
    "build_cva_hedge_batch_from_handoff",
    "build_cva_netting_set_batch_from_handoff",
    "build_sa_cva_sensitivity_batch_from_handoff",
    "normalize_cva_counterparty_arrow_table",
    "normalize_cva_hedge_arrow_table",
    "normalize_cva_netting_set_arrow_table",
    "normalize_sa_cva_sensitivity_arrow_table",
]
