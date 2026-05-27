"""Tests for capital assembly validation."""

import pytest

from frtb_ima.capital import models_based_capital, pla_addon, supervisory_multiplier


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
