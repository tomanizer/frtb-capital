from __future__ import annotations

import pytest
from frtb_cva import (
    SaCvaRiskClass,
    SaCvaRiskMeasure,
    SaCvaSensitivity,
    SensitivityTag,
)
from frtb_cva.sa_cva import calculate_sa_cva_capital
from frtb_cva.sa_cva_reference_data import GIRR_VEGA_RATE_FACTOR


def _girr_delta(amount: float = 1_000_000.0) -> SaCvaSensitivity:
    return SaCvaSensitivity(
        sensitivity_id="sens-girr-5y",
        risk_class=SaCvaRiskClass.GIRR,
        risk_measure=SaCvaRiskMeasure.DELTA,
        sensitivity_tag=SensitivityTag.CVA,
        bucket_id="USD",
        risk_factor_key="5y",
        tenor="5y",
        amount=amount,
        amount_currency="USD",
        sign_convention="positive_loss",
        source_row_id="row-girr-5y",
    )


def _fx_delta(amount: float = 1_000_000.0) -> SaCvaSensitivity:
    return SaCvaSensitivity(
        sensitivity_id="sens-fx-eur",
        risk_class=SaCvaRiskClass.FX,
        risk_measure=SaCvaRiskMeasure.DELTA,
        sensitivity_tag=SensitivityTag.CVA,
        bucket_id="EUR",
        risk_factor_key="SPOT",
        amount=amount,
        amount_currency="USD",
        sign_convention="positive_loss",
        source_row_id="row-fx-eur",
    )


def test_sa_cva_total_sums_supported_risk_classes() -> None:
    """MAR50.42: total SA-CVA equals sum of supported risk-class capitals."""

    girr = _girr_delta(amount=1_000_000.0)
    fx = _fx_delta(amount=1_000_000.0)
    risk_classes = calculate_sa_cva_capital((girr, fx), reporting_currency="USD")
    assert len(risk_classes) == 2
    total = sum(item.post_multiplier_capital for item in risk_classes)
    girr_capital = next(item for item in risk_classes if item.risk_class is SaCvaRiskClass.GIRR)
    fx_capital = next(item for item in risk_classes if item.risk_class is SaCvaRiskClass.FX)
    assert total == pytest.approx(
        girr_capital.post_multiplier_capital + fx_capital.post_multiplier_capital
    )


def test_sa_cva_delta_and_vega_paths_sum() -> None:
    girr_delta = _girr_delta(amount=1_000_000.0)
    girr_vega = SaCvaSensitivity(
        sensitivity_id="sens-girr-vega",
        risk_class=SaCvaRiskClass.GIRR,
        risk_measure=SaCvaRiskMeasure.VEGA,
        sensitivity_tag=SensitivityTag.CVA,
        bucket_id="USD",
        risk_factor_key=GIRR_VEGA_RATE_FACTOR,
        amount=500_000.0,
        amount_currency="USD",
        sign_convention="positive_loss",
        source_row_id="row-girr-vega",
        volatility_input=0.2,
    )
    risk_classes = calculate_sa_cva_capital((girr_delta, girr_vega))
    assert len(risk_classes) == 2
    total = sum(item.post_multiplier_capital for item in risk_classes)
    assert total > 0.0
