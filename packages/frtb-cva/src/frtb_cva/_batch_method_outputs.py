"""Method-specific CVA batch calculation branches."""

from __future__ import annotations

from dataclasses import dataclass
from typing import cast

from frtb_cva._ba_batch_kernel import (
    calculate_full_portfolio_from_batches,
    calculate_reduced_portfolio_from_batches,
)
from frtb_cva._batch_contracts import (
    CvaCounterpartyBatch,
    CvaHedgeBatch,
    CvaNettingSetBatch,
    SaCvaSensitivityBatch,
)
from frtb_cva._batch_utils import (
    _subset_counterparties,
    _subset_hedges,
    _subset_netting_sets,
)
from frtb_cva._sa_batch_kernel import calculate_sa_cva_capital_from_batch
from frtb_cva.data_models import (
    BaCvaCounterpartyCapital,
    BaCvaFullPortfolioResult,
    BaCvaReducedPortfolioResult,
    BaCvaStandAloneLine,
    CvaCalculationContext,
    CvaMethod,
    CvaMethodComponentTotal,
    CvaRegulatoryProfile,
    SaCvaRiskClassCapital,
)
from frtb_cva.scope import require_mixed_sensitivity_scope_evidence
from frtb_cva.validation import CvaInputError


@dataclass(frozen=True)
class _BatchMethodOutputs:
    ba_cva_reduced: BaCvaReducedPortfolioResult | None
    ba_cva_full: BaCvaFullPortfolioResult | None
    ba_cva_counterparty_capitals: tuple[BaCvaCounterpartyCapital, ...]
    ba_cva_netting_set_lines: tuple[BaCvaStandAloneLine, ...]
    sa_cva_risk_class_capitals: tuple[SaCvaRiskClassCapital, ...]
    method_components: tuple[CvaMethodComponentTotal, ...]
    total_cva_capital: float


def _calculate_method_outputs(
    context: CvaCalculationContext,
    profile: CvaRegulatoryProfile | str,
    method: CvaMethod,
    counterparties: CvaCounterpartyBatch,
    netting_sets: CvaNettingSetBatch,
    hedges: CvaHedgeBatch,
    *,
    sensitivities: SaCvaSensitivityBatch | None,
    carve_out_netting_set_ids: tuple[str, ...],
) -> _BatchMethodOutputs:
    if method is CvaMethod.MIXED_CARVE_OUT:
        return _calculate_mixed_outputs(
            context,
            profile,
            counterparties,
            netting_sets,
            hedges,
            sensitivities=sensitivities,
            carve_out_netting_set_ids=carve_out_netting_set_ids,
        )
    if method is CvaMethod.BA_CVA_FULL:
        return _calculate_ba_full_outputs(profile, counterparties, netting_sets, hedges)
    if method is CvaMethod.BA_CVA_REDUCED:
        return _calculate_ba_reduced_outputs(profile, counterparties, netting_sets)
    if method is CvaMethod.SA_CVA:
        return _calculate_sa_outputs(
            context,
            profile,
            counterparties,
            netting_sets,
            hedges,
            sensitivities,
        )
    return _BatchMethodOutputs(None, None, (), (), (), (), 0.0)


def _calculate_mixed_outputs(
    context: CvaCalculationContext,
    profile: CvaRegulatoryProfile | str,
    counterparties: CvaCounterpartyBatch,
    netting_sets: CvaNettingSetBatch,
    hedges: CvaHedgeBatch,
    *,
    sensitivities: SaCvaSensitivityBatch | None,
    carve_out_netting_set_ids: tuple[str, ...],
) -> _BatchMethodOutputs:
    if sensitivities is None:
        raise CvaInputError("mixed carve-out requires SA-CVA sensitivities", field="sensitivities")
    require_mixed_sensitivity_scope_evidence(context)
    ba_counterparties, ba_netting_sets, sa_hedges = _partition_mixed_batches(
        counterparties,
        netting_sets,
        hedges,
        carve_out_netting_set_ids=carve_out_netting_set_ids,
    )
    sa_capitals = calculate_sa_cva_capital_from_batch(
        sensitivities,
        hedges=sa_hedges,
        reporting_currency=context.base_currency,
        profile=profile,
    )
    ba_reduced = calculate_reduced_portfolio_from_batches(
        ba_counterparties,
        ba_netting_sets,
        profile=profile,
    )
    return _mixed_outputs(ba_reduced, sa_capitals)


def _mixed_outputs(
    ba_reduced: BaCvaReducedPortfolioResult,
    sa_capitals: tuple[SaCvaRiskClassCapital, ...],
) -> _BatchMethodOutputs:
    sa_total = sum(item.post_multiplier_capital for item in sa_capitals)
    return _BatchMethodOutputs(
        ba_reduced,
        None,
        ba_reduced.counterparty_capitals,
        ba_reduced.netting_set_lines,
        sa_capitals,
        (
            CvaMethodComponentTotal(
                method=CvaMethod.SA_CVA,
                total_capital=sa_total,
                citations=tuple(citation for item in sa_capitals for citation in item.citations),
            ),
            CvaMethodComponentTotal(
                method=CvaMethod.BA_CVA_REDUCED,
                total_capital=ba_reduced.k_reduced,
                citations=ba_reduced.citations,
            ),
        ),
        sa_total + ba_reduced.k_reduced,
    )


def _calculate_ba_full_outputs(
    profile: CvaRegulatoryProfile | str,
    counterparties: CvaCounterpartyBatch,
    netting_sets: CvaNettingSetBatch,
    hedges: CvaHedgeBatch,
) -> _BatchMethodOutputs:
    ba_full = calculate_full_portfolio_from_batches(
        counterparties,
        netting_sets,
        hedges,
        profile=profile,
    )
    ba_reduced = ba_full.reduced
    return _BatchMethodOutputs(
        ba_reduced,
        ba_full,
        ba_reduced.counterparty_capitals,
        ba_reduced.netting_set_lines,
        (),
        (),
        ba_full.k_full,
    )


def _calculate_ba_reduced_outputs(
    profile: CvaRegulatoryProfile | str,
    counterparties: CvaCounterpartyBatch,
    netting_sets: CvaNettingSetBatch,
) -> _BatchMethodOutputs:
    ba_reduced = calculate_reduced_portfolio_from_batches(
        counterparties,
        netting_sets,
        profile=profile,
    )
    return _BatchMethodOutputs(
        ba_reduced,
        None,
        ba_reduced.counterparty_capitals,
        ba_reduced.netting_set_lines,
        (),
        (),
        ba_reduced.k_reduced,
    )


def _calculate_sa_outputs(
    context: CvaCalculationContext,
    profile: CvaRegulatoryProfile | str,
    counterparties: CvaCounterpartyBatch,
    netting_sets: CvaNettingSetBatch,
    hedges: CvaHedgeBatch,
    sensitivities: SaCvaSensitivityBatch | None,
) -> _BatchMethodOutputs:
    if counterparties.row_count or netting_sets.row_count:
        raise CvaInputError(
            "SA-CVA does not accept counterparty or netting-set inputs; "
            "pass them only when method is BA_CVA_REDUCED or MIXED_CARVE_OUT",
            field="counterparties_or_netting_sets",
        )
    if sensitivities is None:
        raise CvaInputError("SA-CVA requires sensitivities", field="sensitivities")
    sa_capitals = calculate_sa_cva_capital_from_batch(
        sensitivities,
        hedges=hedges,
        reporting_currency=context.base_currency,
        profile=profile,
    )
    return _BatchMethodOutputs(
        None,
        None,
        (),
        (),
        sa_capitals,
        (),
        sum(item.post_multiplier_capital for item in sa_capitals),
    )


def _partition_mixed_batches(
    counterparties: CvaCounterpartyBatch,
    netting_sets: CvaNettingSetBatch,
    hedges: CvaHedgeBatch,
    *,
    carve_out_netting_set_ids: tuple[str, ...],
) -> tuple[CvaCounterpartyBatch, CvaNettingSetBatch, CvaHedgeBatch]:
    carve_out_set = set(carve_out_netting_set_ids)
    netting_indices = [
        index
        for index in range(netting_sets.row_count)
        if netting_sets.netting_set_ids[index] in carve_out_set
    ]
    ba_counterparty_ids = {
        cast(str, netting_sets.counterparty_ids[index]) for index in netting_indices
    }
    counterparty_indices = [
        index
        for index in range(counterparties.row_count)
        if counterparties.counterparty_ids[index] in ba_counterparty_ids
    ]
    hedge_indices = [
        index
        for index in range(hedges.row_count)
        if hedges.counterparty_ids[index] not in ba_counterparty_ids
    ]
    return (
        _subset_counterparties(counterparties, counterparty_indices),
        _subset_netting_sets(netting_sets, netting_indices),
        _subset_hedges(hedges, hedge_indices),
    )
