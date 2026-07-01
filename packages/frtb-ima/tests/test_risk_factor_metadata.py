"""Tests for IMA risk-factor metadata propagation helpers."""

from __future__ import annotations

from datetime import date

import pytest

from frtb_ima.data_models import (
    LiquidityHorizon,
    ModellabilityStatus,
    RealPriceObservation,
    RiskClass,
    RiskFactor,
)
from frtb_ima.nmrf import NMRFStressArtifact, NMRFStressMethod
from frtb_ima.risk_factor_metadata import (
    ImaRiskFactorEvidenceState,
    build_ima_risk_factor_evidence_rows,
)


def test_ima_risk_factor_evidence_rows_preserve_ids_and_evidence() -> None:
    risk_factor = RiskFactor(
        name="USD_SWAP_10Y",
        risk_class=RiskClass.GIRR,
        liquidity_horizon=LiquidityHorizon.LH20,
        risk_factor_id="rf:girr:usd-swap:10y",
        risk_factor_mapping_version="ima-map-v1",
        bucket="USD",
        source_row_id="rf-row-1",
    )
    observation = RealPriceObservation(
        risk_factor_name="USD_SWAP_10Y",
        observation_date=date(2025, 1, 2),
        data_pool_id="rfet-pool-1",
        vendor_audit_evidence_id="rfet-evidence-1",
        risk_factor_id="rf:girr:usd-swap:10y",
        risk_factor_mapping_version="ima-map-v1",
    )
    artifact = NMRFStressArtifact(
        risk_factor_name="USD_SWAP_10Y",
        method=NMRFStressMethod.DIRECT,
        losses=[1.0, 2.0, 3.0],
        liquidity_horizon=LiquidityHorizon.LH20,
        stress_period="stress-2008",
        source="upstream-valuation",
        artifact_id="nmrf-artifact-1",
        risk_factor_id="rf:girr:usd-swap:10y",
        risk_factor_mapping_version="ima-map-v1",
    )

    rows = build_ima_risk_factor_evidence_rows(
        [risk_factor],
        classifications={"USD_SWAP_10Y": ModellabilityStatus.TYPE_A_NMRF},
        observations=[observation],
        nmrf_artifacts=[artifact],
    )

    assert len(rows) == 1
    row = rows[0]
    assert row.risk_factor_id == "rf:girr:usd-swap:10y"
    assert row.risk_factor_mapping_version == "ima-map-v1"
    assert row.rfet_state is ImaRiskFactorEvidenceState.AVAILABLE
    assert row.rfet_evidence_ids == ("rfet-evidence-1",)
    assert row.nmrf_state is ImaRiskFactorEvidenceState.AVAILABLE
    assert row.nmrf_stress_artifact_ids == ("nmrf-artifact-1",)
    assert row.stress_period_ids == ("stress-2008",)
    assert row.as_dict()["modellability_status"] == "TYPE_A_NMRF"


def test_ima_risk_factor_evidence_rows_emit_explicit_no_data_state() -> None:
    rows = build_ima_risk_factor_evidence_rows(
        [
            RiskFactor(
                name="EQ_INDEX",
                risk_class=RiskClass.EQUITY,
                liquidity_horizon=LiquidityHorizon.LH60,
                risk_factor_id="rf:eq:index",
                risk_factor_mapping_version="ima-map-v1",
            )
        ]
    )

    assert rows[0].rfet_state is ImaRiskFactorEvidenceState.NO_DATA
    assert rows[0].nmrf_state is ImaRiskFactorEvidenceState.NO_DATA
    assert rows[0].rfet_evidence_ids == ()
    assert rows[0].nmrf_stress_artifact_ids == ()


def test_ima_risk_factor_evidence_rows_tolerate_nullable_evidence_collections() -> None:
    rows = build_ima_risk_factor_evidence_rows(
        [
            RiskFactor(
                name="EQ_INDEX",
                risk_class=RiskClass.EQUITY,
                liquidity_horizon=LiquidityHorizon.LH60,
                risk_factor_id="",
                risk_factor_mapping_version="",
            )
        ],
        observations=None,  # type: ignore[arg-type]
        nmrf_artifacts=None,  # type: ignore[arg-type]
    )

    assert rows[0].risk_factor_id == ""
    assert rows[0].rfet_state is ImaRiskFactorEvidenceState.NO_DATA
    assert rows[0].nmrf_state is ImaRiskFactorEvidenceState.NO_DATA


def test_ima_optional_metadata_ids_allow_empty_strings() -> None:
    observation = RealPriceObservation(
        risk_factor_name="USD_SWAP_10Y",
        observation_date=date(2025, 1, 2),
        risk_factor_id="",
        risk_factor_mapping_version="",
    )
    artifact = NMRFStressArtifact(
        risk_factor_name="USD_SWAP_10Y",
        method=NMRFStressMethod.DIRECT,
        losses=[1.0, 2.0, 3.0],
        liquidity_horizon=LiquidityHorizon.LH20,
        stress_period="stress-2008",
        source="upstream-valuation",
        risk_factor_id="",
        risk_factor_mapping_version="",
    )
    assert observation.risk_factor_id == ""
    assert observation.risk_factor_mapping_version == ""
    assert artifact.risk_factor_id == ""
    assert artifact.risk_factor_mapping_version == ""


def test_ima_risk_factor_rejects_invalid_stable_id() -> None:
    with pytest.raises(ValueError, match="risk_factor_id"):
        RiskFactor(
            name="BAD",
            risk_class=RiskClass.FX,
            liquidity_horizon=LiquidityHorizon.LH10,
            risk_factor_id="bad id with spaces",
        )
