from __future__ import annotations

from dataclasses import replace
from datetime import date

import pytest
from frtb_common import UnsupportedRegulatoryFeatureError
from frtb_cva import (
    BaCvaHedgeType,
    CreditQuality,
    CvaCalculationContext,
    CvaHedge,
    CvaMethod,
    CvaNettingSet,
    CvaRegulatoryProfile,
    CvaSector,
    HedgeEligibility,
    HedgeReferenceRelation,
    SaCvaRiskClass,
    SaCvaRiskMeasure,
    SaCvaSensitivity,
    SensitivityTag,
    build_cva_counterparty_batch_from_counterparties,
    build_cva_hedge_batch_from_hedges,
    build_cva_netting_set_batch_from_netting_sets,
    calculate_cva_capital,
    calculate_cva_capital_from_batches,
    profile_content_hash,
    validate_cva_result_reconciliation,
)

_PROFILE_BA_CITATIONS = {
    CvaRegulatoryProfile.US_NPR20_VB: "us_npr20_vb_ba_cva",
    CvaRegulatoryProfile.EU_CRR3_CVA: "eu_crr3_article_384",
    CvaRegulatoryProfile.UK_PRA_CVA: "uk_pra_cva_risk_ba",
}
_PROFILE_HEDGE_CITATIONS = {
    CvaRegulatoryProfile.US_NPR20_VB: "us_npr20_vb_hedges",
    CvaRegulatoryProfile.EU_CRR3_CVA: "eu_crr3_article_386",
    CvaRegulatoryProfile.UK_PRA_CVA: "uk_pra_cva_risk_hedges",
}
_PROFILE_SA_CITATIONS = {
    CvaRegulatoryProfile.US_NPR20_VB: "us_npr20_vb_sa_cva",
    CvaRegulatoryProfile.EU_CRR3_CVA: "eu_crr3_articles_383a_383z",
    CvaRegulatoryProfile.UK_PRA_CVA: "uk_pra_cva_risk_sa",
}


def test_materiality_threshold_fails_at_public_api(
    reduced_context,
    sovereign_counterparty,
    sovereign_netting_set,
) -> None:
    context = CvaCalculationContext(
        run_id=reduced_context.run_id,
        calculation_date=reduced_context.calculation_date,
        base_currency=reduced_context.base_currency,
        profile=reduced_context.profile,
        method=CvaMethod.BA_CVA_REDUCED,
        materiality_threshold_elected=True,
    )
    with pytest.raises(UnsupportedRegulatoryFeatureError, match=r"MAR50\.9"):
        calculate_cva_capital(context, (sovereign_counterparty,), (sovereign_netting_set,))


@pytest.mark.parametrize("profile", list(_PROFILE_SA_CITATIONS))
def test_non_basel_profiles_calculate_sa_cva_at_public_api(
    profile: CvaRegulatoryProfile,
) -> None:
    context = CvaCalculationContext(
        run_id=f"run-{profile.value.lower()}-sa",
        calculation_date=date(2026, 5, 31),
        base_currency="USD",
        profile=profile,
        method=CvaMethod.SA_CVA,
        sa_cva_approved=True,
    )
    sensitivity = _girr_delta_sensitivity()
    result = calculate_cva_capital(context, (), (), sensitivities=(sensitivity,))
    assert result.profile_id == profile.value
    assert result.profile_hash == profile_content_hash(profile)
    assert result.total_cva_capital > 0.0
    assert _PROFILE_SA_CITATIONS[profile] in result.citations
    assert not any(citation.startswith("basel_") for citation in result.citations)


@pytest.mark.parametrize(
    ("profile", "citation_id"),
    [(profile, citation_id) for profile, citation_id in _PROFILE_BA_CITATIONS.items()],
)
def test_non_basel_profiles_calculate_ba_cva_reduced_at_public_api(
    reduced_context,
    sovereign_counterparty,
    sovereign_netting_set,
    profile: CvaRegulatoryProfile,
    citation_id: str,
) -> None:
    context = CvaCalculationContext(
        run_id=f"run-{profile.value.lower()}-ba",
        calculation_date=reduced_context.calculation_date,
        base_currency=reduced_context.base_currency,
        profile=profile,
        method=CvaMethod.BA_CVA_REDUCED,
    )
    result = calculate_cva_capital(context, (sovereign_counterparty,), (sovereign_netting_set,))
    assert result.profile_id == profile.value
    assert result.profile_hash == profile_content_hash(profile)
    assert result.total_cva_capital > 0.0
    assert citation_id in result.citations
    assert not any(citation.startswith("basel_") for citation in result.citations)


@pytest.mark.parametrize("profile", list(_PROFILE_BA_CITATIONS))
def test_non_basel_profiles_calculate_ba_cva_full_with_eligible_hedge(
    reduced_context,
    sovereign_counterparty,
    sovereign_netting_set,
    profile: CvaRegulatoryProfile,
) -> None:
    context = CvaCalculationContext(
        run_id=f"run-{profile.value.lower()}-full",
        calculation_date=reduced_context.calculation_date,
        base_currency=reduced_context.base_currency,
        profile=profile,
        method=CvaMethod.BA_CVA_FULL,
    )
    hedge = replace(
        _eligible_direct_hedge(sovereign_counterparty.counterparty_id),
        lineage=sovereign_counterparty.lineage,
    )

    result = calculate_cva_capital(
        context,
        (sovereign_counterparty,),
        (sovereign_netting_set,),
        hedges=(hedge,),
    )

    assert result.profile_id == profile.value
    assert result.ba_cva_full is not None
    assert result.total_cva_capital == result.ba_cva_full.k_full
    assert result.ba_cva_full.hedge_lines[0].snh_contribution > 0.0
    assert _PROFILE_BA_CITATIONS[profile] in result.citations
    assert _PROFILE_HEDGE_CITATIONS[profile] in result.citations
    assert not any(citation.startswith("basel_") for citation in result.citations)
    validate_cva_result_reconciliation(result)


@pytest.mark.parametrize("profile", list(_PROFILE_HEDGE_CITATIONS))
def test_non_basel_profiles_reject_ineligible_ba_cva_hedge_with_profile_citation(
    reduced_context,
    sovereign_counterparty,
    sovereign_netting_set,
    profile: CvaRegulatoryProfile,
) -> None:
    context = CvaCalculationContext(
        run_id=f"run-{profile.value.lower()}-ineligible-hedge",
        calculation_date=reduced_context.calculation_date,
        base_currency=reduced_context.base_currency,
        profile=profile,
        method=CvaMethod.BA_CVA_FULL,
    )
    hedge = replace(
        _eligible_direct_hedge(sovereign_counterparty.counterparty_id),
        hedge_id="hedge-ineligible",
        source_row_id="row-hedge-ineligible",
        eligibility=HedgeEligibility.INELIGIBLE,
        eligibility_evidence_id=None,
        rejection_reason="synthetic_ineligible_profile_fixture",
    )

    result = calculate_cva_capital(
        context,
        (sovereign_counterparty,),
        (sovereign_netting_set,),
        hedges=(hedge,),
    )

    assert result.ba_cva_full is not None
    assert result.ba_cva_full.hedge_lines[0].snh_contribution == 0.0
    assert result.ba_cva_full.hedge_lines[0].reason_code == "synthetic_ineligible_profile_fixture"
    assert _PROFILE_HEDGE_CITATIONS[profile] in result.citations
    assert not any(citation.startswith("basel_") for citation in result.citations)


@pytest.mark.parametrize("profile", list(_PROFILE_SA_CITATIONS))
def test_non_basel_profiles_calculate_mixed_carve_out(
    reduced_context,
    sovereign_counterparty,
    sovereign_netting_set,
    profile: CvaRegulatoryProfile,
) -> None:
    carved = _carved_out(sovereign_netting_set)
    context = CvaCalculationContext(
        run_id=f"run-{profile.value.lower()}-mixed",
        calculation_date=reduced_context.calculation_date,
        base_currency=reduced_context.base_currency,
        profile=profile,
        method=CvaMethod.MIXED_CARVE_OUT,
        sa_cva_approved=True,
        carve_out_netting_set_ids=(carved.netting_set_id,),
        sa_cva_sensitivity_scope_evidence_id=f"{profile.value.lower()}-sa-slice-evidence",
    )

    result = calculate_cva_capital(
        context,
        (sovereign_counterparty,),
        (carved,),
        sensitivities=(_girr_delta_sensitivity(),),
    )

    assert result.method is CvaMethod.MIXED_CARVE_OUT
    assert result.profile_id == profile.value
    assert {component.method for component in result.method_components} == {
        CvaMethod.BA_CVA_REDUCED,
        CvaMethod.SA_CVA,
    }
    assert result.total_cva_capital == pytest.approx(
        sum(component.total_capital for component in result.method_components)
    )
    assert _PROFILE_BA_CITATIONS[profile] in result.citations
    assert _PROFILE_SA_CITATIONS[profile] in result.citations
    assert not any(citation.startswith("basel_") for citation in result.citations)
    validate_cva_result_reconciliation(result)


@pytest.mark.parametrize("profile", list(_PROFILE_BA_CITATIONS))
def test_non_basel_profiles_calculate_full_ba_cva_batch_path(
    reduced_context,
    sovereign_counterparty,
    sovereign_netting_set,
    profile: CvaRegulatoryProfile,
) -> None:
    context = CvaCalculationContext(
        run_id=f"run-{profile.value.lower()}-batch-full",
        calculation_date=reduced_context.calculation_date,
        base_currency=reduced_context.base_currency,
        profile=profile,
        method=CvaMethod.BA_CVA_FULL,
    )
    hedge = replace(
        _eligible_direct_hedge(sovereign_counterparty.counterparty_id),
        lineage=sovereign_counterparty.lineage,
    )

    calc = calculate_cva_capital_from_batches(
        context,
        build_cva_counterparty_batch_from_counterparties((sovereign_counterparty,)),
        build_cva_netting_set_batch_from_netting_sets(
            (sovereign_netting_set,),
            counterparties=(sovereign_counterparty,),
        ),
        hedges=build_cva_hedge_batch_from_hedges((hedge,)),
    )

    assert calc.result.profile_id == profile.value
    assert calc.result.ba_cva_full is not None
    assert _PROFILE_BA_CITATIONS[profile] in calc.result.citations
    assert _PROFILE_HEDGE_CITATIONS[profile] in calc.result.citations
    assert not any(citation.startswith("basel_") for citation in calc.result.citations)
    validate_cva_result_reconciliation(calc.result)


def test_ccs_vega_fails_at_public_api() -> None:
    from frtb_cva import CvaInputError

    context = CvaCalculationContext(
        run_id="run-ccs-vega",
        calculation_date=date(2026, 5, 31),
        base_currency="USD",
        profile=CvaRegulatoryProfile.BASEL_MAR50_2020,
        method=CvaMethod.SA_CVA,
        sa_cva_approved=True,
    )
    sensitivity = SaCvaSensitivity(
        sensitivity_id="sens-ccs-vega",
        risk_class=SaCvaRiskClass.COUNTERPARTY_CREDIT_SPREAD,
        risk_measure=SaCvaRiskMeasure.VEGA,
        sensitivity_tag=SensitivityTag.CVA,
        bucket_id="2",
        risk_factor_key="CP1|INVESTMENT_GRADE",
        tenor="5y",
        amount=1_000_000.0,
        amount_currency="USD",
        sign_convention="positive_loss",
        source_row_id="row-sens-ccs-vega",
        volatility_input=0.2,
    )
    with pytest.raises(CvaInputError, match="CCS vega"):
        calculate_cva_capital(context, (), (), sensitivities=(sensitivity,))


def _girr_delta_sensitivity() -> SaCvaSensitivity:
    return SaCvaSensitivity(
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


def _eligible_direct_hedge(counterparty_id: str) -> CvaHedge:
    return CvaHedge(
        hedge_id="hedge-direct",
        source_row_id="row-hedge-direct",
        counterparty_id=counterparty_id,
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
        eligibility_evidence_id="evidence-direct-hedge",
    )


def _carved_out(netting_set: CvaNettingSet) -> CvaNettingSet:
    return replace(netting_set, carved_out_to_ba_cva=True)
