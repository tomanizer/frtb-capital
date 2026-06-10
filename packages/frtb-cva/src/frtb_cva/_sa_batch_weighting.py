"""SA-CVA batch sensitivity grouping and weighting."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import cast

from frtb_cva._batch_columns import _optional_float_value
from frtb_cva._batch_contracts import CvaHedgeBatch, SaCvaSensitivityBatch
from frtb_cva._sa_batch_routing import _resolve_sa_cva_bucket_from_batch
from frtb_cva.data_models import (
    CvaRegulatoryProfile,
    SaCvaRiskClass,
    SaCvaRiskFactorKey,
    SaCvaRiskMeasure,
    SaCvaWeightedSensitivity,
    SensitivityTag,
)
from frtb_cva.validation import CvaInputError
from frtb_cva.weighted_sensitivity import (
    _weight_ccs_delta,
    _weight_commodity_delta,
    _weight_commodity_vega,
    _weight_equity_delta,
    _weight_equity_vega,
    _weight_fx_delta,
    _weight_fx_vega,
    _weight_girr_delta,
    _weight_girr_vega,
    _weight_rcs_delta,
    _weight_rcs_vega,
)


@dataclass(frozen=True)
class _GroupedSensitivities:
    cva: dict[SaCvaRiskFactorKey, float]
    hedge: dict[SaCvaRiskFactorKey, float]
    ids: dict[SaCvaRiskFactorKey, list[str]]
    volatility: dict[SaCvaRiskFactorKey, float | None]
    keys: list[SaCvaRiskFactorKey]


def _compute_weighted_sensitivities_from_batch(
    batch: SaCvaSensitivityBatch,
    indices: list[int],
    *,
    hedge_batch: CvaHedgeBatch,
    eligible_hedge_ids: frozenset[str],
    reporting_currency: str,
    profile: CvaRegulatoryProfile | str,
) -> tuple[SaCvaWeightedSensitivity, ...]:
    del hedge_batch
    grouped = _group_sensitivities(
        batch,
        indices,
        eligible_hedge_ids=eligible_hedge_ids,
        profile=profile,
    )
    if not grouped.keys:
        raise CvaInputError("SA-CVA path has no eligible sensitivities", field="sensitivities")
    return _weight_grouped_sensitivities(
        grouped,
        reporting_currency=reporting_currency,
        profile=profile,
    )


def _group_sensitivities(
    batch: SaCvaSensitivityBatch,
    indices: list[int],
    *,
    eligible_hedge_ids: frozenset[str],
    profile: CvaRegulatoryProfile | str,
) -> _GroupedSensitivities:
    grouped_cva: dict[SaCvaRiskFactorKey, float] = defaultdict(float)
    grouped_hedge: dict[SaCvaRiskFactorKey, float] = defaultdict(float)
    grouped_ids: dict[SaCvaRiskFactorKey, list[str]] = defaultdict(list)
    grouped_volatility: dict[SaCvaRiskFactorKey, float | None] = {}
    for index in indices:
        key = _risk_factor_key_from_batch(batch, index, profile=profile)
        _record_volatility(batch, index, key, grouped_volatility)
        tag = SensitivityTag(cast(str, batch.sensitivity_tags[index]))
        if tag is SensitivityTag.CVA:
            grouped_cva[key] += float(batch.amounts[index])
            grouped_ids[key].append(cast(str, batch.sensitivity_ids[index]))
        elif tag is SensitivityTag.HDG:
            hedge_id = cast(str | None, batch.hedge_ids[index])
            if hedge_id not in eligible_hedge_ids:
                continue
            grouped_hedge[key] += float(batch.amounts[index])
            grouped_ids[key].append(cast(str, batch.sensitivity_ids[index]))
    return _GroupedSensitivities(
        cva=grouped_cva,
        hedge=grouped_hedge,
        ids=grouped_ids,
        volatility=grouped_volatility,
        keys=sorted(
            set(grouped_cva) | set(grouped_hedge),
            key=lambda item: (item.bucket_id, item.risk_factor_key, item.tenor or ""),
        ),
    )


def _record_volatility(
    batch: SaCvaSensitivityBatch,
    index: int,
    key: SaCvaRiskFactorKey,
    grouped_volatility: dict[SaCvaRiskFactorKey, float | None],
) -> None:
    volatility = _optional_float_value(batch.volatility_inputs[index])
    if key in grouped_volatility and volatility != grouped_volatility[key]:
        raise CvaInputError(
            "conflicting volatility_input for the same risk factor key",
            field="volatility_input",
        )
    grouped_volatility.setdefault(key, volatility)


def _risk_factor_key_from_batch(
    batch: SaCvaSensitivityBatch,
    index: int,
    *,
    profile: CvaRegulatoryProfile | str,
) -> SaCvaRiskFactorKey:
    del profile
    risk_class = SaCvaRiskClass(cast(str, batch.risk_classes[index]))
    bucket_id = _resolve_sa_cva_bucket_from_batch(batch, index)
    return SaCvaRiskFactorKey(
        risk_class=risk_class,
        risk_measure=SaCvaRiskMeasure(cast(str, batch.risk_measures[index])),
        bucket_id=bucket_id,
        risk_factor_key=cast(str, batch.risk_factor_keys[index]),
        tenor=cast(str | None, batch.tenors[index]),
    )


def _weight_grouped_sensitivities(
    grouped: _GroupedSensitivities,
    *,
    reporting_currency: str,
    profile: CvaRegulatoryProfile | str,
) -> tuple[SaCvaWeightedSensitivity, ...]:
    risk_class = grouped.keys[0].risk_class
    risk_measure = grouped.keys[0].risk_measure
    if risk_measure is SaCvaRiskMeasure.DELTA:
        return _weight_delta_group(grouped, risk_class, reporting_currency, profile)
    if risk_measure is SaCvaRiskMeasure.VEGA:
        return _weight_vega_group(grouped, risk_class, profile)
    raise CvaInputError(
        f"unsupported SA-CVA risk class/measure: {risk_class.value}/{risk_measure.value}",
        field="risk_class",
    )


def _weight_delta_group(
    grouped: _GroupedSensitivities,
    risk_class: SaCvaRiskClass,
    reporting_currency: str,
    profile: CvaRegulatoryProfile | str,
) -> tuple[SaCvaWeightedSensitivity, ...]:
    if risk_class is SaCvaRiskClass.GIRR:
        return _weight_girr_delta(
            grouped.keys,
            grouped.cva,
            grouped.hedge,
            grouped.ids,
            reporting_currency=reporting_currency,
            profile=profile,
        )
    if risk_class is SaCvaRiskClass.FX:
        return _weight_fx_delta(
            grouped.keys,
            grouped.cva,
            grouped.hedge,
            grouped.ids,
            reporting_currency=reporting_currency,
            profile=profile,
        )
    if risk_class is SaCvaRiskClass.COUNTERPARTY_CREDIT_SPREAD:
        return _weight_ccs_delta(
            grouped.keys,
            grouped.cva,
            grouped.hedge,
            grouped.ids,
            profile=profile,
        )
    if risk_class is SaCvaRiskClass.REFERENCE_CREDIT_SPREAD:
        return _weight_rcs_delta(
            grouped.keys,
            grouped.cva,
            grouped.hedge,
            grouped.ids,
            profile=profile,
        )
    if risk_class is SaCvaRiskClass.EQUITY:
        return _weight_equity_delta(
            grouped.keys,
            grouped.cva,
            grouped.hedge,
            grouped.ids,
            profile=profile,
        )
    if risk_class is SaCvaRiskClass.COMMODITY:
        return _weight_commodity_delta(
            grouped.keys, grouped.cva, grouped.hedge, grouped.ids, profile=profile
        )
    raise CvaInputError(
        f"unsupported SA-CVA delta risk class: {risk_class.value}",
        field="risk_class",
    )


def _weight_vega_group(
    grouped: _GroupedSensitivities,
    risk_class: SaCvaRiskClass,
    profile: CvaRegulatoryProfile | str,
) -> tuple[SaCvaWeightedSensitivity, ...]:
    if risk_class is SaCvaRiskClass.GIRR:
        return _weight_girr_vega(
            grouped.keys,
            grouped.cva,
            grouped.hedge,
            grouped.ids,
            grouped.volatility,
            profile=profile,
        )
    if risk_class is SaCvaRiskClass.FX:
        return _weight_fx_vega(
            grouped.keys,
            grouped.cva,
            grouped.hedge,
            grouped.ids,
            grouped.volatility,
            profile=profile,
        )
    if risk_class is SaCvaRiskClass.REFERENCE_CREDIT_SPREAD:
        return _weight_rcs_vega(
            grouped.keys,
            grouped.cva,
            grouped.hedge,
            grouped.ids,
            grouped.volatility,
            profile=profile,
        )
    if risk_class is SaCvaRiskClass.EQUITY:
        return _weight_equity_vega(
            grouped.keys,
            grouped.cva,
            grouped.hedge,
            grouped.ids,
            grouped.volatility,
            profile=profile,
        )
    if risk_class is SaCvaRiskClass.COMMODITY:
        return _weight_commodity_vega(
            grouped.keys,
            grouped.cva,
            grouped.hedge,
            grouped.ids,
            grouped.volatility,
            profile=profile,
        )
    raise CvaInputError(
        f"unsupported SA-CVA vega risk class: {risk_class.value}",
        field="risk_class",
    )
