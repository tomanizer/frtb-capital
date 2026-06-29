"""Validation and scope helpers for CVA batch inputs."""

from __future__ import annotations

import math
from typing import cast

import numpy as np
from frtb_common import UnsupportedRegulatoryFeatureError

from frtb_cva._batch_columns import (
    _require_unique,
    _required_text,
)
from frtb_cva._batch_contracts import (
    CvaCounterpartyBatch,
    CvaHedgeBatch,
    CvaNettingSetBatch,
    SaCvaSensitivityBatch,
)
from frtb_cva._unsupported import MAR50_9_UNSUPPORTED_MESSAGE
from frtb_cva.data_models import (
    CvaCalculationContext,
    CvaMethod,
    HedgeEligibility,
    SaCvaRiskClass,
    SaCvaRiskMeasure,
    SensitivityTag,
)
from frtb_cva.scope import (
    ScopeResolution,
    mixed_sensitivity_scope_metadata,
    require_mixed_sensitivity_scope_evidence,
)
from frtb_cva.validation import (
    VALID_AMOUNT_SIGN_CONVENTIONS,
    VALID_EAD_SIGN_CONVENTIONS,
    CvaInputError,
    _validate_effective_maturity,
    normalise_ead_amount,
    normalise_sensitivity_amount,
)


def _validate_netting_set_batch(batch: CvaNettingSetBatch) -> None:
    _require_unique(batch.netting_set_ids, field="netting_set_id")
    for index in range(batch.row_count):
        record_id = cast(str, batch.netting_set_ids[index])
        sign_convention = cast(str, batch.sign_conventions[index])
        if sign_convention not in VALID_EAD_SIGN_CONVENTIONS:
            raise CvaInputError(
                f"sign_convention must be one of {sorted(VALID_EAD_SIGN_CONVENTIONS)}",
                field="sign_convention",
                record_id=record_id,
            )
        ead = float(batch.eads[index])
        normalised_ead = normalise_ead_amount(ead, source_sign_convention=sign_convention)  # type: ignore[arg-type]
        if normalised_ead != ead:
            raise CvaInputError(
                "EAD must be stored after sign-convention normalisation",
                field="ead",
                record_id=record_id,
            )
        _validate_effective_maturity(batch.effective_maturities[index], record_id=record_id)
        if float(batch.discount_factors[index]) <= 0.0:
            raise CvaInputError(
                "discount factor must be positive",
                field="discount_factor",
                record_id=record_id,
            )


def _validate_hedge_batch(batch: CvaHedgeBatch) -> None:
    _require_unique(batch.hedge_ids, field="hedge_id")
    for index in range(batch.row_count):
        record_id = cast(str, batch.hedge_ids[index])
        if float(batch.notionals[index]) < 0.0:
            raise CvaInputError(
                "notional must be non-negative", field="notional", record_id=record_id
            )
        if HedgeEligibility(cast(str, batch.eligibilities[index])) is HedgeEligibility.ELIGIBLE:
            _required_text(
                batch.eligibility_evidence_ids[index], "eligibility_evidence_id", record_id
            )
        if HedgeEligibility(cast(str, batch.eligibilities[index])) is HedgeEligibility.INELIGIBLE:
            _required_text(batch.rejection_reasons[index], "rejection_reason", record_id)
        if HedgeEligibility(cast(str, batch.eligibilities[index])) is HedgeEligibility.EXCLUDED:
            _required_text(batch.rejection_reasons[index], "rejection_reason", record_id)
            _required_text(
                batch.market_risk_ima_exclusion_reasons[index],
                "market_risk_ima_exclusion_reason",
                record_id,
            )


def _validate_sensitivity_batch(batch: SaCvaSensitivityBatch) -> None:
    _require_unique(batch.sensitivity_ids, field="sensitivity_id")
    for index in range(batch.row_count):
        record_id = cast(str, batch.sensitivity_ids[index])
        sign_convention = cast(str, batch.sign_conventions[index])
        if sign_convention not in VALID_AMOUNT_SIGN_CONVENTIONS:
            raise CvaInputError(
                f"sign_convention must be one of {sorted(VALID_AMOUNT_SIGN_CONVENTIONS)}",
                field="sign_convention",
                record_id=record_id,
            )
        amount = float(batch.amounts[index])
        normalised_amount = normalise_sensitivity_amount(
            amount,
            source_sign_convention=sign_convention,  # type: ignore[arg-type]
        )
        if normalised_amount != amount:
            raise CvaInputError(
                "sensitivity amount must be stored after sign-convention normalisation",
                field="amount",
                record_id=record_id,
            )
        risk_class = SaCvaRiskClass(cast(str, batch.risk_classes[index]))
        risk_measure = SaCvaRiskMeasure(cast(str, batch.risk_measures[index]))
        tenor = batch.tenors[index]
        if (
            risk_class is SaCvaRiskClass.GIRR
            and risk_measure is SaCvaRiskMeasure.DELTA
            and tenor is None
        ):
            raise CvaInputError(
                "GIRR delta sensitivities must specify tenor",
                field="tenor",
                record_id=record_id,
            )
        if risk_measure is SaCvaRiskMeasure.VEGA and math.isnan(
            float(batch.volatility_inputs[index])
        ):
            raise CvaInputError(
                "vega sensitivities must specify volatility_input",
                field="volatility_input",
                record_id=record_id,
            )
        if SensitivityTag(cast(str, batch.sensitivity_tags[index])) is SensitivityTag.HDG:
            _required_text(batch.hedge_ids[index], "hedge_id", record_id)
        max_sector_weight = float(batch.index_max_sector_weights[index])
        if not math.isnan(max_sector_weight) and not (0.0 <= max_sector_weight <= 1.0):
            raise CvaInputError(
                "index_max_sector_weight must be between 0.0 and 1.0",
                field="index_max_sector_weight",
                record_id=record_id,
            )


def _validate_ba_relationships(
    counterparties: CvaCounterpartyBatch,
    netting_sets: CvaNettingSetBatch,
) -> None:
    if netting_sets.row_count == 0:
        return
    missing_mask = ~np.isin(netting_sets.counterparty_ids, counterparties.counterparty_ids)
    if bool(np.any(missing_mask)):
        index = int(np.nonzero(missing_mask)[0][0])
        raise CvaInputError(
            "netting set references unknown counterparty",
            field="counterparty_id",
            record_id=cast(str, netting_sets.netting_set_ids[index]),
        )


def _netting_indices_by_counterparty(
    netting_sets: CvaNettingSetBatch,
) -> dict[str, tuple[int, ...]]:
    if netting_sets.row_count == 0:
        return {}
    counterparty_keys = np.asarray(netting_sets.counterparty_ids, dtype=str)
    netting_set_keys = np.asarray(netting_sets.netting_set_ids, dtype=str)
    order = np.lexsort((netting_set_keys, counterparty_keys))
    grouped: dict[str, tuple[int, ...]] = {}
    start = 0
    while start < order.shape[0]:
        counterparty_id = str(counterparty_keys[order[start]])
        end = start + 1
        while end < order.shape[0] and counterparty_keys[order[end]] == counterparty_id:
            end += 1
        grouped[counterparty_id] = tuple(order[start:end].tolist())
        start = end
    return grouped


def _resolve_scope_for_batches(
    context: CvaCalculationContext,
    netting_sets: CvaNettingSetBatch,
) -> ScopeResolution:
    unsupported_flags: list[str] = []
    audit_metadata: list[tuple[str, str]] = [
        ("requested_method", context.method.value),
        ("sa_cva_approved", str(context.sa_cva_approved)),
    ]
    if context.materiality_threshold_elected:
        raise UnsupportedRegulatoryFeatureError(MAR50_9_UNSUPPORTED_MESSAGE)
    if context.method is CvaMethod.BA_CVA_FULL:
        audit_metadata.append(("resolved_method", CvaMethod.BA_CVA_FULL.value))
        return ScopeResolution(
            context.method,
            context.carve_out_netting_set_ids,
            tuple(audit_metadata),
            tuple(unsupported_flags),
        )
    if context.method is CvaMethod.SA_CVA:
        if not context.sa_cva_approved:
            raise CvaInputError(
                "SA-CVA requires sa_cva_approved=True in calculation context",
                field="sa_cva_approved",
            )
        audit_metadata.append(("resolved_method", CvaMethod.SA_CVA.value))
        return ScopeResolution(
            context.method,
            context.carve_out_netting_set_ids,
            tuple(audit_metadata),
            tuple(unsupported_flags),
        )
    if context.method is CvaMethod.MIXED_CARVE_OUT:
        if not context.sa_cva_approved:
            raise CvaInputError(
                "mixed carve-out requires sa_cva_approved=True in calculation context",
                field="sa_cva_approved",
            )
        if not context.carve_out_netting_set_ids:
            raise CvaInputError(
                "mixed carve-out requires carve_out_netting_set_ids",
                field="carve_out_netting_set_ids",
            )
        require_mixed_sensitivity_scope_evidence(context)
        _validate_carve_out_batch_evidence(context.carve_out_netting_set_ids, netting_sets)
        audit_metadata.append(("resolved_method", CvaMethod.MIXED_CARVE_OUT.value))
        audit_metadata.extend(mixed_sensitivity_scope_metadata(context))
        return ScopeResolution(
            context.method,
            context.carve_out_netting_set_ids,
            tuple(audit_metadata),
            tuple(unsupported_flags),
        )
    if context.carve_out_netting_set_ids:
        _validate_carve_out_batch_ids(context.carve_out_netting_set_ids, netting_sets)
    audit_metadata.append(("resolved_method", CvaMethod.BA_CVA_REDUCED.value))
    return ScopeResolution(
        CvaMethod.BA_CVA_REDUCED,
        context.carve_out_netting_set_ids,
        tuple(audit_metadata),
        tuple(unsupported_flags),
    )


def _validate_carve_out_batch_ids(
    carve_out_ids: tuple[str, ...],
    netting_sets: CvaNettingSetBatch,
) -> None:
    known_ids = {cast(str, value) for value in netting_sets.netting_set_ids.tolist()}
    for netting_set_id in carve_out_ids:
        if netting_set_id not in known_ids:
            raise CvaInputError(
                f"carve-out netting set {netting_set_id!r} is missing from inputs",
                field="carve_out_netting_set_ids",
                record_id=netting_set_id,
            )


def _validate_carve_out_batch_evidence(
    carve_out_ids: tuple[str, ...],
    netting_sets: CvaNettingSetBatch,
) -> None:
    _validate_carve_out_batch_ids(carve_out_ids, netting_sets)
    carve_out_set = set(carve_out_ids)
    for index in range(netting_sets.row_count):
        netting_set_id = cast(str, netting_sets.netting_set_ids[index])
        carved = bool(netting_sets.carved_out_to_ba_cva[index])
        if netting_set_id in carve_out_set and not carved:
            raise CvaInputError(
                "carved-out netting set must set carved_out_to_ba_cva=True",
                field="carved_out_to_ba_cva",
                record_id=netting_set_id,
            )
        if carved and netting_set_id not in carve_out_set:
            raise CvaInputError(
                "carved_out_to_ba_cva netting set must appear in carve_out_netting_set_ids",
                field="carve_out_netting_set_ids",
                record_id=netting_set_id,
            )


__all__ = [
    "_netting_indices_by_counterparty",
    "_resolve_scope_for_batches",
    "_validate_ba_relationships",
    "_validate_hedge_batch",
    "_validate_netting_set_batch",
    "_validate_sensitivity_batch",
]
