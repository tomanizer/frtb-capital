from __future__ import annotations

from datetime import date

from hypothesis import given
from hypothesis import strategies as st

from frtb_cva import (
    CreditQuality,
    CvaCalculationContext,
    CvaCounterparty,
    CvaMethod,
    CvaNettingSet,
    CvaRegulatoryProfile,
    CvaSector,
    CvaSourceLineage,
    SaCvaRiskClass,
    SaCvaRiskMeasure,
    SaCvaSensitivity,
    SensitivityTag,
    calculate_cva_capital,
    calculate_reduced_portfolio,
    input_hash,
)
from frtb_cva.aggregation import aggregate_intra_bucket
from frtb_cva.numeric import is_reconciled
from frtb_cva.weighted_sensitivity import compute_weighted_sensitivities

POSITIVE_EAD = st.floats(
    min_value=1.0,
    max_value=50_000_000.0,
    allow_nan=False,
    allow_infinity=False,
    width=32,
)
POSITIVE_AMOUNT = st.floats(
    min_value=1.0,
    max_value=10_000_000.0,
    allow_nan=False,
    allow_infinity=False,
    width=32,
)


def _lineage(row_id: str) -> CvaSourceLineage:
    return CvaSourceLineage(
        source_system="hypothesis",
        source_file="generated",
        source_row_id=row_id,
        source_column_map=(("EAD", "ead"),),
    )


def _counterparty() -> CvaCounterparty:
    return CvaCounterparty(
        counterparty_id="ctp-prop",
        desk_id="desk-a",
        legal_entity="LE-001",
        sector=CvaSector.SOVEREIGN,
        credit_quality=CreditQuality.INVESTMENT_GRADE,
        region="EMEA",
        source_row_id="row-ctp-prop",
        lineage=_lineage("row-ctp-prop"),
    )


def _netting_set(ead: float) -> CvaNettingSet:
    return CvaNettingSet(
        netting_set_id="ns-prop",
        counterparty_id="ctp-prop",
        ead=ead,
        effective_maturity=2.5,
        discount_factor=1.0,
        uses_imm_ead=True,
        currency="USD",
        sign_convention="non_negative",
        source_row_id="row-ns-prop",
        lineage=_lineage("row-ns-prop"),
    )


def _reduced_context() -> CvaCalculationContext:
    return CvaCalculationContext(
        run_id="cva-properties",
        calculation_date=date(2026, 5, 31),
        base_currency="USD",
        profile=CvaRegulatoryProfile.BASEL_MAR50_2020,
        method=CvaMethod.BA_CVA_REDUCED,
    )


def _sa_cva_context() -> CvaCalculationContext:
    return CvaCalculationContext(
        run_id="cva-properties-sa",
        calculation_date=date(2026, 5, 31),
        base_currency="USD",
        profile=CvaRegulatoryProfile.BASEL_MAR50_2020,
        method=CvaMethod.SA_CVA,
        sa_cva_approved=True,
    )


def _girr_sensitivity(amount: float) -> SaCvaSensitivity:
    return SaCvaSensitivity(
        sensitivity_id="sens-prop",
        risk_class=SaCvaRiskClass.GIRR,
        risk_measure=SaCvaRiskMeasure.DELTA,
        sensitivity_tag=SensitivityTag.CVA,
        bucket_id="USD",
        risk_factor_key="5y",
        tenor="5y",
        amount=amount,
        amount_currency="USD",
        sign_convention="positive_loss",
        source_row_id="row-sens-prop",
    )


@given(ead=POSITIVE_EAD)
def test_reduced_ba_cva_portfolio_is_subadditive(ead: float) -> None:
    counterparty = _counterparty()
    netting_set = _netting_set(ead)
    reduced = calculate_reduced_portfolio((counterparty,), (netting_set,))
    assert reduced.k_reduced <= sum(
        line.standalone_capital for line in reduced.netting_set_lines
    ) + 1e-9


@given(amount=POSITIVE_AMOUNT)
def test_sa_cva_capital_is_non_negative(amount: float) -> None:
    result = calculate_cva_capital(
        _sa_cva_context(),
        (),
        (),
        sensitivities=(_girr_sensitivity(amount),),
    )
    assert result.total_cva_capital >= 0.0


@given(amount=POSITIVE_AMOUNT)
def test_sa_cva_input_hash_is_stable(amount: float) -> None:
    context = _sa_cva_context()
    sensitivity = _girr_sensitivity(amount)
    first = input_hash(context, (), (), sensitivities=(sensitivity,))
    second = input_hash(context, (), (), sensitivities=(sensitivity,))
    assert first == second


@given(amount=POSITIVE_AMOUNT)
def test_intra_bucket_capital_reconciles_to_weighted_inputs(amount: float) -> None:
    weighted = compute_weighted_sensitivities((_girr_sensitivity(amount),))
    bucket = aggregate_intra_bucket("USD", weighted)
    assert bucket.k_b >= 0.0
    assert is_reconciled(bucket.k_b, abs(weighted[0].weighted_net))


@given(
    cva_amount=POSITIVE_AMOUNT,
    hedge_fraction=st.floats(
        min_value=0.0,
        max_value=1.0,
        allow_nan=False,
        allow_infinity=False,
        width=32,
    ),
)
def test_partial_eligible_hedge_does_not_increase_sa_cva_capital(
    cva_amount: float,
    hedge_fraction: float,
) -> None:
    hedge_amount = cva_amount * hedge_fraction
    unhedged = compute_weighted_sensitivities((_girr_sensitivity(cva_amount),))
    hedged = compute_weighted_sensitivities(
        (
            _girr_sensitivity(cva_amount),
            SaCvaSensitivity(
                sensitivity_id="sens-hdg-prop",
                risk_class=SaCvaRiskClass.GIRR,
                risk_measure=SaCvaRiskMeasure.DELTA,
                sensitivity_tag=SensitivityTag.HDG,
                bucket_id="USD",
                risk_factor_key="5y",
                tenor="5y",
                amount=hedge_amount,
                amount_currency="USD",
                sign_convention="positive_loss",
                source_row_id="row-sens-hdg-prop",
                hedge_id="hedge-prop",
            ),
        ),
        eligible_hedge_ids=frozenset({"hedge-prop"}),
    )
    unhedged_capital = aggregate_intra_bucket("USD", unhedged).k_b
    hedged_capital = aggregate_intra_bucket("USD", hedged).k_b
    assert hedged_capital <= unhedged_capital + 1e-9
