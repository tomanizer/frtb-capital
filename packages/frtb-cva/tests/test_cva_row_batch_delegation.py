from __future__ import annotations

from dataclasses import replace
from datetime import date

import pytest
from frtb_common import UnsupportedRegulatoryFeatureError
from frtb_cva import (
    CvaCalculationContext,
    CvaMethod,
    CvaRegulatoryProfile,
    SaCvaRiskClass,
    SaCvaRiskMeasure,
    SaCvaSensitivity,
    SensitivityTag,
    build_cva_counterparty_batch_from_counterparties,
    build_cva_netting_set_batch_from_netting_sets,
    build_sa_cva_sensitivity_batch_from_sensitivities,
    calculate_cva_capital,
    calculate_cva_capital_from_batches,
)


def test_row_ba_reduced_entrypoint_uses_canonical_batch_hash(
    sovereign_counterparty,
    sovereign_netting_set,
) -> None:
    context = CvaCalculationContext(
        run_id="run-row-batch-ba-reduced",
        calculation_date=date(2026, 6, 10),
        base_currency="USD",
        profile=CvaRegulatoryProfile.BASEL_MAR50_2020,
        method=CvaMethod.BA_CVA_REDUCED,
    )

    row_result = calculate_cva_capital(
        context,
        (sovereign_counterparty,),
        (sovereign_netting_set,),
    )
    batch_result = calculate_cva_capital_from_batches(
        context,
        build_cva_counterparty_batch_from_counterparties((sovereign_counterparty,)),
        build_cva_netting_set_batch_from_netting_sets(
            (sovereign_netting_set,),
            counterparties=(sovereign_counterparty,),
        ),
    ).result

    assert row_result.input_hash == batch_result.input_hash
    assert row_result.total_cva_capital == batch_result.total_cva_capital


def test_row_sa_entrypoint_uses_canonical_batch_hash() -> None:
    context = CvaCalculationContext(
        run_id="run-row-batch-sa",
        calculation_date=date(2026, 6, 10),
        base_currency="USD",
        profile=CvaRegulatoryProfile.BASEL_MAR50_2020,
        method=CvaMethod.SA_CVA,
        sa_cva_approved=True,
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

    row_result = calculate_cva_capital(context, (), (), sensitivities=(sensitivity,))
    batch_result = calculate_cva_capital_from_batches(
        context,
        sensitivities=build_sa_cva_sensitivity_batch_from_sensitivities((sensitivity,)),
    ).result

    assert row_result.input_hash == batch_result.input_hash
    assert row_result.total_cva_capital == batch_result.total_cva_capital


def test_materiality_threshold_fails_closed_in_row_and_batch_paths(
    reduced_context,
    sovereign_counterparty,
    sovereign_netting_set,
) -> None:
    context = replace(reduced_context, materiality_threshold_elected=True)
    counterparty_batch = build_cva_counterparty_batch_from_counterparties(
        (sovereign_counterparty,),
    )
    netting_set_batch = build_cva_netting_set_batch_from_netting_sets(
        (sovereign_netting_set,),
        counterparties=(sovereign_counterparty,),
    )

    with pytest.raises(UnsupportedRegulatoryFeatureError, match=r"MAR50\.9"):
        calculate_cva_capital(
            context,
            (sovereign_counterparty,),
            (sovereign_netting_set,),
        )

    with pytest.raises(UnsupportedRegulatoryFeatureError, match=r"MAR50\.9"):
        calculate_cva_capital_from_batches(context, counterparty_batch, netting_set_batch)
