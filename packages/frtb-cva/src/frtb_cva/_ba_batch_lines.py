"""BA-CVA batch audit-line construction helpers."""

from __future__ import annotations

from typing import cast

from frtb_cva._batch_contracts import CvaCounterpartyBatch, CvaNettingSetBatch
from frtb_cva.ba_cva import _unique_citations
from frtb_cva.data_models import (
    BaCvaStandAloneLine,
    CreditQuality,
    CvaRegulatoryProfile,
    CvaSector,
)
from frtb_cva.org_scope import scope_at
from frtb_cva.reference_data import (
    ba_cva_alpha,
    ba_cva_risk_weight,
    resolve_netting_set_discount_factor,
)


def _netting_set_line_from_batch(
    netting_sets: CvaNettingSetBatch,
    netting_index: int,
    counterparties: CvaCounterpartyBatch,
    counterparty_index: int,
    *,
    profile: CvaRegulatoryProfile | str,
    risk_weight: float | None = None,
    risk_weight_citation: str | None = None,
    alpha: float | None = None,
    alpha_citation: str | None = None,
    sector: CvaSector | None = None,
    credit_quality: CreditQuality | None = None,
) -> BaCvaStandAloneLine:
    """Build a BA-CVA standalone audit line from aligned batch rows."""
    resolved_sector = sector or CvaSector(cast(str, counterparties.sectors[counterparty_index]))
    resolved_credit_quality = credit_quality or CreditQuality(
        cast(str, counterparties.credit_qualities[counterparty_index])
    )
    if risk_weight is None or risk_weight_citation is None:
        risk_weight, risk_weight_citation = ba_cva_risk_weight(
            resolved_sector,
            resolved_credit_quality,
            profile=profile,
        )
    if alpha is None or alpha_citation is None:
        alpha, alpha_citation = ba_cva_alpha(profile=profile)
    discount_factor, df_citation, discount_factor_supplied = resolve_netting_set_discount_factor(
        uses_imm_ead=bool(netting_sets.uses_imm_eads[netting_index]),
        effective_maturity=float(netting_sets.effective_maturities[netting_index]),
        supplied_discount_factor=float(netting_sets.discount_factors[netting_index]),
        discount_factor_explicit=bool(netting_sets.discount_factor_explicit[netting_index]),
        profile=profile,
    )
    standalone = (
        risk_weight
        * float(netting_sets.effective_maturities[netting_index])
        * float(netting_sets.eads[netting_index])
        * discount_factor
        / alpha
    )
    return BaCvaStandAloneLine(
        netting_set_id=cast(str, netting_sets.netting_set_ids[netting_index]),
        counterparty_id=cast(str, counterparties.counterparty_ids[counterparty_index]),
        sector=resolved_sector,
        credit_quality=resolved_credit_quality,
        ead=float(netting_sets.eads[netting_index]),
        effective_maturity=float(netting_sets.effective_maturities[netting_index]),
        discount_factor=discount_factor,
        alpha=alpha,
        risk_weight=risk_weight,
        standalone_capital=standalone,
        currency=cast(str, netting_sets.currencies[netting_index]),
        source_row_id=cast(str, netting_sets.source_row_ids[netting_index]),
        citations=_unique_citations(risk_weight_citation, alpha_citation, df_citation),
        uses_imm_ead=bool(netting_sets.uses_imm_eads[netting_index]),
        discount_factor_supplied=discount_factor_supplied,
        org_scope=scope_at(netting_sets.org_scopes, netting_index),
    )
