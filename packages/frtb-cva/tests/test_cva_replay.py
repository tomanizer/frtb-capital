from __future__ import annotations

from datetime import date

from frtb_cva import (
    CvaCalculationContext,
    CvaMethod,
    CvaRegulatoryProfile,
    SaCvaRiskClass,
    SaCvaRiskMeasure,
    SaCvaSensitivity,
    SensitivityTag,
    build_sa_cva_sensitivity_batch_from_sensitivities,
    calculate_cva_capital,
    input_hash,
    input_hash_for_cva_batches,
    profile_content_hash,
)


def test_repeated_runs_are_deterministic(
    reduced_context,
    sovereign_counterparty,
    sovereign_netting_set,
) -> None:
    first = calculate_cva_capital(
        reduced_context,
        (sovereign_counterparty,),
        (sovereign_netting_set,),
    )
    second = calculate_cva_capital(
        reduced_context,
        (sovereign_counterparty,),
        (sovereign_netting_set,),
    )
    assert first.total_cva_capital == second.total_cva_capital
    assert first.input_hash == second.input_hash
    assert first.profile_hash == profile_content_hash(CvaRegulatoryProfile.BASEL_MAR50_2020)
    assert (
        input_hash(
            reduced_context,
            (sovereign_counterparty,),
            (sovereign_netting_set,),
        )
        == first.input_hash
    )


def test_sa_cva_repeated_runs_are_deterministic() -> None:
    context = CvaCalculationContext(
        run_id="run-sa-replay",
        calculation_date=date(2026, 5, 31),
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
    sensitivity_batch = build_sa_cva_sensitivity_batch_from_sensitivities((sensitivity,))
    first = calculate_cva_capital(context, (), (), sensitivities=(sensitivity,))
    second = calculate_cva_capital(context, (), (), sensitivities=(sensitivity,))
    assert first.total_cva_capital == second.total_cva_capital
    assert first.input_hash == second.input_hash
    assert first.input_hash == input_hash_for_cva_batches(
        context,
        sensitivities=sensitivity_batch,
    )
