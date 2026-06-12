"""
Public CVA capital calculation entry point.
"""

from __future__ import annotations

from collections.abc import Iterable

from frtb_cva._batch_contracts import (
    CvaCounterpartyBatch,
    CvaHedgeBatch,
    CvaNettingSetBatch,
    SaCvaSensitivityBatch,
)
from frtb_cva.adapters.rows import (
    build_cva_counterparty_batch_from_counterparties,
    build_cva_hedge_batch_from_hedges,
    build_cva_netting_set_batch_from_netting_sets,
    build_sa_cva_sensitivity_batch_from_sensitivities,
)
from frtb_cva.assembly.batches import calculate_cva_capital_from_batches
from frtb_cva.data_models import (
    CvaCalculationContext,
    CvaCapitalResult,
    CvaCounterparty,
    CvaHedge,
    CvaNettingSet,
    SaCvaSensitivity,
)


def calculate_cva_capital(
    context: CvaCalculationContext,
    counterparties: Iterable[CvaCounterparty],
    netting_sets: Iterable[CvaNettingSet],
    *,
    hedges: Iterable[CvaHedge] = (),
    sensitivities: Iterable[SaCvaSensitivity] = (),
) -> CvaCapitalResult:
    """Calculate supported BA-CVA, SA-CVA, or mixed carve-out CVA capital.

    Parameters
    ----------
    context : CvaCalculationContext
        Calculation context carrying profile, currency, and method metadata.
    counterparties : Iterable[CvaCounterparty]
        Counterparty records referenced by netting sets and BA-CVA weights.
    netting_sets : Iterable[CvaNettingSet]
        Netting sets supplying EAD, maturity, and discount inputs for BA-CVA.
    hedges : Iterable[CvaHedge], optional
        Declared BA-CVA or SA-CVA hedge records assessed for eligibility.
    sensitivities : Iterable[SaCvaSensitivity], optional
        Raw SA-CVA sensitivities prior to weighting.

    Returns
    -------
    CvaCapitalResult
        Frozen CVA capital result with method components, citations, and audit hashes.
    """

    counterparty_rows = tuple(counterparties)
    netting_set_rows = tuple(netting_sets)
    hedge_rows = tuple(hedges)
    sensitivity_rows = tuple(sensitivities)

    calculation = calculate_cva_capital_from_batches(
        context,
        _counterparty_batch_or_none(counterparty_rows),
        _netting_set_batch_or_none(netting_set_rows, counterparties=counterparty_rows),
        hedges=_hedge_batch_or_none(hedge_rows),
        sensitivities=_sensitivity_batch_or_none(sensitivity_rows),
    )
    return calculation.result


def _counterparty_batch_or_none(
    counterparties: tuple[CvaCounterparty, ...],
) -> CvaCounterpartyBatch | None:
    if not counterparties:
        return None
    return build_cva_counterparty_batch_from_counterparties(counterparties)


def _netting_set_batch_or_none(
    netting_sets: tuple[CvaNettingSet, ...],
    *,
    counterparties: tuple[CvaCounterparty, ...],
) -> CvaNettingSetBatch | None:
    if not netting_sets:
        return None
    return build_cva_netting_set_batch_from_netting_sets(
        netting_sets,
        counterparties=counterparties,
    )


def _hedge_batch_or_none(hedges: tuple[CvaHedge, ...]) -> CvaHedgeBatch | None:
    if not hedges:
        return None
    return build_cva_hedge_batch_from_hedges(hedges)


def _sensitivity_batch_or_none(
    sensitivities: tuple[SaCvaSensitivity, ...],
) -> SaCvaSensitivityBatch | None:
    if not sensitivities:
        return None
    return build_sa_cva_sensitivity_batch_from_sensitivities(sensitivities)


__all__ = ["calculate_cva_capital"]
