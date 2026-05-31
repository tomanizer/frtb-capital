from __future__ import annotations

import math
from datetime import date

from frtb_cva import (
    CvaCalculationContext,
    CvaMethod,
    CvaRegulatoryProfile,
    SaCvaRiskClass,
    SaCvaRiskMeasure,
    SaCvaSensitivity,
    SensitivityTag,
    calculate_cva_capital,
)
from frtb_cva.aggregation import HEDGING_DISALLOWANCE_R
from frtb_cva.numeric import is_reconciled
from frtb_cva.reference_data import girr_delta_risk_weight

REFERENCE_REL_TOL = 1e-12
REFERENCE_ABS_TOL = 1e-9


def _sa_cva_context() -> CvaCalculationContext:
    return CvaCalculationContext(
        run_id="external-comparator",
        calculation_date=date(2026, 5, 31),
        base_currency="USD",
        profile=CvaRegulatoryProfile.BASEL_MAR50_2020,
        method=CvaMethod.SA_CVA,
        sa_cva_approved=True,
    )


def _girr_cva(amount: float, *, bucket: str = "USD", tenor: str = "5y") -> SaCvaSensitivity:
    return SaCvaSensitivity(
        sensitivity_id=f"sens-{bucket}-{tenor}",
        risk_class=SaCvaRiskClass.GIRR,
        risk_measure=SaCvaRiskMeasure.DELTA,
        sensitivity_tag=SensitivityTag.CVA,
        bucket_id=bucket,
        risk_factor_key=tenor,
        tenor=tenor,
        amount=amount,
        amount_currency=bucket,
        sign_convention="positive_loss",
        source_row_id=f"row-sens-{bucket}-{tenor}",
    )


def test_single_usd_5y_reconciles_to_hand_calculation() -> None:
    amount = 1_000_000.0
    risk_weight, _ = girr_delta_risk_weight("5y")
    expected = amount * risk_weight

    result = calculate_cva_capital(
        _sa_cva_context(),
        (),
        (),
        sensitivities=(_girr_cva(amount),),
    )
    assert math.isclose(
        result.total_cva_capital,
        expected,
        rel_tol=REFERENCE_REL_TOL,
        abs_tol=REFERENCE_ABS_TOL,
    )


def test_offsetting_hedge_reconciles_to_mar50_55_disallowance_floor() -> None:
    amount = 1_000_000.0
    risk_weight, _ = girr_delta_risk_weight("5y")
    weighted_hedge = amount * risk_weight
    expected = math.sqrt(HEDGING_DISALLOWANCE_R * weighted_hedge * weighted_hedge)

    from frtb_cva import (
        BaCvaHedgeType,
        CreditQuality,
        CvaHedge,
        CvaSector,
        HedgeEligibility,
        HedgeReferenceRelation,
    )

    hedge = CvaHedge(
        hedge_id="hedge-usd-5y",
        source_row_id="row-hedge-usd-5y",
        counterparty_id="ctp-1",
        hedge_type=BaCvaHedgeType.SINGLE_NAME_CDS,
        notional=amount,
        remaining_maturity=2.0,
        discount_factor=1.0,
        reference_sector=CvaSector.SOVEREIGN,
        reference_credit_quality=CreditQuality.INVESTMENT_GRADE,
        reference_region="EMEA",
        reference_relation=HedgeReferenceRelation.DIRECT,
        eligibility=HedgeEligibility.ELIGIBLE,
        is_internal=False,
        eligibility_evidence_id="evidence-hedge-usd-5y",
    )
    hedge_sensitivity = SaCvaSensitivity(
        sensitivity_id="sens-hdg-usd-5y",
        risk_class=SaCvaRiskClass.GIRR,
        risk_measure=SaCvaRiskMeasure.DELTA,
        sensitivity_tag=SensitivityTag.HDG,
        bucket_id="USD",
        risk_factor_key="5y",
        tenor="5y",
        amount=amount,
        amount_currency="USD",
        sign_convention="positive_loss",
        source_row_id="row-sens-hdg-usd-5y",
        hedge_id="hedge-usd-5y",
    )

    result = calculate_cva_capital(
        _sa_cva_context(),
        (),
        (),
        sensitivities=(_girr_cva(amount), hedge_sensitivity),
        hedges=(hedge,),
    )
    assert math.isclose(
        result.total_cva_capital,
        expected,
        rel_tol=REFERENCE_REL_TOL,
        abs_tol=REFERENCE_ABS_TOL,
    )


def test_usd_eur_two_bucket_reconciles_to_manual_inter_bucket_formula() -> None:
    risk_weight, _ = girr_delta_risk_weight("5y")
    kb_usd = 1_000_000.0 * risk_weight
    kb_eur = 500_000.0 * risk_weight
    gamma_bc = 0.5
    expected = math.sqrt(kb_usd * kb_usd + kb_eur * kb_eur + 2.0 * gamma_bc * kb_usd * kb_eur)

    result = calculate_cva_capital(
        _sa_cva_context(),
        (),
        (),
        sensitivities=(
            _girr_cva(1_000_000.0, bucket="USD"),
            _girr_cva(500_000.0, bucket="EUR"),
        ),
    )
    assert is_reconciled(result.total_cva_capital, expected)
