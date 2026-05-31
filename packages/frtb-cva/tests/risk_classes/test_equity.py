from __future__ import annotations

import math

import pytest
from frtb_cva import (
    SaCvaRiskClass,
    SaCvaRiskMeasure,
    SaCvaSensitivity,
    SensitivityTag,
)
from frtb_cva.risk_classes.equity import (
    calculate_equity_delta_capital,
    calculate_equity_vega_capital,
)
from frtb_cva.validation import CvaInputError


def _equity_sensitivity(
    *,
    bucket: str = "5",
    equity_name: str = "EQ_A",
    amount: float = 1_000_000.0,
    measure: SaCvaRiskMeasure = SaCvaRiskMeasure.DELTA,
    volatility_input: float | None = None,
) -> SaCvaSensitivity:
    return SaCvaSensitivity(
        sensitivity_id=f"sens-eq-{bucket}-{equity_name}-{measure.value}",
        risk_class=SaCvaRiskClass.EQUITY,
        risk_measure=measure,
        sensitivity_tag=SensitivityTag.CVA,
        bucket_id=bucket,
        risk_factor_key=equity_name,
        amount=amount,
        amount_currency="USD",
        sign_convention="positive_loss",
        source_row_id=f"row-eq-{bucket}",
        volatility_input=volatility_input,
    )


def test_equity_delta_rejects_empty() -> None:
    with pytest.raises(CvaInputError):
        calculate_equity_delta_capital(())


def test_equity_delta_reconciles_by_bucket() -> None:
    capital = calculate_equity_delta_capital((_equity_sensitivity(bucket="5", amount=2_000_000.0),))
    assert capital.post_multiplier_capital == pytest.approx(2_000_000.0 * 0.30)


def test_equity_delta_distinct_names_bucket_5_uses_mar50_72_rho() -> None:
    """MAR50.72: rho_kl = 0.15 for distinct names in buckets 1-10."""
    capital = calculate_equity_delta_capital(
        (
            _equity_sensitivity(bucket="5", equity_name="EQ_A", amount=1_000_000.0),
            _equity_sensitivity(bucket="5", equity_name="EQ_B", amount=1_000_000.0),
        ),
    )
    ws = 1_000_000.0 * 0.30
    kb = math.sqrt(ws**2 + ws**2 + 2 * 0.15 * ws * ws)
    assert capital.bucket_capitals[0].k_b == pytest.approx(kb)


def test_equity_delta_distinct_names_bucket_11_uses_mar50_72_rho() -> None:
    """MAR50.72: rho_kl = 0.25 for distinct names in buckets 11-13."""
    capital = calculate_equity_delta_capital(
        (
            _equity_sensitivity(bucket="11", equity_name="EQ_A", amount=1_000_000.0),
            _equity_sensitivity(bucket="11", equity_name="EQ_B", amount=1_000_000.0),
        ),
    )
    ws = 1_000_000.0 * 0.70
    kb = math.sqrt(ws**2 + ws**2 + 2 * 0.25 * ws * ws)
    assert capital.bucket_capitals[0].k_b == pytest.approx(kb)


def test_equity_delta_distinct_names_bucket_12_uses_0_25_rho() -> None:
    # MAR50.72: bucket 12 (qualified index) uses rho=0.25, not large-cap 0.15.
    ws = 1_000_000.0 * 0.15  # bucket-12 risk weight
    capital = calculate_equity_delta_capital(
        (
            _equity_sensitivity(bucket="12", equity_name="IDX_A", amount=1_000_000.0),
            _equity_sensitivity(bucket="12", equity_name="IDX_B", amount=1_000_000.0),
        ),
    )
    kb = math.sqrt(ws**2 + ws**2 + 2 * 0.25 * ws * ws)
    assert capital.bucket_capitals[0].k_b == pytest.approx(kb)


def test_equity_bucket_11_cross_gamma_is_zero() -> None:
    capital = calculate_equity_delta_capital(
        (
            _equity_sensitivity(bucket="5", amount=1_000_000.0),
            _equity_sensitivity(bucket="11", amount=1_000_000.0),
        ),
    )
    kb_5 = 1_000_000.0 * 0.30
    kb_11 = 1_000_000.0 * 0.70
    expected = (kb_5**2 + kb_11**2) ** 0.5
    assert capital.post_multiplier_capital == pytest.approx(expected)


def test_equity_vega_large_cap_scalar() -> None:
    capital = calculate_equity_vega_capital(
        (
            _equity_sensitivity(
                bucket="5",
                amount=1_000_000.0,
                measure=SaCvaRiskMeasure.VEGA,
                volatility_input=0.2,
            ),
        ),
    )
    assert capital.post_multiplier_capital == pytest.approx(1_000_000.0 * 0.78 * 0.55 * 0.2)
