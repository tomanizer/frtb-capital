"""Low-level CVA batch empty, subset, and array utilities."""

from __future__ import annotations

from typing import cast

import frtb_common.batch_arrays as _batch_arrays
import numpy as np

from frtb_cva._batch_columns import (
    BoolArray,
    FloatArray,
    ObjectArray,
)
from frtb_cva._batch_contracts import (
    CvaCounterpartyBatch,
    CvaHedgeBatch,
    CvaNettingSetBatch,
)


def _sorted_indices(values: ObjectArray) -> list[int]:
    return sorted(range(values.shape[0]), key=lambda index: cast(str, values[index]))


def _empty_counterparty_batch() -> CvaCounterpartyBatch:
    return CvaCounterpartyBatch(
        counterparty_ids=_batch_arrays.object_array([], copy=True),
        desk_ids=_batch_arrays.object_array([], copy=True),
        legal_entities=_batch_arrays.object_array([], copy=True),
        sectors=_batch_arrays.object_array([], copy=True),
        credit_qualities=_batch_arrays.object_array([], copy=True),
        regions=_batch_arrays.object_array([], copy=True),
        source_row_ids=_batch_arrays.object_array([], copy=True),
        lineage_source_systems=_batch_arrays.object_array([], copy=True),
        lineage_source_files=_batch_arrays.object_array([], copy=True),
        lineage_source_row_ids=_batch_arrays.object_array([], copy=True),
        source_column_maps=(),
    )


def _empty_netting_set_batch() -> CvaNettingSetBatch:
    return CvaNettingSetBatch(
        netting_set_ids=_batch_arrays.object_array([], copy=True),
        counterparty_ids=_batch_arrays.object_array([], copy=True),
        eads=_empty_float_array(),
        effective_maturities=_empty_float_array(),
        discount_factors=_empty_float_array(),
        currencies=_batch_arrays.object_array([], copy=True),
        sign_conventions=_batch_arrays.object_array([], copy=True),
        uses_imm_eads=_empty_bool_array(),
        source_row_ids=_batch_arrays.object_array([], copy=True),
        carved_out_to_ba_cva=_empty_bool_array(),
        discount_factor_explicit=_empty_bool_array(),
        lineage_source_systems=_batch_arrays.object_array([], copy=True),
        lineage_source_files=_batch_arrays.object_array([], copy=True),
        lineage_source_row_ids=_batch_arrays.object_array([], copy=True),
        source_column_maps=(),
    )


def _empty_hedge_batch() -> CvaHedgeBatch:
    return CvaHedgeBatch(
        hedge_ids=_batch_arrays.object_array([], copy=True),
        source_row_ids=_batch_arrays.object_array([], copy=True),
        counterparty_ids=_batch_arrays.object_array([], copy=True),
        hedge_types=_batch_arrays.object_array([], copy=True),
        notionals=_empty_float_array(),
        remaining_maturities=_empty_float_array(),
        discount_factors=_empty_float_array(),
        reference_sectors=_batch_arrays.object_array([], copy=True),
        reference_credit_qualities=_batch_arrays.object_array([], copy=True),
        reference_regions=_batch_arrays.object_array([], copy=True),
        reference_relations=_batch_arrays.object_array([], copy=True),
        eligibilities=_batch_arrays.object_array([], copy=True),
        is_internal=_empty_bool_array(),
        discount_factor_explicit=_empty_bool_array(),
        internal_desk_counterparty_ids=_batch_arrays.object_array([], copy=True),
        sa_cva_risk_classes=_batch_arrays.object_array([], copy=True),
        sa_cva_hedge_purposes=_batch_arrays.object_array([], copy=True),
        sa_cva_hedge_instrument_types=_batch_arrays.object_array([], copy=True),
        whole_transaction_evidence_ids=_batch_arrays.object_array([], copy=True),
        market_risk_ima_eligibilities=_batch_arrays.object_array([], copy=True),
        market_risk_ima_exclusion_reasons=_batch_arrays.object_array([], copy=True),
        eligibility_evidence_ids=_batch_arrays.object_array([], copy=True),
        rejection_reasons=_batch_arrays.object_array([], copy=True),
        lineage_source_systems=_batch_arrays.object_array([], copy=True),
        lineage_source_files=_batch_arrays.object_array([], copy=True),
        lineage_source_row_ids=_batch_arrays.object_array([], copy=True),
        source_column_maps=(),
    )


def _subset_counterparties(batch: CvaCounterpartyBatch, indices: list[int]) -> CvaCounterpartyBatch:
    return CvaCounterpartyBatch(
        counterparty_ids=_take_object(batch.counterparty_ids, indices),
        desk_ids=_take_object(batch.desk_ids, indices),
        legal_entities=_take_object(batch.legal_entities, indices),
        sectors=_take_object(batch.sectors, indices),
        credit_qualities=_take_object(batch.credit_qualities, indices),
        regions=_take_object(batch.regions, indices),
        source_row_ids=_take_object(batch.source_row_ids, indices),
        lineage_source_systems=_take_object(batch.lineage_source_systems, indices),
        lineage_source_files=_take_object(batch.lineage_source_files, indices),
        lineage_source_row_ids=_take_object(batch.lineage_source_row_ids, indices),
        source_column_maps=tuple(batch.source_column_maps[index] for index in indices),
        source_hash=batch.source_hash,
        handoff_hash=batch.handoff_hash,
        diagnostics=batch.diagnostics,
        org_scopes=None
        if batch.org_scopes is None
        else tuple(batch.org_scopes[index] for index in indices),
    )


def _subset_netting_sets(batch: CvaNettingSetBatch, indices: list[int]) -> CvaNettingSetBatch:
    return CvaNettingSetBatch(
        netting_set_ids=_take_object(batch.netting_set_ids, indices),
        counterparty_ids=_take_object(batch.counterparty_ids, indices),
        eads=_take_float(batch.eads, indices),
        effective_maturities=_take_float(batch.effective_maturities, indices),
        discount_factors=_take_float(batch.discount_factors, indices),
        currencies=_take_object(batch.currencies, indices),
        sign_conventions=_take_object(batch.sign_conventions, indices),
        uses_imm_eads=_take_bool(batch.uses_imm_eads, indices),
        source_row_ids=_take_object(batch.source_row_ids, indices),
        carved_out_to_ba_cva=_take_bool(batch.carved_out_to_ba_cva, indices),
        discount_factor_explicit=_take_bool(batch.discount_factor_explicit, indices),
        lineage_source_systems=_take_object(batch.lineage_source_systems, indices),
        lineage_source_files=_take_object(batch.lineage_source_files, indices),
        lineage_source_row_ids=_take_object(batch.lineage_source_row_ids, indices),
        source_column_maps=tuple(batch.source_column_maps[index] for index in indices),
        source_hash=batch.source_hash,
        handoff_hash=batch.handoff_hash,
        diagnostics=batch.diagnostics,
        org_scopes=None
        if batch.org_scopes is None
        else tuple(batch.org_scopes[index] for index in indices),
    )


def _subset_hedges(batch: CvaHedgeBatch, indices: list[int]) -> CvaHedgeBatch:
    return CvaHedgeBatch(
        hedge_ids=_take_object(batch.hedge_ids, indices),
        source_row_ids=_take_object(batch.source_row_ids, indices),
        counterparty_ids=_take_object(batch.counterparty_ids, indices),
        hedge_types=_take_object(batch.hedge_types, indices),
        notionals=_take_float(batch.notionals, indices),
        remaining_maturities=_take_float(batch.remaining_maturities, indices),
        discount_factors=_take_float(batch.discount_factors, indices),
        reference_sectors=_take_object(batch.reference_sectors, indices),
        reference_credit_qualities=_take_object(batch.reference_credit_qualities, indices),
        reference_regions=_take_object(batch.reference_regions, indices),
        reference_relations=_take_object(batch.reference_relations, indices),
        eligibilities=_take_object(batch.eligibilities, indices),
        is_internal=_take_bool(batch.is_internal, indices),
        discount_factor_explicit=_take_bool(batch.discount_factor_explicit, indices),
        internal_desk_counterparty_ids=_take_object(batch.internal_desk_counterparty_ids, indices),
        sa_cva_risk_classes=_take_object(batch.sa_cva_risk_classes, indices),
        sa_cva_hedge_purposes=_take_object(batch.sa_cva_hedge_purposes, indices),
        sa_cva_hedge_instrument_types=_take_object(batch.sa_cva_hedge_instrument_types, indices),
        whole_transaction_evidence_ids=_take_object(batch.whole_transaction_evidence_ids, indices),
        market_risk_ima_eligibilities=_take_object(batch.market_risk_ima_eligibilities, indices),
        market_risk_ima_exclusion_reasons=_take_object(
            batch.market_risk_ima_exclusion_reasons,
            indices,
        ),
        eligibility_evidence_ids=_take_object(batch.eligibility_evidence_ids, indices),
        rejection_reasons=_take_object(batch.rejection_reasons, indices),
        lineage_source_systems=_take_object(batch.lineage_source_systems, indices),
        lineage_source_files=_take_object(batch.lineage_source_files, indices),
        lineage_source_row_ids=_take_object(batch.lineage_source_row_ids, indices),
        source_column_maps=tuple(batch.source_column_maps[index] for index in indices),
        source_hash=batch.source_hash,
        handoff_hash=batch.handoff_hash,
        diagnostics=batch.diagnostics,
    )


def _take_object(values: ObjectArray, indices: list[int]) -> ObjectArray:
    return _batch_arrays.object_array(values[indices], copy=True)


def _take_float(values: FloatArray, indices: list[int]) -> FloatArray:
    array = values[indices].copy()
    array.setflags(write=False)
    return array


def _take_bool(values: BoolArray, indices: list[int]) -> BoolArray:
    array = values[indices].copy()
    array.setflags(write=False)
    return array


def _empty_float_array() -> FloatArray:
    array = np.asarray([], dtype=np.float64)
    array.setflags(write=False)
    return array


def _empty_bool_array() -> BoolArray:
    array = np.asarray([], dtype=np.bool_)
    array.setflags(write=False)
    return array
