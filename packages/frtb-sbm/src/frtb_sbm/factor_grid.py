"""SBM package-local regulatory factor-grid helpers."""

from __future__ import annotations

import math
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from types import MappingProxyType

from frtb_sbm.data_models import SbmRiskClass, SbmRiskMeasure, SbmSensitivity, WeightedSensitivity
from frtb_sbm.validation import SbmInputError


@dataclass(frozen=True, order=True)
class GirrDeltaFactorKey:
    """Regulatory GIRR delta factor coordinate within one bucket."""

    bucket: str
    risk_factor: str
    tenor: str

    def as_tuple(self) -> tuple[str, str, str]:
        """Return the stable tuple form used in audit payloads."""

        return (self.bucket, self.risk_factor, self.tenor)


@dataclass(frozen=True)
class GirrDeltaNettedFactorGrid:
    """Netted GIRR delta weighted factors plus lookup metadata."""

    weighted_sensitivities: tuple[WeightedSensitivity, ...]
    tenor_by_id: Mapping[str, str]
    risk_factor_by_id: Mapping[str, str]
    raw_row_count: int
    factor_count: int


def net_girr_delta_weighted_sensitivities(
    sensitivities: Sequence[SbmSensitivity],
    weighted_sensitivities: Sequence[WeightedSensitivity],
) -> GirrDeltaNettedFactorGrid:
    """
    Net GIRR delta weighted sensitivities to distinct regulatory factor keys.

    Netting is exact for duplicate bucket/risk-factor/tenor rows because their
    mutual correlation and their correlations to every other factor are
    identical. The input hash remains tied to the original row sensitivities;
    this helper only changes the internal aggregation grid.
    """

    sensitivity_by_id = _sensitivity_by_id(sensitivities)
    original_ids = frozenset(sensitivity_by_id)
    groups: dict[GirrDeltaFactorKey, list[WeightedSensitivity]] = {}
    for weighted in weighted_sensitivities:
        _require_girr_delta_weighted(weighted)
        sensitivity = sensitivity_by_id.get(weighted.sensitivity_id)
        if sensitivity is None:
            raise SbmInputError(
                "weighted sensitivity has no matching source sensitivity",
                field="weighted_sensitivities",
            )
        key = GirrDeltaFactorKey(
            bucket=weighted.bucket,
            risk_factor=sensitivity.risk_factor,
            tenor=sensitivity.tenor or "",
        )
        groups.setdefault(key, []).append(weighted)

    netted: list[WeightedSensitivity] = []
    tenor_by_id: dict[str, str] = {}
    risk_factor_by_id: dict[str, str] = {}
    for key, members in sorted(groups.items()):
        source_sensitivities = tuple(sensitivity_by_id[item.sensitivity_id] for item in members)
        netted_weighted = (
            members[0]
            if len(members) == 1
            else _net_weighted_group(key, members, source_sensitivities, original_ids)
        )
        netted.append(netted_weighted)
        tenor_by_id[netted_weighted.sensitivity_id] = key.tenor
        risk_factor_by_id[netted_weighted.sensitivity_id] = key.risk_factor

    return GirrDeltaNettedFactorGrid(
        weighted_sensitivities=tuple(netted),
        tenor_by_id=MappingProxyType(tenor_by_id),
        risk_factor_by_id=MappingProxyType(risk_factor_by_id),
        raw_row_count=len(weighted_sensitivities),
        factor_count=len(netted),
    )


def _sensitivity_by_id(
    sensitivities: Sequence[SbmSensitivity],
) -> dict[str, SbmSensitivity]:
    by_id: dict[str, SbmSensitivity] = {}
    for sensitivity in sensitivities:
        if sensitivity.sensitivity_id in by_id:
            raise SbmInputError(
                "sensitivity_id values must be unique before factor-grid netting",
                field="sensitivity_id",
            )
        if sensitivity.risk_class is not SbmRiskClass.GIRR:
            raise SbmInputError(
                "GIRR delta factor-grid netting only accepts GIRR sensitivities",
                field="risk_class",
            )
        if sensitivity.risk_measure is not SbmRiskMeasure.DELTA:
            raise SbmInputError(
                "GIRR delta factor-grid netting only accepts delta sensitivities",
                field="risk_measure",
            )
        by_id[sensitivity.sensitivity_id] = sensitivity
    return by_id


def _require_girr_delta_weighted(weighted: WeightedSensitivity) -> None:
    if weighted.risk_class is not SbmRiskClass.GIRR:
        raise SbmInputError(
            "GIRR delta factor-grid netting only accepts GIRR weighted sensitivities",
            field="risk_class",
        )
    if weighted.risk_measure is not SbmRiskMeasure.DELTA:
        raise SbmInputError(
            "GIRR delta factor-grid netting only accepts delta weighted sensitivities",
            field="risk_measure",
        )


def _net_weighted_group(
    key: GirrDeltaFactorKey,
    members: Sequence[WeightedSensitivity],
    source_sensitivities: Sequence[SbmSensitivity],
    original_ids: frozenset[str],
) -> WeightedSensitivity:
    first = members[0]
    _validate_group_has_consistent_weighting(key, members)
    sensitivity_id = _netted_factor_id(key, original_ids)
    return WeightedSensitivity(
        sensitivity_id=sensitivity_id,
        risk_class=SbmRiskClass.GIRR,
        risk_measure=SbmRiskMeasure.DELTA,
        bucket=key.bucket,
        raw_amount=math.fsum(item.raw_amount for item in members),
        risk_weight=first.risk_weight,
        scaled_amount=math.fsum(item.scaled_amount for item in members),
        citation_ids=_merge_citation_ids(item.citation_ids for item in members),
        qualifier=key.tenor,
        factor_key=key.as_tuple(),
        contributing_sensitivity_ids=tuple(item.sensitivity_id for item in members),
        contributing_source_row_ids=tuple(item.source_row_id for item in source_sensitivities),
    )


def _validate_group_has_consistent_weighting(
    key: GirrDeltaFactorKey,
    members: Sequence[WeightedSensitivity],
) -> None:
    first = members[0]
    for item in members[1:]:
        if item.risk_weight != first.risk_weight:
            raise SbmInputError(
                "duplicate GIRR delta factor rows must share one risk weight",
                field=f"risk_weight[{key.as_tuple()}]",
            )
        if item.citation_ids != first.citation_ids:
            raise SbmInputError(
                "duplicate GIRR delta factor rows must share citation ids",
                field=f"citation_ids[{key.as_tuple()}]",
            )


def _netted_factor_id(key: GirrDeltaFactorKey, original_ids: frozenset[str]) -> str:
    factor_id = f"girr_delta_factor::{key.bucket}::{key.risk_factor}::{key.tenor}"
    if factor_id in original_ids:
        raise SbmInputError(
            "synthetic GIRR delta factor id collides with an input sensitivity id",
            field="sensitivity_id",
        )
    return factor_id


def _merge_citation_ids(citation_groups: Iterable[tuple[str, ...]]) -> tuple[str, ...]:
    merged: list[str] = []
    seen: set[str] = set()
    for citation_ids in citation_groups:
        for citation_id in citation_ids:
            if citation_id not in seen:
                merged.append(citation_id)
                seen.add(citation_id)
    return tuple(merged)


__all__ = [
    "GirrDeltaFactorKey",
    "GirrDeltaNettedFactorGrid",
    "net_girr_delta_weighted_sensitivities",
]
