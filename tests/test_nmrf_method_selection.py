"""Tests for NMRF stress-method selection."""

import pytest

from frtb_ima.data_models import LiquidityHorizon, ModellabilityStatus
from frtb_ima.nmrf import NMRFStressMethod
from frtb_ima.nmrf_method_selection import (
    NMRFDiagnosticOutcome,
    NMRFMethodDiagnostic,
    NMRFMethodEvidence,
    NMRFMethodReason,
    NMRFMethodSelectionError,
    NMRFMethodSelectionInput,
    assess_direct_loss_robustness,
    select_nmrf_method,
    select_nmrf_method_from_evidence,
    select_nmrf_methods,
    selection_input_from_method_evidence,
)
from frtb_ima.regimes import RegulatoryRegime, UnsupportedRegulatoryFeature, get_policy


def _base_input(**overrides: object) -> NMRFMethodSelectionInput:
    values: dict[str, object] = {
        "risk_factor_name": "EXOTIC_RF",
        "modellability_status": ModellabilityStatus.TYPE_B_NMRF,
        "liquidity_horizon": LiquidityHorizon.LH10,
    }
    values.update(overrides)
    return NMRFMethodSelectionInput(**values)


def test_selector_chooses_full_revaluation_for_nonlinear_available_case() -> None:
    decision = select_nmrf_method(
        _base_input(nonlinear=True, full_revaluation_available=True),
        get_policy(),
    )

    assert decision.method == NMRFStressMethod.FULL_REVALUATION
    assert decision.reason == NMRFMethodReason.NONLINEAR_FULL_REVAL_AVAILABLE
    assert decision.required_liquidity_horizon == LiquidityHorizon.LH20


def test_selector_chooses_direct_when_stable_and_well_defined() -> None:
    decision = select_nmrf_method(
        _base_input(
            modellability_status=ModellabilityStatus.TYPE_A_NMRF,
            liquidity_horizon=LiquidityHorizon.LH40,
            direct_method_available=True,
            direct_shock_well_defined=True,
            direct_robust=True,
        ),
        get_policy(),
    )

    assert decision.method == NMRFStressMethod.DIRECT
    assert decision.reason == NMRFMethodReason.DIRECT_STABLE_AND_WELL_DEFINED
    assert decision.to_valuation_instruction().required_liquidity_horizon == (
        LiquidityHorizon.LH40
    )


def test_selector_chooses_stepwise_when_direct_robustness_fails() -> None:
    decision = select_nmrf_method(
        _base_input(
            direct_method_available=True,
            direct_shock_well_defined=True,
            direct_robust=False,
            stepwise_available=True,
        ),
        get_policy(),
    )

    assert decision.method == NMRFStressMethod.STEPWISE
    assert decision.reason == NMRFMethodReason.DIRECT_FAILED_NONLINEARITY_TEST


def test_selector_chooses_stepwise_when_grid_search_is_required() -> None:
    decision = select_nmrf_method(
        _base_input(stepwise_required=True, stepwise_available=True),
        get_policy(),
    )

    assert decision.method == NMRFStressMethod.STEPWISE
    assert decision.reason == NMRFMethodReason.STEPWISE_REQUIRED_FOR_GRID_SEARCH


def test_selector_chooses_stepwise_as_only_available_method() -> None:
    decision = select_nmrf_method(
        _base_input(stepwise_available=True),
        get_policy(),
    )

    assert decision.method == NMRFStressMethod.STEPWISE
    assert decision.reason == NMRFMethodReason.STEPWISE_ONLY_AVAILABLE_METHOD


def test_selector_uses_max_loss_fallback_only_when_allowed() -> None:
    decision = select_nmrf_method(
        _base_input(max_loss_fallback_allowed=True),
        get_policy(),
    )

    assert decision.method == NMRFStressMethod.MAX_LOSS_FALLBACK
    assert decision.reason == NMRFMethodReason.NO_ACCEPTABLE_SCENARIO_REQUIRES_MAX_LOSS


def test_selector_fails_when_no_acceptable_method_exists() -> None:
    with pytest.raises(NMRFMethodSelectionError, match="No acceptable"):
        select_nmrf_method(_base_input(), get_policy())


def test_bulk_selector_rejects_empty_inputs() -> None:
    with pytest.raises(ValueError, match="non-empty"):
        select_nmrf_methods((), get_policy())


def test_selector_rejects_modellable_inputs() -> None:
    with pytest.raises(NMRFMethodSelectionError, match="TYPE_A_NMRF"):
        select_nmrf_method(
            _base_input(modellability_status=ModellabilityStatus.MODELLABLE),
            get_policy(),
        )


def test_selector_does_not_use_fed_type_a_type_b_taxonomy_for_ecb_profile() -> None:
    with pytest.raises(UnsupportedRegulatoryFeature, match="type_a_type_b"):
        select_nmrf_method(
            _base_input(direct_method_available=True, direct_shock_well_defined=True),
            get_policy(RegulatoryRegime.ECB_CRR3),
        )


def test_direct_robustness_assessment_passes_within_threshold() -> None:
    diagnostic = assess_direct_loss_robustness(
        direct_losses=[100.0, 210.0, -50.0],
        benchmark_losses=[100.0, 200.0, -50.0],
        max_relative_error_threshold=0.10,
        source="synthetic checkpoint revaluation",
    )

    assert diagnostic.outcome == NMRFDiagnosticOutcome.PASS
    assert diagnostic.value == pytest.approx(0.05)
    assert diagnostic.threshold == pytest.approx(0.10)
    assert "observations=3" in diagnostic.notes


def test_direct_robustness_assessment_fails_large_deviation() -> None:
    diagnostic = assess_direct_loss_robustness(
        direct_losses=[100.0, 260.0],
        benchmark_losses=[100.0, 200.0],
        max_relative_error_threshold=0.10,
    )

    assert diagnostic.outcome == NMRFDiagnosticOutcome.FAIL
    assert diagnostic.value == pytest.approx(0.30)


def test_direct_robustness_assessment_validates_vector_shapes() -> None:
    with pytest.raises(ValueError, match="same shape"):
        assess_direct_loss_robustness([1.0, 2.0], [1.0])


def test_method_evidence_selects_direct_when_diagnostic_passes() -> None:
    evidence = NMRFMethodEvidence(
        risk_factor_name="HY_CREDIT_SPD",
        direct_method_available=True,
        direct_shock_well_defined=True,
        direct_robustness=NMRFMethodDiagnostic(
            name="direct_loss_robustness",
            outcome=NMRFDiagnosticOutcome.PASS,
            value=0.03,
            threshold=0.10,
        ),
        source="synthetic governance evidence",
    )

    decision = select_nmrf_method_from_evidence(
        evidence,
        ModellabilityStatus.TYPE_A_NMRF,
        LiquidityHorizon.LH40,
        get_policy(),
    )

    assert decision.method == NMRFStressMethod.DIRECT
    assert decision.reason == NMRFMethodReason.DIRECT_STABLE_AND_WELL_DEFINED


def test_method_evidence_routes_failed_direct_test_to_stepwise() -> None:
    evidence = NMRFMethodEvidence(
        risk_factor_name="HY_CREDIT_SPD",
        direct_method_available=True,
        direct_shock_well_defined=True,
        direct_robustness=NMRFMethodDiagnostic(
            name="direct_loss_robustness",
            outcome=NMRFDiagnosticOutcome.FAIL,
            value=0.30,
            threshold=0.10,
        ),
        stepwise_available=True,
    )

    selection_input = selection_input_from_method_evidence(
        evidence,
        ModellabilityStatus.TYPE_A_NMRF,
        LiquidityHorizon.LH20,
    )
    decision = select_nmrf_method(selection_input, get_policy())

    assert selection_input.direct_robust is False
    assert decision.method == NMRFStressMethod.STEPWISE
    assert decision.reason == NMRFMethodReason.DIRECT_FAILED_NONLINEARITY_TEST


def test_method_evidence_direct_is_not_robust_with_pricing_failures() -> None:
    evidence = NMRFMethodEvidence(
        risk_factor_name="HY_CREDIT_SPD",
        direct_method_available=True,
        direct_shock_well_defined=True,
        direct_robustness=NMRFMethodDiagnostic(
            name="direct_loss_robustness",
            outcome=NMRFDiagnosticOutcome.PASS,
        ),
        pricing_attempt_count=5,
        pricing_failure_count=1,
    )

    assert evidence.direct_robust is False


def test_method_evidence_rejects_inconsistent_pricing_counts() -> None:
    with pytest.raises(ValueError, match="cannot exceed"):
        NMRFMethodEvidence(
            risk_factor_name="HY_CREDIT_SPD",
            pricing_attempt_count=1,
            pricing_failure_count=2,
        )
