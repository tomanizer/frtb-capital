from __future__ import annotations

import math

import pytest
from frtb_cva import (
    SaCvaRiskClass,
    SaCvaRiskMeasure,
    SaCvaSensitivity,
    SensitivityTag,
)
from frtb_cva.risk_classes.rcs import calculate_rcs_delta_capital, calculate_rcs_vega_capital


def _rcs_sensitivity(
    *,
    bucket: str = "3",
    amount: float = 1_000_000.0,
    measure: SaCvaRiskMeasure = SaCvaRiskMeasure.DELTA,
    volatility_input: float | None = None,
) -> SaCvaSensitivity:
    return SaCvaSensitivity(
        sensitivity_id=f"sens-rcs-{bucket}-{measure.value}",
        risk_class=SaCvaRiskClass.REFERENCE_CREDIT_SPREAD,
        risk_measure=measure,
        sensitivity_tag=SensitivityTag.CVA,
        bucket_id=bucket,
        risk_factor_key="BUCKET_WIDE",
        amount=amount,
        amount_currency="USD",
        sign_convention="positive_loss",
        source_row_id=f"row-rcs-{bucket}",
        volatility_input=volatility_input,
    )


def test_rcs_delta_single_bucket_reconciles() -> None:
    capital = calculate_rcs_delta_capital((_rcs_sensitivity(bucket="3", amount=2_000_000.0),))
    assert capital.post_multiplier_capital == pytest.approx(2_000_000.0 * 0.05)


def test_rcs_cross_quality_gamma_is_halved() -> None:
    capital = calculate_rcs_delta_capital(
        (
            _rcs_sensitivity(bucket="3", amount=1_000_000.0),
            _rcs_sensitivity(bucket="10", amount=1_000_000.0),
        ),
    )
    kb_ig = 1_000_000.0 * 0.05
    kb_hy = 1_000_000.0 * 0.085
    sb_ig = kb_ig
    sb_hy = kb_hy
    gamma = 0.5
    expected = math.sqrt(kb_ig**2 + kb_hy**2 + 2 * gamma * sb_ig * sb_hy)
    assert capital.post_multiplier_capital == pytest.approx(expected)


def test_rcs_vega_reconciles() -> None:
    capital = calculate_rcs_vega_capital(
        (
            _rcs_sensitivity(
                bucket="3",
                amount=1_000_000.0,
                measure=SaCvaRiskMeasure.VEGA,
                volatility_input=0.25,
            ),
        ),
    )
    assert capital.post_multiplier_capital == pytest.approx(1_000_000.0 * 0.55 * 0.25)
