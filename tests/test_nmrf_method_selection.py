"""Tests for NMRF stress-method selection."""

import pytest

from frtb_ima.data_models import LiquidityHorizon, ModellabilityStatus
from frtb_ima.nmrf import NMRFStressMethod
from frtb_ima.nmrf_method_selection import (
    NMRFMethodReason,
    NMRFMethodSelectionError,
    NMRFMethodSelectionInput,
    select_nmrf_method,
    select_nmrf_methods,
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
