"""Reduced BA-CVA batch capital kernel."""

from __future__ import annotations

import math
from typing import cast

from frtb_cva._ba_batch_lines import _netting_set_line_from_batch
from frtb_cva._batch_contracts import CvaCounterpartyBatch, CvaNettingSetBatch
from frtb_cva._batch_utils import _sorted_indices
from frtb_cva._batch_validation import (
    _netting_indices_by_counterparty,
    _validate_ba_relationships,
)
from frtb_cva.ba_cva import _unique_citations
from frtb_cva.data_models import (
    BaCvaCounterpartyCapital,
    BaCvaReducedPortfolioResult,
    BaCvaStandAloneLine,
    CreditQuality,
    CvaRegulatoryProfile,
    CvaSector,
)
from frtb_cva.reference_data import (
    ba_cva_alpha,
    ba_cva_discount_scalar,
    ba_cva_rho,
    ba_cva_risk_weight,
    profile_citation_id,
)
from frtb_cva.validation import CvaInputError


def calculate_reduced_portfolio_from_batches(
    counterparties: CvaCounterpartyBatch,
    netting_sets: CvaNettingSetBatch,
    *,
    profile: CvaRegulatoryProfile | str = CvaRegulatoryProfile.BASEL_MAR50_2020,
) -> BaCvaReducedPortfolioResult:
    """Calculate reduced BA-CVA from counterparty and netting-set batches.

    Parameters
    ----------
    counterparties : CvaCounterpartyBatch
        Counterparty classification columns used for risk-weight lookup.
    netting_sets : CvaNettingSetBatch
        Netting-set EAD, maturity, discount, and lineage columns.
    profile : CvaRegulatoryProfile or str, optional
        Regulatory profile controlling BA-CVA citations and parameters.

    Returns
    -------
    BaCvaReducedPortfolioResult
        Reduced portfolio total plus per-counterparty and per-netting-set audit lines.
    """
    _validate_ba_relationships(counterparties, netting_sets)
    if counterparties.row_count == 0:
        raise CvaInputError("at least one counterparty is required", field="counterparties")

    rho, rho_citation = ba_cva_rho(profile=profile)
    discount_scalar, discount_citation = ba_cva_discount_scalar(profile=profile)
    alpha, alpha_citation = ba_cva_alpha(profile=profile)
    capitals, lines = _reduced_counterparty_capitals(
        counterparties,
        netting_sets,
        profile=profile,
        alpha=alpha,
        alpha_citation=alpha_citation,
    )
    standalone_values = [capital.standalone_capital for capital in capitals]
    _validate_finite_standalone_capitals(capitals)
    sum_scva = sum(standalone_values)
    sum_scva_squared = sum(value * value for value in standalone_values)
    k_portfolio = math.sqrt((rho * sum_scva) ** 2 + (1.0 - rho**2) * sum_scva_squared)
    return BaCvaReducedPortfolioResult(
        k_portfolio=k_portfolio,
        k_reduced=discount_scalar * k_portfolio,
        sum_scva=sum_scva,
        sum_scva_squared=sum_scva_squared,
        rho=rho,
        d_ba_cva=discount_scalar,
        alpha=alpha,
        counterparty_capitals=tuple(capitals),
        netting_set_lines=tuple(lines),
        citations=_unique_citations(
            rho_citation,
            discount_citation,
            alpha_citation,
            profile_citation_id("basel_mar50_14", profile),
        ),
    )


def _reduced_counterparty_capitals(
    counterparties: CvaCounterpartyBatch,
    netting_sets: CvaNettingSetBatch,
    *,
    profile: CvaRegulatoryProfile | str,
    alpha: float,
    alpha_citation: str,
) -> tuple[list[BaCvaCounterpartyCapital], list[BaCvaStandAloneLine]]:
    netting_indices_by_counterparty = _netting_indices_by_counterparty(netting_sets)
    capitals: list[BaCvaCounterpartyCapital] = []
    lines: list[BaCvaStandAloneLine] = []
    for counterparty_index in _sorted_indices(counterparties.counterparty_ids):
        capital, counterparty_lines = _counterparty_capital_from_batch(
            counterparties,
            netting_sets,
            counterparty_index,
            netting_indices_by_counterparty=netting_indices_by_counterparty,
            profile=profile,
            alpha=alpha,
            alpha_citation=alpha_citation,
        )
        capitals.append(capital)
        lines.extend(counterparty_lines)
    return capitals, lines


def _counterparty_capital_from_batch(
    counterparties: CvaCounterpartyBatch,
    netting_sets: CvaNettingSetBatch,
    counterparty_index: int,
    *,
    netting_indices_by_counterparty: dict[str, tuple[int, ...]],
    profile: CvaRegulatoryProfile | str,
    alpha: float,
    alpha_citation: str,
) -> tuple[BaCvaCounterpartyCapital, tuple[BaCvaStandAloneLine, ...]]:
    counterparty_id = cast(str, counterparties.counterparty_ids[counterparty_index])
    netting_indices = netting_indices_by_counterparty.get(counterparty_id, ())
    if not netting_indices:
        raise CvaInputError(
            "counterparty has no netting sets",
            field="netting_sets",
            record_id=counterparty_id,
        )
    sector = CvaSector(cast(str, counterparties.sectors[counterparty_index]))
    credit_quality = CreditQuality(cast(str, counterparties.credit_qualities[counterparty_index]))
    risk_weight, rw_citation = ba_cva_risk_weight(sector, credit_quality, profile=profile)
    counterparty_lines = tuple(
        _netting_set_line_from_batch(
            netting_sets,
            netting_index,
            counterparties,
            counterparty_index,
            profile=profile,
            risk_weight=risk_weight,
            risk_weight_citation=rw_citation,
            alpha=alpha,
            alpha_citation=alpha_citation,
            sector=sector,
            credit_quality=credit_quality,
        )
        for netting_index in netting_indices
    )
    capital = BaCvaCounterpartyCapital(
        counterparty_id=counterparty_id,
        standalone_capital=sum(line.standalone_capital for line in counterparty_lines),
        netting_set_ids=tuple(line.netting_set_id for line in counterparty_lines),
        sector=sector,
        credit_quality=credit_quality,
        region=cast(str, counterparties.regions[counterparty_index]),
        citations=_unique_citations(rw_citation, profile_citation_id("basel_mar50_15", profile)),
    )
    return capital, counterparty_lines


def _validate_finite_standalone_capitals(
    capitals: list[BaCvaCounterpartyCapital],
) -> None:
    for counterparty_capital in capitals:
        if not math.isfinite(counterparty_capital.standalone_capital):
            raise CvaInputError(
                "standalone capital must be finite",
                field="standalone_capital",
                record_id=counterparty_capital.counterparty_id,
            )


__all__ = ["calculate_reduced_portfolio_from_batches"]
