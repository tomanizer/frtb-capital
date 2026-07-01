"""Risk-factor evidence mart row serialization helpers for result-store tables."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date

from frtb_result_store._model_risk_factor_evidence import (
    ModellabilityState,
    NMRFSESBridge,
    RFETObservationEvidence,
    RfetStaleState,
    RiskFactorEvidenceRow,
    RiskFactorHierarchyUsage,
)
from frtb_result_store._row_codecs import (
    json_mapping as _json_mapping,
)
from frtb_result_store._row_codecs import (
    metadata_json as _metadata_json,
)
from frtb_result_store._row_codecs import (
    optional_text as _optional_text,
)
from frtb_result_store._row_codecs import (
    stored_value as _stored_value,
)

__all__ = [
    "_nmrf_ses_bridge_from_row",
    "_nmrf_ses_bridge_row",
    "_rfet_observation_evidence_from_row",
    "_rfet_observation_evidence_row",
    "_risk_factor_evidence_mart_from_row",
    "_risk_factor_evidence_mart_row",
    "_risk_factor_hierarchy_usage_from_row",
    "_risk_factor_hierarchy_usage_row",
]


def _rfet_observation_evidence_row(evidence: RFETObservationEvidence) -> dict[str, object]:
    """Serialize RFET observation evidence to a row dict."""
    return {
        "observation_count": evidence.observation_count,
        "latest_observation_date": None
        if evidence.latest_observation_date is None
        else evidence.latest_observation_date.isoformat(),
        "gap_days": evidence.gap_days,
        "stale_state": _stored_value(evidence.stale_state),
        "rejected_observation_count": evidence.rejected_observation_count,
        "artifact_id": evidence.artifact_id,
    }


def _risk_factor_hierarchy_usage_row(usage: RiskFactorHierarchyUsage) -> dict[str, object]:
    """Serialize risk factor hierarchy usage to a row dict."""
    return {
        "risk_factor_id": str(usage.risk_factor_id),
        "book_id": usage.book_id,
        "desk_id": usage.desk_id,
        "volcker_desk_id": usage.volcker_desk_id,
        "business_line_id": usage.business_line_id,
        "legal_entity_id": usage.legal_entity_id,
        "usage_count": usage.usage_count,
    }


def _nmrf_ses_bridge_row(bridge: NMRFSESBridge) -> dict[str, object]:
    """Serialize NMRF/SES bridge to a row dict."""
    return {
        "risk_factor_id": str(bridge.risk_factor_id),
        "ses_component": (
            None if bridge.ses_component is None else _stored_value(bridge.ses_component)
        ),
        "ses_amount": bridge.ses_amount,
        "ses_movement": bridge.ses_movement,
        "stress_period_id": bridge.stress_period_id,
        "liquidity_horizon_days": bridge.liquidity_horizon_days,
        "aggregation_bucket": bridge.aggregation_bucket,
        "capital_node_id": bridge.capital_node_id,
    }


def _risk_factor_evidence_mart_row(row: RiskFactorEvidenceRow) -> dict[str, object]:
    """Serialize a complete risk factor evidence mart row."""
    evidence_row = _rfet_observation_evidence_row(row.rfet_observation_evidence)
    bridge_row = None if row.nmrf_ses_bridge is None else _nmrf_ses_bridge_row(row.nmrf_ses_bridge)
    usage_row = (
        None
        if row.hierarchy_usage is None
        else _risk_factor_hierarchy_usage_row(row.hierarchy_usage)
    )

    return {
        "run_id": row.run_id,
        "risk_factor_id": str(row.risk_factor_id),
        "display_name": row.display_name,
        "risk_class": row.risk_class,
        "risk_factor_type": row.risk_factor_type,
        "observation_count": evidence_row["observation_count"],
        "latest_observation_date": evidence_row["latest_observation_date"],
        "gap_days": evidence_row["gap_days"],
        "stale_state": evidence_row["stale_state"],
        "rejected_observation_count": evidence_row["rejected_observation_count"],
        "rfet_artifact_id": evidence_row["artifact_id"],
        "modellability_state": _stored_value(row.modellability_state),
        "ses_component": None if bridge_row is None else bridge_row["ses_component"],
        "ses_amount": None if bridge_row is None else bridge_row["ses_amount"],
        "ses_movement": None if bridge_row is None else bridge_row["ses_movement"],
        "stress_period_id": None if bridge_row is None else bridge_row["stress_period_id"],
        "liquidity_horizon_days": (
            None if bridge_row is None else bridge_row["liquidity_horizon_days"]
        ),
        "aggregation_bucket": None if bridge_row is None else bridge_row["aggregation_bucket"],
        "capital_node_id": None if bridge_row is None else bridge_row["capital_node_id"],
        "book_id": None if usage_row is None else usage_row["book_id"],
        "desk_id": None if usage_row is None else usage_row["desk_id"],
        "volcker_desk_id": None if usage_row is None else usage_row["volcker_desk_id"],
        "business_line_id": None if usage_row is None else usage_row["business_line_id"],
        "legal_entity_id": None if usage_row is None else usage_row["legal_entity_id"],
        "usage_count": None if usage_row is None else usage_row["usage_count"],
        "source_artifact_id": row.source_artifact_id,
        "metadata_json": _metadata_json(row.metadata),
    }


def _rfet_observation_evidence_from_row(row: Sequence[object]) -> RFETObservationEvidence:
    """Deserialize RFET observation evidence from a row sequence."""
    latest_date = None if row[1] is None else date.fromisoformat(str(row[1]))
    return RFETObservationEvidence(
        observation_count=int(row[0]),
        latest_observation_date=latest_date,
        gap_days=None if row[2] is None else int(row[2]),
        stale_state=RfetStaleState(str(row[3])),
        rejected_observation_count=None if row[4] is None else int(row[4]),
        artifact_id=_optional_text(row[5]),
    )


def _risk_factor_hierarchy_usage_from_row(row: Sequence[object]) -> RiskFactorHierarchyUsage:
    """Deserialize risk factor hierarchy usage from a row sequence."""
    return RiskFactorHierarchyUsage(
        risk_factor_id=str(row[0]),
        book_id=_optional_text(row[1]),
        desk_id=_optional_text(row[2]),
        volcker_desk_id=_optional_text(row[3]),
        business_line_id=_optional_text(row[4]),
        legal_entity_id=_optional_text(row[5]),
        usage_count=int(row[6]),
    )


def _nmrf_ses_bridge_from_row(row: Sequence[object]) -> NMRFSESBridge:
    """Deserialize NMRF/SES bridge from a row sequence."""
    return NMRFSESBridge(
        risk_factor_id=str(row[0]),
        ses_component=_optional_text(row[1]),
        ses_amount=None if row[2] is None else float(row[2]),
        ses_movement=None if row[3] is None else float(row[3]),
        stress_period_id=_optional_text(row[4]),
        liquidity_horizon_days=None if row[5] is None else int(row[5]),
        aggregation_bucket=_optional_text(row[6]),
        capital_node_id=_optional_text(row[7]),
    )


def _risk_factor_evidence_mart_from_row(row: Sequence[object]) -> RiskFactorEvidenceRow:
    """Deserialize a complete risk factor evidence mart row from a row sequence."""
    rfet_evidence = RFETObservationEvidence(
        observation_count=int(row[6]),
        latest_observation_date=None if row[7] is None else date.fromisoformat(str(row[7])),
        gap_days=None if row[8] is None else int(row[8]),
        stale_state=RfetStaleState(str(row[9])),
        rejected_observation_count=None if row[10] is None else int(row[10]),
        artifact_id=None if row[11] is None else str(row[11]),
    )

    nmrf_bridge = None
    bridge_offset = 12
    if row[bridge_offset] is not None:
        nmrf_bridge = NMRFSESBridge(
            risk_factor_id=str(row[0]),
            ses_component=_optional_text(row[bridge_offset]),
            ses_amount=None if row[bridge_offset + 1] is None else float(row[bridge_offset + 1]),
            ses_movement=None if row[bridge_offset + 2] is None else float(row[bridge_offset + 2]),
            stress_period_id=_optional_text(row[bridge_offset + 3]),
            liquidity_horizon_days=None
            if row[bridge_offset + 4] is None
            else int(row[bridge_offset + 4]),
            aggregation_bucket=_optional_text(row[bridge_offset + 5]),
            capital_node_id=_optional_text(row[bridge_offset + 6]),
        )

    usage_offset = bridge_offset + 7
    hierarchy_usage = None
    if row[usage_offset] is not None:
        hierarchy_usage = RiskFactorHierarchyUsage(
            risk_factor_id=str(row[0]),
            book_id=_optional_text(row[usage_offset]),
            desk_id=_optional_text(row[usage_offset + 1]),
            volcker_desk_id=_optional_text(row[usage_offset + 2]),
            business_line_id=_optional_text(row[usage_offset + 3]),
            legal_entity_id=_optional_text(row[usage_offset + 4]),
            usage_count=int(row[usage_offset + 5]),
        )

    source_offset = usage_offset + 6
    return RiskFactorEvidenceRow(
        run_id=str(row[0]),
        risk_factor_id=str(row[1]),
        display_name=str(row[2]),
        risk_class=str(row[3]),
        risk_factor_type=str(row[4]),
        rfet_observation_evidence=rfet_evidence,
        modellability_state=ModellabilityState(str(row[5])),
        nmrf_ses_bridge=nmrf_bridge,
        hierarchy_usage=hierarchy_usage,
        rfet_artifact_id=None if row[11] is None else str(row[11]),
        source_artifact_id=_optional_text(row[source_offset]),
        metadata=_json_mapping(row[source_offset + 1]),
    )
