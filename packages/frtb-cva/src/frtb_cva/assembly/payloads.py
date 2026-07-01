"""Deterministic JSON payload builders for CVA input hashing and audit replay.

This module serialises :class:`~frtb_cva.data_models.CvaCalculationContext` rows and
package-owned columnar batches into canonical dictionaries consumed by
:func:`hash_payload` and batch capital entrypoints. It owns handoff hashing shape
only and does not perform regulatory capital calculations.
"""

from __future__ import annotations

import math
from collections.abc import Iterable
from typing import Any, cast

import numpy as np
from frtb_common import stable_json_hash

from frtb_cva.data_models import (
    CvaCalculationContext,
    CvaCounterparty,
    CvaHedge,
    CvaNettingSet,
    CvaRunControls,
    CvaSourceLineage,
    SaCvaSensitivity,
)
from frtb_cva.org_scope import scope_at, scope_payload
from frtb_cva.validation import CvaInputError

hash_payload = stable_json_hash


def input_payload(
    context: CvaCalculationContext,
    counterparties: Iterable[CvaCounterparty],
    netting_sets: Iterable[CvaNettingSet],
    *,
    hedges: Iterable[CvaHedge] = (),
    sensitivities: Iterable[SaCvaSensitivity] = (),
) -> dict[str, object]:
    """Return the canonical row-input payload used for CVA input hashes.

    Parameters
    ----------
    context : CvaCalculationContext
        Run controls and method selection for the capital calculation.
    counterparties : Iterable[CvaCounterparty]
        Counterparty rows included in the hash.
    netting_sets : Iterable[CvaNettingSet]
        Netting-set rows included in the hash.
    hedges : Iterable[CvaHedge], optional
        Hedge rows included when BA-CVA full or mixed carve-out paths apply.
    sensitivities : Iterable[SaCvaSensitivity], optional
        SA-CVA sensitivity rows included when SA-CVA or mixed paths apply.

    Returns
    -------
    dict[str, object]
        Nested mapping with ``context``, entity lists, and lineage metadata.
    """

    return {
        "context": context_payload(context),
        "counterparties": [counterparty_payload(counterparty) for counterparty in counterparties],
        "netting_sets": [netting_set_payload(netting_set) for netting_set in netting_sets],
        "hedges": [hedge_payload(hedge) for hedge in hedges],
        "sensitivities": [sensitivity_payload(sensitivity) for sensitivity in sensitivities],
    }


def batch_input_payload(
    context: CvaCalculationContext,
    counterparties: Any | None = None,
    netting_sets: Any | None = None,
    *,
    hedges: Any | None = None,
    sensitivities: Any | None = None,
) -> dict[str, object]:
    """Return the row-compatible payload for package-owned CVA batches.

    Parameters
    ----------
    context : CvaCalculationContext
        Run controls and method selection for the capital calculation.
    counterparties : Any or None
        Optional :class:`~frtb_cva.batch.CvaCounterpartyBatch` (or compatible batch).
    netting_sets : Any or None
        Optional :class:`~frtb_cva.batch.CvaNettingSetBatch`.
    hedges : Any or None
        Optional :class:`~frtb_cva.batch.CvaHedgeBatch`.
    sensitivities : Any or None
        Optional :class:`~frtb_cva.batch.SaCvaSensitivityBatch`.

    Returns
    -------
    dict[str, object]
        Nested mapping mirroring :func:`input_payload` but built from batch columns.
    """

    return {
        "context": context_payload(context),
        "counterparties": []
        if counterparties is None
        else [
            batch_counterparty_payload(counterparties, index)
            for index in range(counterparties.row_count)
        ],
        "netting_sets": []
        if netting_sets is None
        else [
            batch_netting_set_payload(netting_sets, index)
            for index in range(netting_sets.row_count)
        ],
        "hedges": []
        if hedges is None
        else [batch_hedge_payload(hedges, index) for index in range(hedges.row_count)],
        "sensitivities": []
        if sensitivities is None
        else [
            batch_sensitivity_payload(sensitivities, index)
            for index in range(sensitivities.row_count)
        ],
    }


def context_payload(context: CvaCalculationContext) -> dict[str, object]:
    """Serialise calculation context and run controls for deterministic hashing.

    Parameters
    ----------
    context : CvaCalculationContext
        Validated run metadata, profile, method, and carve-out identifiers.

    Returns
    -------
    dict[str, object]
        JSON-compatible context mapping including nested ``run_controls``.
    """
    run_controls = context.run_controls or CvaRunControls()
    payload: dict[str, object] = {
        "run_id": context.run_id,
        "calculation_date": context.calculation_date.isoformat(),
        "base_currency": context.base_currency,
        "profile": context.profile.value,
        "method": context.method.value,
        "sa_cva_approved": context.sa_cva_approved,
        "materiality_threshold_elected": context.materiality_threshold_elected,
        "carve_out_netting_set_ids": list(context.carve_out_netting_set_ids),
        "sa_cva_sensitivity_scope_evidence_id": context.sa_cva_sensitivity_scope_evidence_id,
        "desk_id": context.desk_id,
        "legal_entity": context.legal_entity,
        "citation_policy": context.citation_policy,
        "run_controls": {
            "audit_verbosity": run_controls.audit_verbosity,
            "retain_intermediate_details": run_controls.retain_intermediate_details,
            "unsupported_feature_behaviour": run_controls.unsupported_feature_behaviour,
        },
    }
    calculation_scope = scope_payload(context.calculation_scope)
    if calculation_scope is not None:
        payload["calculation_scope"] = calculation_scope
    return payload


def counterparty_payload(counterparty: CvaCounterparty) -> dict[str, object]:
    """Serialise one counterparty dataclass row for input hashing.

    Parameters
    ----------
    counterparty : CvaCounterparty
        Canonical counterparty record.

    Returns
    -------
    dict[str, object]
        Counterparty fields with enum values exported as strings.
    """
    payload: dict[str, object] = {
        "counterparty_id": counterparty.counterparty_id,
        "desk_id": counterparty.desk_id,
        "legal_entity": counterparty.legal_entity,
        "sector": counterparty.sector.value,
        "credit_quality": counterparty.credit_quality.value,
        "region": counterparty.region,
        "source_row_id": counterparty.source_row_id,
        "lineage": lineage_payload(counterparty.lineage),
    }
    org_scope = scope_payload(counterparty.org_scope)
    if org_scope is not None:
        payload["org_scope"] = org_scope
    return payload


def netting_set_payload(netting_set: CvaNettingSet) -> dict[str, object]:
    """Serialise one netting-set dataclass row for input hashing.

    Parameters
    ----------
    netting_set : CvaNettingSet
        Canonical netting-set record with EAD and discount metadata.

    Returns
    -------
    dict[str, object]
        Netting-set fields including sign convention and carve-out flags.
    """
    payload: dict[str, object] = {
        "netting_set_id": netting_set.netting_set_id,
        "counterparty_id": netting_set.counterparty_id,
        "ead": netting_set.ead,
        "effective_maturity": netting_set.effective_maturity,
        "discount_factor": netting_set.discount_factor,
        "discount_factor_explicit": netting_set.discount_factor_explicit,
        "currency": netting_set.currency,
        "sign_convention": netting_set.sign_convention,
        "uses_imm_ead": netting_set.uses_imm_ead,
        "carved_out_to_ba_cva": netting_set.carved_out_to_ba_cva,
        "source_row_id": netting_set.source_row_id,
        "lineage": lineage_payload(netting_set.lineage),
    }
    if netting_set.exposure_time_series_id:
        payload["exposure_time_series_id"] = netting_set.exposure_time_series_id
    org_scope = scope_payload(netting_set.org_scope)
    if org_scope is not None:
        payload["org_scope"] = org_scope
    return payload


def hedge_payload(hedge: CvaHedge) -> dict[str, object]:
    """Serialise one hedge dataclass row for input hashing.

    Parameters
    ----------
    hedge : CvaHedge
        Canonical hedge record with eligibility and reference metadata.

    Returns
    -------
    dict[str, object]
        Hedge fields including optional SA-CVA risk-class assignment.
    """
    return {
        "hedge_id": hedge.hedge_id,
        "source_row_id": hedge.source_row_id,
        "hedge_type": None if hedge.hedge_type is None else hedge.hedge_type.value,
        "eligibility": hedge.eligibility.value,
        "counterparty_id": hedge.counterparty_id,
        "reference_sector": hedge.reference_sector.value,
        "reference_credit_quality": hedge.reference_credit_quality.value,
        "reference_region": hedge.reference_region,
        "reference_relation": hedge.reference_relation.value,
        "notional": hedge.notional,
        "remaining_maturity": hedge.remaining_maturity,
        "discount_factor": hedge.discount_factor,
        "discount_factor_explicit": hedge.discount_factor_explicit,
        "is_internal": hedge.is_internal,
        "internal_desk_counterparty_id": hedge.internal_desk_counterparty_id,
        "sa_cva_hedge_purpose": None
        if hedge.sa_cva_hedge_purpose is None
        else hedge.sa_cva_hedge_purpose.value,
        "sa_cva_hedge_instrument_type": None
        if hedge.sa_cva_hedge_instrument_type is None
        else hedge.sa_cva_hedge_instrument_type.value,
        "whole_transaction_evidence_id": hedge.whole_transaction_evidence_id,
        "market_risk_ima_eligible": hedge.market_risk_ima_eligible,
        "market_risk_ima_exclusion_reason": hedge.market_risk_ima_exclusion_reason,
        "eligibility_evidence_id": hedge.eligibility_evidence_id,
        "rejection_reason": hedge.rejection_reason,
        "sa_cva_risk_class": hedge.sa_cva_risk_class.value
        if hedge.sa_cva_risk_class is not None
        else None,
        "lineage": lineage_payload(hedge.lineage),
    }


def sensitivity_payload(sensitivity: SaCvaSensitivity) -> dict[str, object]:
    """Serialise one SA-CVA sensitivity dataclass row for input hashing.

    Parameters
    ----------
    sensitivity : SaCvaSensitivity
        Canonical sensitivity with bucket, tag, and index-treatment metadata.

    Returns
    -------
    dict[str, object]
        Sensitivity fields with optional index remapping attributes.
    """
    payload: dict[str, object] = {
        "sensitivity_id": sensitivity.sensitivity_id,
        "risk_class": sensitivity.risk_class.value,
        "risk_measure": sensitivity.risk_measure.value,
        "sensitivity_tag": sensitivity.sensitivity_tag.value,
        "bucket_id": sensitivity.bucket_id,
        "risk_factor_key": sensitivity.risk_factor_key,
        "tenor": sensitivity.tenor,
        "amount": sensitivity.amount,
        "amount_currency": sensitivity.amount_currency,
        "sign_convention": sensitivity.sign_convention,
        "volatility_input": sensitivity.volatility_input,
        "hedge_id": sensitivity.hedge_id,
        "index_treatment": sensitivity.index_treatment.value
        if sensitivity.index_treatment is not None
        else None,
        "index_max_sector_weight": sensitivity.index_max_sector_weight,
        "index_homogeneous_sector_quality": sensitivity.index_homogeneous_sector_quality,
        "index_dominant_sector": sensitivity.index_dominant_sector.value
        if sensitivity.index_dominant_sector is not None
        else None,
        "index_remap_bucket_id": sensitivity.index_remap_bucket_id,
        "source_row_id": sensitivity.source_row_id,
        "lineage": lineage_payload(sensitivity.lineage),
    }
    if sensitivity.volatility_surface_id:
        payload["volatility_surface_id"] = sensitivity.volatility_surface_id
    if sensitivity.volatility_surface_point_id:
        payload["volatility_surface_point_id"] = sensitivity.volatility_surface_point_id
    if sensitivity.shock_id:
        payload["shock_id"] = sensitivity.shock_id
    return payload


def lineage_payload(lineage: CvaSourceLineage | None) -> dict[str, object] | None:
    """Serialise optional source lineage for one input row.

    Parameters
    ----------
    lineage : CvaSourceLineage or None
        Adapter lineage attached to a counterparty, netting set, hedge, or sensitivity.

    Returns
    -------
    dict[str, object] or None
        Lineage mapping, or ``None`` when lineage is absent.
    """
    if lineage is None:
        return None
    return {
        "source_system": lineage.source_system,
        "source_file": lineage.source_file,
        "source_row_id": lineage.source_row_id,
        "source_column_map": [list(pair) for pair in lineage.source_column_map],
    }


def batch_counterparty_payload(batch: Any, index: int) -> dict[str, object]:
    """Serialise one counterparty batch row for input hashing.

    Parameters
    ----------
    batch : CvaCounterpartyBatch
        Columnar counterparty batch.
    index : int
        Zero-based row index.

    Returns
    -------
    dict[str, object]
        Row payload matching :func:`counterparty_payload` field names.
    """
    payload: dict[str, object] = {
        "counterparty_id": batch.counterparty_ids[index],
        "desk_id": batch.desk_ids[index],
        "legal_entity": batch.legal_entities[index],
        "sector": batch.sectors[index],
        "credit_quality": batch.credit_qualities[index],
        "region": batch.regions[index],
        "source_row_id": batch.source_row_ids[index],
        "lineage": batch_lineage_payload(batch, index),
    }
    org_scope = scope_payload(scope_at(batch.org_scopes, index))
    if org_scope is not None:
        payload["org_scope"] = org_scope
    return payload


def batch_netting_set_payload(batch: Any, index: int) -> dict[str, object]:
    """Serialise one netting-set batch row for input hashing.

    Parameters
    ----------
    batch : CvaNettingSetBatch
        Columnar netting-set batch.
    index : int
        Zero-based row index.

    Returns
    -------
    dict[str, object]
        Row payload matching :func:`netting_set_payload` field names.
    """
    payload: dict[str, object] = {
        "netting_set_id": batch.netting_set_ids[index],
        "counterparty_id": batch.counterparty_ids[index],
        "ead": float(batch.eads[index]),
        "effective_maturity": float(batch.effective_maturities[index]),
        "discount_factor": float(batch.discount_factors[index]),
        "discount_factor_explicit": bool(batch.discount_factor_explicit[index]),
        "currency": batch.currencies[index],
        "sign_convention": batch.sign_conventions[index],
        "uses_imm_ead": bool(batch.uses_imm_eads[index]),
        "carved_out_to_ba_cva": bool(batch.carved_out_to_ba_cva[index]),
        "source_row_id": batch.source_row_ids[index],
        "lineage": batch_lineage_payload(batch, index),
    }
    exposure_time_series_id = _optional_batch_text(batch.exposure_time_series_ids, index)
    if exposure_time_series_id:
        payload["exposure_time_series_id"] = exposure_time_series_id
    org_scope = scope_payload(scope_at(batch.org_scopes, index))
    if org_scope is not None:
        payload["org_scope"] = org_scope
    return payload


def batch_hedge_payload(batch: Any, index: int) -> dict[str, object]:
    """Serialise one hedge batch row for input hashing.

    Parameters
    ----------
    batch : CvaHedgeBatch
        Columnar hedge batch.
    index : int
        Zero-based row index.

    Returns
    -------
    dict[str, object]
        Row payload matching :func:`hedge_payload` field names.
    """
    return {
        "hedge_id": batch.hedge_ids[index],
        "source_row_id": batch.source_row_ids[index],
        "hedge_type": batch.hedge_types[index],
        "eligibility": batch.eligibilities[index],
        "counterparty_id": batch.counterparty_ids[index],
        "reference_sector": batch.reference_sectors[index],
        "reference_credit_quality": batch.reference_credit_qualities[index],
        "reference_region": batch.reference_regions[index],
        "reference_relation": batch.reference_relations[index],
        "notional": float(batch.notionals[index]),
        "remaining_maturity": float(batch.remaining_maturities[index]),
        "discount_factor": float(batch.discount_factors[index]),
        "discount_factor_explicit": bool(batch.discount_factor_explicit[index]),
        "is_internal": bool(batch.is_internal[index]),
        "internal_desk_counterparty_id": batch.internal_desk_counterparty_ids[index],
        "sa_cva_hedge_purpose": batch.sa_cva_hedge_purposes[index],
        "sa_cva_hedge_instrument_type": batch.sa_cva_hedge_instrument_types[index],
        "whole_transaction_evidence_id": batch.whole_transaction_evidence_ids[index],
        "market_risk_ima_eligible": batch.market_risk_ima_eligibilities[index],
        "market_risk_ima_exclusion_reason": batch.market_risk_ima_exclusion_reasons[index],
        "eligibility_evidence_id": batch.eligibility_evidence_ids[index],
        "rejection_reason": batch.rejection_reasons[index],
        "sa_cva_risk_class": batch.sa_cva_risk_classes[index],
        "lineage": batch_lineage_payload(batch, index),
    }


def batch_sensitivity_payload(batch: Any, index: int) -> dict[str, object]:
    """Serialise one SA-CVA sensitivity batch row for input hashing.

    Parameters
    ----------
    batch : SaCvaSensitivityBatch
        Columnar sensitivity batch.
    index : int
        Zero-based row index.

    Returns
    -------
    dict[str, object]
        Row payload matching :func:`sensitivity_payload` field names.
    """
    payload: dict[str, object] = {
        "sensitivity_id": batch.sensitivity_ids[index],
        "risk_class": batch.risk_classes[index],
        "risk_measure": batch.risk_measures[index],
        "sensitivity_tag": batch.sensitivity_tags[index],
        "bucket_id": batch.bucket_ids[index],
        "risk_factor_key": batch.risk_factor_keys[index],
        "tenor": batch.tenors[index],
        "amount": float(batch.amounts[index]),
        "amount_currency": batch.amount_currencies[index],
        "sign_convention": batch.sign_conventions[index],
        "volatility_input": _optional_float_value(batch.volatility_inputs[index]),
        "hedge_id": batch.hedge_ids[index],
        "index_treatment": batch.index_treatments[index],
        "index_max_sector_weight": _optional_float_value(batch.index_max_sector_weights[index]),
        "index_homogeneous_sector_quality": bool(batch.index_homogeneous_sector_quality[index]),
        "index_dominant_sector": batch.index_dominant_sectors[index],
        "index_remap_bucket_id": batch.index_remap_bucket_ids[index],
        "source_row_id": batch.source_row_ids[index],
        "lineage": batch_lineage_payload(batch, index),
    }
    volatility_surface_id = _optional_batch_text(batch.volatility_surface_ids, index)
    if volatility_surface_id:
        payload["volatility_surface_id"] = volatility_surface_id
    volatility_surface_point_id = _optional_batch_text(batch.volatility_surface_point_ids, index)
    if volatility_surface_point_id:
        payload["volatility_surface_point_id"] = volatility_surface_point_id
    shock_id = _optional_batch_text(batch.shock_ids, index)
    if shock_id:
        payload["shock_id"] = shock_id
    return payload


def batch_lineage_payload(batch: Any, index: int) -> dict[str, object] | None:
    """Serialise optional lineage columns for one batch row.

    Parameters
    ----------
    batch
        Columnar batch exposing ``lineage_source_*`` and ``source_column_maps``.
    index : int
        Zero-based row index.

    Returns
    -------
    dict[str, object] or None
        Lineage mapping when either source system or file is non-empty.
    """
    source_system = batch.lineage_source_systems[index]
    source_file = batch.lineage_source_files[index]
    if not source_system and not source_file:
        return None
    return {
        "source_system": source_system,
        "source_file": source_file,
        "source_row_id": batch.lineage_source_row_ids[index],
        "source_column_map": [list(pair) for pair in batch.source_column_maps[index]],
    }


def _optional_float_value(value: object) -> float | None:
    if isinstance(value, (bool, np.bool_)):
        raise CvaInputError("value must be numeric", field="optional numeric field")
    if isinstance(value, (int, float, np.integer, np.floating)):
        raw = float(value)
        if math.isnan(raw):
            return None
        if not math.isfinite(raw):
            raise CvaInputError("value must be finite", field="optional numeric field")
        return raw
    try:
        number = float(cast(Any, value))
    except (TypeError, ValueError) as exc:
        raise CvaInputError("value must be numeric", field="optional numeric field") from exc
    if math.isnan(number):
        return None
    if not math.isfinite(number):
        raise CvaInputError("value must be finite", field="optional numeric field")
    return number


def _optional_batch_text(values: Any, index: int) -> str | None:
    if values is None:
        return None
    value = values[index]
    if value is None:
        return None
    if isinstance(value, (float, np.floating)) and math.isnan(float(value)):
        return None
    return str(value)
