"""Risk-factor evidence mart fixtures for result-store integration tests.

This module provides synthetic RFET/NMRF/SES risk-factor evidence data
covering modellable, non-modellable, stale/missing, and no-data/unsupported
states for Capital Navigator testing.
"""

from __future__ import annotations

from datetime import date

from frtb_result_store._model_risk_factor_evidence import (
    ModellabilityState,
    NMRFSESBridge,
    RFETObservationEvidence,
    RfetStaleState,
    RiskFactorEvidenceRow,
    RiskFactorHierarchyUsage,
    SesComponent,
)

# Synthetic risk factor IDs
_RF_MODELLABLE_USD_5Y = "rf-girr-usd-5y"
_RF_MODELLABLE_USD_10Y = "rf-girr-usd-10y"
_RF_NMRF_TYPE_A_IR = "rf-csr-ig-hy-spread"
_RF_NMRF_TYPE_B_EQUITY = "rf-equity-index-xxx"
_RF_STALE_MISSING = "rf-girr-eur-2y-stale"
_RF_UNSUPPORTED = "rf-commodity-crude-unsupported"

# Run ID for evidence fixtures
_EVIDENCE_RUN_ID = "frtb/risk-factor-evidence/2026-07-01/test"


def _modellable_usd_5y() -> RiskFactorEvidenceRow:
    """Modellable USD 5Y swap rate factor with full RFET evidence."""
    return RiskFactorEvidenceRow(
        run_id=_EVIDENCE_RUN_ID,
        risk_factor_id=_RF_MODELLABLE_USD_5Y,
        display_name="USD 5Y Swap Rate",
        risk_class="GIRR",
        risk_factor_type="CURVE",
        rfet_observation_evidence=RFETObservationEvidence(
            observation_count=252,
            latest_observation_date=date(2026, 6, 30),
            gap_days=0,
            stale_state=RfetStaleState.CURRENT,
            rejected_observation_count=0,
            artifact_id="navigator-rfet-observation-timeline",
        ),
        modellability_state=ModellabilityState.MODELLABLE,
        nmrf_ses_bridge=None,
        hierarchy_usage=RiskFactorHierarchyUsage(
            risk_factor_id=_RF_MODELLABLE_USD_5Y,
            book_id="rates-trading",
            desk_id="rates",
            volcker_desk_id=None,
            business_line_id="ficc",
            legal_entity_id="le-demo",
            usage_count=42,
        ),
        rfet_artifact_id="navigator-rfet-observation-timeline",
        source_artifact_id="navigator-girr-sensitivities",
    )


def _modellable_usd_10y() -> RiskFactorEvidenceRow:
    """Modellable USD 10Y swap rate factor with minimal evidence."""
    return RiskFactorEvidenceRow(
        run_id=_EVIDENCE_RUN_ID,
        risk_factor_id=_RF_MODELLABLE_USD_10Y,
        display_name="USD 10Y Swap Rate",
        risk_class="GIRR",
        risk_factor_type="CURVE",
        rfet_observation_evidence=RFETObservationEvidence(
            observation_count=252,
            latest_observation_date=date(2026, 6, 30),
            gap_days=0,
            stale_state=RfetStaleState.CURRENT,
            rejected_observation_count=None,
            artifact_id="navigator-rfet-observation-timeline",
        ),
        modellability_state=ModellabilityState.MODELLABLE,
        nmrf_ses_bridge=None,
        hierarchy_usage=RiskFactorHierarchyUsage(
            risk_factor_id=_RF_MODELLABLE_USD_10Y,
            book_id="rates-options",
            desk_id="rates",
            volcker_desk_id=None,
            business_line_id="ficc",
            legal_entity_id="le-demo",
            usage_count=15,
        ),
        rfet_artifact_id="navigator-rfet-observation-timeline",
        source_artifact_id="navigator-girr-sensitivities",
    )


def _nmrf_type_a_ir() -> RiskFactorEvidenceRow:
    """Non-modellable Type A NMRF/SES-driving credit spread factor."""
    return RiskFactorEvidenceRow(
        run_id=_EVIDENCE_RUN_ID,
        risk_factor_id=_RF_NMRF_TYPE_A_IR,
        display_name="IG/HY Spread Factor",
        risk_class="CSR_NON_SECURITISATION",
        risk_factor_type="SPREAD_CURVE",
        rfet_observation_evidence=RFETObservationEvidence(
            observation_count=180,
            latest_observation_date=date(2026, 6, 15),
            gap_days=15,
            stale_state=RfetStaleState.STALE,
            rejected_observation_count=3,
            artifact_id="navigator-rfet-csr-observations",
        ),
        modellability_state=ModellabilityState.NON_MODELLABLE,
        nmrf_ses_bridge=NMRFSESBridge(
            risk_factor_id=_RF_NMRF_TYPE_A_IR,
            ses_component=SesComponent.TYPE_A,
            ses_amount=12500.00,
            ses_movement=500.00,
            stress_period_id="stress-period-250d",
            liquidity_horizon_days=10,
            aggregation_bucket="csr-ig-hy",
            capital_node_id="ima-desk-credit",
        ),
        hierarchy_usage=RiskFactorHierarchyUsage(
            risk_factor_id=_RF_NMRF_TYPE_A_IR,
            book_id="credit-trading",
            desk_id="credit",
            volcker_desk_id=None,
            business_line_id="ficc",
            legal_entity_id="le-demo",
            usage_count=28,
        ),
        rfet_artifact_id="navigator-rfet-csr-observations",
        source_artifact_id="navigator-csr-sensitivities",
    )


def _nmrf_type_b_equity() -> RiskFactorEvidenceRow:
    """Non-modellable Type B NMRF/SES-driving equity index factor."""
    return RiskFactorEvidenceRow(
        run_id=_EVIDENCE_RUN_ID,
        risk_factor_id=_RF_NMRF_TYPE_B_EQUITY,
        display_name="Emerging Market Equity Index",
        risk_class="EQUITY",
        risk_factor_type="INDEX",
        rfet_observation_evidence=RFETObservationEvidence(
            observation_count=0,
            latest_observation_date=None,
            gap_days=None,
            stale_state=RfetStaleState.MISSING_EVIDENCE,
            rejected_observation_count=None,
            artifact_id=None,
        ),
        modellability_state=ModellabilityState.NON_MODELLABLE,
        nmrf_ses_bridge=NMRFSESBridge(
            risk_factor_id=_RF_NMRF_TYPE_B_EQUITY,
            ses_component=SesComponent.TYPE_B,
            ses_amount=8750.00,
            ses_movement=None,
            stress_period_id="stress-period-curved",
            liquidity_horizon_days=20,
            aggregation_bucket="equity-em",
            capital_node_id="ima-desk-equity",
        ),
        hierarchy_usage=RiskFactorHierarchyUsage(
            risk_factor_id=_RF_NMRF_TYPE_B_EQUITY,
            book_id="em-equity",
            desk_id="equity",
            volcker_desk_id=None,
            business_line_id="equities",
            legal_entity_id="le-demo",
            usage_count=12,
        ),
        rfet_artifact_id=None,
        source_artifact_id="navigator-equity-sensitivities",
    )


def _stale_eur_2y() -> RiskFactorEvidenceRow:
    """Stale EUR 2Y swap rate factor."""
    return RiskFactorEvidenceRow(
        run_id=_EVIDENCE_RUN_ID,
        risk_factor_id=_RF_STALE_MISSING,
        display_name="EUR 2Y Swap Rate (Stale)",
        risk_class="GIRR",
        risk_factor_type="CURVE",
        rfet_observation_evidence=RFETObservationEvidence(
            observation_count=120,
            latest_observation_date=date(2026, 5, 15),
            gap_days=46,
            stale_state=RfetStaleState.STALE,
            rejected_observation_count=None,
            artifact_id="navigator-rfet-eur-stale",
        ),
        modellability_state=ModellabilityState.STALE,
        nmrf_ses_bridge=None,
        hierarchy_usage=RiskFactorHierarchyUsage(
            risk_factor_id=_RF_STALE_MISSING,
            book_id="rates-europe",
            desk_id="rates",
            volcker_desk_id=None,
            business_line_id="ficc",
            legal_entity_id="le-demo",
            usage_count=8,
        ),
        rfet_artifact_id="navigator-rfet-eur-stale",
        source_artifact_id="navigator-girr-eur-sensitivities",
    )


def _unsupported_commodity() -> RiskFactorEvidenceRow:
    """No-data/unsupported commodity risk factor."""
    return RiskFactorEvidenceRow(
        run_id=_EVIDENCE_RUN_ID,
        risk_factor_id=_RF_UNSUPPORTED,
        display_name="Crude Oil Risk Factor (Unsupported)",
        risk_class="COMMODITY",
        risk_factor_type="SPOT",
        rfet_observation_evidence=RFETObservationEvidence(
            observation_count=0,
            latest_observation_date=None,
            gap_days=None,
            stale_state=RfetStaleState.NO_DATA,
            rejected_observation_count=None,
            artifact_id=None,
        ),
        modellability_state=ModellabilityState.UNSUPPORTED,
        nmrf_ses_bridge=None,
        hierarchy_usage=RiskFactorHierarchyUsage(
            risk_factor_id=_RF_UNSUPPORTED,
            book_id="commodities",
            desk_id="commodities",
            volcker_desk_id=None,
            business_line_id="commodities",
            legal_entity_id="le-demo",
            usage_count=3,
        ),
        rfet_artifact_id=None,
        source_artifact_id=None,
    )


def risk_factor_evidence_rows() -> tuple[RiskFactorEvidenceRow, ...]:
    """Build synthetic RFET/NMRF/SES evidence rows for testing.

    Returns
    -------
    tuple[RiskFactorEvidenceRow, ...]
        Evidence rows covering:
        - One modellable factor with full RFET evidence
        - One modellable factor with minimal evidence
        - One non-modellable Type A NMRF/SES-driving factor
        - One non-modellable Type B NMRF/SES-driving factor
        - One stale/missing-evidence factor
        - One no-data/unsupported state factor
    """
    return (
        _modellable_usd_5y(),
        _modellable_usd_10y(),
        _nmrf_type_a_ir(),
        _nmrf_type_b_equity(),
        _stale_eur_2y(),
        _unsupported_commodity(),
    )


def nmrf_ses_bridge_rows() -> tuple[NMRFSESBridge, ...]:
    """Build NMRF/SES bridge rows for testing.

    Returns
    -------
    tuple[NMRFSESBridge, ...]
        SES bridge rows for Type A and Type B factors.
    """
    return (
        NMRFSESBridge(
            risk_factor_id=_RF_NMRF_TYPE_A_IR,
            ses_component=SesComponent.TYPE_A,
            ses_amount=12500.00,
            ses_movement=500.00,
            stress_period_id="stress-period-250d",
            liquidity_horizon_days=10,
            aggregation_bucket="csr-ig-hy",
            capital_node_id="ima-desk-credit",
        ),
        NMRFSESBridge(
            risk_factor_id=_RF_NMRF_TYPE_B_EQUITY,
            ses_component=SesComponent.TYPE_B,
            ses_amount=8750.00,
            ses_movement=None,
            stress_period_id="stress-period-curved",
            liquidity_horizon_days=20,
            aggregation_bucket="equity-em",
            capital_node_id="ima-desk-equity",
        ),
    )


def rfet_observation_evidence_rows() -> tuple[RFETObservationEvidence, ...]:
    """Build RFET observation evidence rows for testing.

    Returns
    -------
    tuple[RFETObservationEvidence, ...]
        Observation evidence rows covering various staleness states.
    """
    return (
        RFETObservationEvidence(
            observation_count=252,
            latest_observation_date=date(2026, 6, 30),
            gap_days=0,
            stale_state=RfetStaleState.CURRENT,
            rejected_observation_count=0,
            artifact_id="navigator-rfet-observation-timeline",
        ),
        RFETObservationEvidence(
            observation_count=180,
            latest_observation_date=date(2026, 6, 15),
            gap_days=15,
            stale_state=RfetStaleState.STALE,
            rejected_observation_count=3,
            artifact_id="navigator-rfet-csr-observations",
        ),
        RFETObservationEvidence(
            observation_count=0,
            latest_observation_date=None,
            gap_days=None,
            stale_state=RfetStaleState.MISSING_EVIDENCE,
            rejected_observation_count=None,
            artifact_id=None,
        ),
        RFETObservationEvidence(
            observation_count=120,
            latest_observation_date=date(2026, 5, 15),
            gap_days=46,
            stale_state=RfetStaleState.STALE,
            rejected_observation_count=None,
            artifact_id="navigator-rfet-eur-stale",
        ),
        RFETObservationEvidence(
            observation_count=0,
            latest_observation_date=None,
            gap_days=None,
            stale_state=RfetStaleState.NO_DATA,
            rejected_observation_count=None,
            artifact_id=None,
        ),
    )


__all__ = [
    "nmrf_ses_bridge_rows",
    "rfet_observation_evidence_rows",
    "risk_factor_evidence_rows",
]
