from __future__ import annotations

import math

import pytest
from frtb_cva import (
    SaCvaRiskClass,
    SaCvaRiskMeasure,
    SaCvaSensitivity,
    SensitivityTag,
)
from frtb_cva.risk_classes.girr import calculate_girr_delta_capital, calculate_girr_vega_capital
from frtb_cva.sa_cva_reference_data import GIRR_VEGA_INFLATION_FACTOR, GIRR_VEGA_RATE_FACTOR
from frtb_cva.validation import CvaInputError


def _girr_delta(
    bucket: str = "USD", tenor: str = "5y", amount: float = 1_000_000.0
) -> SaCvaSensitivity:
    return SaCvaSensitivity(
        sensitivity_id=f"sens-girr-{bucket}-{tenor}",
        risk_class=SaCvaRiskClass.GIRR,
        risk_measure=SaCvaRiskMeasure.DELTA,
        sensitivity_tag=SensitivityTag.CVA,
        bucket_id=bucket,
        risk_factor_key=tenor,
        tenor=tenor,
        amount=amount,
        amount_currency="USD",
        sign_convention="positive_loss",
        source_row_id=f"row-girr-{bucket}-{tenor}",
    )


def _girr_vega(
    bucket: str = "USD",
    factor: str = GIRR_VEGA_RATE_FACTOR,
    amount: float = 1_000_000.0,
    volatility_input: float = 0.2,
) -> SaCvaSensitivity:
    return SaCvaSensitivity(
        sensitivity_id=f"sens-girr-vega-{bucket}-{factor}",
        risk_class=SaCvaRiskClass.GIRR,
        risk_measure=SaCvaRiskMeasure.VEGA,
        sensitivity_tag=SensitivityTag.CVA,
        bucket_id=bucket,
        risk_factor_key=factor,
        amount=amount,
        amount_currency="USD",
        sign_convention="positive_loss",
        source_row_id=f"row-girr-vega-{bucket}-{factor}",
        volatility_input=volatility_input,
    )


def test_girr_delta_unchanged() -> None:
    capital = calculate_girr_delta_capital((_girr_delta(amount=2_000_000.0),))
    assert capital.post_multiplier_capital == pytest.approx(2_000_000.0 * 0.0074)


def test_girr_vega_single_factor_reconciles() -> None:
    capital = calculate_girr_vega_capital((_girr_vega(amount=1_000_000.0, volatility_input=0.2),))
    assert capital.post_multiplier_capital == pytest.approx(1_000_000.0 * 0.55 * 0.2)


def test_girr_vega_inflation_and_rate_correlation() -> None:
    capital = calculate_girr_vega_capital(
        (
            _girr_vega(factor=GIRR_VEGA_RATE_FACTOR, amount=1_000_000.0, volatility_input=0.2),
            _girr_vega(factor=GIRR_VEGA_INFLATION_FACTOR, amount=1_000_000.0, volatility_input=0.2),
        ),
    )
    ws = 1_000_000.0 * 0.55 * 0.2
    kb = math.sqrt(ws**2 + ws**2 + 2 * 0.4 * ws * ws)
    assert capital.bucket_capitals[0].k_b == pytest.approx(kb)


def test_girr_vega_missing_volatility_fails_validation() -> None:
    with pytest.raises(CvaInputError, match="volatility_input"):
        calculate_girr_vega_capital(
            (
                SaCvaSensitivity(
                    sensitivity_id="sens-girr-vega-missing-vol",
                    risk_class=SaCvaRiskClass.GIRR,
                    risk_measure=SaCvaRiskMeasure.VEGA,
                    sensitivity_tag=SensitivityTag.CVA,
                    bucket_id="USD",
                    risk_factor_key=GIRR_VEGA_RATE_FACTOR,
                    amount=1_000_000.0,
                    amount_currency="USD",
                    sign_convention="positive_loss",
                    source_row_id="row-girr-vega-missing-vol",
                ),
            ),
        )
