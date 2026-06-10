from __future__ import annotations

from dataclasses import replace
from datetime import date

import pytest
from frtb_cva import (
    CvaCalculationContext,
    CvaInputError,
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
    non_carved_counterparty = replace(
        sovereign_counterparty,
        counterparty_id="ctp-sa-slice",
        source_row_id="row-ctp-sa-slice",
    )
    non_carved = replace(
        sovereign_netting_set,
        netting_set_id="ns-sa-slice",
        counterparty_id=non_carved_counterparty.counterparty_id,
        source_row_id="row-ns-sa-slice",
    )
    context = CvaCalculationContext(
        run_id="run-mixed",
        calculation_date=date(2026, 5, 31),
        base_currency="USD",
        profile=CvaRegulatoryProfile.BASEL_MAR50_2020,
        method=CvaMethod.MIXED_CARVE_OUT,
        sa_cva_approved=True,
        carve_out_netting_set_ids=(carved.netting_set_id,),
        sa_cva_sensitivity_scope_evidence_id="sa-slice-non-carved-ledger-2026-05-31",
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
        (sovereign_counterparty, non_carved_counterparty),
        (carved, non_carved),
        sensitivities=(sensitivity,),
    )
    assert result.method is CvaMethod.MIXED_CARVE_OUT
    assert len(result.method_components) == 2
    assert (
        "sa_cva_sensitivity_scope_evidence_id",
        "sa-slice-non-carved-ledger-2026-05-31",
    ) in result.audit_metadata
    assert result.ba_cva_reduced is not None
    assert {line.netting_set_id for line in result.ba_cva_reduced.netting_set_lines} == {
        carved.netting_set_id
    }
    assert result.total_cva_capital == pytest.approx(
        sum(component.total_capital for component in result.method_components)
    )
    validate_cva_result_reconciliation(result)


def test_mixed_carve_out_rejects_unaudited_sa_sensitivity_scope(
    sovereign_counterparty,
    sovereign_netting_set,
) -> None:
    carved = replace(sovereign_netting_set, carved_out_to_ba_cva=True)
    context = CvaCalculationContext(
        run_id="run-mixed-double-count",
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

    with pytest.raises(CvaInputError, match="sensitivity scope evidence"):
        calculate_cva_capital(
            context,
            (sovereign_counterparty,),
            (carved,),
            sensitivities=(sensitivity,),
        )
