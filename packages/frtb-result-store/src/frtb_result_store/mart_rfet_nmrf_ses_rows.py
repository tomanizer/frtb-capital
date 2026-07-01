"""RFET/NMRF/SES risk-factor evidence mart row builders for result-store bundles."""

from __future__ import annotations

from frtb_result_store._model_attribution import CapitalAttributionRecord
from frtb_result_store._model_risk_factor_evidence import (
    ModellabilityState,
    NMRFSESBridge,
    RFETObservationEvidence,
    RfetStaleState,
    RiskFactorEvidenceRow,
    RiskFactorHierarchyUsage,
    SesComponent,
)
from frtb_result_store._model_risk_factor_metadata import RiskFactorMetadataRecord
from frtb_result_store.model import ResultBundle
from frtb_result_store.risk_factor_evidence_rows import (
    _risk_factor_evidence_mart_row,
)

__all__ = [
    "_rfet_nmrf_ses_evidence_mart_rows",
]


def _rfet_nmrf_ses_evidence_mart_rows(bundle: ResultBundle) -> list[dict[str, object]]:
    """Build RFET/NMRF/SES evidence mart rows from a result bundle.

    This function aggregates risk factor metadata, RFET observation evidence,
    NMRF/SES capital linkage, and hierarchy usage into denormalized mart rows
    for Navigator consumption.

    Parameters
    ----------
    bundle : ResultBundle
        Committed result bundle with risk factor metadata, attribution,
        and hierarchy data.

    Returns
    -------
    list[dict[str, object]]
        Mart rows suitable for writing to the rfet_nmrf_ses_evidence table.
    """
    rows: list[dict[str, object]] = []

    # Build lookup maps
    metadata_by_risk_factor = {
        str(record.risk_factor_id): record for record in bundle.risk_factor_metadata
    }

    # Build hierarchy usage from attribution where source_level is RISK_FACTOR
    hierarchy_usage_by_risk_factor = _build_hierarchy_usage(bundle)

    # Build NMRF/SES bridge from attribution where category is NMRF_SES
    ses_bridge_by_risk_factor = _build_ses_bridge(bundle)

    for risk_factor_id, metadata in sorted(
        metadata_by_risk_factor.items(),
        key=lambda item: (
            item[1].risk_class,
            str(item[0]),
        ),
    ):
        # Build RFET observation evidence from metadata
        rfet_evidence = _build_rfet_observation_evidence(metadata)

        # Determine modellability state from metadata
        modellability_state = _determine_modellability_state(metadata)

        # Build the complete evidence row
        evidence_row = RiskFactorEvidenceRow(
            run_id=bundle.run.run_id,
            risk_factor_id=risk_factor_id,
            display_name=metadata.display_name,
            risk_class=str(metadata.risk_class),
            risk_factor_type=str(metadata.risk_factor_type),
            rfet_observation_evidence=rfet_evidence,
            modellability_state=modellability_state,
            nmrf_ses_bridge=ses_bridge_by_risk_factor.get(risk_factor_id),
            hierarchy_usage=hierarchy_usage_by_risk_factor.get(risk_factor_id),
            rfet_artifact_id=(
                None if metadata.rfet_evidence_id is None else str(metadata.rfet_evidence_id)
            ),
            source_artifact_id=None
            if metadata.source_row_id is None
            else str(metadata.source_row_id),
        )
        rows.append(_risk_factor_evidence_mart_row(evidence_row))

    return rows


def _build_rfet_observation_evidence(
    metadata: RiskFactorMetadataRecord,
) -> RFETObservationEvidence:
    """Build RFET observation evidence from risk factor metadata.

    This extracts observation counts, gap information, and staleness state
    from the risk factor metadata record.
    """
    # Default evidence when no detailed RFET data is available
    return RFETObservationEvidence(
        observation_count=0,
        latest_observation_date=None,
        gap_days=None,
        stale_state=_rfet_stale_state_from_metadata(metadata),
        rejected_observation_count=None,
        artifact_id=None if metadata.rfet_evidence_id is None else str(metadata.rfet_evidence_id),
    )


def _rfet_stale_state_from_metadata(metadata: RiskFactorMetadataRecord) -> RfetStaleState:
    """Determine RFET staleness state from risk factor metadata."""
    if metadata.rfet_evidence_state == "no_data":
        return RfetStaleState.NO_DATA
    if metadata.modellability_state == "unsupported":
        return RfetStaleState.NO_DATA
    # Default to current for modellable factors
    if metadata.modellability_state == "available":
        return RfetStaleState.CURRENT
    # For now, default to current - real implementation would check observation dates
    return RfetStaleState.CURRENT


def _determine_modellability_state(metadata: RiskFactorMetadataRecord) -> ModellabilityState:
    """Determine extended modellability state from risk factor metadata."""
    # Map existing evidence states to extended modellability states
    mod_state = str(metadata.modellability_state)

    if mod_state == "available":
        return ModellabilityState.MODELLABLE
    if mod_state == "no_data":
        return ModellabilityState.UNSUPPORTED
    if mod_state == "unsupported":
        return ModellabilityState.UNSUPPORTED

    # For now, default to non_modellable for other states
    return ModellabilityState.NON_MODELLABLE


def _build_hierarchy_usage(bundle: ResultBundle) -> dict[str, RiskFactorHierarchyUsage]:
    """Build hierarchy usage mapping from attribution records.

    This extracts book, desk, and business lineage from attribution records
    where source_level is RISK_FACTOR.
    """
    usage_counts: dict[str, int] = {}
    first_attribution_by_risk_factor: dict[str, CapitalAttributionRecord] = {}

    for attribution in bundle.attributions:
        if attribution.source_level != "RISK_FACTOR":
            continue

        risk_factor_id = str(attribution.source_id)
        usage_counts[risk_factor_id] = usage_counts.get(risk_factor_id, 0) + 1
        first_attribution_by_risk_factor.setdefault(risk_factor_id, attribution)

    return {
        risk_factor_id: RiskFactorHierarchyUsage(
            risk_factor_id=risk_factor_id,
            book_id=getattr(attribution, "book_id", None),
            desk_id=getattr(attribution, "desk_id", None),
            volcker_desk_id=None,
            business_line_id=None,
            legal_entity_id=None,
            usage_count=usage_counts[risk_factor_id],
        )
        for risk_factor_id, attribution in first_attribution_by_risk_factor.items()
    }


def _build_ses_bridge(bundle: ResultBundle) -> dict[str, NMRFSESBridge]:
    """Build NMRF/SES capital bridge from attribution records.

    This extracts SES component, amount, and linkage data from attribution
    records where category is NMRF or SES-related.
    """
    bridge_by_risk_factor: dict[str, NMRFSESBridge] = {}

    for attribution in bundle.attributions:
        # Skip attribution not related to NMRF/SES
        if attribution.category != "NMRF_SES" and "NMRF" not in (attribution.category or ""):
            continue

        risk_factor_id = str(attribution.source_id)
        ses_component = _infer_ses_component(attribution)

        existing = bridge_by_risk_factor.get(risk_factor_id)
        bridge_by_risk_factor[risk_factor_id] = _merge_ses_bridge(
            existing,
            risk_factor_id=risk_factor_id,
            ses_component=ses_component,
            ses_amount=attribution.contribution,
            aggregation_bucket=attribution.bucket_key,
            capital_node_id=attribution.node_id,
        )

    return bridge_by_risk_factor


def _merge_ses_bridge(
    existing: NMRFSESBridge | None,
    *,
    risk_factor_id: str,
    ses_component: SesComponent | None,
    ses_amount: float | None,
    aggregation_bucket: str | None,
    capital_node_id: str | None,
) -> NMRFSESBridge:
    """Merge one attribution contribution into an NMRF/SES bridge row."""
    if existing is None:
        return NMRFSESBridge(
            risk_factor_id=risk_factor_id,
            ses_component=ses_component,
            ses_amount=ses_amount,
            ses_movement=None,
            stress_period_id=None,
            liquidity_horizon_days=None,
            aggregation_bucket=aggregation_bucket,
            capital_node_id=capital_node_id,
        )

    return NMRFSESBridge(
        risk_factor_id=risk_factor_id,
        ses_component=existing.ses_component or ses_component,
        ses_amount=_sum_optional(existing.ses_amount, ses_amount),
        ses_movement=None,  # Movement requires baseline comparison.
        stress_period_id=existing.stress_period_id,
        liquidity_horizon_days=existing.liquidity_horizon_days,
        aggregation_bucket=existing.aggregation_bucket or aggregation_bucket,
        capital_node_id=existing.capital_node_id or capital_node_id,
    )


def _sum_optional(first: float | None, second: float | None) -> float | None:
    """Sum optional contribution values while preserving all-null as absent."""
    if first is None and second is None:
        return None
    return (first or 0.0) + (second or 0.0)


def _infer_ses_component(attribution: CapitalAttributionRecord) -> SesComponent | None:
    """Infer SES component type from attribution metadata."""
    category = attribution.category or ""
    if "TYPE_A" in category:
        return SesComponent.TYPE_A
    if "TYPE_B" in category:
        return SesComponent.TYPE_B
    return None
