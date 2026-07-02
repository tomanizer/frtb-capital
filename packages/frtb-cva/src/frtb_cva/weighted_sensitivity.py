"""
SA-CVA weighted sensitivity calculation.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass

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
from frtb_cva.qualified_index import resolve_sa_cva_bucket
from frtb_cva.reference_data import (
    girr_delta_risk_weight,
    girr_is_specified_currency,
    girr_other_currency_risk_weight_scalar,
    profile_citation_id,
)
from frtb_cva.sa_cva_reference_data import (
    CCS_DELTA_TENORS,
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

_WeightingFn = Callable[..., tuple[SaCvaWeightedSensitivity, ...]]
_GroupedProvenance = dict[SaCvaRiskFactorKey, dict[str, list[str]]]


@dataclass(frozen=True)
class SaCvaWeightingSpec:
    """Table entry for one SA-CVA weighted-sensitivity calculation path."""

    risk_class: SaCvaRiskClass
    risk_measure: SaCvaRiskMeasure
    weight_fn: _WeightingFn | None
    requires_reporting_currency: bool = False
    requires_volatility: bool = False
    unsupported_message: str | None = None


def _risk_factor_key(
    sensitivity: SaCvaSensitivity,
    *,
    profile: CvaRegulatoryProfile | str = CvaRegulatoryProfile.BASEL_MAR50_2020,
) -> SaCvaRiskFactorKey:
    bucket_id, _ = resolve_sa_cva_bucket(sensitivity, profile=profile)
    return SaCvaRiskFactorKey(
        risk_class=sensitivity.risk_class,
        risk_measure=sensitivity.risk_measure,
        bucket_id=bucket_id,
        risk_factor_key=sensitivity.risk_factor_key,
        tenor=sensitivity.tenor,
    )


def _group_sensitivity_amounts(
    sensitivities: tuple[SaCvaSensitivity, ...],
    *,
    hedges: tuple[CvaHedge, ...],
    eligible_hedge_ids: frozenset[str] | None,
    profile: CvaRegulatoryProfile | str = CvaRegulatoryProfile.BASEL_MAR50_2020,
) -> tuple[
    dict[SaCvaRiskFactorKey, float],
    dict[SaCvaRiskFactorKey, float],
    dict[SaCvaRiskFactorKey, list[str]],
    dict[SaCvaRiskFactorKey, float | None],
    _GroupedProvenance,
]:
    grouped_cva: dict[SaCvaRiskFactorKey, float] = defaultdict(float)
    grouped_hedge: dict[SaCvaRiskFactorKey, float] = defaultdict(float)
    grouped_ids: dict[SaCvaRiskFactorKey, list[str]] = defaultdict(list)
    grouped_volatility: dict[SaCvaRiskFactorKey, float | None] = {}
    grouped_provenance: _GroupedProvenance = defaultdict(_empty_provenance_values)
    hedge_ids = (
        eligible_hedge_ids
        if eligible_hedge_ids is not None
        else eligible_sa_cva_hedge_ids(hedges, profile=profile)
    )

    for sensitivity in sensitivities:
        key = _risk_factor_key(sensitivity, profile=profile)
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
            _record_sensitivity_provenance(grouped_provenance, key, sensitivity)
        elif sensitivity.sensitivity_tag is SensitivityTag.HDG:
            if sensitivity.hedge_id not in hedge_ids:
                continue
            grouped_hedge[key] += sensitivity.amount
            grouped_ids[key].append(sensitivity.sensitivity_id)
            _record_sensitivity_provenance(grouped_provenance, key, sensitivity)
    return grouped_cva, grouped_hedge, grouped_ids, grouped_volatility, grouped_provenance


def _empty_provenance_values() -> dict[str, list[str]]:
    return {
        "volatility_surface_ids": [],
        "volatility_surface_point_ids": [],
        "shock_ids": [],
    }


def _record_sensitivity_provenance(
    grouped_provenance: _GroupedProvenance,
    key: SaCvaRiskFactorKey,
    sensitivity: SaCvaSensitivity,
) -> None:
    values = grouped_provenance[key]
    if sensitivity.volatility_surface_id:
        values["volatility_surface_ids"].append(sensitivity.volatility_surface_id)
    if sensitivity.volatility_surface_point_id:
        values["volatility_surface_point_ids"].append(sensitivity.volatility_surface_point_id)
    if sensitivity.shock_id:
        values["shock_ids"].append(sensitivity.shock_id)


def _build_weighted_sensitivity(
    key: SaCvaRiskFactorKey,
    *,
    gross_cva: float,
    gross_hedge: float,
    risk_weight: float,
    citations: tuple[str, ...],
    grouped_ids: dict[SaCvaRiskFactorKey, list[str]],
    grouped_provenance: _GroupedProvenance | None = None,
) -> SaCvaWeightedSensitivity:
    net_amount = gross_cva - gross_hedge
    weighted_cva = gross_cva * risk_weight
    weighted_hedge = gross_hedge * risk_weight
    weighted_net = net_amount * risk_weight
    provenance = (
        _empty_provenance_values()
        if grouped_provenance is None
        else grouped_provenance.get(key, _empty_provenance_values())
    )
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
        volatility_surface_ids=_unique_sorted(provenance["volatility_surface_ids"]),
        volatility_surface_point_ids=_unique_sorted(provenance["volatility_surface_point_ids"]),
        shock_ids=_unique_sorted(provenance["shock_ids"]),
    )


def _unique_sorted(values: list[str]) -> tuple[str, ...]:
    return tuple(sorted(set(values)))


def compute_weighted_sensitivities(
    sensitivities: tuple[SaCvaSensitivity, ...],
    *,
    hedges: tuple[CvaHedge, ...] = (),
    eligible_hedge_ids: frozenset[str] | None = None,
    reporting_currency: str = "USD",
    profile: CvaRegulatoryProfile | str = CvaRegulatoryProfile.BASEL_MAR50_2020,
) -> tuple[SaCvaWeightedSensitivity, ...]:
    """Convert canonical sensitivities into cited weighted sensitivity records.

    Parameters
    ----------
    sensitivities :
        Raw SA-CVA sensitivities prior to weighting.

    hedges, optional :
        Declared BA-CVA or SA-CVA hedge records assessed for eligibility.

    eligible_hedge_ids, optional :
        Stable identifiers for eligible hedge recorded on results.

    reporting_currency, optional :
        Input for ``compute_weighted_sensitivities`` used in the CVA capital path.

    profile, optional :
        Optional ``CvaRegulatoryProfile`` or profile label; default Basel MAR50 (2020).

    Returns
    -------
    tuple[SaCvaWeightedSensitivity, ...]
        Result of ``compute_weighted_sensitivities`` for audit and downstream aggregation."""

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

    (
        grouped_cva,
        grouped_hedge,
        grouped_ids,
        grouped_volatility,
        grouped_provenance,
    ) = _group_sensitivity_amounts(
        sensitivities,
        hedges=hedges,
        eligible_hedge_ids=eligible_hedge_ids,
        profile=profile,
    )
    keys = sorted(
        set(grouped_cva) | set(grouped_hedge),
        key=lambda item: (
            item.bucket_id,
            item.risk_factor_key,
            item.tenor or "",
        ),
    )

    return weight_grouped_sa_cva_sensitivities(
        keys,
        grouped_cva,
        grouped_hedge,
        grouped_ids,
        grouped_volatility,
        grouped_provenance=grouped_provenance,
        risk_class=risk_class,
        risk_measure=risk_measure,
        reporting_currency=reporting_currency,
        profile=profile,
    )


def weight_grouped_sa_cva_sensitivities(
    keys: list[SaCvaRiskFactorKey],
    grouped_cva: dict[SaCvaRiskFactorKey, float],
    grouped_hedge: dict[SaCvaRiskFactorKey, float],
    grouped_ids: dict[SaCvaRiskFactorKey, list[str]],
    grouped_volatility: dict[SaCvaRiskFactorKey, float | None],
    *,
    grouped_provenance: _GroupedProvenance | None = None,
    risk_class: SaCvaRiskClass,
    risk_measure: SaCvaRiskMeasure,
    reporting_currency: str,
    profile: CvaRegulatoryProfile | str,
) -> tuple[SaCvaWeightedSensitivity, ...]:
    """Dispatch grouped SA-CVA sensitivities through the weighting registry."""

    spec = _weighting_spec_for(risk_class, risk_measure)
    weight_fn = spec.weight_fn
    if weight_fn is None:
        raise CvaInputError(
            spec.unsupported_message
            or f"unsupported SA-CVA risk class/measure: {risk_class.value}/{risk_measure.value}",
            field="risk_class",
        )
    if spec.requires_volatility:
        return weight_fn(
            keys,
            grouped_cva,
            grouped_hedge,
            grouped_ids,
            grouped_volatility,
            grouped_provenance,
            profile=profile,
        )
    if spec.requires_reporting_currency:
        return weight_fn(
            keys,
            grouped_cva,
            grouped_hedge,
            grouped_ids,
            reporting_currency=reporting_currency,
            profile=profile,
        )
    return weight_fn(keys, grouped_cva, grouped_hedge, grouped_ids, profile=profile)


def _weighting_spec_for(
    risk_class: SaCvaRiskClass,
    risk_measure: SaCvaRiskMeasure,
) -> SaCvaWeightingSpec:
    spec = SA_CVA_WEIGHTING_REGISTRY.get((risk_class, risk_measure))
    if spec is None:
        raise CvaInputError(
            f"unsupported SA-CVA risk class/measure: {risk_class.value}/{risk_measure.value}",
            field="risk_class",
        )
    if spec.unsupported_message is not None:
        raise CvaInputError(spec.unsupported_message, field="risk_class")
    return spec


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
        netting_citation = profile_citation_id("basel_mar50_52", profile)
        citations: tuple[str, ...] = (citation_id, netting_citation)
        risk_weight = base_risk_weight
        if not girr_is_specified_currency(key.bucket_id, reporting_currency=reporting_currency):
            scalar, scalar_citation = girr_other_currency_risk_weight_scalar(profile=profile)
            risk_weight = base_risk_weight * scalar
            citations = (citation_id, scalar_citation, netting_citation)
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
    grouped_provenance: _GroupedProvenance,
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
                citations=(citation_id, profile_citation_id("basel_mar50_52", profile)),
                grouped_ids=grouped_ids,
                grouped_provenance=grouped_provenance,
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
                citations=(citation_id, profile_citation_id("basel_mar50_52", profile)),
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
    grouped_provenance: _GroupedProvenance,
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
                citations=(citation_id, profile_citation_id("basel_mar50_52", profile)),
                grouped_ids=grouped_ids,
                grouped_provenance=grouped_provenance,
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
                citations=(citation_id, profile_citation_id("basel_mar50_52", profile)),
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
                citations=(citation_id, profile_citation_id("basel_mar50_52", profile)),
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
    grouped_provenance: _GroupedProvenance,
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
                citations=(citation_id, profile_citation_id("basel_mar50_52", profile)),
                grouped_ids=grouped_ids,
                grouped_provenance=grouped_provenance,
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
                citations=(citation_id, profile_citation_id("basel_mar50_52", profile)),
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
    grouped_provenance: _GroupedProvenance,
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
                citations=(
                    citation_id,
                    scalar_citation,
                    profile_citation_id("basel_mar50_52", profile),
                ),
                grouped_ids=grouped_ids,
                grouped_provenance=grouped_provenance,
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
                citations=(citation_id, profile_citation_id("basel_mar50_52", profile)),
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
    grouped_provenance: _GroupedProvenance,
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
                citations=(citation_id, profile_citation_id("basel_mar50_52", profile)),
                grouped_ids=grouped_ids,
                grouped_provenance=grouped_provenance,
            )
        )
    return tuple(weighted)


SA_CVA_WEIGHTING_REGISTRY: dict[tuple[SaCvaRiskClass, SaCvaRiskMeasure], SaCvaWeightingSpec] = {
    (SaCvaRiskClass.GIRR, SaCvaRiskMeasure.DELTA): SaCvaWeightingSpec(
        SaCvaRiskClass.GIRR,
        SaCvaRiskMeasure.DELTA,
        _weight_girr_delta,
        requires_reporting_currency=True,
    ),
    (SaCvaRiskClass.GIRR, SaCvaRiskMeasure.VEGA): SaCvaWeightingSpec(
        SaCvaRiskClass.GIRR,
        SaCvaRiskMeasure.VEGA,
        _weight_girr_vega,
        requires_volatility=True,
    ),
    (SaCvaRiskClass.FX, SaCvaRiskMeasure.DELTA): SaCvaWeightingSpec(
        SaCvaRiskClass.FX,
        SaCvaRiskMeasure.DELTA,
        _weight_fx_delta,
        requires_reporting_currency=True,
    ),
    (SaCvaRiskClass.FX, SaCvaRiskMeasure.VEGA): SaCvaWeightingSpec(
        SaCvaRiskClass.FX,
        SaCvaRiskMeasure.VEGA,
        _weight_fx_vega,
        requires_volatility=True,
    ),
    (
        SaCvaRiskClass.COUNTERPARTY_CREDIT_SPREAD,
        SaCvaRiskMeasure.DELTA,
    ): SaCvaWeightingSpec(
        SaCvaRiskClass.COUNTERPARTY_CREDIT_SPREAD,
        SaCvaRiskMeasure.DELTA,
        _weight_ccs_delta,
    ),
    (
        SaCvaRiskClass.COUNTERPARTY_CREDIT_SPREAD,
        SaCvaRiskMeasure.VEGA,
    ): SaCvaWeightingSpec(
        SaCvaRiskClass.COUNTERPARTY_CREDIT_SPREAD,
        SaCvaRiskMeasure.VEGA,
        None,
        unsupported_message="CCS vega capital is not permitted under MAR50.45 and MAR50.63",
    ),
    (
        SaCvaRiskClass.REFERENCE_CREDIT_SPREAD,
        SaCvaRiskMeasure.DELTA,
    ): SaCvaWeightingSpec(
        SaCvaRiskClass.REFERENCE_CREDIT_SPREAD,
        SaCvaRiskMeasure.DELTA,
        _weight_rcs_delta,
    ),
    (
        SaCvaRiskClass.REFERENCE_CREDIT_SPREAD,
        SaCvaRiskMeasure.VEGA,
    ): SaCvaWeightingSpec(
        SaCvaRiskClass.REFERENCE_CREDIT_SPREAD,
        SaCvaRiskMeasure.VEGA,
        _weight_rcs_vega,
        requires_volatility=True,
    ),
    (SaCvaRiskClass.EQUITY, SaCvaRiskMeasure.DELTA): SaCvaWeightingSpec(
        SaCvaRiskClass.EQUITY,
        SaCvaRiskMeasure.DELTA,
        _weight_equity_delta,
    ),
    (SaCvaRiskClass.EQUITY, SaCvaRiskMeasure.VEGA): SaCvaWeightingSpec(
        SaCvaRiskClass.EQUITY,
        SaCvaRiskMeasure.VEGA,
        _weight_equity_vega,
        requires_volatility=True,
    ),
    (SaCvaRiskClass.COMMODITY, SaCvaRiskMeasure.DELTA): SaCvaWeightingSpec(
        SaCvaRiskClass.COMMODITY,
        SaCvaRiskMeasure.DELTA,
        _weight_commodity_delta,
    ),
    (SaCvaRiskClass.COMMODITY, SaCvaRiskMeasure.VEGA): SaCvaWeightingSpec(
        SaCvaRiskClass.COMMODITY,
        SaCvaRiskMeasure.VEGA,
        _weight_commodity_vega,
        requires_volatility=True,
    ),
}


def sort_weighted_sensitivities(
    weighted_sensitivities: tuple[SaCvaWeightedSensitivity, ...],
) -> tuple[SaCvaWeightedSensitivity, ...]:
    """Return weighted sensitivities in deterministic order.

    Parameters
    ----------
    weighted_sensitivities :
        Net and hedge-weighted SA-CVA sensitivities validated for bucket aggregation.

    Returns
    -------
    tuple[SaCvaWeightedSensitivity, ...]
        Result of ``sort_weighted_sensitivities`` for audit and downstream aggregation."""

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
    "SA_CVA_WEIGHTING_REGISTRY",
    "SaCvaWeightingSpec",
    "compute_weighted_sensitivities",
    "sort_weighted_sensitivities",
    "weight_grouped_sa_cva_sensitivities",
]
