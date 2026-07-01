"""Helpers shared by risk-factor evidence API routes.

These functions provide Navigator-ready payloads for RFET/NMRF/SES evidence,
following the pattern of api_metadata_helpers.py for consistency.
"""

from __future__ import annotations

from frtb_result_store._model_risk_factor_evidence import (
    NMRFSESBridge,
    RFETObservationEvidence,
    RiskFactorEvidenceRow,
    RiskFactorHierarchyUsage,
)
from frtb_result_store.io import DuckDbParquetResultStore


def risk_factor_evidence_payload(
    result_store: DuckDbParquetResultStore,
    run_id: str,
    *,
    risk_class: str | None = None,
    desk_id: str | None = None,
    book_id: str | None = None,
    modellability_state: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> dict[str, object]:
    """Build Navigator RFET/NMRF/SES evidence payload.

    Parameters
    ----------
    result_store : DuckDbParquetResultStore
        Store queried for risk-factor evidence.
    run_id : str
        Committed run identifier.
    risk_class : str | None, optional
        Optional risk-class filter.
    desk_id : str | None, optional
        Optional desk filter.
    book_id : str | None, optional
        Optional book filter.
    modellability_state : str | None, optional
        Optional modellability state filter.
    limit : int, optional
        Maximum page size, capped at 1000.
    offset : int, optional
        Zero-based page offset.

    Returns
    -------
    dict[str, object]
        JSON-ready payload containing evidence rows, paging metadata,
        and status summary.
    """
    page = result_store.list_risk_factor_evidence(
        run_id,
        risk_class=risk_class,
        desk_id=desk_id,
        book_id=book_id,
        modellability_state=modellability_state,
        limit=limit,
        offset=offset,
    )

    return {
        "state": page["state"],
        "items": [_evidence_row_to_jsonable(row) for row in page["items"]],
        "total_count": page["total_count"],
        "limit": page["limit"],
        "offset": page["offset"],
        "next_offset": page["next_offset"],
        "filters": {
            "risk_class": risk_class,
            "desk_id": desk_id,
            "book_id": book_id,
            "modellability_state": modellability_state,
        },
    }


def risk_factor_evidence_detail_payload(
    result_store: DuckDbParquetResultStore,
    run_id: str,
    risk_factor_id: str,
) -> dict[str, object]:
    """Build Navigator risk-factor evidence detail payload.

    Parameters
    ----------
    result_store : DuckDbParquetResultStore
        Store queried for risk-factor evidence.
    run_id : str
        Committed run identifier.
    risk_factor_id : str
        Stable risk-factor identifier.

    Returns
    -------
    dict[str, object]
        JSON-ready payload containing complete evidence for one risk factor,
        including RFET observation summary, NMRF/SES bridge, and hierarchy usage.
    """
    detail = result_store.get_risk_factor_evidence(run_id, risk_factor_id)

    if detail["state"] == "no_data":
        return {
            "state": "no_data",
            "risk_factor_id": risk_factor_id,
            "evidence": None,
            "rfet_observation_evidence": None,
            "nmrf_ses_bridge": None,
            "hierarchy_usage": None,
        }

    evidence = detail["evidence"]
    return {
        "state": "available",
        "risk_factor_id": risk_factor_id,
        "evidence": _evidence_row_to_jsonable(evidence),
        "rfet_observation_evidence": (
            _rfet_observation_evidence_to_jsonable(evidence.rfet_observation_evidence)
            if evidence.rfet_observation_evidence
            else None
        ),
        "nmrf_ses_bridge": (
            _nmrf_ses_bridge_to_jsonable(evidence.nmrf_ses_bridge)
            if evidence.nmrf_ses_bridge
            else None
        ),
        "hierarchy_usage": (
            _hierarchy_usage_to_jsonable(evidence.hierarchy_usage)
            if evidence.hierarchy_usage
            else None
        ),
    }


def risk_factor_evidence_summary(
    result_store: DuckDbParquetResultStore,
    run_id: str,
) -> dict[str, object]:
    """Build Navigator risk-factor evidence summary for one run.

    Parameters
    ----------
    result_store : DuckDbParquetResultStore
        Store queried for risk-factor evidence.
    run_id : str
        Committed run identifier.

    Returns
    -------
    dict[str, object]
        JSON-ready payload containing counts by modellability state,
        SES capital totals, and evidence completeness summary.
    """
    page = result_store.list_risk_factor_evidence(run_id, limit=1000)

    modellability_counts: dict[str, int] = {}
    ses_total = 0.0
    ses_type_a_count = 0
    ses_type_b_count = 0
    stale_evidence_count = 0

    for row in page["items"]:
        state = str(row.modellability_state)
        modellability_counts[state] = modellability_counts.get(state, 0) + 1

        if row.nmrf_ses_bridge:
            if row.nmrf_ses_bridge.ses_amount:
                ses_total += row.nmrf_ses_bridge.ses_amount
            if row.nmrf_ses_bridge.ses_component == "TYPE_A":
                ses_type_a_count += 1
            elif row.nmrf_ses_bridge.ses_component == "TYPE_B":
                ses_type_b_count += 1

        if row.rfet_observation_evidence:
            if row.rfet_observation_evidence.stale_state in ("stale", "missing_evidence"):
                stale_evidence_count += 1

    return {
        "state": page["state"],
        "total_count": page["total_count"],
        "modellability_counts": modellability_counts,
        "ses_summary": {
            "ses_total": ses_total if ses_total > 0 else None,
            "ses_type_a_count": ses_type_a_count if ses_type_a_count > 0 else None,
            "ses_type_b_count": ses_type_b_count if ses_type_b_count > 0 else None,
        },
        "evidence_completeness": {
            "stale_or_missing_count": stale_evidence_count if stale_evidence_count > 0 else None,
            "complete_count": page["total_count"] - stale_evidence_count,
        },
    }


def _evidence_row_to_jsonable(row: RiskFactorEvidenceRow) -> dict[str, object]:
    """Convert a risk-factor evidence row to a JSON-ready dict."""
    return {
        "run_id": row.run_id,
        "risk_factor_id": str(row.risk_factor_id),
        "display_name": row.display_name,
        "risk_class": row.risk_class,
        "risk_factor_type": row.risk_factor_type,
        "modellability_state": str(row.modellability_state),
        "rfet_observation_evidence": (
            _rfet_observation_evidence_to_jsonable(row.rfet_observation_evidence)
            if row.rfet_observation_evidence
            else None
        ),
        "nmrf_ses_bridge": (
            _nmrf_ses_bridge_to_jsonable(row.nmrf_ses_bridge) if row.nmrf_ses_bridge else None
        ),
        "hierarchy_usage": (
            _hierarchy_usage_to_jsonable(row.hierarchy_usage) if row.hierarchy_usage else None
        ),
        "rfet_artifact_id": row.rfet_artifact_id,
        "source_artifact_id": row.source_artifact_id,
    }


def _rfet_observation_evidence_to_jsonable(evidence: RFETObservationEvidence) -> dict[str, object]:
    """Convert RFET observation evidence to a JSON-ready dict."""
    return {
        "observation_count": evidence.observation_count,
        "latest_observation_date": (
            evidence.latest_observation_date.isoformat()
            if evidence.latest_observation_date
            else None
        ),
        "gap_days": evidence.gap_days,
        "stale_state": str(evidence.stale_state),
        "rejected_observation_count": evidence.rejected_observation_count,
        "artifact_id": evidence.artifact_id,
    }


def _nmrf_ses_bridge_to_jsonable(bridge: NMRFSESBridge) -> dict[str, object]:
    """Convert NMRF/SES bridge to a JSON-ready dict."""
    return {
        "risk_factor_id": str(bridge.risk_factor_id),
        "ses_component": str(bridge.ses_component) if bridge.ses_component else None,
        "ses_amount": bridge.ses_amount,
        "ses_movement": bridge.ses_movement,
        "stress_period_id": bridge.stress_period_id,
        "liquidity_horizon_days": bridge.liquidity_horizon_days,
        "aggregation_bucket": bridge.aggregation_bucket,
        "capital_node_id": bridge.capital_node_id,
    }


def _hierarchy_usage_to_jsonable(usage: RiskFactorHierarchyUsage) -> dict[str, object]:
    """Convert hierarchy usage to a JSON-ready dict."""
    return {
        "risk_factor_id": str(usage.risk_factor_id),
        "book_id": usage.book_id,
        "desk_id": usage.desk_id,
        "volcker_desk_id": usage.volcker_desk_id,
        "business_line_id": usage.business_line_id,
        "legal_entity_id": usage.legal_entity_id,
        "usage_count": usage.usage_count,
    }


__all__ = [
    "_evidence_row_to_jsonable",
    "_hierarchy_usage_to_jsonable",
    "_nmrf_ses_bridge_to_jsonable",
    "_rfet_observation_evidence_to_jsonable",
    "risk_factor_evidence_detail_payload",
    "risk_factor_evidence_payload",
    "risk_factor_evidence_summary",
]
