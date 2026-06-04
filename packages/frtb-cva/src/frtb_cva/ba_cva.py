"""
Basic approach CVA capital mechanics.
"""

from __future__ import annotations

import math
from collections import defaultdict

from frtb_cva.data_models import (
    BaCvaCounterpartyCapital,
    BaCvaFullPortfolioResult,
    BaCvaHedgeRecognitionLine,
    BaCvaHedgeType,
    BaCvaReducedPortfolioResult,
    BaCvaStandAloneLine,
    CvaCounterparty,
    CvaHedge,
    CvaNettingSet,
    CvaRegulatoryProfile,
    HedgeEligibility,
)
from frtb_cva.hedges import assess_ba_cva_hedge_eligibility
from frtb_cva.reference_data import (
    ba_cva_alpha,
    ba_cva_beta,
    ba_cva_discount_scalar,
    ba_cva_hedge_counterparty_correlation,
    ba_cva_index_risk_weight_scalar,
    ba_cva_rho,
    ba_cva_risk_weight,
    compute_non_imm_discount_factor,
    profile_citation_id,
    profile_citation_ids,
    resolve_netting_set_discount_factor,
)
from frtb_cva.validation import CvaInputError


def calculate_netting_set_standalone(
    netting_set: CvaNettingSet,
    counterparty: CvaCounterparty,
    *,
    profile: CvaRegulatoryProfile | str = CvaRegulatoryProfile.BASEL_MAR50_2020,
) -> BaCvaStandAloneLine:
    """Calculate stand-alone BA-CVA capital for one netting set.

    Parameters
    ----------
    netting_set :
        Input for ``calculate_netting_set_standalone`` used in the CVA capital path.

    counterparty :
        Input for ``calculate_netting_set_standalone`` used in the CVA capital path.

    profile, optional :
        Optional ``CvaRegulatoryProfile`` or profile label; default Basel MAR50 (2020).

    Returns
    -------
    BaCvaStandAloneLine
        Result of ``calculate_netting_set_standalone`` for audit and downstream aggregation."""

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
        risk_weight * netting_set.effective_maturity * netting_set.ead * discount_factor / alpha
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
    """Aggregate netting-set stand-alone capital to counterparty stand-alone capital.

    Parameters
    ----------
    counterparty :
        Input for ``calculate_counterparty_standalone`` used in the CVA capital path.

    netting_sets :
        Input for ``calculate_counterparty_standalone`` used in the CVA capital path.

    profile, optional :
        Optional ``CvaRegulatoryProfile`` or profile label; default Basel MAR50 (2020).

    Returns
    -------
    BaCvaCounterpartyCapital
        Result of ``calculate_counterparty_standalone`` for audit and downstream aggregation."""

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
        citations=_unique_citations(
            rw_citation,
            profile_citation_id("basel_mar50_15", profile),
        ),
    )
    return capital, lines


def calculate_reduced_portfolio(
    counterparties: tuple[CvaCounterparty, ...],
    netting_sets: tuple[CvaNettingSet, ...],
    *,
    profile: CvaRegulatoryProfile | str = CvaRegulatoryProfile.BASEL_MAR50_2020,
) -> BaCvaReducedPortfolioResult:
    """Calculate reduced BA-CVA portfolio capital per MAR50.14.

    Parameters
    ----------
    counterparties :
        Input for ``calculate_reduced_portfolio`` used in the CVA capital path.

    netting_sets :
        Input for ``calculate_reduced_portfolio`` used in the CVA capital path.

    profile, optional :
        Optional ``CvaRegulatoryProfile`` or profile label; default Basel MAR50 (2020).

    Returns
    -------
    BaCvaReducedPortfolioResult
        Result of ``calculate_reduced_portfolio`` for audit and downstream aggregation."""

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
    for counterparty_capital in counterparty_capitals:
        if not math.isfinite(counterparty_capital.standalone_capital):
            raise CvaInputError(
                "standalone capital must be finite",
                field="standalone_capital",
                record_id=counterparty_capital.counterparty_id,
            )
    sum_scva = sum(standalones)
    sum_scva_squared = sum(value * value for value in standalones)
    k_portfolio = math.sqrt((rho * sum_scva) ** 2 + (1.0 - rho**2) * sum_scva_squared)
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
            profile_citation_id("basel_mar50_14", profile),
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


def _resolve_hedge_discount_factor(
    hedge: CvaHedge,
    *,
    profile: CvaRegulatoryProfile | str,
) -> tuple[float, str, bool]:
    if hedge.discount_factor_explicit or hedge.discount_factor != 1.0:
        return hedge.discount_factor, profile_citation_id("basel_mar50_23", profile), True
    discount_factor, citation = compute_non_imm_discount_factor(hedge.remaining_maturity)
    return discount_factor, profile_citation_id(citation, profile), False


def _hedge_risk_weight(
    hedge: CvaHedge,
    *,
    profile: CvaRegulatoryProfile | str,
) -> tuple[float, str]:
    risk_weight, citation = ba_cva_risk_weight(
        hedge.reference_sector,
        hedge.reference_credit_quality,
        profile=profile,
    )
    if hedge.hedge_type is BaCvaHedgeType.INDEX_CDS:
        scalar, scalar_citation = ba_cva_index_risk_weight_scalar(profile=profile)
        combined = _unique_citations(citation, scalar_citation)
        return risk_weight * scalar, combined[-1]
    return risk_weight, citation


def calculate_full_portfolio(
    counterparties: tuple[CvaCounterparty, ...],
    netting_sets: tuple[CvaNettingSet, ...],
    hedges: tuple[CvaHedge, ...] = (),
    *,
    profile: CvaRegulatoryProfile | str = CvaRegulatoryProfile.BASEL_MAR50_2020,
) -> BaCvaFullPortfolioResult:
    """Calculate full BA-CVA with hedge recognition per MAR50.17-MAR50.26.

    Parameters
    ----------
    counterparties :
        Input for ``calculate_full_portfolio`` used in the CVA capital path.

    netting_sets :
        Input for ``calculate_full_portfolio`` used in the CVA capital path.

    hedges, optional :
        Declared BA-CVA or SA-CVA hedge records assessed for eligibility.

    profile, optional :
        Optional ``CvaRegulatoryProfile`` or profile label; default Basel MAR50 (2020).

    Returns
    -------
    BaCvaFullPortfolioResult
        Result of ``calculate_full_portfolio`` for audit and downstream aggregation."""

    reduced = calculate_reduced_portfolio(counterparties, netting_sets, profile=profile)
    rho, rho_citation = ba_cva_rho(profile=profile)
    discount_scalar, discount_citation = ba_cva_discount_scalar(profile=profile)
    beta, beta_citation = ba_cva_beta(profile=profile)

    scva_by_counterparty = {
        capital.counterparty_id: capital.standalone_capital
        for capital in reduced.counterparty_capitals
    }
    snh_by_counterparty: dict[str, float] = {cp_id: 0.0 for cp_id in scva_by_counterparty}
    hma_by_counterparty: dict[str, float] = {cp_id: 0.0 for cp_id in scva_by_counterparty}
    ih = 0.0
    hedge_lines: list[BaCvaHedgeRecognitionLine] = []

    for hedge in sorted(hedges, key=lambda item: item.hedge_id):
        decision = assess_ba_cva_hedge_eligibility(hedge, profile=profile)
        if decision.eligibility is not HedgeEligibility.ELIGIBLE:
            hedge_lines.append(
                BaCvaHedgeRecognitionLine(
                    hedge_id=hedge.hedge_id,
                    counterparty_id=hedge.counterparty_id,
                    hedge_type=hedge.hedge_type,
                    eligibility=decision.eligibility,
                    reference_relation=hedge.reference_relation,
                    r_hc=0.0,
                    risk_weight=0.0,
                    snh_contribution=0.0,
                    hma_contribution=0.0,
                    index_contribution=0.0,
                    reason_code=decision.reason_code,
                    citations=decision.citations,
                )
            )
            continue

        if hedge.counterparty_id not in scva_by_counterparty:
            raise CvaInputError(
                "hedge counterparty is not in BA-CVA counterparty set",
                field="counterparty_id",
                record_id=hedge.counterparty_id,
            )

        r_hc, rhc_citation = ba_cva_hedge_counterparty_correlation(
            hedge.reference_relation,
            profile=profile,
        )
        risk_weight, rw_citation = _hedge_risk_weight(hedge, profile=profile)
        discount_factor, df_citation, _ = _resolve_hedge_discount_factor(
            hedge,
            profile=profile,
        )
        weighted_notional = (
            risk_weight * hedge.remaining_maturity * hedge.notional * discount_factor
        )

        if hedge.hedge_type is BaCvaHedgeType.INDEX_CDS:
            index_term = weighted_notional
            ih += index_term
            hedge_lines.append(
                BaCvaHedgeRecognitionLine(
                    hedge_id=hedge.hedge_id,
                    counterparty_id=hedge.counterparty_id,
                    hedge_type=hedge.hedge_type,
                    eligibility=HedgeEligibility.ELIGIBLE,
                    reference_relation=hedge.reference_relation,
                    r_hc=r_hc,
                    risk_weight=risk_weight,
                    snh_contribution=0.0,
                    hma_contribution=0.0,
                    index_contribution=index_term,
                    reason_code=decision.reason_code,
                    citations=_unique_citations(
                        *decision.citations,
                        rhc_citation,
                        rw_citation,
                        df_citation,
                        profile_citation_id("basel_mar50_24", profile),
                    ),
                )
            )
            continue

        snh_term = r_hc * weighted_notional
        snh_by_counterparty[hedge.counterparty_id] += snh_term
        hma_term = 0.0
        if hedge.reference_relation.value != "DIRECT":
            hma_term = (1.0 - r_hc**2) * (weighted_notional**2)
            hma_by_counterparty[hedge.counterparty_id] += hma_term

        hedge_lines.append(
            BaCvaHedgeRecognitionLine(
                hedge_id=hedge.hedge_id,
                counterparty_id=hedge.counterparty_id,
                hedge_type=hedge.hedge_type,
                eligibility=HedgeEligibility.ELIGIBLE,
                reference_relation=hedge.reference_relation,
                r_hc=r_hc,
                risk_weight=risk_weight,
                snh_contribution=snh_term,
                hma_contribution=hma_term,
                index_contribution=0.0,
                reason_code=decision.reason_code,
                citations=_unique_citations(
                    *decision.citations,
                    rhc_citation,
                    rw_citation,
                    df_citation,
                    profile_citation_id("basel_mar50_23", profile),
                ),
            )
        )

    adjusted = [
        scva_by_counterparty[cp_id] - snh_by_counterparty[cp_id]
        for cp_id in sorted(scva_by_counterparty)
    ]
    sum_adjusted = sum(adjusted)
    systematic = rho * sum_adjusted - ih
    idiosyncratic = sum(value * value for value in adjusted)
    hma_total = sum(hma_by_counterparty.values())
    k_portfolio_hedged = math.sqrt(systematic**2 + (1.0 - rho**2) * idiosyncratic + hma_total)
    k_hedged = discount_scalar * k_portfolio_hedged
    k_full = beta * reduced.k_reduced + (1.0 - beta) * k_hedged
    beta_floor = beta * reduced.k_reduced
    beta_floor_binding = k_full + 1e-12 < beta_floor
    if beta_floor_binding:
        k_full = beta_floor

    return BaCvaFullPortfolioResult(
        k_full=k_full,
        k_hedged=k_hedged,
        k_reduced=reduced.k_reduced,
        k_portfolio_hedged=k_portfolio_hedged,
        ih=ih,
        beta=beta,
        beta_floor_binding=beta_floor_binding,
        rho=rho,
        d_ba_cva=discount_scalar,
        reduced=reduced,
        hedge_lines=tuple(hedge_lines),
        counterparty_adjusted_standalone=tuple(
            (cp_id, scva_by_counterparty[cp_id] - snh_by_counterparty[cp_id])
            for cp_id in sorted(scva_by_counterparty)
        ),
        citations=_unique_citations(
            rho_citation,
            discount_citation,
            beta_citation,
            *profile_citation_ids(
                ("basel_mar50_17", "basel_mar50_20", "basel_mar50_21"),
                profile,
            ),
            *(citation for line in hedge_lines for citation in line.citations),
        ),
    )


__all__ = [
    "calculate_counterparty_standalone",
    "calculate_full_portfolio",
    "calculate_netting_set_standalone",
    "calculate_reduced_portfolio",
]
