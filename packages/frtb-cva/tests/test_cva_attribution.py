from __future__ import annotations

from dataclasses import replace
from datetime import date

import pytest
from frtb_common.attribution import AttributionMethod, CapitalContribution, ReconciliationStatus
from frtb_cva import CvaMethod, calculate_cva_capital
from frtb_cva.attribution import attribute_cva_capital, project_cva_attribution


def _projected_total(projected: tuple[CapitalContribution, ...]) -> float:
    return sum((record.contribution or 0.0) + record.residual for record in projected)


def _records_by_method(
    projected: tuple[CapitalContribution, ...],
) -> dict[AttributionMethod, tuple[CapitalContribution, ...]]:
    return {
        method: tuple(record for record in projected if record.method is method)
        for method in AttributionMethod
    }


def test_attribution_does_not_change_capital(
    reduced_context,
    sovereign_counterparty,
    sovereign_netting_set,
) -> None:
    result = calculate_cva_capital(
        reduced_context,
        (sovereign_counterparty,),
        (sovereign_netting_set,),
    )
    attribution = attribute_cva_capital(result)
    assert attribution.total_capital == result.total_cva_capital
    assert result.method is CvaMethod.BA_CVA_REDUCED
    assert attribution.unsupported_branches


def test_attribution_ba_cva_full(
    sovereign_counterparty,
    sovereign_netting_set,
) -> None:
    from datetime import date

    from frtb_cva import (
        BaCvaHedgeType,
        CreditQuality,
        CvaCalculationContext,
        CvaHedge,
        CvaMethod,
        CvaRegulatoryProfile,
        CvaSector,
        HedgeEligibility,
        HedgeReferenceRelation,
    )

    context = CvaCalculationContext(
        run_id="run-full-1",
        calculation_date=date(2026, 5, 31),
        base_currency="USD",
        profile=CvaRegulatoryProfile.BASEL_MAR50_2020,
        method=CvaMethod.BA_CVA_FULL,
    )
    hedge = CvaHedge(
        hedge_id="hedge-1",
        source_row_id="row-hedge-1",
        counterparty_id=sovereign_counterparty.counterparty_id,
        hedge_type=BaCvaHedgeType.SINGLE_NAME_CDS,
        notional=500_000.0,
        remaining_maturity=1.0,
        discount_factor=1.0,
        reference_sector=CvaSector.SOVEREIGN,
        reference_credit_quality=CreditQuality.INVESTMENT_GRADE,
        reference_region="EMEA",
        reference_relation=HedgeReferenceRelation.DIRECT,
        eligibility=HedgeEligibility.ELIGIBLE,
        is_internal=False,
        eligibility_evidence_id="evidence-1",
    )
    result = calculate_cva_capital(
        context,
        (sovereign_counterparty,),
        (sovereign_netting_set,),
        hedges=(hedge,),
    )
    attribution = attribute_cva_capital(result)
    assert attribution.total_capital == result.total_cva_capital
    assert result.method is CvaMethod.BA_CVA_FULL
    assert "ba_cva_reduced_portfolio_sqrt" in attribution.unsupported_branches
    assert "ba_cva_hedged_sqrt" in attribution.unsupported_branches


def test_attribution_sa_cva() -> None:
    from datetime import date

    from frtb_cva import (
        CvaCalculationContext,
        CvaMethod,
        CvaRegulatoryProfile,
        SaCvaRiskClass,
        SaCvaRiskMeasure,
        SaCvaSensitivity,
        SensitivityTag,
    )

    context = CvaCalculationContext(
        run_id="run-sa-1",
        calculation_date=date(2026, 5, 31),
        base_currency="USD",
        profile=CvaRegulatoryProfile.BASEL_MAR50_2020,
        method=CvaMethod.SA_CVA,
        sa_cva_approved=True,
    )
    sens = SaCvaSensitivity(
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
        source_row_id="row-girr-5y",
    )
    result = calculate_cva_capital(
        context,
        (),
        (),
        sensitivities=(sens,),
    )
    attribution = attribute_cva_capital(result)
    assert attribution.total_capital == result.total_cva_capital
    assert result.method is CvaMethod.SA_CVA
    assert len(attribution.contributions) == 1
    assert "sa_cva_risk_class_sqrt:GIRR" in attribution.unsupported_branches


def test_project_cva_attribution_returns_capital_contributions(
    reduced_context,
    sovereign_counterparty,
    sovereign_netting_set,
) -> None:
    result = calculate_cva_capital(
        reduced_context,
        (sovereign_counterparty,),
        (sovereign_netting_set,),
    )
    attribution = attribute_cva_capital(result)
    projected = project_cva_attribution(attribution, result)
    assert isinstance(projected, tuple)
    assert all(isinstance(c, CapitalContribution) for c in projected)
    assert len(projected) > len(attribution.contributions)
    assert _projected_total(projected) == pytest.approx(result.total_cva_capital)


def test_project_cva_attribution_populates_input_hash(
    reduced_context,
    sovereign_counterparty,
    sovereign_netting_set,
) -> None:
    result = calculate_cva_capital(
        reduced_context,
        (sovereign_counterparty,),
        (sovereign_netting_set,),
    )
    attribution = attribute_cva_capital(result)
    projected = project_cva_attribution(attribution, result)
    assert all(c.input_hash == result.input_hash for c in projected)


def test_project_cva_attribution_populates_profile_hash(
    reduced_context,
    sovereign_counterparty,
    sovereign_netting_set,
) -> None:
    result = calculate_cva_capital(
        reduced_context,
        (sovereign_counterparty,),
        (sovereign_netting_set,),
    )
    attribution = attribute_cva_capital(result)
    projected = project_cva_attribution(attribution, result)
    assert all(c.profile_hash == result.profile_hash for c in projected)


def test_project_cva_attribution_reconciles_with_residual_records(
    reduced_context,
    sovereign_counterparty,
    sovereign_netting_set,
) -> None:
    result = calculate_cva_capital(
        reduced_context,
        (sovereign_counterparty,),
        (sovereign_netting_set,),
    )
    attribution = attribute_cva_capital(result)
    assert not attribution.reconciled
    projected = project_cva_attribution(attribution, result)
    by_method = _records_by_method(projected)
    assert by_method[AttributionMethod.STANDALONE]
    assert by_method[AttributionMethod.UNSUPPORTED]
    assert len(by_method[AttributionMethod.RESIDUAL]) == 1
    assert not by_method[AttributionMethod.ANALYTICAL_EULER]
    assert all(c.reconciliation_status == ReconciliationStatus.PARTIAL_RESIDUAL for c in projected)
    assert _projected_total(projected) == pytest.approx(result.total_cva_capital)
    unsupported = by_method[AttributionMethod.UNSUPPORTED][0]
    assert unsupported.bucket_key == "ba_cva_reduced_portfolio_sqrt"
    assert "square-root aggregation" in unsupported.reason


def test_project_cva_attribution_ba_full_exposes_all_unsupported_branches(
    sovereign_counterparty,
    sovereign_netting_set,
) -> None:
    from frtb_cva import (
        BaCvaHedgeType,
        CreditQuality,
        CvaCalculationContext,
        CvaHedge,
        CvaRegulatoryProfile,
        CvaSector,
        HedgeEligibility,
        HedgeReferenceRelation,
    )

    context = CvaCalculationContext(
        run_id="run-full-1",
        calculation_date=date(2026, 5, 31),
        base_currency="USD",
        profile=CvaRegulatoryProfile.BASEL_MAR50_2020,
        method=CvaMethod.BA_CVA_FULL,
    )
    hedge = CvaHedge(
        hedge_id="hedge-1",
        source_row_id="row-hedge-1",
        counterparty_id=sovereign_counterparty.counterparty_id,
        hedge_type=BaCvaHedgeType.SINGLE_NAME_CDS,
        notional=500_000.0,
        remaining_maturity=1.0,
        discount_factor=1.0,
        reference_sector=CvaSector.SOVEREIGN,
        reference_credit_quality=CreditQuality.INVESTMENT_GRADE,
        reference_region="EMEA",
        reference_relation=HedgeReferenceRelation.DIRECT,
        eligibility=HedgeEligibility.ELIGIBLE,
        is_internal=False,
        eligibility_evidence_id="evidence-1",
    )
    result = calculate_cva_capital(
        context,
        (sovereign_counterparty,),
        (sovereign_netting_set,),
        hedges=(hedge,),
    )
    attribution = attribute_cva_capital(result)
    projected = project_cva_attribution(attribution, result)
    unsupported_branches = {
        record.bucket_key for record in projected if record.method is AttributionMethod.UNSUPPORTED
    }
    assert unsupported_branches == {
        "ba_cva_reduced_portfolio_sqrt",
        "ba_cva_hedged_sqrt",
        "ba_cva_beta_floor",
    }
    assert _projected_total(projected) == pytest.approx(result.total_cva_capital)


def test_project_cva_attribution_sa_bucket_allocations_are_not_euler() -> None:
    from frtb_cva import (
        CvaCalculationContext,
        CvaRegulatoryProfile,
        SaCvaRiskClass,
        SaCvaRiskMeasure,
        SaCvaSensitivity,
        SensitivityTag,
    )

    context = CvaCalculationContext(
        run_id="run-sa-1",
        calculation_date=date(2026, 5, 31),
        base_currency="USD",
        profile=CvaRegulatoryProfile.BASEL_MAR50_2020,
        method=CvaMethod.SA_CVA,
        sa_cva_approved=True,
    )
    sens = SaCvaSensitivity(
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
        source_row_id="row-girr-5y",
    )
    result = calculate_cva_capital(context, (), (), sensitivities=(sens,))
    attribution = attribute_cva_capital(result)
    projected = project_cva_attribution(attribution, result)
    by_method = _records_by_method(projected)
    assert not by_method[AttributionMethod.ANALYTICAL_EULER]
    assert by_method[AttributionMethod.STANDALONE][0].category == "standalone_allocated"
    assert {
        record.bucket_key for record in projected if record.method is AttributionMethod.UNSUPPORTED
    } == {"sa_cva_risk_class_sqrt:GIRR"}
    assert _projected_total(projected) == pytest.approx(result.total_cva_capital)


def test_project_cva_attribution_mixed_carve_out_reconciles_projection(
    sovereign_counterparty,
    sovereign_netting_set,
) -> None:
    from frtb_cva import (
        CvaCalculationContext,
        CvaRegulatoryProfile,
        SaCvaRiskClass,
        SaCvaRiskMeasure,
        SaCvaSensitivity,
        SensitivityTag,
    )

    carved = replace(sovereign_netting_set, carved_out_to_ba_cva=True)
    context = CvaCalculationContext(
        run_id="run-mixed",
        calculation_date=date(2026, 5, 31),
        base_currency="USD",
        profile=CvaRegulatoryProfile.BASEL_MAR50_2020,
        method=CvaMethod.MIXED_CARVE_OUT,
        sa_cva_approved=True,
        carve_out_netting_set_ids=(carved.netting_set_id,),
        sa_cva_sensitivity_scope_evidence_id="attribution-sa-slice-evidence",
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
    attribution = attribute_cva_capital(result)
    projected = project_cva_attribution(attribution, result)
    unsupported_branches = {
        record.bucket_key for record in projected if record.method is AttributionMethod.UNSUPPORTED
    }
    assert unsupported_branches == {
        "ba_cva_reduced_portfolio_sqrt",
        "sa_cva_risk_class_sqrt:GIRR",
    }
    assert _projected_total(projected) == pytest.approx(result.total_cva_capital)
