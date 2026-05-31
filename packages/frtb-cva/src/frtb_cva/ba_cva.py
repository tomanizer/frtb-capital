"""
Basic approach CVA capital mechanics.
"""

from __future__ import annotations

import math
from collections import defaultdict

from frtb_cva.data_models import (
    BaCvaCounterpartyCapital,
    BaCvaReducedPortfolioResult,
    BaCvaStandAloneLine,
    CvaCounterparty,
    CvaNettingSet,
    CvaRegulatoryProfile,
)
from frtb_cva.reference_data import (
    ba_cva_alpha,
    ba_cva_discount_scalar,
    ba_cva_rho,
    ba_cva_risk_weight,
    resolve_netting_set_discount_factor,
)
from frtb_cva.validation import CvaInputError


def calculate_netting_set_standalone(
    netting_set: CvaNettingSet,
    counterparty: CvaCounterparty,
    *,
    profile: CvaRegulatoryProfile | str = CvaRegulatoryProfile.BASEL_MAR50_2020,
) -> BaCvaStandAloneLine:
    """Calculate stand-alone BA-CVA capital for one netting set."""

    if netting_set.counterparty_id != counterparty.counterparty_id:
        raise CvaInputError(
            "netting set counterparty does not match supplied counterparty",
            field="counterparty_id",
            record_id=netting_set.netting_set_id,
        )

    risk_weight, rw_citation = ba_cva_risk_weight(
        counterparty.sector,
        counterparty.credit_quality,
        profile=profile,
    )
    alpha, alpha_citation = ba_cva_alpha(profile=profile)
    discount_factor, df_citation, discount_factor_supplied = resolve_netting_set_discount_factor(
        uses_imm_ead=netting_set.uses_imm_ead,
        effective_maturity=netting_set.effective_maturity,
        supplied_discount_factor=netting_set.discount_factor,
        discount_factor_explicit=netting_set.discount_factor_explicit,
        profile=profile,
    )
    standalone = (
        alpha * risk_weight * netting_set.effective_maturity * netting_set.ead * discount_factor
    )
    return BaCvaStandAloneLine(
        netting_set_id=netting_set.netting_set_id,
        counterparty_id=counterparty.counterparty_id,
        sector=counterparty.sector,
        credit_quality=counterparty.credit_quality,
        ead=netting_set.ead,
        effective_maturity=netting_set.effective_maturity,
        discount_factor=discount_factor,
        alpha=alpha,
        risk_weight=risk_weight,
        standalone_capital=standalone,
        currency=netting_set.currency,
        source_row_id=netting_set.source_row_id,
        citations=_unique_citations(rw_citation, alpha_citation, df_citation),
        uses_imm_ead=netting_set.uses_imm_ead,
        discount_factor_supplied=discount_factor_supplied,
    )


def calculate_counterparty_standalone(
    counterparty: CvaCounterparty,
    netting_sets: tuple[CvaNettingSet, ...],
    *,
    profile: CvaRegulatoryProfile | str = CvaRegulatoryProfile.BASEL_MAR50_2020,
) -> BaCvaCounterpartyCapital:
    """Aggregate netting-set stand-alone capital to counterparty stand-alone capital."""

    capital, _ = _counterparty_standalone_with_lines(counterparty, netting_sets, profile=profile)
    return capital


def _counterparty_standalone_with_lines(
    counterparty: CvaCounterparty,
    netting_sets: tuple[CvaNettingSet, ...],
    *,
    profile: CvaRegulatoryProfile | str = CvaRegulatoryProfile.BASEL_MAR50_2020,
) -> tuple[BaCvaCounterpartyCapital, tuple[BaCvaStandAloneLine, ...]]:
    """Return counterparty capital and netting-set lines in a single pass."""

    counterparty_netting_sets = tuple(
        sorted(
            (
                netting_set
                for netting_set in netting_sets
                if netting_set.counterparty_id == counterparty.counterparty_id
            ),
            key=lambda item: item.netting_set_id,
        )
    )
    if not counterparty_netting_sets:
        raise CvaInputError(
            "counterparty has no netting sets",
            field="netting_sets",
            record_id=counterparty.counterparty_id,
        )

    lines = tuple(
        calculate_netting_set_standalone(netting_set, counterparty, profile=profile)
        for netting_set in counterparty_netting_sets
    )
    _, rw_citation = ba_cva_risk_weight(
        counterparty.sector,
        counterparty.credit_quality,
        profile=profile,
    )
    standalone_total = sum(line.standalone_capital for line in lines)
    capital = BaCvaCounterpartyCapital(
        counterparty_id=counterparty.counterparty_id,
        standalone_capital=standalone_total,
        netting_set_ids=tuple(line.netting_set_id for line in lines),
        sector=counterparty.sector,
        credit_quality=counterparty.credit_quality,
        region=counterparty.region,
        citations=_unique_citations(rw_citation, "basel_mar50_15"),
    )
    return capital, lines


def calculate_reduced_portfolio(
    counterparties: tuple[CvaCounterparty, ...],
    netting_sets: tuple[CvaNettingSet, ...],
    *,
    profile: CvaRegulatoryProfile | str = CvaRegulatoryProfile.BASEL_MAR50_2020,
) -> BaCvaReducedPortfolioResult:
    """Calculate reduced BA-CVA portfolio capital per MAR50.14."""

    netting_sets_by_counterparty: dict[str, list[CvaNettingSet]] = defaultdict(list)
    for netting_set in netting_sets:
        netting_sets_by_counterparty[netting_set.counterparty_id].append(netting_set)

    capitals_and_lines = [
        _counterparty_standalone_with_lines(
            counterparty,
            tuple(netting_sets_by_counterparty[counterparty.counterparty_id]),
            profile=profile,
        )
        for counterparty in sorted(counterparties, key=lambda item: item.counterparty_id)
    ]
    if not capitals_and_lines:
        raise CvaInputError("at least one counterparty is required", field="counterparties")

    counterparty_capitals = tuple(capital for capital, _ in capitals_and_lines)
    netting_set_lines = tuple(line for _, lines in capitals_and_lines for line in lines)

    rho, rho_citation = ba_cva_rho(profile=profile)
    discount_scalar, discount_citation = ba_cva_discount_scalar(profile=profile)
    alpha, alpha_citation = ba_cva_alpha(profile=profile)
    standalones = [capital.standalone_capital for capital in counterparty_capitals]
    sum_scva = sum(standalones)
    sum_scva_squared = sum(value * value for value in standalones)
    k_portfolio = math.sqrt(rho * (sum_scva**2) + (1.0 - rho) * sum_scva_squared)
    k_reduced = discount_scalar * k_portfolio

    return BaCvaReducedPortfolioResult(
        k_portfolio=k_portfolio,
        k_reduced=k_reduced,
        sum_scva=sum_scva,
        sum_scva_squared=sum_scva_squared,
        rho=rho,
        d_ba_cva=discount_scalar,
        alpha=alpha,
        counterparty_capitals=counterparty_capitals,
        netting_set_lines=netting_set_lines,
        citations=_unique_citations(
            rho_citation,
            discount_citation,
            alpha_citation,
            "basel_mar50_14",
        ),
    )


def _unique_citations(*citation_ids: str) -> tuple[str, ...]:
    merged: list[str] = []
    seen: set[str] = set()
    for citation_id in citation_ids:
        if citation_id not in seen:
            merged.append(citation_id)
            seen.add(citation_id)
    return tuple(merged)


__all__ = [
    "calculate_counterparty_standalone",
    "calculate_netting_set_standalone",
    "calculate_reduced_portfolio",
]
