"""BA-CVA full-method hedge recognition line helpers."""

from __future__ import annotations

from typing import cast

from frtb_cva._batch_contracts import CvaHedgeBatch
from frtb_cva._batch_hedges import (
    _assess_ba_cva_hedge_eligibility,
    _hedge_discount_factor,
    _hedge_risk_weight,
)
from frtb_cva._batch_utils import _sorted_indices
from frtb_cva.ba_cva import _unique_citations
from frtb_cva.data_models import (
    BaCvaHedgeRecognitionLine,
    BaCvaHedgeType,
    CvaRegulatoryProfile,
    HedgeEligibility,
    HedgeReferenceRelation,
)
from frtb_cva.hedges import HedgeEligibilityDecision
from frtb_cva.reference_data import (
    ba_cva_hedge_counterparty_correlation,
    profile_citation_id,
)
from frtb_cva.validation import CvaInputError


def _recognise_batch_hedges(
    hedge_batch: CvaHedgeBatch,
    *,
    scva_by_counterparty: dict[str, float],
    profile: CvaRegulatoryProfile | str,
) -> tuple[dict[str, float], dict[str, float], float, list[BaCvaHedgeRecognitionLine]]:
    snh_by_counterparty = {counterparty_id: 0.0 for counterparty_id in scva_by_counterparty}
    hma_by_counterparty = {counterparty_id: 0.0 for counterparty_id in scva_by_counterparty}
    ih = 0.0
    hedge_lines: list[BaCvaHedgeRecognitionLine] = []
    for hedge_index in _sorted_indices(hedge_batch.hedge_ids):
        line = _hedge_recognition_line(
            hedge_batch,
            hedge_index,
            scva_by_counterparty=scva_by_counterparty,
            profile=profile,
        )
        hedge_lines.append(line)
        snh_by_counterparty[line.counterparty_id] += line.snh_contribution
        hma_by_counterparty[line.counterparty_id] += line.hma_contribution
        ih += line.index_contribution
    return snh_by_counterparty, hma_by_counterparty, ih, hedge_lines


def _hedge_recognition_line(
    hedge_batch: CvaHedgeBatch,
    hedge_index: int,
    *,
    scva_by_counterparty: dict[str, float],
    profile: CvaRegulatoryProfile | str,
) -> BaCvaHedgeRecognitionLine:
    decision = _assess_ba_cva_hedge_eligibility(hedge_batch, hedge_index, profile=profile)
    hedge_type, reference_relation, counterparty_id = _hedge_row_context(hedge_batch, hedge_index)
    if decision.eligibility is not HedgeEligibility.ELIGIBLE:
        return _ineligible_hedge_line(
            hedge_batch, hedge_index, decision, hedge_type, reference_relation, counterparty_id
        )
    if counterparty_id not in scva_by_counterparty:
        raise CvaInputError(
            "hedge counterparty is not in BA-CVA counterparty set",
            field="counterparty_id",
            record_id=counterparty_id,
        )
    r_hc, rhc_citation = ba_cva_hedge_counterparty_correlation(
        reference_relation,
        profile=profile,
    )
    risk_weight, rw_citation = _hedge_risk_weight(hedge_batch, hedge_index, profile=profile)
    discount_factor, df_citation, _ = _hedge_discount_factor(
        hedge_batch,
        hedge_index,
        profile=profile,
    )
    weighted_notional = (
        risk_weight
        * float(hedge_batch.remaining_maturities[hedge_index])
        * float(hedge_batch.notionals[hedge_index])
        * discount_factor
    )
    line_factory = (
        _index_hedge_line if hedge_type is BaCvaHedgeType.INDEX_CDS else _single_name_hedge_line
    )
    return line_factory(
        hedge_batch,
        hedge_index,
        decision,
        hedge_type,
        reference_relation,
        counterparty_id,
        r_hc=r_hc,
        risk_weight=risk_weight,
        weighted_notional=weighted_notional,
        citations=(rhc_citation, rw_citation, df_citation),
        profile=profile,
    )


def _hedge_row_context(
    hedge_batch: CvaHedgeBatch,
    hedge_index: int,
) -> tuple[BaCvaHedgeType, HedgeReferenceRelation, str]:
    hedge_type_value = hedge_batch.hedge_types[hedge_index]
    if hedge_type_value is None:
        raise CvaInputError(
            "BA-CVA hedge requires hedge_type",
            field="hedge_type",
            record_id=cast(str, hedge_batch.hedge_ids[hedge_index]),
        )
    return (
        BaCvaHedgeType(cast(str, hedge_type_value)),
        HedgeReferenceRelation(cast(str, hedge_batch.reference_relations[hedge_index])),
        cast(str, hedge_batch.counterparty_ids[hedge_index]),
    )


def _ineligible_hedge_line(
    hedge_batch: CvaHedgeBatch,
    hedge_index: int,
    decision: HedgeEligibilityDecision,
    hedge_type: BaCvaHedgeType,
    reference_relation: HedgeReferenceRelation,
    counterparty_id: str,
) -> BaCvaHedgeRecognitionLine:
    return BaCvaHedgeRecognitionLine(
        hedge_id=cast(str, hedge_batch.hedge_ids[hedge_index]),
        counterparty_id=counterparty_id,
        hedge_type=hedge_type,
        eligibility=decision.eligibility,
        reference_relation=reference_relation,
        r_hc=0.0,
        risk_weight=0.0,
        snh_contribution=0.0,
        hma_contribution=0.0,
        index_contribution=0.0,
        reason_code=decision.reason_code,
        citations=decision.citations,
    )


def _index_hedge_line(
    hedge_batch: CvaHedgeBatch,
    hedge_index: int,
    decision: HedgeEligibilityDecision,
    hedge_type: BaCvaHedgeType,
    reference_relation: HedgeReferenceRelation,
    counterparty_id: str,
    *,
    r_hc: float,
    risk_weight: float,
    weighted_notional: float,
    citations: tuple[str, str, str],
    profile: CvaRegulatoryProfile | str,
) -> BaCvaHedgeRecognitionLine:
    return BaCvaHedgeRecognitionLine(
        hedge_id=cast(str, hedge_batch.hedge_ids[hedge_index]),
        counterparty_id=counterparty_id,
        hedge_type=hedge_type,
        eligibility=HedgeEligibility.ELIGIBLE,
        reference_relation=reference_relation,
        r_hc=r_hc,
        risk_weight=risk_weight,
        snh_contribution=0.0,
        hma_contribution=0.0,
        index_contribution=weighted_notional,
        reason_code=decision.reason_code,
        citations=_unique_citations(
            *decision.citations,
            *citations,
            profile_citation_id("basel_mar50_24", profile),
        ),
    )


def _single_name_hedge_line(
    hedge_batch: CvaHedgeBatch,
    hedge_index: int,
    decision: HedgeEligibilityDecision,
    hedge_type: BaCvaHedgeType,
    reference_relation: HedgeReferenceRelation,
    counterparty_id: str,
    *,
    r_hc: float,
    risk_weight: float,
    weighted_notional: float,
    citations: tuple[str, str, str],
    profile: CvaRegulatoryProfile | str,
) -> BaCvaHedgeRecognitionLine:
    snh_term = r_hc * weighted_notional
    hma_term = 0.0
    if reference_relation is not HedgeReferenceRelation.DIRECT:
        hma_term = (1.0 - r_hc**2) * (weighted_notional**2)
    return BaCvaHedgeRecognitionLine(
        hedge_id=cast(str, hedge_batch.hedge_ids[hedge_index]),
        counterparty_id=counterparty_id,
        hedge_type=hedge_type,
        eligibility=HedgeEligibility.ELIGIBLE,
        reference_relation=reference_relation,
        r_hc=r_hc,
        risk_weight=risk_weight,
        snh_contribution=snh_term,
        hma_contribution=hma_term,
        index_contribution=0.0,
        reason_code=decision.reason_code,
        citations=_unique_citations(
            *decision.citations,
            *citations,
            profile_citation_id("basel_mar50_23", profile),
        ),
    )
