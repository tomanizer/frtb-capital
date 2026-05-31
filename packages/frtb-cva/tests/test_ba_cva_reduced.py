from __future__ import annotations

import pytest
from frtb_cva import (
    CreditQuality,
    CvaCounterparty,
    CvaNettingSet,
    CvaSector,
    calculate_reduced_portfolio,
)


def _counterparty(
    counterparty_id: str,
    sector: CvaSector,
    quality: CreditQuality,
    sample_lineage,
) -> CvaCounterparty:
    return CvaCounterparty(
        counterparty_id=counterparty_id,
        desk_id="desk-a",
        legal_entity="LE-001",
        sector=sector,
        credit_quality=quality,
        region="EMEA",
        source_row_id=f"row-{counterparty_id}",
        lineage=sample_lineage,
    )


def _netting_set(
    netting_set_id: str,
    counterparty_id: str,
    ead: float,
    sample_lineage,
) -> CvaNettingSet:
    return CvaNettingSet(
        netting_set_id=netting_set_id,
        counterparty_id=counterparty_id,
        ead=ead,
        effective_maturity=1.0,
        discount_factor=1.0,
        currency="USD",
        sign_convention="non_negative",
        uses_imm_ead=True,
        source_row_id=f"row-{netting_set_id}",
        lineage=sample_lineage,
    )


def test_single_counterparty_equals_scaled_standalone(sample_lineage) -> None:
    counterparty = _counterparty(
        "ctp-1",
        CvaSector.SOVEREIGN,
        CreditQuality.INVESTMENT_GRADE,
        sample_lineage,
    )
    netting_set = _netting_set("ns-1", "ctp-1", 1_000_000.0, sample_lineage)
    reduced = calculate_reduced_portfolio((counterparty,), (netting_set,))
    standalone = reduced.counterparty_capitals[0].standalone_capital
    assert reduced.k_reduced == pytest.approx(0.65 * standalone)


def test_multi_counterparty_diversifies_below_sum(sample_lineage) -> None:
    counterparties = (
        _counterparty("ctp-1", CvaSector.SOVEREIGN, CreditQuality.INVESTMENT_GRADE, sample_lineage),
        _counterparty("ctp-2", CvaSector.FINANCIALS, CreditQuality.HIGH_YIELD, sample_lineage),
    )
    netting_sets = (
        _netting_set("ns-1", "ctp-1", 1_000_000.0, sample_lineage),
        _netting_set("ns-2", "ctp-2", 500_000.0, sample_lineage),
    )
    reduced = calculate_reduced_portfolio(counterparties, netting_sets)
    simple_sum = sum(capital.standalone_capital for capital in reduced.counterparty_capitals)
    assert reduced.k_reduced < 0.65 * simple_sum


def test_portfolio_components_reconcile(sample_lineage) -> None:
    counterparty = _counterparty(
        "ctp-1",
        CvaSector.SOVEREIGN,
        CreditQuality.INVESTMENT_GRADE,
        sample_lineage,
    )
    netting_set = _netting_set("ns-1", "ctp-1", 750_000.0, sample_lineage)
    reduced = calculate_reduced_portfolio((counterparty,), (netting_set,))
    expected_portfolio = (
        reduced.rho * (reduced.sum_scva**2) + (1.0 - reduced.rho) * reduced.sum_scva_squared
    ) ** 0.5
    assert reduced.k_portfolio == pytest.approx(expected_portfolio)
    assert reduced.k_reduced == pytest.approx(reduced.d_ba_cva * reduced.k_portfolio)
