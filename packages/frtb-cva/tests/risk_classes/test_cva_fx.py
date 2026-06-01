from __future__ import annotations

import math

import pytest
from frtb_cva import (
    SaCvaRiskClass,
    SaCvaRiskMeasure,
    SaCvaSensitivity,
    SensitivityTag,
)
from frtb_cva.risk_classes.fx import calculate_fx_delta_capital, calculate_fx_vega_capital
from frtb_cva.validation import CvaInputError


def _fx_sensitivity(
    *,
    bucket: str = "EUR",
    amount: float = 1_000_000.0,
    measure: SaCvaRiskMeasure = SaCvaRiskMeasure.DELTA,
    volatility_input: float | None = None,
) -> SaCvaSensitivity:
    return SaCvaSensitivity(
        sensitivity_id=f"sens-fx-{bucket}-{measure.value}",
        risk_class=SaCvaRiskClass.FX,
        risk_measure=measure,
        sensitivity_tag=SensitivityTag.CVA,
        bucket_id=bucket,
        risk_factor_key="SPOT",
        amount=amount,
        amount_currency="USD",
        sign_convention="positive_loss",
        source_row_id=f"row-fx-{bucket}",
        volatility_input=volatility_input,
    )


def test_fx_delta_single_bucket_reconciles() -> None:
    capital = calculate_fx_delta_capital(
        (_fx_sensitivity(bucket="EUR", amount=2_000_000.0),),
        reporting_currency="USD",
    )
    assert capital.post_multiplier_capital == pytest.approx(2_000_000.0 * 0.11)
    assert len(capital.bucket_capitals) == 1
    assert capital.bucket_capitals[0].bucket_id == "EUR"


def test_fx_delta_multi_bucket_uses_gamma_bc() -> None:
    capital = calculate_fx_delta_capital(
        (
            _fx_sensitivity(bucket="EUR", amount=1_000_000.0),
            _fx_sensitivity(bucket="GBP", amount=1_000_000.0),
        ),
        reporting_currency="USD",
    )
    kb_eur = 1_000_000.0 * 0.11
    kb_gbp = 1_000_000.0 * 0.11
    sb = 1_000_000.0 * 0.11
    expected = math.sqrt(kb_eur**2 + kb_gbp**2 + 2 * 0.6 * sb * sb)
    assert capital.post_multiplier_capital == pytest.approx(expected)


def test_fx_delta_rejects_reporting_currency_bucket() -> None:
    with pytest.raises(CvaInputError, match="reporting currency"):
        calculate_fx_delta_capital(
            (_fx_sensitivity(bucket="USD"),),
            reporting_currency="USD",
        )


def test_fx_vega_requires_volatility_input_at_validation() -> None:
    with pytest.raises(CvaInputError, match="volatility_input"):
        calculate_fx_vega_capital((_fx_sensitivity(bucket="EUR", measure=SaCvaRiskMeasure.VEGA),))


def test_fx_vega_reconciles_with_rw_sigma() -> None:
    capital = calculate_fx_vega_capital(
        (
            _fx_sensitivity(
                bucket="EUR",
                amount=1_000_000.0,
                measure=SaCvaRiskMeasure.VEGA,
                volatility_input=0.2,
            ),
        ),
    )
    assert capital.post_multiplier_capital == pytest.approx(1_000_000.0 * 0.55 * 0.2)
