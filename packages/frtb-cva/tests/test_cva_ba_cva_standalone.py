from __future__ import annotations

import pytest
from frtb_cva import (
    CreditQuality,
    CvaCounterparty,
    CvaNettingSet,
    CvaSector,
    calculate_counterparty_standalone,
    calculate_netting_set_standalone,
    compute_non_imm_discount_factor,
)

# MAR50.15: SCVA_c = (1/alpha) * RW_c * sum_NS(M_NS * EAD_NS * DF_NS), alpha = 1.4
_ALPHA = 1.4


def test_sovereign_ig_standalone_capital(sovereign_counterparty, sovereign_netting_set) -> None:
    line = calculate_netting_set_standalone(sovereign_netting_set, sovereign_counterparty)
    assert line.risk_weight == pytest.approx(0.005)
    assert line.alpha == pytest.approx(1.4)
    assert line.standalone_capital == pytest.approx(
        0.005 * 2.5 * 1_000_000.0 * 0.9400247793232364 / _ALPHA
    )


def test_financial_hy_standalone_capital(sample_lineage) -> None:
    counterparty = CvaCounterparty(
        counterparty_id="ctp-fin-hy",
        desk_id="desk-b",
        legal_entity="LE-002",
        sector=CvaSector.FINANCIALS,
        credit_quality=CreditQuality.HIGH_YIELD,
        region="AMER",
        source_row_id="row-ctp-fin-hy",
        lineage=sample_lineage,
    )
    netting_set = CvaNettingSet(
        netting_set_id="ns-fin-hy",
        counterparty_id="ctp-fin-hy",
        ead=500_000.0,
        effective_maturity=1.0,
        discount_factor=1.0,
        currency="USD",
        sign_convention="non_negative",
        uses_imm_ead=True,
        source_row_id="row-ns-fin-hy",
        lineage=sample_lineage,
    )
    line = calculate_netting_set_standalone(netting_set, counterparty)
    assert line.discount_factor == pytest.approx(1.0)
    assert line.standalone_capital == pytest.approx(0.12 * 1.0 * 500_000.0 * 1.0 / _ALPHA)


def test_imm_discount_factor_branch(sample_lineage) -> None:
    counterparty = CvaCounterparty(
        counterparty_id="ctp-imm",
        desk_id="desk-a",
        legal_entity="LE-001",
        sector=CvaSector.SOVEREIGN,
        credit_quality=CreditQuality.INVESTMENT_GRADE,
        region="EMEA",
        source_row_id="row-ctp-imm",
        lineage=sample_lineage,
    )
    netting_set = CvaNettingSet(
        netting_set_id="ns-imm",
        counterparty_id="ctp-imm",
        ead=100.0,
        effective_maturity=3.0,
        discount_factor=0.5,
        currency="USD",
        sign_convention="non_negative",
        uses_imm_ead=True,
        source_row_id="row-ns-imm",
        lineage=sample_lineage,
    )
    line = calculate_netting_set_standalone(netting_set, counterparty)
    assert line.discount_factor == pytest.approx(1.0)
    assert line.discount_factor_supplied is False


def test_non_imm_computed_discount_factor(sample_lineage) -> None:
    discount_factor, _ = compute_non_imm_discount_factor(2.5)
    counterparty = CvaCounterparty(
        counterparty_id="ctp-non-imm",
        desk_id="desk-a",
        legal_entity="LE-001",
        sector=CvaSector.SOVEREIGN,
        credit_quality=CreditQuality.INVESTMENT_GRADE,
        region="EMEA",
        source_row_id="row-ctp-non-imm",
        lineage=sample_lineage,
    )
    netting_set = CvaNettingSet(
        netting_set_id="ns-non-imm",
        counterparty_id="ctp-non-imm",
        ead=100.0,
        effective_maturity=2.5,
        discount_factor=1.0,
        currency="USD",
        sign_convention="non_negative",
        uses_imm_ead=False,
        source_row_id="row-ns-non-imm",
        lineage=sample_lineage,
    )
    line = calculate_netting_set_standalone(netting_set, counterparty)
    assert line.discount_factor == pytest.approx(discount_factor)


def test_counterparty_aggregates_netting_sets(sample_lineage) -> None:
    counterparty = CvaCounterparty(
        counterparty_id="ctp-multi",
        desk_id="desk-a",
        legal_entity="LE-001",
        sector=CvaSector.LOCAL_GOVERNMENT,
        credit_quality=CreditQuality.INVESTMENT_GRADE,
        region="EMEA",
        source_row_id="row-ctp-multi",
        lineage=sample_lineage,
    )
    netting_sets = tuple(
        CvaNettingSet(
            netting_set_id=f"ns-{index}",
            counterparty_id="ctp-multi",
            ead=100_000.0 * (index + 1),
            effective_maturity=1.0 + index,
            discount_factor=1.0,
            currency="USD",
            sign_convention="non_negative",
            uses_imm_ead=True,
            source_row_id=f"row-ns-{index}",
            lineage=sample_lineage,
        )
        for index in range(2)
    )
    capital = calculate_counterparty_standalone(counterparty, netting_sets)
    assert len(capital.netting_set_ids) == 2
    assert capital.standalone_capital == pytest.approx(
        sum(
            calculate_netting_set_standalone(netting_set, counterparty).standalone_capital
            for netting_set in netting_sets
        )
    )


def test_netting_set_standalone_matches_mar50_15_formula(sample_lineage) -> None:
    """Independent MAR50.15 oracle: SCVA = (1/alpha) * RW * M * EAD * DF.

    Uses IMM EAD so DF=1 and the expected value reduces to a single
    multiplication, independent of the non-IMM discount-factor path.

    The regression guard asserts the corrected value is strictly below the
    previous (alpha*RW*M*EAD*DF) value, which overstated SCVA by exactly
    alpha**2 = 1.96.
    """
    counterparty = CvaCounterparty(
        counterparty_id="ctp-oracle",
        desk_id="desk-a",
        legal_entity="LE-001",
        sector=CvaSector.SOVEREIGN,
        credit_quality=CreditQuality.INVESTMENT_GRADE,
        region="EMEA",
        source_row_id="row-oracle",
        lineage=sample_lineage,
    )
    netting_set = CvaNettingSet(
        netting_set_id="ns-oracle",
        counterparty_id="ctp-oracle",
        ead=1_000_000.0,
        effective_maturity=2.0,
        discount_factor=1.0,
        currency="USD",
        sign_convention="non_negative",
        uses_imm_ead=True,
        source_row_id="row-ns-oracle",
        lineage=sample_lineage,
    )
    line = calculate_netting_set_standalone(netting_set, counterparty)

    # MAR50.15: alpha=1.4, RW_sovereign_IG=0.5%, M=2, EAD=1_000_000, DF=1
    expected_scva = 0.005 * 2.0 * 1_000_000.0 * 1.0 / 1.4
    assert line.standalone_capital == pytest.approx(expected_scva)

    # Regression guard: previous implementation used alpha as multiplier, overstating by alpha**2
    buggy_scva = 1.4 * 0.005 * 2.0 * 1_000_000.0 * 1.0
    assert line.standalone_capital < buggy_scva
