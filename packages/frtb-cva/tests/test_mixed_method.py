from __future__ import annotations

from dataclasses import replace
from datetime import date

import pytest
from frtb_cva import (
    CvaCalculationContext,
    CvaMethod,
    CvaRegulatoryProfile,
    SaCvaRiskClass,
    SaCvaRiskMeasure,
    SaCvaSensitivity,
    SensitivityTag,
    calculate_cva_capital,
    validate_cva_result_reconciliation,
)


def test_mixed_carve_out_sums_components(
    sovereign_counterparty,
    sovereign_netting_set,
) -> None:
    carved = replace(sovereign_netting_set, carved_out_to_ba_cva=True)
    context = CvaCalculationContext(
        run_id="run-mixed",
        calculation_date=date(2026, 5, 31),
        base_currency="USD",
        profile=CvaRegulatoryProfile.BASEL_MAR50_2020,
        method=CvaMethod.MIXED_CARVE_OUT,
        sa_cva_approved=True,
        carve_out_netting_set_ids=(carved.netting_set_id,),
    )
    sensitivity = SaCvaSensitivity(
        sensitivity_id="sens-girr-5y",
        risk_class=SaCvaRiskClass.GIRR,
        risk_measure=SaCvaRiskMeasure.DELTA,
        sensitivity_tag=SensitivityTag.CVA,
        bucket_id="USD",
        risk_factor_key="5y",
        tenor="5y",
        amount=1_000_000.0,
        amount_currency="USD",
        sign_convention="positive_loss",
        source_row_id="row-sens-girr-5y",
    )
    result = calculate_cva_capital(
        context,
        (sovereign_counterparty,),
        (carved,),
        sensitivities=(sensitivity,),
    )
    assert result.method is CvaMethod.MIXED_CARVE_OUT
    assert len(result.method_components) == 2
    assert result.total_cva_capital == pytest.approx(
        sum(component.total_capital for component in result.method_components)
    )
    validate_cva_result_reconciliation(result)
