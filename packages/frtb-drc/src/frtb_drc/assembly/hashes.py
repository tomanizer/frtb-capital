"""Deterministic hash assembly for DRC batch and context inputs."""

from __future__ import annotations

import math
from collections.abc import Mapping
from typing import TYPE_CHECKING, cast

from frtb_drc._batch_order import sorted_position_indices as _sorted_indices
from frtb_drc._hashing import hash_payload
from frtb_drc.data_models import DrcCalculationContext, DrcRiskClass
from frtb_drc.fair_value_cap import fair_value_cap_hash_payload
from frtb_drc.org_scope import scope_at, scope_payload
from frtb_drc.risk_weight_evidence import effective_risk_weights, risk_weight_evidence_hash_payload

if TYPE_CHECKING:
    from frtb_drc.batch import DrcPositionBatch

INPUT_HASH_ALGORITHM_ARROW_COLUMNAR_V2 = "arrow-columnar-v2"
INPUT_HASH_ALGORITHM_JSON_ROW_V1 = "json-row-v1"


def input_hash_for_drc_batch(batch: DrcPositionBatch) -> str:
    """Hash canonical DRC batch inputs in deterministic position-id order.

    Parameters
    ----------
    batch : DrcPositionBatch
        Columnar batch whose fields are serialised in sorted position order.

    Returns
    -------
    str
        Lowercase SHA-256 hex digest of the canonical payload.
    """

    payload = [_position_payload(batch, index) for index in _sorted_indices(batch)]
    return hash_payload(payload)


def context_input_hash_for_drc_batch(
    input_hash: str,
    batch: DrcPositionBatch,
    *,
    context: DrcCalculationContext,
    risk_class: DrcRiskClass,
) -> str:
    """Hash risk-class-specific context maps into a DRC batch input hash.

    Parameters
    ----------
    input_hash : str
        Deterministic hash of the canonical DRC position batch before run-scoped context maps.
    batch : DrcPositionBatch
        Columnar batch carrying the position ids to select context evidence.
    context : DrcCalculationContext
        Run context containing securitisation non-CTP or CTP evidence maps.
    risk_class : DrcRiskClass
        Risk class that determines which context maps enter the hash.

    Returns
    -------
    str
        Lowercase SHA-256 hex digest including applicable context maps.
    """

    if risk_class is DrcRiskClass.SECURITISATION_NON_CTP:
        return _hash_context_position_maps(
            input_hash,
            batch,
            risk_weights=effective_risk_weights(
                context,
                risk_class=DrcRiskClass.SECURITISATION_NON_CTP,
            ),
            offset_groups=context.securitisation_non_ctp_offset_groups,
            risk_weight_key="securitisation_non_ctp_risk_weights",
            risk_weight_evidence_key="securitisation_non_ctp_risk_weight_evidence",
            fair_value_cap_evidence_key="securitisation_non_ctp_fair_value_cap_evidence",
            offset_group_key="securitisation_non_ctp_offset_groups",
            context=context,
            risk_class=risk_class,
        )
    if risk_class is DrcRiskClass.CORRELATION_TRADING_PORTFOLIO:
        return _hash_context_position_maps(
            input_hash,
            batch,
            risk_weights=effective_risk_weights(
                context,
                risk_class=DrcRiskClass.CORRELATION_TRADING_PORTFOLIO,
            ),
            offset_groups=context.ctp_offset_groups,
            risk_weight_key="ctp_risk_weights",
            risk_weight_evidence_key="ctp_risk_weight_evidence",
            fair_value_cap_evidence_key="",
            offset_group_key="ctp_offset_groups",
            context=context,
            risk_class=risk_class,
        )
    return input_hash


def _hash_context_position_maps(
    input_hash: str,
    batch: DrcPositionBatch,
    *,
    risk_weights: Mapping[str, float],
    offset_groups: Mapping[str, str],
    risk_weight_key: str,
    risk_weight_evidence_key: str,
    fair_value_cap_evidence_key: str,
    offset_group_key: str,
    context: DrcCalculationContext,
    risk_class: DrcRiskClass,
) -> str:
    position_ids = tuple(sorted(cast(str, position_id) for position_id in batch.position_ids))
    payload = {
        "input_hash": input_hash,
        risk_weight_key: {position_id: risk_weights[position_id] for position_id in position_ids},
        risk_weight_evidence_key: risk_weight_evidence_hash_payload(
            position_ids,
            context,
            risk_class=risk_class,
        ),
        offset_group_key: {
            position_id: offset_groups[position_id]
            for position_id in position_ids
            if position_id in offset_groups
        },
    }
    if fair_value_cap_evidence_key:
        payload[fair_value_cap_evidence_key] = fair_value_cap_hash_payload(
            position_ids,
            context,
        )
    return hash_payload(payload)


def _position_payload(batch: DrcPositionBatch, index: int) -> dict[str, object]:
    lineage = None
    if bool(batch.lineage_present[index]):
        lineage = {
            "source_system": batch.lineage_source_systems[index],
            "source_file": batch.lineage_source_files[index],
            "source_row_id": batch.source_row_ids[index],
            "source_column_map": dict(batch.source_column_maps[index]),
        }
    payload: dict[str, object] = {
        "position_id": batch.position_ids[index],
        "source_row_id": batch.source_row_ids[index],
        "desk_id": batch.desk_ids[index],
        "legal_entity": batch.legal_entities[index],
        "risk_class": batch.risk_classes[index],
        "instrument_type": batch.instrument_types[index],
        "default_direction": batch.default_directions[index],
        "issuer_id": batch.issuer_ids[index],
        "tranche_id": batch.tranche_ids[index],
        "index_series_id": batch.index_series_ids[index],
        "bucket_key": batch.bucket_keys[index],
        "seniority": batch.seniorities[index],
        "credit_quality": batch.credit_qualities[index],
        "notional": float(batch.notionals[index]),
        "market_value": _optional_float_payload(batch.market_values[index]),
        "cumulative_pnl": _optional_float_payload(batch.cumulative_pnls[index]),
        "maturity_years": float(batch.maturity_years[index]),
        "currency": batch.currencies[index],
        "lgd_override": _optional_float_payload(batch.lgd_overrides[index]),
        "is_defaulted": bool(batch.is_defaulted[index]),
        "is_gse": bool(batch.is_gse[index]),
        "is_pse": bool(batch.is_pse[index]),
        "is_covered_bond": bool(batch.is_covered_bond[index]),
        "lineage": lineage,
        "citation_ids": list(batch.citation_ids[index]),
    }
    org_scope = scope_payload(scope_at(batch.org_scopes, index))
    if org_scope is not None:
        payload["org_scope"] = org_scope
    return payload


def _optional_float_payload(value: float) -> float | None:
    return None if math.isnan(float(value)) else float(value)


__all__ = [
    "INPUT_HASH_ALGORITHM_ARROW_COLUMNAR_V2",
    "INPUT_HASH_ALGORITHM_JSON_ROW_V1",
    "context_input_hash_for_drc_batch",
    "input_hash_for_drc_batch",
]
