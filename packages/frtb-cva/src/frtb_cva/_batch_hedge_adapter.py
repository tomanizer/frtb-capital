"""Hedge column adapter for CVA batch contracts."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

import frtb_common.batch_arrays as _batch_arrays

from frtb_cva._batch_columns import (
    ColumnInput,
    NullableColumnInput,
    ObjectArray,
    _bool_array,
    _default_text_sequence,
    _enum_array,
    _float_array,
    _freeze_source_column_maps,
    _optional_enum_array,
    _optional_text_array,
    _require_lengths,
    _require_optional_lengths,
    _required_text_array,
)
from frtb_cva._batch_contracts import CvaHedgeBatch
from frtb_cva._batch_validation import _validate_hedge_batch
from frtb_cva.data_models import (
    BaCvaHedgeType,
    CreditQuality,
    CvaSector,
    HedgeEligibility,
    HedgeReferenceRelation,
    SaCvaHedgeInstrumentType,
    SaCvaHedgePurpose,
    SaCvaRiskClass,
)


def build_cva_hedge_batch_from_columns(
    *,
    hedge_ids: ColumnInput,
    source_row_ids: ColumnInput,
    counterparty_ids: ColumnInput,
    hedge_types: ColumnInput,
    notionals: ColumnInput,
    remaining_maturities: ColumnInput,
    discount_factors: ColumnInput,
    reference_sectors: ColumnInput,
    reference_credit_qualities: ColumnInput,
    reference_regions: ColumnInput,
    reference_relations: ColumnInput,
    eligibilities: ColumnInput,
    is_internal: ColumnInput,
    discount_factor_explicit: ColumnInput | None = None,
    internal_desk_counterparty_ids: NullableColumnInput | None = None,
    sa_cva_risk_classes: NullableColumnInput | None = None,
    sa_cva_hedge_purposes: NullableColumnInput | None = None,
    sa_cva_hedge_instrument_types: NullableColumnInput | None = None,
    whole_transaction_evidence_ids: NullableColumnInput | None = None,
    market_risk_ima_eligibilities: NullableColumnInput | None = None,
    market_risk_ima_exclusion_reasons: NullableColumnInput | None = None,
    eligibility_evidence_ids: NullableColumnInput | None = None,
    rejection_reasons: NullableColumnInput | None = None,
    lineage_source_systems: ColumnInput | None = None,
    lineage_source_files: ColumnInput | None = None,
    lineage_source_row_ids: ColumnInput | None = None,
    source_column_maps: Sequence[Sequence[tuple[str, str]]] | None = None,
    source_hash: str | None = None,
    handoff_hash: str | None = None,
    diagnostics: Sequence[Mapping[str, object]] = (),
    copy_arrays: bool = True,
) -> CvaHedgeBatch:
    """Build a validated hedge batch from aligned column inputs.

    Parameters
    ----------
    hedge_ids, source_row_ids, counterparty_ids, hedge_types, notionals,
    remaining_maturities, discount_factors, reference_* columns, eligibilities,
    is_internal : ColumnInput
        Required aligned hedge columns.
    """
    row_count = len(hedge_ids)
    _require_hedge_lengths(
        row_count,
        required={
            "source_row_ids": source_row_ids,
            "counterparty_ids": counterparty_ids,
            "hedge_types": hedge_types,
            "notionals": notionals,
            "remaining_maturities": remaining_maturities,
            "discount_factors": discount_factors,
            "reference_sectors": reference_sectors,
            "reference_credit_qualities": reference_credit_qualities,
            "reference_regions": reference_regions,
            "reference_relations": reference_relations,
            "eligibilities": eligibilities,
            "is_internal": is_internal,
        },
        optional={
            "discount_factor_explicit": discount_factor_explicit,
            "internal_desk_counterparty_ids": internal_desk_counterparty_ids,
            "sa_cva_risk_classes": sa_cva_risk_classes,
            "sa_cva_hedge_purposes": sa_cva_hedge_purposes,
            "sa_cva_hedge_instrument_types": sa_cva_hedge_instrument_types,
            "whole_transaction_evidence_ids": whole_transaction_evidence_ids,
            "market_risk_ima_eligibilities": market_risk_ima_eligibilities,
            "market_risk_ima_exclusion_reasons": market_risk_ima_exclusion_reasons,
            "eligibility_evidence_ids": eligibility_evidence_ids,
            "rejection_reasons": rejection_reasons,
            "lineage_source_systems": lineage_source_systems,
            "lineage_source_files": lineage_source_files,
            "lineage_source_row_ids": lineage_source_row_ids,
            "source_column_maps": source_column_maps,
        },
    )
    batch = CvaHedgeBatch(
        **_hedge_batch_fields(
            row_count=row_count,
            source_hash=source_hash,
            handoff_hash=handoff_hash,
            diagnostics=diagnostics,
            copy_arrays=copy_arrays,
            columns=locals(),
        )
    )
    _validate_hedge_batch(batch)
    return batch


def _sa_cva_hedge_metadata_arrays(
    *,
    row_count: int,
    sa_cva_risk_classes: NullableColumnInput | None,
    sa_cva_hedge_purposes: NullableColumnInput | None,
    sa_cva_hedge_instrument_types: NullableColumnInput | None,
    whole_transaction_evidence_ids: NullableColumnInput | None,
    market_risk_ima_eligibilities: NullableColumnInput | None,
    market_risk_ima_exclusion_reasons: NullableColumnInput | None,
    copy_arrays: bool,
) -> dict[str, ObjectArray]:
    return {
        "sa_cva_risk_classes": _optional_enum_array(
            sa_cva_risk_classes, row_count, SaCvaRiskClass, "sa_cva_risk_class", copy=copy_arrays
        ),
        "sa_cva_hedge_purposes": _optional_enum_array(
            sa_cva_hedge_purposes,
            row_count,
            SaCvaHedgePurpose,
            "sa_cva_hedge_purpose",
            copy=copy_arrays,
        ),
        "sa_cva_hedge_instrument_types": _optional_enum_array(
            sa_cva_hedge_instrument_types,
            row_count,
            SaCvaHedgeInstrumentType,
            "sa_cva_hedge_instrument_type",
            copy=copy_arrays,
        ),
        "whole_transaction_evidence_ids": _optional_text_array(
            whole_transaction_evidence_ids, row_count, copy=copy_arrays
        ),
        "market_risk_ima_eligibilities": _batch_arrays.optional_bool_object_array(
            market_risk_ima_eligibilities, row_count, copy=copy_arrays
        ),
        "market_risk_ima_exclusion_reasons": _optional_text_array(
            market_risk_ima_exclusion_reasons, row_count, copy=copy_arrays
        ),
    }


def _require_hedge_lengths(
    row_count: int,
    *,
    required: Mapping[str, ColumnInput],
    optional: Mapping[str, ColumnInput | Sequence[Sequence[tuple[str, str]]] | None],
) -> None:
    _require_lengths(row_count, **required)
    _require_optional_lengths(row_count, **optional)


def _hedge_batch_fields(
    *,
    row_count: int,
    source_hash: str | None,
    handoff_hash: str | None,
    diagnostics: Sequence[Mapping[str, object]],
    copy_arrays: bool,
    columns: Mapping[str, Any],
) -> dict[str, Any]:
    fields = _hedge_core_fields(row_count=row_count, copy_arrays=copy_arrays, columns=columns)
    fields.update(
        _sa_cva_hedge_metadata_arrays(
            row_count=row_count,
            sa_cva_risk_classes=columns["sa_cva_risk_classes"],
            sa_cva_hedge_purposes=columns["sa_cva_hedge_purposes"],
            sa_cva_hedge_instrument_types=columns["sa_cva_hedge_instrument_types"],
            whole_transaction_evidence_ids=columns["whole_transaction_evidence_ids"],
            market_risk_ima_eligibilities=columns["market_risk_ima_eligibilities"],
            market_risk_ima_exclusion_reasons=columns["market_risk_ima_exclusion_reasons"],
            copy_arrays=copy_arrays,
        )
    )
    fields.update(
        _hedge_evidence_and_lineage_fields(
            row_count=row_count,
            source_hash=source_hash,
            handoff_hash=handoff_hash,
            diagnostics=diagnostics,
            copy_arrays=copy_arrays,
            columns=columns,
        )
    )
    return fields


def _hedge_core_fields(
    *,
    row_count: int,
    copy_arrays: bool,
    columns: Mapping[str, Any],
) -> dict[str, Any]:
    return {
        "hedge_ids": _required_text_array(columns["hedge_ids"], "hedge_id", copy=copy_arrays),
        "source_row_ids": _required_text_array(
            columns["source_row_ids"], "source_row_id", copy=copy_arrays
        ),
        "counterparty_ids": _required_text_array(
            columns["counterparty_ids"], "counterparty_id", copy=copy_arrays
        ),
        "hedge_types": _optional_enum_array(
            columns["hedge_types"], row_count, BaCvaHedgeType, "hedge_type", copy=copy_arrays
        ),
        "notionals": _float_array(columns["notionals"], "notional", copy=copy_arrays),
        "remaining_maturities": _float_array(
            columns["remaining_maturities"], "remaining_maturity", copy=copy_arrays
        ),
        "discount_factors": _float_array(
            columns["discount_factors"], "discount_factor", copy=copy_arrays
        ),
        "reference_sectors": _enum_array(
            columns["reference_sectors"], CvaSector, "reference_sector", copy=copy_arrays
        ),
        "reference_credit_qualities": _enum_array(
            columns["reference_credit_qualities"],
            CreditQuality,
            "reference_credit_quality",
            copy=copy_arrays,
        ),
        "reference_regions": _required_text_array(
            columns["reference_regions"], "reference_region", copy=copy_arrays
        ),
        "reference_relations": _enum_array(
            columns["reference_relations"],
            HedgeReferenceRelation,
            "reference_relation",
            copy=copy_arrays,
        ),
        "eligibilities": _enum_array(
            columns["eligibilities"], HedgeEligibility, "eligibility", copy=copy_arrays
        ),
        "is_internal": _bool_array(
            columns["is_internal"], row_count, default=False, copy=copy_arrays
        ),
        "discount_factor_explicit": _bool_array(
            columns["discount_factor_explicit"], row_count, default=False, copy=copy_arrays
        ),
        "internal_desk_counterparty_ids": _optional_text_array(
            columns["internal_desk_counterparty_ids"], row_count, copy=copy_arrays
        ),
    }


def _hedge_evidence_and_lineage_fields(
    *,
    row_count: int,
    source_hash: str | None,
    handoff_hash: str | None,
    diagnostics: Sequence[Mapping[str, object]],
    copy_arrays: bool,
    columns: Mapping[str, Any],
) -> dict[str, Any]:
    source_row_ids = columns["source_row_ids"]
    lineage_source_row_ids = columns["lineage_source_row_ids"]
    return {
        "eligibility_evidence_ids": _optional_text_array(
            columns["eligibility_evidence_ids"], row_count, copy=copy_arrays
        ),
        "rejection_reasons": _optional_text_array(
            columns["rejection_reasons"], row_count, copy=copy_arrays
        ),
        "lineage_source_systems": _required_text_array(
            _default_text_sequence(columns["lineage_source_systems"], row_count, "cva-batch"),
            "lineage.source_system",
            copy=copy_arrays,
        ),
        "lineage_source_files": _required_text_array(
            _default_text_sequence(columns["lineage_source_files"], row_count, "columns"),
            "lineage.source_file",
            copy=copy_arrays,
        ),
        "lineage_source_row_ids": _required_text_array(
            source_row_ids if lineage_source_row_ids is None else lineage_source_row_ids,
            "lineage.source_row_id",
            copy=copy_arrays,
        ),
        "source_column_maps": _freeze_source_column_maps(
            columns["source_column_maps"], row_count
        ),
        "source_hash": source_hash,
        "handoff_hash": handoff_hash,
        "diagnostics": tuple(dict(item) for item in diagnostics),
    }
