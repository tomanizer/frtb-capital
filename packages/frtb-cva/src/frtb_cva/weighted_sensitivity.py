"""
SA-CVA weighted sensitivity calculation.
"""

from __future__ import annotations

from collections import defaultdict

from frtb_cva.data_models import (
    CvaRegulatoryProfile,
    SaCvaRiskClass,
    SaCvaRiskFactorKey,
    SaCvaRiskMeasure,
    SaCvaSensitivity,
    SaCvaWeightedSensitivity,
    SensitivityTag,
)
from frtb_cva.hedges import eligible_sa_cva_hedge_ids
from frtb_cva.reference_data import (
    girr_delta_risk_weight,
    girr_is_specified_currency,
    girr_other_currency_risk_weight_scalar,
)
from frtb_cva.validation import CvaInputError


def _risk_factor_key(sensitivity: SaCvaSensitivity) -> SaCvaRiskFactorKey:
    return SaCvaRiskFactorKey(
        risk_class=sensitivity.risk_class,
        risk_measure=sensitivity.risk_measure,
        bucket_id=sensitivity.bucket_id,
        risk_factor_key=sensitivity.risk_factor_key,
        tenor=sensitivity.tenor,
    )


def compute_weighted_sensitivities(
    sensitivities: tuple[SaCvaSensitivity, ...],
    *,
    hedges: tuple[object, ...] = (),
    eligible_hedge_ids: frozenset[str] | None = None,
    reporting_currency: str = "USD",
    profile: CvaRegulatoryProfile | str = CvaRegulatoryProfile.BASEL_MAR50_2020,
) -> tuple[SaCvaWeightedSensitivity, ...]:
    """Convert canonical sensitivities into cited weighted sensitivity records."""

    if not sensitivities:
        return ()

    risk_classes = {item.risk_class for item in sensitivities}
    risk_measures = {item.risk_measure for item in sensitivities}
    if len(risk_classes) != 1 or len(risk_measures) != 1:
        raise CvaInputError(
            "weighted sensitivity calculation requires homogeneous risk class and measure",
            field="sensitivities",
        )
    risk_class = next(iter(risk_classes))
    risk_measure = next(iter(risk_measures))
    if risk_class is not SaCvaRiskClass.GIRR or risk_measure is not SaCvaRiskMeasure.DELTA:
        raise CvaInputError(
            "only GIRR delta weighted sensitivities are supported in phase 2",
            field="risk_class",
        )

    grouped_cva: dict[SaCvaRiskFactorKey, float] = defaultdict(float)
    grouped_hedge: dict[SaCvaRiskFactorKey, float] = defaultdict(float)
    hedge_ids = eligible_hedge_ids
    if hedge_ids is None:
        if hedges:
            from frtb_cva.data_models import CvaHedge

            validated_hedges = tuple(hedge for hedge in hedges if isinstance(hedge, CvaHedge))
            hedge_ids = eligible_sa_cva_hedge_ids(validated_hedges)
        else:
            hedge_ids = frozenset()

    for sensitivity in sensitivities:
        key = _risk_factor_key(sensitivity)
        if sensitivity.sensitivity_tag is SensitivityTag.CVA:
            grouped_cva[key] += sensitivity.amount
        elif sensitivity.sensitivity_tag is SensitivityTag.HDG:
            if sensitivity.hedge_id not in hedge_ids:
                continue
            grouped_hedge[key] += sensitivity.amount

    keys = sorted(
        set(grouped_cva) | set(grouped_hedge),
        key=lambda item: (
            item.bucket_id,
            item.risk_factor_key,
            item.tenor or "",
        ),
    )
    weighted: list[SaCvaWeightedSensitivity] = []
    for key in keys:
        gross_cva = grouped_cva.get(key, 0.0)
        gross_hedge = grouped_hedge.get(key, 0.0)
        net_amount = gross_cva - gross_hedge
        # tenor is required for GIRR delta (validated at input boundary)
        tenor = key.tenor if key.tenor is not None else key.risk_factor_key
        base_risk_weight, citation_id = girr_delta_risk_weight(tenor, profile=profile)
        citations: tuple[str, ...] = (citation_id, "basel_mar50_52")
        risk_weight = base_risk_weight
        if not girr_is_specified_currency(
            key.bucket_id,
            reporting_currency=reporting_currency,
        ):
            scalar, scalar_citation = girr_other_currency_risk_weight_scalar(profile=profile)
            risk_weight = base_risk_weight * scalar
            citations = (citation_id, scalar_citation, "basel_mar50_52")
        weighted_cva = gross_cva * risk_weight
        weighted_hedge = gross_hedge * risk_weight
        weighted_net = net_amount * risk_weight
        weighted.append(
            SaCvaWeightedSensitivity(
                risk_factor_key=key,
                gross_cva_amount=gross_cva,
                gross_hedge_amount=gross_hedge,
                net_amount=net_amount,
                risk_weight=risk_weight,
                weighted_cva=weighted_cva,
                weighted_hedge=weighted_hedge,
                weighted_net=weighted_net,
                citations=citations,
            )
        )
    return tuple(weighted)


def sort_weighted_sensitivities(
    weighted_sensitivities: tuple[SaCvaWeightedSensitivity, ...],
) -> tuple[SaCvaWeightedSensitivity, ...]:
    """Return weighted sensitivities in deterministic order."""

    return tuple(
        sorted(
            weighted_sensitivities,
            key=lambda item: (
                item.risk_factor_key.bucket_id,
                item.risk_factor_key.risk_factor_key,
                item.risk_factor_key.tenor or "",
            ),
        )
    )


__all__ = [
    "compute_weighted_sensitivities",
    "sort_weighted_sensitivities",
]
