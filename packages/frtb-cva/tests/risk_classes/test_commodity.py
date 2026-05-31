from __future__ import annotations

import math

import pytest
from frtb_cva import (
    SaCvaRiskClass,
    SaCvaRiskMeasure,
    SaCvaSensitivity,
    SensitivityTag,
)
from frtb_cva.risk_classes.commodity import (
    calculate_commodity_delta_capital,
    calculate_commodity_vega_capital,
)
from frtb_cva.validation import CvaInputError


def _commodity_sensitivity(
    *,
    bucket: str = "1",
    commodity_name: str = "COM_A",
    amount: float = 1_000_000.0,
    measure: SaCvaRiskMeasure = SaCvaRiskMeasure.DELTA,
    volatility_input: float | None = None,
) -> SaCvaSensitivity:
    return SaCvaSensitivity(
        sensitivity_id=f"sens-com-{bucket}-{commodity_name}-{measure.value}",
        risk_class=SaCvaRiskClass.COMMODITY,
        risk_measure=measure,
        sensitivity_tag=SensitivityTag.CVA,
        bucket_id=bucket,
        risk_factor_key=commodity_name,
        amount=amount,
        amount_currency="USD",
        sign_convention="positive_loss",
        source_row_id=f"row-com-{bucket}",
        volatility_input=volatility_input,
    )


def test_commodity_delta_rejects_empty() -> None:
    with pytest.raises(CvaInputError):
        calculate_commodity_delta_capital(())


def test_commodity_delta_reconciles() -> None:
    capital = calculate_commodity_delta_capital(
        (_commodity_sensitivity(bucket="1", amount=2_000_000.0),)
    )
    assert capital.post_multiplier_capital == pytest.approx(2_000_000.0 * 0.30)


def test_commodity_delta_distinct_names_use_mar50_76_rho() -> None:
    """MAR50.76: rho_kl = 0.20 when commodity names differ within the same bucket."""
    capital = calculate_commodity_delta_capital(
        (
            _commodity_sensitivity(bucket="1", commodity_name="COM_A", amount=1_000_000.0),
            _commodity_sensitivity(bucket="1", commodity_name="COM_B", amount=1_000_000.0),
        ),
    )
    ws = 1_000_000.0 * 0.30
    kb = math.sqrt(ws**2 + ws**2 + 2 * 0.20 * ws * ws)
    assert capital.bucket_capitals[0].k_b == pytest.approx(kb)


def test_commodity_bucket_11_cross_gamma_is_zero() -> None:
    capital = calculate_commodity_delta_capital(
        (
            _commodity_sensitivity(bucket="1", amount=1_000_000.0),
            _commodity_sensitivity(bucket="11", amount=1_000_000.0),
        ),
    )
    kb_1 = 1_000_000.0 * 0.30
    kb_11 = 1_000_000.0 * 0.50
    assert capital.post_multiplier_capital == pytest.approx((kb_1**2 + kb_11**2) ** 0.5)


def test_commodity_vega_reconciles() -> None:
    capital = calculate_commodity_vega_capital(
        (
            _commodity_sensitivity(
                bucket="1",
                amount=1_000_000.0,
                measure=SaCvaRiskMeasure.VEGA,
                volatility_input=0.3,
            ),
        ),
    )
    assert capital.post_multiplier_capital == pytest.approx(1_000_000.0 * 0.55 * 0.3)
