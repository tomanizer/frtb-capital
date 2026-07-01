from __future__ import annotations

from dataclasses import FrozenInstanceError
from datetime import date

import pytest
from frtb_sbm import (
    DEFAULT_PAIRWISE_EVIDENCE_LIMIT,
    BucketCapital,
    CurvatureBucketBranchRecord,
    CurvatureInput,
    CurvatureResult,
    RiskClassCapital,
    SbmCalculationContext,
    SbmCapitalResult,
    SbmCitation,
    SbmFxRiskFactorBasis,
    SbmPairwiseEvidenceMode,
    SbmReconciliationMetadata,
    SbmRegulatoryProfile,
    SbmRiskClass,
    SbmRiskMeasure,
    SbmRunControls,
    SbmScenarioLabel,
    SbmSensitivity,
    SbmSignConvention,
    SbmUnsupportedFeature,
    SbmWarning,
    WeightedSensitivity,
    coerce_fx_risk_factor_basis,
)
from frtb_sbm.assembly.hashes import sensitivity_payload, sensitivity_payloads_from_batch
from frtb_sbm.batch import build_sbm_batch_from_sensitivities

from tests.sbm_fixture_helpers import sample_sbm_lineage as sample_lineage


def sample_sensitivity() -> SbmSensitivity:
    return SbmSensitivity(
        sensitivity_id="sens-001",
        source_row_id="row-001",
        desk_id="rates-desk",
        legal_entity="LE-001",
        risk_class=SbmRiskClass.GIRR,
        risk_measure=SbmRiskMeasure.DELTA,
        bucket="1",
        risk_factor="USD",
        amount=1_000_000.0,
        amount_currency="USD",
        tenor="5y",
        sign_convention=SbmSignConvention.RECEIVE,
        lineage=sample_lineage(),
        mapping_citation_ids=("basel_mar21_girr",),
    )


def test_sbm_enums_cover_seven_risk_classes_and_three_measures() -> None:
    assert len(SbmRiskClass) == 7
    assert SbmRiskClass.GIRR == "GIRR"
    assert SbmRiskClass.CSR_NONSEC == "CSR_NONSEC"
    assert SbmRiskClass.CSR_SEC_CTP == "CSR_SEC_CTP"
    assert SbmRiskClass.CSR_SEC_NONCTP == "CSR_SEC_NONCTP"
    assert SbmRiskClass.EQUITY == "EQUITY"
    assert SbmRiskClass.COMMODITY == "COMMODITY"
    assert SbmRiskClass.FX == "FX"
    assert SbmRiskMeasure.DELTA == "DELTA"
    assert SbmRiskMeasure.VEGA == "VEGA"
    assert SbmRiskMeasure.CURVATURE == "CURVATURE"
    assert SbmScenarioLabel.MEDIUM == "MEDIUM"
    assert SbmRegulatoryProfile.US_NPR_2_0 == "US_NPR_2_0"


def test_sbm_sensitivity_is_frozen_and_carries_lineage() -> None:
    sensitivity = sample_sensitivity()

    assert sensitivity.sensitivity_id == "sens-001"
    assert sensitivity.lineage == sample_lineage()
    assert sensitivity.mapping_citation_ids == ("basel_mar21_girr",)
    with pytest.raises(FrozenInstanceError):
        sensitivity.amount = 0.0  # type: ignore[misc]


def test_sbm_sensitivity_preserves_optional_shock_and_surface_provenance() -> None:
    sensitivity = SbmSensitivity(
        **{
            **sample_sensitivity().__dict__,
            "risk_measure": SbmRiskMeasure.CURVATURE,
            "up_shock_amount": 125.0,
            "down_shock_amount": -125.0,
            "up_shock_id": "shock-up-001",
            "down_shock_id": "shock-down-001",
            "surface_id": "surface-usd-swaption-vol",
            "surface_point_id": "surface-usd-swaption-vol:3m:5y",
        }
    )

    payload = sensitivity_payload(sensitivity)
    batch_payload = next(
        iter(sensitivity_payloads_from_batch(build_sbm_batch_from_sensitivities((sensitivity,))))
    )

    assert payload["up_shock_id"] == "shock-up-001"
    assert payload["down_shock_id"] == "shock-down-001"
    assert payload["surface_id"] == "surface-usd-swaption-vol"
    assert payload["surface_point_id"] == "surface-usd-swaption-vol:3m:5y"
    assert batch_payload["up_shock_id"] == "shock-up-001"
    assert batch_payload["down_shock_id"] == "shock-down-001"
    assert batch_payload["surface_id"] == "surface-usd-swaption-vol"
    assert batch_payload["surface_point_id"] == "surface-usd-swaption-vol:3m:5y"


def test_public_result_model_covers_weighted_bucket_risk_class_and_total() -> None:
    citation = SbmCitation(
        source_id="basel_mar21",
        location="MAR21.38",
        url="https://www.bis.org/basel_framework/chapter/MAR/21.htm",
    )
    weighted = WeightedSensitivity(
        sensitivity_id="sens-001",
        risk_class=SbmRiskClass.GIRR,
        risk_measure=SbmRiskMeasure.DELTA,
        bucket="1",
        raw_amount=1_000_000.0,
        risk_weight=0.016,
        scaled_amount=16_000.0,
        citation_ids=(citation.source_id,),
    )
    bucket = BucketCapital(
        bucket_id="1",
        risk_class=SbmRiskClass.GIRR,
        risk_measure=SbmRiskMeasure.DELTA,
        kb=16_000.0,
        weighted_sensitivities=(weighted,),
        citation_ids=(citation.source_id,),
        sb=16_000.0,
    )
    risk_class = RiskClassCapital(
        risk_class=SbmRiskClass.GIRR,
        risk_measure=SbmRiskMeasure.DELTA,
        scenario_totals={SbmScenarioLabel.MEDIUM: 16_000.0},
        selected_scenario=SbmScenarioLabel.MEDIUM,
        selected_capital=16_000.0,
        buckets=(bucket,),
        citation_ids=(citation.source_id,),
    )
    result = SbmCapitalResult(
        total_capital=16_000.0,
        risk_classes=(risk_class,),
        profile_id=SbmRegulatoryProfile.US_NPR_2_0.value,
        profile_hash="profile-hash",
        input_hash="input-hash",
        warnings=("synthetic-fixture",),
        unsupported_flags=(),
        structured_warnings=(SbmWarning(code="SYNTHETIC", message="synthetic fixture only"),),
        unsupported_features=(),
        reconciliation=SbmReconciliationMetadata(
            input_count=1,
            rejected_input_count=0,
            requirement_ids=("SBM-DATA-001",),
            citation_ids=(citation.source_id,),
        ),
    )

    assert result.risk_classes == (risk_class,)
    assert result.total_capital == 16_000.0
    assert result.reconciliation is not None
    assert result.reconciliation.input_count == 1


def test_curvature_records_are_frozen() -> None:
    curvature_input = CurvatureInput(
        sensitivity_id="sens-curv-001",
        risk_class=SbmRiskClass.GIRR,
        bucket="1",
        risk_factor="USD",
        amount_currency="USD",
        up_shock_amount=10_000.0,
        down_shock_amount=-8_000.0,
        citation_ids=("basel_mar21_curvature",),
    )
    curvature_result = CurvatureResult(
        bucket_id="1",
        selected_branch="down",
        bucket_capital=8_000.0,
        citation_ids=("basel_mar21_curvature",),
        floor_applied=False,
    )
    curvature_bucket_branch = CurvatureBucketBranchRecord(
        bucket_id="1",
        scenario=SbmScenarioLabel.MEDIUM,
        selected_branch="up",
        rejected_branch="down",
        selected_bucket_capital=8_000.0,
        rejected_bucket_capital=7_000.0,
        up_bucket_capital=8_000.0,
        down_bucket_capital=7_000.0,
        selected_sum=10_000.0,
        up_sum=10_000.0,
        down_sum=-9_000.0,
        selected_psi_zero_count=0,
        up_psi_zero_count=0,
        down_psi_zero_count=1,
        floor_applied=False,
        citation_ids=("basel_mar21_curvature",),
    )

    assert curvature_input.up_shock_amount == 10_000.0
    assert curvature_result.selected_branch == "down"
    assert curvature_bucket_branch.scenario is SbmScenarioLabel.MEDIUM
    with pytest.raises(FrozenInstanceError):
        curvature_result.bucket_capital = 0.0  # type: ignore[misc]
    with pytest.raises(FrozenInstanceError):
        curvature_bucket_branch.selected_branch = "down"  # type: ignore[misc]


def test_calculation_context_carries_run_controls() -> None:
    context = SbmCalculationContext(
        run_id="run-001",
        calculation_date=date(2026, 5, 30),
        base_currency="USD",
        reporting_currency="USD",
        profile_id=SbmRegulatoryProfile.US_NPR_2_0.value,
        run_controls=SbmRunControls(retain_scenario_detail=True),
    )

    assert context.run_controls is not None
    assert context.run_controls.retain_scenario_detail is True
    assert context.run_controls.pairwise_evidence_mode is SbmPairwiseEvidenceMode.AUTO
    assert context.run_controls.pairwise_evidence_limit == DEFAULT_PAIRWISE_EVIDENCE_LIMIT
    assert context.run_controls.fx_risk_factor_basis is SbmFxRiskFactorBasis.REPORTING_CURRENCY
    assert context.run_controls.fx_base_currency_approval_ids == ()


def test_fx_risk_factor_basis_is_publicly_coercible() -> None:
    assert (
        coerce_fx_risk_factor_basis("REPORTING_CURRENCY") is SbmFxRiskFactorBasis.REPORTING_CURRENCY
    )


def test_unsupported_feature_metadata_is_structured() -> None:
    unsupported = SbmUnsupportedFeature(
        feature_key="CSR_SEC_NONCTP_DELTA",
        dimension="risk_class",
        reason="CSR securitisation non-CTP delta is not implemented",
        requirement_id="SBM-FUNC-015",
    )

    assert unsupported.dimension == "risk_class"
    assert unsupported.requirement_id == "SBM-FUNC-015"
