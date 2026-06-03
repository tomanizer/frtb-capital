from __future__ import annotations

from datetime import date

import pytest
from frtb_cva import (
    CreditQuality,
    CvaCalculationContext,
    CvaMethod,
    CvaRegulatoryProfile,
    CvaSector,
    calculate_cva_capital,
)
from frtb_orchestration import OrchestrationInputError, recognise_cva_summary


def test_orchestration_recognises_public_cva_result() -> None:
    from frtb_cva import CvaCounterparty, CvaNettingSet

    counterparty = CvaCounterparty(
        counterparty_id="ctp-1",
        desk_id="desk-a",
        legal_entity="LE-001",
        sector=CvaSector.SOVEREIGN,
        credit_quality=CreditQuality.INVESTMENT_GRADE,
        region="EMEA",
        source_row_id="row-ctp-1",
    )
    netting_set = CvaNettingSet(
        netting_set_id="ns-1",
        counterparty_id="ctp-1",
        ead=1_000_000.0,
        effective_maturity=1.0,
        discount_factor=1.0,
        currency="USD",
        sign_convention="non_negative",
        uses_imm_ead=True,
        source_row_id="row-ns-1",
    )
    context = CvaCalculationContext(
        run_id="orch-cva",
        calculation_date=date(2026, 5, 31),
        base_currency="USD",
        profile=CvaRegulatoryProfile.BASEL_MAR50_2020,
        method=CvaMethod.BA_CVA_REDUCED,
    )
    result = calculate_cva_capital(context, (counterparty,), (netting_set,))
    summary = recognise_cva_summary(result)
    assert summary.package_name == "frtb-cva"
    assert summary.total_cva_capital == result.total_cva_capital
    assert summary.ba_cva_reduced_total == result.ba_cva_reduced.k_reduced
    assert summary.method == result.method.value


def test_cva_summary_rejects_invalid_shape() -> None:
    with pytest.raises(OrchestrationInputError, match="missing required field"):
        recognise_cva_summary(object())
