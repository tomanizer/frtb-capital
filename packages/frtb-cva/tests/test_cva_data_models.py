from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest
from frtb_cva import (
    BaCvaCounterpartyCapital,
    BaCvaReducedPortfolioResult,
    BaCvaStandAloneLine,
    CreditQuality,
    CvaCalculationContext,
    CvaInputError,
    CvaMethod,
    CvaNettingSet,
    CvaRegulatoryProfile,
    CvaSector,
    SaCvaRiskClass,
    SaCvaRiskMeasure,
    SaCvaSensitivity,
    SensitivityTag,
    build_cva_netting_set_batch_from_netting_sets,
    build_sa_cva_sensitivity_batch_from_sensitivities,
)
from frtb_cva.assembly.payloads import batch_input_payload, input_payload


def test_cva_enums_have_stable_wire_values() -> None:
    assert CvaMethod.BA_CVA_REDUCED == "BA_CVA_REDUCED"
    assert CvaSector.SOVEREIGN == "SOVEREIGN"
    assert CreditQuality.INVESTMENT_GRADE == "INVESTMENT_GRADE"
    assert CvaRegulatoryProfile.BASEL_MAR50_2020 == "BASEL_MAR50_2020"


def test_ba_cva_standalone_line_is_frozen() -> None:
    line = BaCvaStandAloneLine(
        netting_set_id="ns-1",
        counterparty_id="ctp-1",
        sector=CvaSector.SOVEREIGN,
        credit_quality=CreditQuality.INVESTMENT_GRADE,
        ead=1_000_000.0,
        effective_maturity=2.5,
        discount_factor=0.975,
        alpha=1.4,
        risk_weight=0.005,
        standalone_capital=17.0625,
        currency="USD",
        source_row_id="row-1",
        citations=("basel_mar50_15",),
    )
    with pytest.raises(FrozenInstanceError):
        line.ead = 2.0  # type: ignore[misc]


def test_cva_capital_result_as_dict_uses_audit_serializer(
    reduced_context: CvaCalculationContext,
    sovereign_counterparty,
    sovereign_netting_set,
) -> None:
    from frtb_cva import calculate_cva_capital

    result = calculate_cva_capital(
        reduced_context,
        (sovereign_counterparty,),
        (sovereign_netting_set,),
    )
    payload = result.as_dict()
    assert payload["method"] == CvaMethod.BA_CVA_REDUCED.value
    assert payload["total_cva_capital"] == result.total_cva_capital


def test_reduced_portfolio_result_fields() -> None:
    counterparty = BaCvaCounterpartyCapital(
        counterparty_id="ctp-1",
        standalone_capital=100.0,
        netting_set_ids=("ns-1",),
        sector=CvaSector.SOVEREIGN,
        credit_quality=CreditQuality.INVESTMENT_GRADE,
        region="EMEA",
        citations=("basel_mar50_15",),
    )
    reduced = BaCvaReducedPortfolioResult(
        k_portfolio=65.0,
        k_reduced=42.25,
        sum_scva=100.0,
        sum_scva_squared=10_000.0,
        rho=0.5,
        d_ba_cva=0.65,
        alpha=1.4,
        counterparty_capitals=(counterparty,),
        netting_set_lines=(),
        citations=("basel_mar50_14",),
    )
    assert reduced.k_reduced == pytest.approx(reduced.d_ba_cva * reduced.k_portfolio)


def test_cva_time_series_and_surface_provenance_survives_payloads(
    reduced_context: CvaCalculationContext,
    sovereign_counterparty,
) -> None:
    netting_set = CvaNettingSet(
        netting_set_id="ns-1",
        counterparty_id=sovereign_counterparty.counterparty_id,
        ead=1_000_000.0,
        effective_maturity=2.5,
        discount_factor=0.975,
        currency="USD",
        sign_convention="non_negative",
        uses_imm_ead=False,
        source_row_id="netting-row-1",
        exposure_time_series_id="ts-cva-exposure-ns-1",
    )
    sensitivity = SaCvaSensitivity(
        sensitivity_id="sens-1",
        risk_class=SaCvaRiskClass.GIRR,
        risk_measure=SaCvaRiskMeasure.VEGA,
        sensitivity_tag=SensitivityTag.CVA,
        bucket_id="USD",
        risk_factor_key="USD_SWAPTION_5Y",
        amount=100.0,
        amount_currency="USD",
        sign_convention="positive_loss",
        source_row_id="sens-row-1",
        volatility_input=0.35,
        volatility_surface_id="surface-usd-swaption",
        volatility_surface_point_id="surface-usd-swaption:5y:atm",
        shock_id="shock-girr-vega-up",
    )

    row_payload = input_payload(
        reduced_context,
        (sovereign_counterparty,),
        (netting_set,),
        sensitivities=(sensitivity,),
    )
    batch_payload = batch_input_payload(
        reduced_context,
        netting_sets=build_cva_netting_set_batch_from_netting_sets(
            (netting_set,), counterparties=(sovereign_counterparty,)
        ),
        sensitivities=build_sa_cva_sensitivity_batch_from_sensitivities((sensitivity,)),
    )

    assert row_payload["netting_sets"][0]["exposure_time_series_id"] == ("ts-cva-exposure-ns-1")
    assert row_payload["sensitivities"][0]["volatility_surface_point_id"] == (
        "surface-usd-swaption:5y:atm"
    )
    assert batch_payload["netting_sets"][0]["exposure_time_series_id"] == ("ts-cva-exposure-ns-1")
    assert batch_payload["sensitivities"][0]["shock_id"] == "shock-girr-vega-up"


def test_cva_provenance_ids_reject_blank_row_values(
    sovereign_counterparty,
) -> None:
    bad_netting_set = CvaNettingSet(
        netting_set_id="ns-1",
        counterparty_id=sovereign_counterparty.counterparty_id,
        ead=1_000_000.0,
        effective_maturity=2.5,
        discount_factor=0.975,
        currency="USD",
        sign_convention="non_negative",
        uses_imm_ead=False,
        source_row_id="netting-row-1",
        exposure_time_series_id=" ",
    )
    bad_sensitivity = SaCvaSensitivity(
        sensitivity_id="sens-1",
        risk_class=SaCvaRiskClass.GIRR,
        risk_measure=SaCvaRiskMeasure.VEGA,
        sensitivity_tag=SensitivityTag.CVA,
        bucket_id="USD",
        risk_factor_key="RATE",
        amount=100.0,
        amount_currency="USD",
        sign_convention="positive_loss",
        source_row_id="sens-row-1",
        volatility_input=0.35,
        volatility_surface_id=" ",
    )

    with pytest.raises(CvaInputError, match="exposure_time_series_id"):
        build_cva_netting_set_batch_from_netting_sets(
            (bad_netting_set,), counterparties=(sovereign_counterparty,)
        )
    with pytest.raises(CvaInputError, match="volatility_surface_id"):
        build_sa_cva_sensitivity_batch_from_sensitivities((bad_sensitivity,))
