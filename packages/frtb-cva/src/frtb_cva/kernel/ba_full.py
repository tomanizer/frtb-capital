"""Full BA-CVA batch capital kernel."""

from __future__ import annotations

import math

from frtb_cva._ba_full_hedge_lines import _recognise_batch_hedges
from frtb_cva._batch_contracts import CvaCounterpartyBatch, CvaHedgeBatch, CvaNettingSetBatch
from frtb_cva._batch_utils import _empty_hedge_batch
from frtb_cva.ba_cva import _unique_citations
from frtb_cva.data_models import (
    BaCvaFullPortfolioResult,
    CvaRegulatoryProfile,
)
from frtb_cva.kernel.ba_reduced import calculate_reduced_portfolio_from_batches
from frtb_cva.reference_data import (
    ba_cva_beta,
    ba_cva_discount_scalar,
    ba_cva_rho,
    profile_citation_ids,
)


def calculate_full_portfolio_from_batches(
    counterparties: CvaCounterpartyBatch,
    netting_sets: CvaNettingSetBatch,
    hedges: CvaHedgeBatch | None = None,
    *,
    profile: CvaRegulatoryProfile | str = CvaRegulatoryProfile.BASEL_MAR50_2020,
) -> BaCvaFullPortfolioResult:
    """Calculate full BA-CVA with hedge recognition from columnar batches.

    Parameters
    ----------
    counterparties, netting_sets : CvaCounterpartyBatch, CvaNettingSetBatch
        BA-CVA exposure batches shared with the embedded reduced calculation.
    hedges : CvaHedgeBatch or None, optional
        Hedge batch evaluated for MAR50 hedge recognition.
    profile : CvaRegulatoryProfile or str, optional
        Regulatory profile controlling BA-CVA citations and parameters.

    Returns
    -------
    BaCvaFullPortfolioResult
        Full portfolio capital combining reduced and hedged components.
    """
    hedge_batch = hedges or _empty_hedge_batch()
    reduced = calculate_reduced_portfolio_from_batches(
        counterparties, netting_sets, profile=profile
    )
    rho, rho_citation = ba_cva_rho(profile=profile)
    discount_scalar, discount_citation = ba_cva_discount_scalar(profile=profile)
    beta, beta_citation = ba_cva_beta(profile=profile)
    scva_by_counterparty = {
        item.counterparty_id: item.standalone_capital for item in reduced.counterparty_capitals
    }
    snh_by_counterparty, hma_by_counterparty, ih, hedge_lines = _recognise_batch_hedges(
        hedge_batch,
        scva_by_counterparty=scva_by_counterparty,
        profile=profile,
    )
    k_portfolio_hedged = _k_portfolio_hedged(
        scva_by_counterparty,
        snh_by_counterparty=snh_by_counterparty,
        hma_by_counterparty=hma_by_counterparty,
        ih=ih,
        rho=rho,
    )
    k_hedged = discount_scalar * k_portfolio_hedged
    k_full, beta_floor_binding = _apply_beta_floor(beta, reduced.k_reduced, k_hedged)
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
            (
                counterparty_id,
                scva_by_counterparty[counterparty_id] - snh_by_counterparty[counterparty_id],
            )
            for counterparty_id in sorted(scva_by_counterparty)
        ),
        citations=_unique_citations(
            rho_citation,
            discount_citation,
            beta_citation,
            *profile_citation_ids(("basel_mar50_17", "basel_mar50_20", "basel_mar50_21"), profile),
            *(citation for line in hedge_lines for citation in line.citations),
        ),
    )


def _k_portfolio_hedged(
    scva_by_counterparty: dict[str, float],
    *,
    snh_by_counterparty: dict[str, float],
    hma_by_counterparty: dict[str, float],
    ih: float,
    rho: float,
) -> float:
    adjusted = [
        scva_by_counterparty[counterparty_id] - snh_by_counterparty[counterparty_id]
        for counterparty_id in sorted(scva_by_counterparty)
    ]
    systematic = rho * sum(adjusted) - ih
    idiosyncratic = sum(value * value for value in adjusted)
    hma_total = sum(hma_by_counterparty.values())
    return math.sqrt(systematic**2 + (1.0 - rho**2) * idiosyncratic + hma_total)


def _apply_beta_floor(beta: float, k_reduced: float, k_hedged: float) -> tuple[float, bool]:
    k_full = beta * k_reduced + (1.0 - beta) * k_hedged
    beta_floor = beta * k_reduced
    beta_floor_binding = k_full + 1e-12 < beta_floor
    if beta_floor_binding:
        return beta_floor, True
    return k_full, False


__all__ = ["calculate_full_portfolio_from_batches"]
