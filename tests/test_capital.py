"""Tests for capital assembly validation."""

import pytest

from frtb_ima.capital import models_based_capital, supervisory_multiplier


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
