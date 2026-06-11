"""Shared test-only helpers for DRC fixture JSON loaders."""

from __future__ import annotations

from datetime import date
from typing import Any

from frtb_drc import DrcFairValueCapEvidence, DrcRiskWeightEvidence, DrcSourceLineage
from frtb_drc.data_models import DrcPosition


def drc_position_from_dict(raw: dict[str, Any]) -> DrcPosition:
    lineage = raw["lineage"]
    return DrcPosition(
        position_id=raw["position_id"],
        source_row_id=raw["source_row_id"],
        desk_id=raw["desk_id"],
        legal_entity=raw["legal_entity"],
        risk_class=raw["risk_class"],
        instrument_type=raw["instrument_type"],
        default_direction=raw["default_direction"],
        issuer_id=raw.get("issuer_id"),
        tranche_id=raw.get("tranche_id"),
        index_series_id=raw.get("index_series_id"),
        bucket_key=raw["bucket_key"],
        seniority=raw.get("seniority"),
        credit_quality=raw.get("credit_quality"),
        notional=float(raw["notional"]),
        market_value=None if raw.get("market_value") is None else float(raw["market_value"]),
        cumulative_pnl=raw.get("cumulative_pnl"),
        maturity_years=float(raw["maturity_years"]),
        currency=raw["currency"],
        lineage=DrcSourceLineage(
            source_system=lineage["source_system"],
            source_file=lineage["source_file"],
            source_row_id=lineage["source_row_id"],
            source_column_map=dict(lineage.get("source_column_map") or {}),
        ),
        citation_ids=tuple(raw["citation_ids"]),
    )


def drc_risk_weight_evidence_from_dict(raw: dict[str, Any]) -> DrcRiskWeightEvidence:
    lineage = raw["lineage"]
    return DrcRiskWeightEvidence(
        position_id=raw["position_id"],
        risk_class=raw["risk_class"],
        source_profile_id=raw["source_profile_id"],
        source_table=raw["source_table"],
        source_method=raw["source_method"],
        effective_risk_weight=float(raw["effective_risk_weight"]),
        as_of_date=date.fromisoformat(raw["as_of_date"]),
        source_id=raw["source_id"],
        lineage=DrcSourceLineage(
            source_system=lineage["source_system"],
            source_file=lineage["source_file"],
            source_row_id=lineage["source_row_id"],
            source_column_map=dict(lineage.get("source_column_map") or {}),
        ),
        citation_ids=tuple(raw["citation_ids"]),
        is_stale=bool(raw.get("is_stale", False)),
        validation_flags=tuple(raw.get("validation_flags", ())),
    )


def drc_fair_value_cap_evidence_from_dict(
    raw: dict[str, Any],
) -> DrcFairValueCapEvidence:
    lineage = raw["lineage"]
    return DrcFairValueCapEvidence(
        position_id=raw["position_id"],
        source_profile_id=raw["source_profile_id"],
        eligible=bool(raw["eligible"]),
        fair_value_cap_amount=(
            None
            if raw.get("fair_value_cap_amount") is None
            else float(raw["fair_value_cap_amount"])
        ),
        eligibility_reason=raw["eligibility_reason"],
        as_of_date=date.fromisoformat(raw["as_of_date"]),
        source_id=raw["source_id"],
        lineage=DrcSourceLineage(
            source_system=lineage["source_system"],
            source_file=lineage["source_file"],
            source_row_id=lineage["source_row_id"],
            source_column_map=dict(lineage.get("source_column_map") or {}),
        ),
        citation_ids=tuple(raw["citation_ids"]),
        is_stale=bool(raw.get("is_stale", False)),
        validation_flags=tuple(raw.get("validation_flags", ())),
    )
