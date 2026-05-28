"""Tests for capital assembly validation."""

import pytest

from frtb_ima.backtesting import BacktestLevelResult, TradingDeskBacktestResult
from frtb_ima.capital import (
    CapitalComponents,
    IMAIneligibleError,
    desk_eligibility_from_results,
    models_based_capital,
    models_based_capital_for_policy,
    pla_addon,
    supervisory_multiplier,
    supervisory_multiplier_for_policy,
)
from frtb_ima.regimes import DeskEligibilityStatus, get_policy


def _trading_desk_backtest_result(*, model_eligible: bool) -> TradingDeskBacktestResult:
    return TradingDeskBacktestResult(
        levels=(
            BacktestLevelResult(
                confidence_level=0.99,
                apl_exceptions=0 if model_eligible else 13,
                hpl_exceptions=0,
                exception_limit=12.0,
                apl_passed=model_eligible,
                hpl_passed=True,
                level_passed=model_eligible,
                window_size=250,
            ),
        ),
        window_size=250,
        model_eligible=model_eligible,
    )


def test_models_based_capital_rejects_negative_components() -> None:
    with pytest.raises(ValueError, match="imcc_t_minus_1"):
        models_based_capital(
            imcc_t_minus_1=-1.0,
            ses_t_minus_1=0.0,
            imcc_60d_avg=0.0,
            ses_60d_avg=0.0,
        )


def test_models_based_capital_rejects_non_finite_components() -> None:
    with pytest.raises(ValueError, match="pla_addon"):
        models_based_capital(
            imcc_t_minus_1=1.0,
            ses_t_minus_1=1.0,
            imcc_60d_avg=1.0,
            ses_60d_avg=1.0,
            pla_addon=float("inf"),
        )


def test_models_based_capital_rejects_non_finite_multiplier() -> None:
    with pytest.raises(ValueError, match="multiplier"):
        models_based_capital(
            imcc_t_minus_1=1.0,
            ses_t_minus_1=1.0,
            imcc_60d_avg=1.0,
            ses_60d_avg=1.0,
            multiplier=float("nan"),
        )


def test_supervisory_multiplier_rejects_negative_exception_count() -> None:
    with pytest.raises(ValueError, match="non-negative"):
        supervisory_multiplier(-1)


def test_supervisory_multiplier_rejects_non_integer_exception_count() -> None:
    with pytest.raises(TypeError, match="integer"):
        supervisory_multiplier(1.5)  # type: ignore[arg-type]


def test_pla_addon_uses_half_amber_standardized_share() -> None:
    result = pla_addon(
        standardized_green_amber=1_000.0,
        standardized_amber=200.0,
        ima_green_amber=700.0,
    )

    assert result.k_factor == pytest.approx(0.1)
    assert result.capital_benefit == pytest.approx(300.0)
    assert result.pla_addon == pytest.approx(30.0)
    assert result.as_dict()["pla_addon"] == pytest.approx(30.0)


def test_pla_addon_floors_negative_capital_benefit_at_zero() -> None:
    result = pla_addon(
        standardized_green_amber=1_000.0,
        standardized_amber=500.0,
        ima_green_amber=1_200.0,
    )

    assert result.pla_addon == pytest.approx(0.0)


def test_pla_addon_rejects_amber_exceeding_green_amber() -> None:
    with pytest.raises(ValueError, match="standardized_amber"):
        pla_addon(
            standardized_green_amber=100.0,
            standardized_amber=101.0,
            ima_green_amber=50.0,
        )


def test_models_based_capital_serializes_audit_breakdown() -> None:
    result = models_based_capital(
        imcc_t_minus_1=100.0,
        ses_t_minus_1=20.0,
        imcc_60d_avg=90.0,
        ses_60d_avg=10.0,
    )

    assert result.as_dict()["models_based_capital"] == pytest.approx(145.0)
    assert result.as_dict()["binding_term"] == "AVERAGE"


def test_desk_eligibility_from_results_falls_back_when_backtesting_fails() -> None:
    result = desk_eligibility_from_results(
        _trading_desk_backtest_result(model_eligible=False),
        "GREEN",
    )

    assert result == DeskEligibilityStatus.SA_FALLBACK


def test_desk_eligibility_from_results_falls_back_for_red_pla() -> None:
    result = desk_eligibility_from_results(
        _trading_desk_backtest_result(model_eligible=True),
        "RED",
    )

    assert result == DeskEligibilityStatus.SA_FALLBACK


def test_desk_eligibility_from_results_allows_amber_pla_when_backtesting_passes() -> None:
    result = desk_eligibility_from_results(
        _trading_desk_backtest_result(model_eligible=True),
        "AMBER",
    )

    assert result == DeskEligibilityStatus.IMA_ELIGIBLE


def test_desk_eligibility_from_results_uses_configured_pla_zone_labels() -> None:
    passing_backtest = _trading_desk_backtest_result(model_eligible=True)

    amber_result = desk_eligibility_from_results(
        passing_backtest,
        "WATCH",
        pla_zone_labels=("OK", "WATCH", "FAIL"),
    )
    red_result = desk_eligibility_from_results(
        passing_backtest,
        "FAIL",
        pla_zone_labels=("OK", "WATCH", "FAIL"),
    )

    assert amber_result == DeskEligibilityStatus.IMA_ELIGIBLE
    assert red_result == DeskEligibilityStatus.SA_FALLBACK


def test_desk_eligibility_from_results_rejects_unknown_pla_zone() -> None:
    with pytest.raises(ValueError, match="pla_zone"):
        desk_eligibility_from_results(
            _trading_desk_backtest_result(model_eligible=True),
            "YELLOW",
        )


def test_desk_eligibility_from_results_rejects_invalid_pla_zone_labels() -> None:
    with pytest.raises(ValueError, match="pla_zone_labels"):
        desk_eligibility_from_results(
            _trading_desk_backtest_result(model_eligible=True),
            "GREEN",
            pla_zone_labels=("GREEN", "GREEN", "RED"),
        )


def test_models_based_capital_for_policy_rejects_sa_fallback_desks() -> None:
    with pytest.raises(IMAIneligibleError, match="SA_FALLBACK"):
        models_based_capital_for_policy(
            DeskEligibilityStatus.SA_FALLBACK,
            imcc_t_minus_1=100.0,
            ses_t_minus_1=20.0,
            imcc_60d_avg=90.0,
            ses_60d_avg=10.0,
            pla_addon=0.0,
            policy=get_policy(),
        )


def test_models_based_capital_for_policy_returns_capital_components() -> None:
    policy = get_policy()

    result = models_based_capital_for_policy(
        DeskEligibilityStatus.IMA_ELIGIBLE,
        imcc_t_minus_1=100.0,
        ses_t_minus_1=20.0,
        imcc_60d_avg=90.0,
        ses_60d_avg=10.0,
        pla_addon=5.0,
        policy=policy,
    )

    assert isinstance(result, CapitalComponents)
    assert result.multiplier == pytest.approx(supervisory_multiplier_for_policy(0, policy))
    assert result.models_based_capital == pytest.approx(150.0)
    assert result.binding_term == "AVERAGE"


def test_models_based_capital_for_policy_uses_policy_exception_count_multiplier() -> None:
    policy = get_policy()

    result = models_based_capital_for_policy(
        DeskEligibilityStatus.IMA_ELIGIBLE,
        imcc_t_minus_1=100.0,
        ses_t_minus_1=20.0,
        imcc_60d_avg=90.0,
        ses_60d_avg=10.0,
        pla_addon=0.0,
        policy=policy,
        exception_count=6,
    )

    assert result.multiplier == pytest.approx(supervisory_multiplier_for_policy(6, policy))
    assert result.models_based_capital == pytest.approx(168.4)
