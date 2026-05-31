from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest
from frtb_cva import (
    BaCvaCounterpartyCapital,
    BaCvaReducedPortfolioResult,
    BaCvaStandAloneLine,
    CreditQuality,
    CvaCalculationContext,
    CvaMethod,
    CvaRegulatoryProfile,
    CvaSector,
)


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
