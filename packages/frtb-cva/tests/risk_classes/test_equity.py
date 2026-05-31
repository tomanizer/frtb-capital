from __future__ import annotations

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


def _equity_sensitivity(
    *,
    bucket: str = "5",
    amount: float = 1_000_000.0,
    measure: SaCvaRiskMeasure = SaCvaRiskMeasure.DELTA,
    volatility_input: float | None = None,
) -> SaCvaSensitivity:
    return SaCvaSensitivity(
        sensitivity_id=f"sens-eq-{bucket}-{measure.value}",
        risk_class=SaCvaRiskClass.EQUITY,
        risk_measure=measure,
        sensitivity_tag=SensitivityTag.CVA,
        bucket_id=bucket,
        risk_factor_key="BUCKET_WIDE",
        amount=amount,
        amount_currency="USD",
        sign_convention="positive_loss",
        source_row_id=f"row-eq-{bucket}",
        volatility_input=volatility_input,
    )


def test_equity_delta_reconciles_by_bucket() -> None:
    capital = calculate_equity_delta_capital((_equity_sensitivity(bucket="5", amount=2_000_000.0),))
    assert capital.post_multiplier_capital == pytest.approx(2_000_000.0 * 0.30)


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
