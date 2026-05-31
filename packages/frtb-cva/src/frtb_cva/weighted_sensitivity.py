"""
SA-CVA weighted sensitivity calculation.
"""

from __future__ import annotations

from collections import defaultdict

from frtb_cva.data_models import (
    CvaHedge,
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
from frtb_cva.sa_cva_reference_data import (
    CCS_DELTA_TENORS,
    CCS_QUALIFIED_INDEX_BUCKET,
    GIRR_VEGA_INFLATION_FACTOR,
    GIRR_VEGA_RATE_FACTOR,
    ccs_delta_risk_weight,
    commodity_delta_risk_weight,
    equity_delta_risk_weight,
    equity_vega_rw_scalar,
    fx_delta_risk_weight,
    parse_ccs_entity_key,
    rcs_delta_risk_weight,
    sa_cva_vega_risk_weight,
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


def _group_sensitivity_amounts(
    sensitivities: tuple[SaCvaSensitivity, ...],
    *,
    hedges: tuple[CvaHedge, ...],
    eligible_hedge_ids: frozenset[str] | None,
) -> tuple[
    dict[SaCvaRiskFactorKey, float],
    dict[SaCvaRiskFactorKey, float],
    dict[SaCvaRiskFactorKey, list[str]],
    dict[SaCvaRiskFactorKey, float | None],
]:
    grouped_cva: dict[SaCvaRiskFactorKey, float] = defaultdict(float)
    grouped_hedge: dict[SaCvaRiskFactorKey, float] = defaultdict(float)
    grouped_ids: dict[SaCvaRiskFactorKey, list[str]] = defaultdict(list)
    grouped_volatility: dict[SaCvaRiskFactorKey, float | None] = {}
    hedge_ids = (
        eligible_hedge_ids if eligible_hedge_ids is not None else eligible_sa_cva_hedge_ids(hedges)
    )

    for sensitivity in sensitivities:
        key = _risk_factor_key(sensitivity)
        if key in grouped_volatility:
            if sensitivity.volatility_input != grouped_volatility[key]:
                raise CvaInputError(
                    "conflicting volatility_input for the same risk factor key",
                    field="volatility_input",
                )
        else:
            grouped_volatility[key] = sensitivity.volatility_input
        if sensitivity.sensitivity_tag is SensitivityTag.CVA:
            grouped_cva[key] += sensitivity.amount
            grouped_ids[key].append(sensitivity.sensitivity_id)
        elif sensitivity.sensitivity_tag is SensitivityTag.HDG:
            if sensitivity.hedge_id not in hedge_ids:
                continue
            grouped_hedge[key] += sensitivity.amount
            grouped_ids[key].append(sensitivity.sensitivity_id)
    return grouped_cva, grouped_hedge, grouped_ids, grouped_volatility


def _build_weighted_sensitivity(
    key: SaCvaRiskFactorKey,
    *,
    gross_cva: float,
    gross_hedge: float,
    risk_weight: float,
    citations: tuple[str, ...],
    grouped_ids: dict[SaCvaRiskFactorKey, list[str]],
) -> SaCvaWeightedSensitivity:
    net_amount = gross_cva - gross_hedge
    weighted_cva = gross_cva * risk_weight
    weighted_hedge = gross_hedge * risk_weight
    weighted_net = net_amount * risk_weight
    return SaCvaWeightedSensitivity(
        risk_factor_key=key,
        gross_cva_amount=gross_cva,
        gross_hedge_amount=gross_hedge,
        net_amount=net_amount,
        risk_weight=risk_weight,
        weighted_cva=weighted_cva,
        weighted_hedge=weighted_hedge,
        weighted_net=weighted_net,
        source_sensitivity_ids=tuple(sorted(set(grouped_ids[key]))),
        citations=citations,
    )


def compute_weighted_sensitivities(
    sensitivities: tuple[SaCvaSensitivity, ...],
    *,
    hedges: tuple[CvaHedge, ...] = (),
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

    grouped_cva, grouped_hedge, grouped_ids, grouped_volatility = _group_sensitivity_amounts(
        sensitivities,
        hedges=hedges,
        eligible_hedge_ids=eligible_hedge_ids,
    )
    keys = sorted(
        set(grouped_cva) | set(grouped_hedge),
        key=lambda item: (
            item.bucket_id,
            item.risk_factor_key,
            item.tenor or "",
        ),
    )

    if risk_class is SaCvaRiskClass.GIRR and risk_measure is SaCvaRiskMeasure.DELTA:
        return _weight_girr_delta(
            keys,
            grouped_cva,
            grouped_hedge,
            grouped_ids,
            reporting_currency=reporting_currency,
            profile=profile,
        )
    if risk_class is SaCvaRiskClass.GIRR and risk_measure is SaCvaRiskMeasure.VEGA:
        return _weight_girr_vega(
            keys,
            grouped_cva,
            grouped_hedge,
            grouped_ids,
            grouped_volatility,
            profile=profile,
        )
    if risk_class is SaCvaRiskClass.FX and risk_measure is SaCvaRiskMeasure.DELTA:
        return _weight_fx_delta(
            keys,
            grouped_cva,
            grouped_hedge,
            grouped_ids,
            reporting_currency=reporting_currency,
            profile=profile,
        )
    if risk_class is SaCvaRiskClass.FX and risk_measure is SaCvaRiskMeasure.VEGA:
        return _weight_fx_vega(
            keys,
            grouped_cva,
            grouped_hedge,
            grouped_ids,
            grouped_volatility,
            profile=profile,
        )
    if (
        risk_class is SaCvaRiskClass.COUNTERPARTY_CREDIT_SPREAD
        and risk_measure is SaCvaRiskMeasure.DELTA
    ):
        return _weight_ccs_delta(keys, grouped_cva, grouped_hedge, grouped_ids, profile=profile)
    if (
        risk_class is SaCvaRiskClass.REFERENCE_CREDIT_SPREAD
        and risk_measure is SaCvaRiskMeasure.DELTA
    ):
        return _weight_rcs_delta(keys, grouped_cva, grouped_hedge, grouped_ids, profile=profile)
    if (
        risk_class is SaCvaRiskClass.REFERENCE_CREDIT_SPREAD
        and risk_measure is SaCvaRiskMeasure.VEGA
    ):
        return _weight_rcs_vega(
            keys,
            grouped_cva,
            grouped_hedge,
            grouped_ids,
            grouped_volatility,
            profile=profile,
        )
    if risk_class is SaCvaRiskClass.EQUITY and risk_measure is SaCvaRiskMeasure.DELTA:
        return _weight_equity_delta(keys, grouped_cva, grouped_hedge, grouped_ids, profile=profile)
    if risk_class is SaCvaRiskClass.EQUITY and risk_measure is SaCvaRiskMeasure.VEGA:
        return _weight_equity_vega(
            keys,
            grouped_cva,
            grouped_hedge,
            grouped_ids,
            grouped_volatility,
            profile=profile,
        )
    if risk_class is SaCvaRiskClass.COMMODITY and risk_measure is SaCvaRiskMeasure.DELTA:
        return _weight_commodity_delta(
            keys, grouped_cva, grouped_hedge, grouped_ids, profile=profile
        )
    if risk_class is SaCvaRiskClass.COMMODITY and risk_measure is SaCvaRiskMeasure.VEGA:
        return _weight_commodity_vega(
            keys,
            grouped_cva,
            grouped_hedge,
            grouped_ids,
            grouped_volatility,
            profile=profile,
        )

    raise CvaInputError(
        f"unsupported SA-CVA risk class/measure: {risk_class.value}/{risk_measure.value}",
        field="risk_class",
    )


def _require_volatility(
    grouped_volatility: dict[SaCvaRiskFactorKey, float | None],
    key: SaCvaRiskFactorKey,
) -> float:
    volatility = grouped_volatility.get(key)
    if volatility is None:
        raise CvaInputError(
            "vega weighted sensitivity requires volatility_input on sensitivity rows",
            field="volatility_input",
        )
    return volatility


def _weight_girr_delta(
    keys: list[SaCvaRiskFactorKey],
    grouped_cva: dict[SaCvaRiskFactorKey, float],
    grouped_hedge: dict[SaCvaRiskFactorKey, float],
    grouped_ids: dict[SaCvaRiskFactorKey, list[str]],
    *,
    reporting_currency: str,
    profile: CvaRegulatoryProfile | str,
) -> tuple[SaCvaWeightedSensitivity, ...]:
    weighted: list[SaCvaWeightedSensitivity] = []
    for key in keys:
        if key.tenor is None:
            raise CvaInputError(
                "GIRR delta weighted sensitivity requires tenor",
                field="tenor",
            )
        base_risk_weight, citation_id = girr_delta_risk_weight(key.tenor, profile=profile)
        citations: tuple[str, ...] = (citation_id, "basel_mar50_52")
        risk_weight = base_risk_weight
        if not girr_is_specified_currency(key.bucket_id, reporting_currency=reporting_currency):
            scalar, scalar_citation = girr_other_currency_risk_weight_scalar(profile=profile)
            risk_weight = base_risk_weight * scalar
            citations = (citation_id, scalar_citation, "basel_mar50_52")
        weighted.append(
            _build_weighted_sensitivity(
                key,
                gross_cva=grouped_cva.get(key, 0.0),
                gross_hedge=grouped_hedge.get(key, 0.0),
                risk_weight=risk_weight,
                citations=citations,
                grouped_ids=grouped_ids,
            )
        )
    return tuple(weighted)


def _weight_girr_vega(
    keys: list[SaCvaRiskFactorKey],
    grouped_cva: dict[SaCvaRiskFactorKey, float],
    grouped_hedge: dict[SaCvaRiskFactorKey, float],
    grouped_ids: dict[SaCvaRiskFactorKey, list[str]],
    grouped_volatility: dict[SaCvaRiskFactorKey, float | None],
    *,
    profile: CvaRegulatoryProfile | str,
) -> tuple[SaCvaWeightedSensitivity, ...]:
    weighted: list[SaCvaWeightedSensitivity] = []
    for key in keys:
        if key.risk_factor_key not in {GIRR_VEGA_INFLATION_FACTOR, GIRR_VEGA_RATE_FACTOR}:
            raise CvaInputError(
                f"GIRR vega risk_factor_key must be {GIRR_VEGA_INFLATION_FACTOR} or "
                f"{GIRR_VEGA_RATE_FACTOR}",
                field="risk_factor_key",
            )
        volatility = _require_volatility(grouped_volatility, key)
        risk_weight, citation_id = sa_cva_vega_risk_weight(volatility, profile=profile)
        weighted.append(
            _build_weighted_sensitivity(
                key,
                gross_cva=grouped_cva.get(key, 0.0),
                gross_hedge=grouped_hedge.get(key, 0.0),
                risk_weight=risk_weight,
                citations=(citation_id, "basel_mar50_52"),
                grouped_ids=grouped_ids,
            )
        )
    return tuple(weighted)


def _weight_fx_delta(
    keys: list[SaCvaRiskFactorKey],
    grouped_cva: dict[SaCvaRiskFactorKey, float],
    grouped_hedge: dict[SaCvaRiskFactorKey, float],
    grouped_ids: dict[SaCvaRiskFactorKey, list[str]],
    *,
    reporting_currency: str,
    profile: CvaRegulatoryProfile | str,
) -> tuple[SaCvaWeightedSensitivity, ...]:
    reporting = reporting_currency.upper()
    weighted: list[SaCvaWeightedSensitivity] = []
    for key in keys:
        if key.bucket_id.upper() == reporting:
            raise CvaInputError(
                "FX buckets exclude the reporting currency",
                field="bucket_id",
            )
        risk_weight, citation_id = fx_delta_risk_weight(profile=profile)
        weighted.append(
            _build_weighted_sensitivity(
                key,
                gross_cva=grouped_cva.get(key, 0.0),
                gross_hedge=grouped_hedge.get(key, 0.0),
                risk_weight=risk_weight,
                citations=(citation_id, "basel_mar50_52"),
                grouped_ids=grouped_ids,
            )
        )
    return tuple(weighted)


def _weight_fx_vega(
    keys: list[SaCvaRiskFactorKey],
    grouped_cva: dict[SaCvaRiskFactorKey, float],
    grouped_hedge: dict[SaCvaRiskFactorKey, float],
    grouped_ids: dict[SaCvaRiskFactorKey, list[str]],
    grouped_volatility: dict[SaCvaRiskFactorKey, float | None],
    *,
    profile: CvaRegulatoryProfile | str,
) -> tuple[SaCvaWeightedSensitivity, ...]:
    weighted: list[SaCvaWeightedSensitivity] = []
    for key in keys:
        volatility = _require_volatility(grouped_volatility, key)
        risk_weight, citation_id = sa_cva_vega_risk_weight(volatility, profile=profile)
        weighted.append(
            _build_weighted_sensitivity(
                key,
                gross_cva=grouped_cva.get(key, 0.0),
                gross_hedge=grouped_hedge.get(key, 0.0),
                risk_weight=risk_weight,
                citations=(citation_id, "basel_mar50_52"),
                grouped_ids=grouped_ids,
            )
        )
    return tuple(weighted)


def _weight_ccs_delta(
    keys: list[SaCvaRiskFactorKey],
    grouped_cva: dict[SaCvaRiskFactorKey, float],
    grouped_hedge: dict[SaCvaRiskFactorKey, float],
    grouped_ids: dict[SaCvaRiskFactorKey, list[str]],
    *,
    profile: CvaRegulatoryProfile | str,
) -> tuple[SaCvaWeightedSensitivity, ...]:
    weighted: list[SaCvaWeightedSensitivity] = []
    for key in keys:
        if key.bucket_id == CCS_QUALIFIED_INDEX_BUCKET:
            raise CvaInputError(
                "CCS qualified-index bucket 8 is unsupported"
                " until qualified-index mapping is delivered",
                field="bucket_id",
            )
        if key.tenor is None or key.tenor not in CCS_DELTA_TENORS:
            raise CvaInputError(
                f"CCS delta requires tenor in {CCS_DELTA_TENORS}",
                field="tenor",
            )
        _, quality, _ = parse_ccs_entity_key(key.risk_factor_key)
        risk_weight, citation_id = ccs_delta_risk_weight(
            key.bucket_id,
            quality,
            profile=profile,
        )
        weighted.append(
            _build_weighted_sensitivity(
                key,
                gross_cva=grouped_cva.get(key, 0.0),
                gross_hedge=grouped_hedge.get(key, 0.0),
                risk_weight=risk_weight,
                citations=(citation_id, "basel_mar50_52"),
                grouped_ids=grouped_ids,
            )
        )
    return tuple(weighted)


def _weight_rcs_delta(
    keys: list[SaCvaRiskFactorKey],
    grouped_cva: dict[SaCvaRiskFactorKey, float],
    grouped_hedge: dict[SaCvaRiskFactorKey, float],
    grouped_ids: dict[SaCvaRiskFactorKey, list[str]],
    *,
    profile: CvaRegulatoryProfile | str,
) -> tuple[SaCvaWeightedSensitivity, ...]:
    weighted: list[SaCvaWeightedSensitivity] = []
    for key in keys:
        risk_weight, citation_id = rcs_delta_risk_weight(key.bucket_id, profile=profile)
        weighted.append(
            _build_weighted_sensitivity(
                key,
                gross_cva=grouped_cva.get(key, 0.0),
                gross_hedge=grouped_hedge.get(key, 0.0),
                risk_weight=risk_weight,
                citations=(citation_id, "basel_mar50_52"),
                grouped_ids=grouped_ids,
            )
        )
    return tuple(weighted)


def _weight_rcs_vega(
    keys: list[SaCvaRiskFactorKey],
    grouped_cva: dict[SaCvaRiskFactorKey, float],
    grouped_hedge: dict[SaCvaRiskFactorKey, float],
    grouped_ids: dict[SaCvaRiskFactorKey, list[str]],
    grouped_volatility: dict[SaCvaRiskFactorKey, float | None],
    *,
    profile: CvaRegulatoryProfile | str,
) -> tuple[SaCvaWeightedSensitivity, ...]:
    weighted: list[SaCvaWeightedSensitivity] = []
    for key in keys:
        volatility = _require_volatility(grouped_volatility, key)
        risk_weight, citation_id = sa_cva_vega_risk_weight(volatility, profile=profile)
        weighted.append(
            _build_weighted_sensitivity(
                key,
                gross_cva=grouped_cva.get(key, 0.0),
                gross_hedge=grouped_hedge.get(key, 0.0),
                risk_weight=risk_weight,
                citations=(citation_id, "basel_mar50_52"),
                grouped_ids=grouped_ids,
            )
        )
    return tuple(weighted)


def _weight_equity_delta(
    keys: list[SaCvaRiskFactorKey],
    grouped_cva: dict[SaCvaRiskFactorKey, float],
    grouped_hedge: dict[SaCvaRiskFactorKey, float],
    grouped_ids: dict[SaCvaRiskFactorKey, list[str]],
    *,
    profile: CvaRegulatoryProfile | str,
) -> tuple[SaCvaWeightedSensitivity, ...]:
    weighted: list[SaCvaWeightedSensitivity] = []
    for key in keys:
        risk_weight, citation_id = equity_delta_risk_weight(key.bucket_id, profile=profile)
        weighted.append(
            _build_weighted_sensitivity(
                key,
                gross_cva=grouped_cva.get(key, 0.0),
                gross_hedge=grouped_hedge.get(key, 0.0),
                risk_weight=risk_weight,
                citations=(citation_id, "basel_mar50_52"),
                grouped_ids=grouped_ids,
            )
        )
    return tuple(weighted)


def _weight_equity_vega(
    keys: list[SaCvaRiskFactorKey],
    grouped_cva: dict[SaCvaRiskFactorKey, float],
    grouped_hedge: dict[SaCvaRiskFactorKey, float],
    grouped_ids: dict[SaCvaRiskFactorKey, list[str]],
    grouped_volatility: dict[SaCvaRiskFactorKey, float | None],
    *,
    profile: CvaRegulatoryProfile | str,
) -> tuple[SaCvaWeightedSensitivity, ...]:
    weighted: list[SaCvaWeightedSensitivity] = []
    for key in keys:
        volatility = _require_volatility(grouped_volatility, key)
        rw_scalar, scalar_citation = equity_vega_rw_scalar(key.bucket_id, profile=profile)
        risk_weight, citation_id = sa_cva_vega_risk_weight(
            volatility,
            rw_scalar=rw_scalar,
            profile=profile,
        )
        weighted.append(
            _build_weighted_sensitivity(
                key,
                gross_cva=grouped_cva.get(key, 0.0),
                gross_hedge=grouped_hedge.get(key, 0.0),
                risk_weight=risk_weight,
                citations=(citation_id, scalar_citation, "basel_mar50_52"),
                grouped_ids=grouped_ids,
            )
        )
    return tuple(weighted)


def _weight_commodity_delta(
    keys: list[SaCvaRiskFactorKey],
    grouped_cva: dict[SaCvaRiskFactorKey, float],
    grouped_hedge: dict[SaCvaRiskFactorKey, float],
    grouped_ids: dict[SaCvaRiskFactorKey, list[str]],
    *,
    profile: CvaRegulatoryProfile | str,
) -> tuple[SaCvaWeightedSensitivity, ...]:
    weighted: list[SaCvaWeightedSensitivity] = []
    for key in keys:
        risk_weight, citation_id = commodity_delta_risk_weight(key.bucket_id, profile=profile)
        weighted.append(
            _build_weighted_sensitivity(
                key,
                gross_cva=grouped_cva.get(key, 0.0),
                gross_hedge=grouped_hedge.get(key, 0.0),
                risk_weight=risk_weight,
                citations=(citation_id, "basel_mar50_52"),
                grouped_ids=grouped_ids,
            )
        )
    return tuple(weighted)


def _weight_commodity_vega(
    keys: list[SaCvaRiskFactorKey],
    grouped_cva: dict[SaCvaRiskFactorKey, float],
    grouped_hedge: dict[SaCvaRiskFactorKey, float],
    grouped_ids: dict[SaCvaRiskFactorKey, list[str]],
    grouped_volatility: dict[SaCvaRiskFactorKey, float | None],
    *,
    profile: CvaRegulatoryProfile | str,
) -> tuple[SaCvaWeightedSensitivity, ...]:
    weighted: list[SaCvaWeightedSensitivity] = []
    for key in keys:
        volatility = _require_volatility(grouped_volatility, key)
        risk_weight, citation_id = sa_cva_vega_risk_weight(volatility, profile=profile)
        weighted.append(
            _build_weighted_sensitivity(
                key,
                gross_cva=grouped_cva.get(key, 0.0),
                gross_hedge=grouped_hedge.get(key, 0.0),
                risk_weight=risk_weight,
                citations=(citation_id, "basel_mar50_52"),
                grouped_ids=grouped_ids,
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
