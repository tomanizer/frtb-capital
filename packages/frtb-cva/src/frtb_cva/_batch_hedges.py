"""CVA batch hedge eligibility and BA hedge weighting helpers."""

from __future__ import annotations

import math
from enum import StrEnum
from numbers import Real
from typing import TypeVar, cast

from frtb_cva._batch_contracts import CvaHedgeBatch
from frtb_cva.data_models import (
    BaCvaHedgeType,
    CreditQuality,
    CvaHedge,
    CvaRegulatoryProfile,
    CvaSector,
    CvaSourceLineage,
    HedgeEligibility,
    HedgeReferenceRelation,
    SaCvaHedgeInstrumentType,
    SaCvaHedgePurpose,
    SaCvaRiskClass,
)
from frtb_cva.hedges import (
    HedgeEligibilityDecision,
    assess_ba_cva_hedge_eligibility,
    assess_hedge_eligibility,
)
from frtb_cva.reference_data import (
    ba_cva_index_risk_weight_scalar,
    ba_cva_risk_weight,
    compute_non_imm_discount_factor,
    profile_citation_id,
)

_OptionalEnum = TypeVar("_OptionalEnum", bound=StrEnum)


def _assess_sa_cva_hedge_eligibility(
    batch: CvaHedgeBatch,
    index: int,
    *,
    profile: CvaRegulatoryProfile | str,
) -> HedgeEligibilityDecision:
    return assess_hedge_eligibility(_hedge_from_batch_row(batch, index), profile=profile)


def _assess_ba_cva_hedge_eligibility(
    batch: CvaHedgeBatch,
    index: int,
    *,
    profile: CvaRegulatoryProfile | str,
) -> HedgeEligibilityDecision:
    return assess_ba_cva_hedge_eligibility(_hedge_from_batch_row(batch, index), profile=profile)


def _hedge_from_batch_row(batch: CvaHedgeBatch, index: int) -> CvaHedge:
    return CvaHedge(
        hedge_id=cast(str, batch.hedge_ids[index]),
        source_row_id=cast(str, batch.source_row_ids[index]),
        counterparty_id=cast(str, batch.counterparty_ids[index]),
        hedge_type=_optional_enum(batch.hedge_types[index], BaCvaHedgeType),
        notional=float(batch.notionals[index]),
        remaining_maturity=float(batch.remaining_maturities[index]),
        discount_factor=float(batch.discount_factors[index]),
        reference_sector=CvaSector(cast(str, batch.reference_sectors[index])),
        reference_credit_quality=CreditQuality(cast(str, batch.reference_credit_qualities[index])),
        reference_region=cast(str, batch.reference_regions[index]),
        reference_relation=HedgeReferenceRelation(cast(str, batch.reference_relations[index])),
        eligibility=HedgeEligibility(cast(str, batch.eligibilities[index])),
        is_internal=bool(batch.is_internal[index]),
        discount_factor_explicit=bool(batch.discount_factor_explicit[index]),
        internal_desk_counterparty_id=_optional_text(batch.internal_desk_counterparty_ids[index]),
        sa_cva_risk_class=_optional_enum(batch.sa_cva_risk_classes[index], SaCvaRiskClass),
        sa_cva_hedge_purpose=_optional_enum(
            batch.sa_cva_hedge_purposes[index],
            SaCvaHedgePurpose,
        ),
        sa_cva_hedge_instrument_type=_optional_enum(
            batch.sa_cva_hedge_instrument_types[index],
            SaCvaHedgeInstrumentType,
        ),
        whole_transaction_evidence_id=_optional_text(batch.whole_transaction_evidence_ids[index]),
        market_risk_ima_eligible=_optional_bool(batch.market_risk_ima_eligibilities[index]),
        market_risk_ima_exclusion_reason=_optional_text(
            batch.market_risk_ima_exclusion_reasons[index]
        ),
        eligibility_evidence_id=_optional_text(batch.eligibility_evidence_ids[index]),
        rejection_reason=_optional_text(batch.rejection_reasons[index]),
        lineage=CvaSourceLineage(
            source_system=cast(str, batch.lineage_source_systems[index]),
            source_file=cast(str, batch.lineage_source_files[index]),
            source_row_id=cast(str, batch.lineage_source_row_ids[index]),
            source_column_map=batch.source_column_maps[index],
        ),
    )


def _optional_enum(value: object, enum_type: type[_OptionalEnum]) -> _OptionalEnum | None:
    if _is_missing_optional(value):
        return None
    return enum_type(str(value))


def _optional_bool(value: object) -> bool | None:
    if _is_missing_optional(value):
        return None
    return bool(value)


def _optional_text(value: object) -> str | None:
    if _is_missing_optional(value):
        return None
    return cast(str, value)


def _is_missing_optional(value: object) -> bool:
    return value is None or (
        isinstance(value, Real) and not isinstance(value, bool) and math.isnan(float(value))
    )


def _eligible_sa_cva_hedge_ids(
    batch: CvaHedgeBatch,
    *,
    profile: CvaRegulatoryProfile | str,
) -> frozenset[str]:
    eligible: set[str] = set()
    for index in range(batch.row_count):
        if (
            _assess_sa_cva_hedge_eligibility(batch, index, profile=profile).eligibility
            is HedgeEligibility.ELIGIBLE
        ):
            eligible.add(cast(str, batch.hedge_ids[index]))
    return frozenset(eligible)


def _hedge_discount_factor(
    batch: CvaHedgeBatch,
    index: int,
    *,
    profile: CvaRegulatoryProfile | str,
) -> tuple[float, str, bool]:
    discount_factor = float(batch.discount_factors[index])
    if bool(batch.discount_factor_explicit[index]) or discount_factor != 1.0:
        return discount_factor, profile_citation_id("basel_mar50_23", profile), True
    calculated, citation = compute_non_imm_discount_factor(float(batch.remaining_maturities[index]))
    return calculated, profile_citation_id(citation, profile), False


def _hedge_risk_weight(
    batch: CvaHedgeBatch,
    index: int,
    *,
    profile: CvaRegulatoryProfile | str,
) -> tuple[float, str]:
    risk_weight, citation = ba_cva_risk_weight(
        CvaSector(cast(str, batch.reference_sectors[index])),
        CreditQuality(cast(str, batch.reference_credit_qualities[index])),
        profile=profile,
    )
    if BaCvaHedgeType(cast(str, batch.hedge_types[index])) is BaCvaHedgeType.INDEX_CDS:
        scalar, scalar_citation = ba_cva_index_risk_weight_scalar(profile=profile)
        return risk_weight * scalar, scalar_citation
    return risk_weight, citation
