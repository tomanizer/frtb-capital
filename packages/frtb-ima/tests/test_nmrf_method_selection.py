"""Tests for NMRF stress-method selection."""

import numpy as np
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
    NMRFValuationInstruction,
    assess_direct_loss_robustness,
    select_nmrf_method,
    select_nmrf_method_from_evidence,
    select_nmrf_methods,
    selection_input_from_method_evidence,
)
from frtb_ima.regimes import RegulatoryRegime, get_policy


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
    assert decision.to_valuation_instruction().required_liquidity_horizon == (LiquidityHorizon.LH40)


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


def test_selector_uses_fallback_when_required_stepwise_is_unavailable() -> None:
    decision = select_nmrf_method(
        _base_input(
            stepwise_required=True,
            stepwise_available=False,
            max_loss_fallback_allowed=True,
        ),
        get_policy(),
    )

    assert decision.method == NMRFStressMethod.MAX_LOSS_FALLBACK


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


def test_selector_uses_full_revaluation_when_direct_is_unavailable() -> None:
    decision = select_nmrf_method(
        _base_input(full_revaluation_available=True),
        get_policy(),
    )

    assert decision.method == NMRFStressMethod.FULL_REVALUATION
    assert decision.reason == NMRFMethodReason.FULL_REVALUATION_AVAILABLE
    assert decision.as_dict()["required_liquidity_horizon"] == LiquidityHorizon.LH20.value


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


def test_method_selection_input_validates_required_types() -> None:
    with pytest.raises(ValueError, match="risk_factor_name"):
        _base_input(risk_factor_name="")
    with pytest.raises(TypeError, match="ModellabilityStatus"):
        _base_input(modellability_status="TYPE_A_NMRF")
    with pytest.raises(TypeError, match="LiquidityHorizon"):
        _base_input(liquidity_horizon=20)


def test_selector_supports_ecb_nmrf_without_type_a_type_b_taxonomy_gate() -> None:
    decision = select_nmrf_method(
        _base_input(
            direct_method_available=True,
            direct_shock_well_defined=True,
            direct_robust=True,
        ),
        get_policy(RegulatoryRegime.ECB_CRR3),
    )
    assert decision.method is NMRFStressMethod.DIRECT


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


def test_direct_robustness_assessment_handles_single_near_zero_observation() -> None:
    diagnostic = assess_direct_loss_robustness(
        direct_losses=[1e-14],
        benchmark_losses=[0.0],
        max_relative_error_threshold=0.02,
        absolute_tolerance=1e-12,
        notes="single-point edge case",
    )

    assert diagnostic.outcome == NMRFDiagnosticOutcome.PASS
    assert diagnostic.value == pytest.approx(0.01)
    assert "single-point edge case" in diagnostic.notes
    assert "observations=1" in diagnostic.notes


def test_direct_robustness_assessment_validates_vector_shapes() -> None:
    with pytest.raises(ValueError, match="same shape"):
        assess_direct_loss_robustness([1.0, 2.0], [1.0])


def test_direct_robustness_assessment_validates_thresholds_and_vectors() -> None:
    with pytest.raises(ValueError, match="max_relative_error_threshold"):
        assess_direct_loss_robustness([1.0], [1.0], max_relative_error_threshold=float("nan"))
    with pytest.raises(ValueError, match="absolute_tolerance"):
        assess_direct_loss_robustness([1.0], [1.0], absolute_tolerance=0.0)
    with pytest.raises(ValueError, match="one-dimensional"):
        assess_direct_loss_robustness([[1.0]], [1.0])  # type: ignore[list-item]
    with pytest.raises(ValueError, match="non-empty"):
        assess_direct_loss_robustness([], [])
    with pytest.raises(ValueError, match="finite"):
        assess_direct_loss_robustness([np.inf], [1.0])


def test_method_diagnostic_validates_fields_and_serializes() -> None:
    diagnostic = NMRFMethodDiagnostic(
        name="direct_loss_robustness",
        outcome=NMRFDiagnosticOutcome.NOT_RUN,
        value=None,
        threshold=None,
        source="synthetic",
        notes="not enough observations",
    )

    assert diagnostic.passed is False
    assert diagnostic.as_dict()["outcome"] == "NOT_RUN"

    with pytest.raises(ValueError, match="diagnostic name"):
        NMRFMethodDiagnostic(name="", outcome=NMRFDiagnosticOutcome.PASS)
    with pytest.raises(TypeError, match="NMRFDiagnosticOutcome"):
        NMRFMethodDiagnostic(name="direct", outcome="PASS")  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="diagnostic value"):
        NMRFMethodDiagnostic(
            name="direct",
            outcome=NMRFDiagnosticOutcome.PASS,
            value=float("nan"),
        )
    with pytest.raises(ValueError, match="diagnostic threshold"):
        NMRFMethodDiagnostic(
            name="direct",
            outcome=NMRFDiagnosticOutcome.PASS,
            threshold=float("inf"),
        )


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


def test_method_evidence_without_direct_diagnostic_preserves_supplemental_diagnostics() -> None:
    supplemental = NMRFMethodDiagnostic(
        name="pricing_engine_available",
        outcome=NMRFDiagnosticOutcome.PASS,
    )
    evidence = NMRFMethodEvidence(
        risk_factor_name="HY_CREDIT_SPD",
        diagnostics=(supplemental,),
        proxy_or_basis_risk=True,
    )

    assert evidence.direct_robust is False
    assert evidence.all_diagnostics == (supplemental,)
    assert evidence.as_dict()["diagnostics"][0]["name"] == "pricing_engine_available"


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


def test_method_evidence_rejects_invalid_diagnostics() -> None:
    with pytest.raises(ValueError, match="risk_factor_name"):
        NMRFMethodEvidence(risk_factor_name="")
    with pytest.raises(TypeError, match="direct_robustness"):
        NMRFMethodEvidence(
            risk_factor_name="HY_CREDIT_SPD",
            direct_robustness=object(),  # type: ignore[arg-type]
        )
    with pytest.raises(ValueError, match="non-negative"):
        NMRFMethodEvidence(
            risk_factor_name="HY_CREDIT_SPD",
            pricing_attempt_count=-1,
        )
    with pytest.raises(TypeError, match="diagnostics"):
        NMRFMethodEvidence(
            risk_factor_name="HY_CREDIT_SPD",
            diagnostics=(object(),),  # type: ignore[arg-type]
        )


def test_method_evidence_rejects_inconsistent_pricing_counts() -> None:
    with pytest.raises(ValueError, match="cannot exceed"):
        NMRFMethodEvidence(
            risk_factor_name="HY_CREDIT_SPD",
            pricing_attempt_count=1,
            pricing_failure_count=2,
        )


def test_selector_from_evidence_errors_when_no_method_is_supported() -> None:
    with pytest.raises(NMRFMethodSelectionError, match="No acceptable"):
        select_nmrf_method_from_evidence(
            NMRFMethodEvidence(risk_factor_name="HY_CREDIT_SPD"),
            ModellabilityStatus.TYPE_A_NMRF,
            LiquidityHorizon.LH20,
            get_policy(),
        )


def test_selection_input_from_evidence_rejects_invalid_evidence_type() -> None:
    with pytest.raises(TypeError, match="NMRFMethodEvidence"):
        selection_input_from_method_evidence(  # type: ignore[arg-type]
            "not-evidence",
            ModellabilityStatus.TYPE_A_NMRF,
            LiquidityHorizon.LH20,
        )


def test_selector_uses_fallback_when_direct_robustness_fails_without_stepwise() -> None:
    decision = select_nmrf_method(
        _base_input(
            direct_method_available=True,
            direct_shock_well_defined=True,
            direct_robust=False,
            max_loss_fallback_allowed=True,
        ),
        get_policy(),
    )

    assert decision.method == NMRFStressMethod.MAX_LOSS_FALLBACK
    assert decision.reason == NMRFMethodReason.NO_ACCEPTABLE_SCENARIO_REQUIRES_MAX_LOSS


def test_bulk_selector_raises_for_mixed_portfolio_with_modellable_input() -> None:
    with pytest.raises(NMRFMethodSelectionError, match="TYPE_A_NMRF"):
        select_nmrf_methods(
            (
                _base_input(
                    risk_factor_name="TYPE_A_DIRECT",
                    modellability_status=ModellabilityStatus.TYPE_A_NMRF,
                    direct_method_available=True,
                    direct_shock_well_defined=True,
                    direct_robust=True,
                ),
                _base_input(
                    risk_factor_name="TYPE_B_STEPWISE",
                    modellability_status=ModellabilityStatus.TYPE_B_NMRF,
                    stepwise_required=True,
                    stepwise_available=True,
                ),
                _base_input(
                    risk_factor_name="MODELLABLE_RF",
                    modellability_status=ModellabilityStatus.MODELLABLE,
                ),
            ),
            get_policy(),
        )


def test_valuation_instruction_validates_types_and_serialization() -> None:
    with pytest.raises(ValueError, match="risk_factor_name"):
        NMRFValuationInstruction(
            risk_factor_name="",
            modellability_status=ModellabilityStatus.TYPE_A_NMRF,
            method=NMRFStressMethod.DIRECT,
            risk_factor_liquidity_horizon=LiquidityHorizon.LH20,
            required_liquidity_horizon=LiquidityHorizon.LH20,
            reason=NMRFMethodReason.DIRECT_STABLE_AND_WELL_DEFINED,
        )

    with pytest.raises(ValueError, match="only valid for NMRFs"):
        NMRFValuationInstruction(
            risk_factor_name="RF",
            modellability_status=ModellabilityStatus.MODELLABLE,
            method=NMRFStressMethod.DIRECT,
            risk_factor_liquidity_horizon=LiquidityHorizon.LH20,
            required_liquidity_horizon=LiquidityHorizon.LH20,
            reason=NMRFMethodReason.DIRECT_STABLE_AND_WELL_DEFINED,
        )
    with pytest.raises(TypeError, match="method"):
        NMRFValuationInstruction(  # type: ignore[arg-type]
            risk_factor_name="RF",
            modellability_status=ModellabilityStatus.TYPE_A_NMRF,
            method="DIRECT",
            risk_factor_liquidity_horizon=LiquidityHorizon.LH20,
            required_liquidity_horizon=LiquidityHorizon.LH20,
            reason=NMRFMethodReason.DIRECT_STABLE_AND_WELL_DEFINED,
        )
    with pytest.raises(ValueError, match="below the NMRF floor"):
        NMRFValuationInstruction(
            risk_factor_name="RF",
            modellability_status=ModellabilityStatus.TYPE_A_NMRF,
            method=NMRFStressMethod.DIRECT,
            risk_factor_liquidity_horizon=LiquidityHorizon.LH120,
            required_liquidity_horizon=LiquidityHorizon.LH40,
            reason=NMRFMethodReason.DIRECT_STABLE_AND_WELL_DEFINED,
        )
    with pytest.raises(TypeError, match="reason"):
        NMRFValuationInstruction(  # type: ignore[arg-type]
            risk_factor_name="RF",
            modellability_status=ModellabilityStatus.TYPE_A_NMRF,
            method=NMRFStressMethod.DIRECT,
            risk_factor_liquidity_horizon=LiquidityHorizon.LH20,
            required_liquidity_horizon=LiquidityHorizon.LH20,
            reason="DIRECT_STABLE_AND_WELL_DEFINED",
        )

    decision = select_nmrf_method(
        _base_input(
            risk_factor_name="RF_VALID",
            direct_method_available=True,
            direct_shock_well_defined=True,
            direct_robust=True,
        ),
        get_policy(),
    )
    instruction = decision.to_valuation_instruction()
    assert instruction.as_dict()["risk_factor_name"] == "RF_VALID"
