from __future__ import annotations

import pytest
from frtb_cva import (
    CvaInputError,
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


def _rcs_delta() -> SaCvaSensitivity:
    return SaCvaSensitivity(
        sensitivity_id="sens-rcs-delta",
        risk_class=SaCvaRiskClass.REFERENCE_CREDIT_SPREAD,
        risk_measure=SaCvaRiskMeasure.DELTA,
        sensitivity_tag=SensitivityTag.CVA,
        bucket_id="1",
        risk_factor_key="1y",
        tenor="1y",
        amount=1_000_000.0,
        amount_currency="USD",
        sign_convention="positive_loss",
        source_row_id="row-rcs-delta",
    )


def _rcs_vega() -> SaCvaSensitivity:
    return SaCvaSensitivity(
        sensitivity_id="sens-rcs-vega",
        risk_class=SaCvaRiskClass.REFERENCE_CREDIT_SPREAD,
        risk_measure=SaCvaRiskMeasure.VEGA,
        sensitivity_tag=SensitivityTag.CVA,
        bucket_id="1",
        risk_factor_key="1y",
        amount=500_000.0,
        amount_currency="USD",
        sign_convention="positive_loss",
        source_row_id="row-rcs-vega",
        volatility_input=0.3,
    )


def _equity_delta() -> SaCvaSensitivity:
    return SaCvaSensitivity(
        sensitivity_id="sens-eq-delta",
        risk_class=SaCvaRiskClass.EQUITY,
        risk_measure=SaCvaRiskMeasure.DELTA,
        sensitivity_tag=SensitivityTag.CVA,
        bucket_id="1",
        risk_factor_key="SPOT",
        amount=1_000_000.0,
        amount_currency="USD",
        sign_convention="positive_loss",
        source_row_id="row-eq-delta",
    )


def _equity_vega() -> SaCvaSensitivity:
    return SaCvaSensitivity(
        sensitivity_id="sens-eq-vega",
        risk_class=SaCvaRiskClass.EQUITY,
        risk_measure=SaCvaRiskMeasure.VEGA,
        sensitivity_tag=SensitivityTag.CVA,
        bucket_id="1",
        risk_factor_key="SPOT",
        amount=500_000.0,
        amount_currency="USD",
        sign_convention="positive_loss",
        source_row_id="row-eq-vega",
        volatility_input=0.3,
    )


def _commodity_delta() -> SaCvaSensitivity:
    return SaCvaSensitivity(
        sensitivity_id="sens-commodity-delta",
        risk_class=SaCvaRiskClass.COMMODITY,
        risk_measure=SaCvaRiskMeasure.DELTA,
        sensitivity_tag=SensitivityTag.CVA,
        bucket_id="1",
        risk_factor_key="OIL",
        amount=1_000_000.0,
        amount_currency="USD",
        sign_convention="positive_loss",
        source_row_id="row-commodity-delta",
    )


def _commodity_vega() -> SaCvaSensitivity:
    return SaCvaSensitivity(
        sensitivity_id="sens-commodity-vega",
        risk_class=SaCvaRiskClass.COMMODITY,
        risk_measure=SaCvaRiskMeasure.VEGA,
        sensitivity_tag=SensitivityTag.CVA,
        bucket_id="1",
        risk_factor_key="OIL",
        amount=500_000.0,
        amount_currency="USD",
        sign_convention="positive_loss",
        source_row_id="row-commodity-vega",
        volatility_input=0.3,
    )


def test_all_supported_sa_cva_paths() -> None:
    from frtb_cva.sa_cva import sa_cva_aggregation_config

    sens_list = [
        _girr_delta(),
        SaCvaSensitivity(
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
        ),
        _fx_delta(),
        SaCvaSensitivity(
            sensitivity_id="sens-fx-vega",
            risk_class=SaCvaRiskClass.FX,
            risk_measure=SaCvaRiskMeasure.VEGA,
            sensitivity_tag=SensitivityTag.CVA,
            bucket_id="EUR",
            risk_factor_key="SPOT",
            amount=500_000.0,
            amount_currency="USD",
            sign_convention="positive_loss",
            source_row_id="row-fx-vega",
            volatility_input=0.2,
        ),
        _rcs_delta(),
        _rcs_vega(),
        _equity_delta(),
        _equity_vega(),
        _commodity_delta(),
        _commodity_vega(),
        SaCvaSensitivity(
            sensitivity_id="sens-ccs-delta",
            risk_class=SaCvaRiskClass.COUNTERPARTY_CREDIT_SPREAD,
            risk_measure=SaCvaRiskMeasure.DELTA,
            sensitivity_tag=SensitivityTag.CVA,
            bucket_id="1a",
            risk_factor_key="ctp1|INVESTMENT_GRADE",
            tenor="5y",
            amount=1_000_000.0,
            amount_currency="USD",
            sign_convention="positive_loss",
            source_row_id="row-ccs-delta",
        ),
    ]
    results = calculate_sa_cva_capital(tuple(sens_list))
    assert len(results) == 11

    for item in sens_list:
        cfg = sa_cva_aggregation_config(item.risk_class, item.risk_measure)
        assert cfg is not None


def test_sa_cva_empty_sensitivities_fails() -> None:
    with pytest.raises(CvaInputError, match="at least one sensitivity"):
        calculate_sa_cva_capital(())


def test_sa_cva_unsupported_path_fails() -> None:
    sens_ccs_vega = SaCvaSensitivity(
        sensitivity_id="sens-ccs-vega",
        risk_class=SaCvaRiskClass.COUNTERPARTY_CREDIT_SPREAD,
        risk_measure=SaCvaRiskMeasure.VEGA,
        sensitivity_tag=SensitivityTag.CVA,
        bucket_id="1",
        risk_factor_key="ctp1|INVESTMENT_GRADE",
        amount=1_000_000.0,
        amount_currency="USD",
        sign_convention="positive_loss",
        source_row_id="row-ccs-vega",
        volatility_input=0.2,
    )
    with pytest.raises(CvaInputError, match="CCS vega capital is not permitted"):
        calculate_sa_cva_capital((sens_ccs_vega,))

    from unittest.mock import MagicMock

    mock_sens = MagicMock(spec=SaCvaSensitivity)
    mock_sens.risk_class = SaCvaRiskClass.GIRR
    mock_sens.risk_measure = MagicMock()
    mock_sens.risk_measure.value = "invalid_measure"
    # To satisfy sorted() key sorting
    mock_sens.risk_measure.__str__ = lambda x: "invalid_measure"

    with pytest.raises(CvaInputError, match="unsupported SA-CVA risk classes"):
        calculate_sa_cva_capital((mock_sens,))


def test_sa_cva_unsupported_aggregation_config_fails() -> None:
    from frtb_cva.sa_cva import sa_cva_aggregation_config

    with pytest.raises(CvaInputError, match="unsupported SA-CVA aggregation config"):
        sa_cva_aggregation_config(SaCvaRiskClass.COUNTERPARTY_CREDIT_SPREAD, SaCvaRiskMeasure.VEGA)
