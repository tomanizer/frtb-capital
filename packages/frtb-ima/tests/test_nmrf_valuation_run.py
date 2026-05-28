"""Tests for NMRF valuation-run reconciliation."""

import logging
from datetime import date
from types import MappingProxyType

import pytest

from frtb_ima.data_models import LiquidityHorizon, ModellabilityStatus, RiskClass
from frtb_ima.nmrf import NMRFStressArtifact, NMRFStressMethod
from frtb_ima.nmrf_stress_spec import (
    NMRFDirectShockSpec,
    NMRFFullRevaluationSpec,
    NMRFMaxLossFallbackSpec,
    NMRFShockDirection,
    NMRFStepwiseShockGrid,
    NMRFStressPeriodSpec,
    NMRFValuationSpec,
)
from frtb_ima.nmrf_valuation_run import (
    NMRFArtifactReconciliationItem,
    NMRFArtifactReconciliationResult,
    NMRFValuationRunError,
    build_nmrf_valuation_run_request,
    calculate_nmrf_capital_from_valuation_run,
    complete_nmrf_valuation_run,
    reconcile_nmrf_valuation_artifacts,
    require_nmrf_valuation_reconciliation_passed,
)
from frtb_ima.regimes import RegulatoryRegime, get_policy

CONFIDENCE_LEVEL = 0.975


def _stress_period(period_id: str = "csr-2008") -> NMRFStressPeriodSpec:
    return NMRFStressPeriodSpec(
        stress_period_id=period_id,
        calibration_source="synthetic stress-window selector",
        start_date=date(2008, 9, 1),
        end_date=date(2009, 8, 31),
    )


def _direct_spec(name: str = "RF_DIRECT") -> NMRFValuationSpec:
    return NMRFValuationSpec(
        risk_factor_name=name,
        modellability_status=ModellabilityStatus.TYPE_A_NMRF,
        risk_class=RiskClass.CSR,
        method=NMRFStressMethod.DIRECT,
        required_liquidity_horizon=LiquidityHorizon.LH20,
        stress_period=_stress_period(),
        direct_shock=NMRFDirectShockSpec(
            shock_size=250.0,
            shock_unit="spread_bps",
            direction=NMRFShockDirection.UP,
            calibration_source="synthetic",
            confidence_level=CONFIDENCE_LEVEL,
        ),
        source="unit-test spec",
    )


def _full_reval_spec(name: str = "RF_FULL") -> NMRFValuationSpec:
    return NMRFValuationSpec(
        risk_factor_name=name,
        modellability_status=ModellabilityStatus.TYPE_B_NMRF,
        risk_class=RiskClass.EQUITY,
        method=NMRFStressMethod.FULL_REVALUATION,
        required_liquidity_horizon=LiquidityHorizon.LH120,
        stress_period=_stress_period("equity-2020"),
        full_revaluation=NMRFFullRevaluationSpec(
            scenario_set_id="full-reval-set",
            market_state_ids=("ms-1", "ms-2", "ms-3"),
            calibration_source="synthetic",
        ),
        source="unit-test spec",
    )


def _stepwise_spec(name: str = "RF_STEP") -> NMRFValuationSpec:
    return NMRFValuationSpec(
        risk_factor_name=name,
        modellability_status=ModellabilityStatus.TYPE_A_NMRF,
        risk_class=RiskClass.CSR,
        method=NMRFStressMethod.STEPWISE,
        required_liquidity_horizon=LiquidityHorizon.LH20,
        stress_period=_stress_period(),
        stepwise_grid=NMRFStepwiseShockGrid(
            shock_points=(-100.0, 0.0, 100.0),
            shock_unit="spread_bps",
            calibration_source="synthetic",
        ),
        source="unit-test spec",
    )


def _max_loss_spec(name: str = "RF_MAX") -> NMRFValuationSpec:
    return NMRFValuationSpec(
        risk_factor_name=name,
        modellability_status=ModellabilityStatus.TYPE_B_NMRF,
        risk_class=RiskClass.CSR,
        method=NMRFStressMethod.MAX_LOSS_FALLBACK,
        required_liquidity_horizon=LiquidityHorizon.LH20,
        stress_period=_stress_period(),
        max_loss_fallback=NMRFMaxLossFallbackSpec(
            candidate_scenario_ids=("candidate-1", "candidate-2"),
            loss_source="synthetic candidate losses",
        ),
        source="unit-test spec",
    )


def _artifact(
    spec: NMRFValuationSpec,
    *,
    method: NMRFStressMethod | None = None,
    losses: tuple[float, ...] = (1.0, 2.0, 100.0),
    liquidity_horizon: LiquidityHorizon | None = None,
    stress_period: str | None = None,
    scenario_ids: tuple[str, ...] = (),
    risk_factor_name: str | None = None,
    generated_by_prototype: bool = False,
) -> NMRFStressArtifact:
    return NMRFStressArtifact(
        risk_factor_name=risk_factor_name or spec.risk_factor_name,
        method=method or spec.method,
        losses=losses,
        liquidity_horizon=liquidity_horizon or spec.required_liquidity_horizon,
        stress_period=stress_period or spec.stress_period.stress_period_id,
        source="synthetic upstream artifact",
        scenario_ids=scenario_ids,
        generated_by_prototype=generated_by_prototype,
    )


def test_valuation_run_request_is_immutable_and_serialisable() -> None:
    request = build_nmrf_valuation_run_request(
        (_direct_spec(),),
        get_policy(),
        run_id="run-1",
        desk_id="desk-1",
        as_of_date=date(2026, 5, 27),
        metadata={"batch": "unit-test"},
    )

    assert request.regime == "FED_NPR_2_0"
    assert request.spec_count == 1
    assert isinstance(request.metadata, MappingProxyType)
    assert request.as_dict()["as_of_date"] == "2026-05-27"


def test_reconciliation_passes_exact_direct_and_full_revaluation_artifacts(
    caplog: pytest.LogCaptureFixture,
) -> None:
    direct = _direct_spec()
    full = _full_reval_spec()
    artifacts = (
        _artifact(direct),
        _artifact(
            full,
            losses=(10.0, 20.0, 30.0),
            scenario_ids=("ms-1", "ms-2", "ms-3"),
        ),
    )

    with caplog.at_level(logging.INFO, logger="frtb_ima.nmrf_valuation_run"):
        result = reconcile_nmrf_valuation_artifacts(
            (direct, full),
            artifacts,
            run_id="run-1",
            desk_id="desk-1",
            regime="FED_NPR_2_0",
        )

    assert result.passed is True
    assert result.spec_count == 2
    assert result.artifact_count == 2
    assert result.items[1].scenario_ids_matched is True
    assert result.as_dict()["items"][1]["artifact_loss_count"] == 3
    record = next(
        record
        for record in caplog.records
        if record.getMessage() == "nmrf_valuation_reconciliation_complete"
    )
    assert record.passed is True
    assert record.spec_count == 2


def test_reconciliation_reports_missing_unexpected_and_duplicate_artifacts() -> None:
    direct = _direct_spec()
    unexpected = _artifact(
        direct,
        risk_factor_name="RF_UNEXPECTED",
    )
    duplicate_1 = _artifact(direct)
    duplicate_2 = _artifact(direct)

    missing_result = reconcile_nmrf_valuation_artifacts((direct,), ())
    unexpected_result = reconcile_nmrf_valuation_artifacts((direct,), (unexpected,))
    duplicate_result = reconcile_nmrf_valuation_artifacts(
        (direct,),
        (duplicate_1, duplicate_2),
    )

    assert missing_result.passed is False
    assert missing_result.missing_count == 1
    assert missing_result.items[0].errors == ("missing_artifact",)
    assert unexpected_result.unexpected_artifacts == ("RF_UNEXPECTED",)
    assert duplicate_result.duplicate_artifacts == ("RF_DIRECT",)
    assert "duplicate_artifacts" in duplicate_result.items[0].errors


def test_reconciliation_artifact_count_fallback_uses_unexpected_artifact_count() -> None:
    result = NMRFArtifactReconciliationResult(
        items=(
            NMRFArtifactReconciliationItem(
                risk_factor_name="RF_DIRECT",
                required_method=NMRFStressMethod.DIRECT,
                required_liquidity_horizon=LiquidityHorizon.LH20,
                required_stress_period="csr-2008",
                artifact_count=1,
            ),
        ),
        unexpected_artifacts=("RF_UNEXPECTED",),
        unexpected_artifact_count=2,
    )

    assert result.unexpected_count == 2
    assert result.unexpected_risk_factor_count == 1
    assert result.artifact_count == 3


def test_reconciliation_reports_method_lh_and_stress_period_mismatches() -> None:
    direct = _direct_spec()
    artifact = _artifact(
        direct,
        method=NMRFStressMethod.STEPWISE,
        liquidity_horizon=LiquidityHorizon.LH20,
        stress_period="wrong-period",
    )

    result = reconcile_nmrf_valuation_artifacts((direct,), (artifact,))

    assert result.passed is False
    assert result.items[0].method_matched is False
    assert result.items[0].stress_period_matched is False
    assert result.items[0].errors == (
        "method_mismatch",
        "stress_period_mismatch",
    )


def test_reconciliation_reports_liquidity_horizon_too_short() -> None:
    full = _full_reval_spec()
    artifact = _artifact(
        full,
        losses=(1.0, 2.0, 3.0),
        liquidity_horizon=LiquidityHorizon.LH60,
        scenario_ids=("ms-1", "ms-2", "ms-3"),
    )

    result = reconcile_nmrf_valuation_artifacts((full,), (artifact,))

    assert result.passed is False
    assert result.items[0].liquidity_horizon_matched is False
    assert "liquidity_horizon_too_short" in result.items[0].errors


def test_reconciliation_rejects_prototype_artifacts_by_default() -> None:
    direct = _direct_spec()
    artifact = _artifact(direct, generated_by_prototype=True)

    result = reconcile_nmrf_valuation_artifacts((direct,), (artifact,))
    allowed_result = reconcile_nmrf_valuation_artifacts(
        (direct,),
        (artifact,),
        allow_prototype_artifacts=True,
    )

    assert result.passed is False
    assert result.items[0].generated_by_prototype is True
    assert "prototype_artifact" in result.items[0].errors
    assert allowed_result.passed is True


def test_full_revaluation_reconciliation_requires_market_state_ids() -> None:
    full = _full_reval_spec()
    wrong_count = _artifact(
        full,
        losses=(1.0, 2.0),
        scenario_ids=("ms-1", "ms-2"),
    )
    wrong_ids = _artifact(
        full,
        losses=(1.0, 2.0, 3.0),
        scenario_ids=("ms-1", "ms-3", "ms-2"),
    )

    count_result = reconcile_nmrf_valuation_artifacts((full,), (wrong_count,))
    id_result = reconcile_nmrf_valuation_artifacts((full,), (wrong_ids,))

    assert count_result.items[0].scenario_count_matched is False
    assert count_result.items[0].scenario_ids_matched is False
    assert id_result.items[0].scenario_count_matched is True
    assert id_result.items[0].scenario_ids_matched is False


def test_stepwise_reconciliation_requires_grid_loss_count() -> None:
    stepwise = _stepwise_spec()
    artifact = _artifact(stepwise, losses=(1.0, 2.0))

    result = reconcile_nmrf_valuation_artifacts((stepwise,), (artifact,))

    assert result.passed is False
    assert result.items[0].required_scenario_count == 3
    assert result.items[0].scenario_count_matched is False
    assert result.items[0].scenario_ids_matched is None


def test_max_loss_reconciliation_requires_candidate_scenario_ids() -> None:
    max_loss = _max_loss_spec()
    artifact = _artifact(
        max_loss,
        losses=(10.0, 20.0),
        scenario_ids=("candidate-2", "candidate-1"),
    )

    result = reconcile_nmrf_valuation_artifacts((max_loss,), (artifact,))

    assert result.passed is False
    assert result.items[0].scenario_count_matched is True
    assert result.items[0].scenario_ids_matched is False


def test_failed_reconciliation_blocks_capital_consumption() -> None:
    direct = _direct_spec()
    request = build_nmrf_valuation_run_request(
        (direct,),
        get_policy(),
        run_id="run-1",
        desk_id="desk-1",
    )
    valuation_run = complete_nmrf_valuation_run(request, ())

    with pytest.raises(NMRFValuationRunError, match="reconciliation failed"):
        calculate_nmrf_capital_from_valuation_run(
            {"RF_DIRECT": ModellabilityStatus.TYPE_A_NMRF},
            valuation_run,
            get_policy(),
        )


def test_regime_mismatch_blocks_capital_consumption() -> None:
    direct = _direct_spec()
    artifacts = (_artifact(direct),)
    request = build_nmrf_valuation_run_request(
        (direct,),
        get_policy(),
        run_id="run-1",
        desk_id="desk-1",
    )
    valuation_run = complete_nmrf_valuation_run(request, artifacts)

    with pytest.raises(NMRFValuationRunError, match="regime does not match"):
        calculate_nmrf_capital_from_valuation_run(
            {"RF_DIRECT": ModellabilityStatus.TYPE_A_NMRF},
            valuation_run,
            get_policy(RegulatoryRegime.ECB_CRR3),
        )


def test_reconciled_valuation_run_feeds_nmrf_capital() -> None:
    direct = _direct_spec()
    full = _full_reval_spec()
    artifacts = (
        _artifact(direct, losses=(1.0, 2.0, 100.0)),
        _artifact(
            full,
            losses=(10.0, 20.0, 200.0),
            scenario_ids=("ms-1", "ms-2", "ms-3"),
        ),
    )
    request = build_nmrf_valuation_run_request(
        (direct, full),
        get_policy(),
        run_id="run-1",
        desk_id="desk-1",
    )
    valuation_run = complete_nmrf_valuation_run(request, artifacts)

    capital = calculate_nmrf_capital_from_valuation_run(
        {
            "RF_DIRECT": ModellabilityStatus.TYPE_A_NMRF,
            "RF_FULL": ModellabilityStatus.TYPE_B_NMRF,
        },
        valuation_run,
        get_policy(),
    )

    require_nmrf_valuation_reconciliation_passed(valuation_run.reconciliation)
    assert capital.routing.ses_risk_factors == ("RF_DIRECT", "RF_FULL")
    assert capital.total_ses > 0.0
