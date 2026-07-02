"""SA-CVA batch sensitivity grouping and weighting."""

from __future__ import annotations

import math
from collections import defaultdict
from dataclasses import dataclass
from typing import cast

import numpy as np

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
from frtb_cva.weighted_sensitivity import weight_grouped_sa_cva_sensitivities


@dataclass(frozen=True)
class _GroupedSensitivities:
    cva: dict[SaCvaRiskFactorKey, float]
    hedge: dict[SaCvaRiskFactorKey, float]
    ids: dict[SaCvaRiskFactorKey, list[str]]
    volatility: dict[SaCvaRiskFactorKey, float | None]
    provenance: dict[SaCvaRiskFactorKey, dict[str, list[str]]]
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
    grouped_provenance: dict[SaCvaRiskFactorKey, dict[str, list[str]]] = defaultdict(
        _empty_provenance_values
    )
    for index in indices:
        key = _risk_factor_key_from_batch(batch, index, profile=profile)
        _record_volatility(batch, index, key, grouped_volatility)
        tag = SensitivityTag(cast(str, batch.sensitivity_tags[index]))
        if tag is SensitivityTag.CVA:
            grouped_cva[key] += float(batch.amounts[index])
            grouped_ids[key].append(cast(str, batch.sensitivity_ids[index]))
            _record_batch_provenance(grouped_provenance, key, batch, index)
        elif tag is SensitivityTag.HDG:
            hedge_id = cast(str | None, batch.hedge_ids[index])
            if hedge_id not in eligible_hedge_ids:
                continue
            grouped_hedge[key] += float(batch.amounts[index])
            grouped_ids[key].append(cast(str, batch.sensitivity_ids[index]))
            _record_batch_provenance(grouped_provenance, key, batch, index)
    return _GroupedSensitivities(
        cva=grouped_cva,
        hedge=grouped_hedge,
        ids=grouped_ids,
        volatility=grouped_volatility,
        provenance=grouped_provenance,
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


def _empty_provenance_values() -> dict[str, list[str]]:
    return {
        "volatility_surface_ids": [],
        "volatility_surface_point_ids": [],
        "shock_ids": [],
    }


def _record_batch_provenance(
    grouped_provenance: dict[SaCvaRiskFactorKey, dict[str, list[str]]],
    key: SaCvaRiskFactorKey,
    batch: SaCvaSensitivityBatch,
    index: int,
) -> None:
    values = grouped_provenance[key]
    if volatility_surface_id := _optional_text_at(batch.volatility_surface_ids, index):
        values["volatility_surface_ids"].append(volatility_surface_id)
    if volatility_surface_point_id := _optional_text_at(batch.volatility_surface_point_ids, index):
        values["volatility_surface_point_ids"].append(volatility_surface_point_id)
    if shock_id := _optional_text_at(batch.shock_ids, index):
        values["shock_ids"].append(shock_id)


def _optional_text_at(values: object, index: int) -> str:
    if values is None:
        return ""
    value = cast(object, values[index])  # type: ignore[index]
    if value is None:
        return ""
    if isinstance(value, (float, np.floating)) and math.isnan(float(value)):
        return ""
    text = str(value)
    return text if text.strip() else ""


def _risk_factor_key_from_batch(
    batch: SaCvaSensitivityBatch,
    index: int,
    *,
    profile: CvaRegulatoryProfile | str,
) -> SaCvaRiskFactorKey:
    risk_class = SaCvaRiskClass(cast(str, batch.risk_classes[index]))
    bucket_id = _resolve_sa_cva_bucket_from_batch(batch, index, profile=profile)
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
    return weight_grouped_sa_cva_sensitivities(
        grouped.keys,
        grouped.cva,
        grouped.hedge,
        grouped.ids,
        grouped.volatility,
        grouped_provenance=grouped.provenance,
        risk_class=risk_class,
        risk_measure=risk_measure,
        reporting_currency=reporting_currency,
        profile=profile,
    )
