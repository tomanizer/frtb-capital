"""
SA-CVA GIRR delta risk-class calculation.
"""

from __future__ import annotations

from frtb_cva.aggregation import aggregate_weighted_sensitivities
from frtb_cva.data_models import (
    CvaHedge,
    CvaRegulatoryProfile,
    SaCvaRiskClassCapital,
    SaCvaSensitivity,
)
from frtb_cva.hedges import eligible_sa_cva_hedge_ids
from frtb_cva.validation import CvaInputError, validate_cva_hedges, validate_sa_cva_sensitivities
from frtb_cva.weighted_sensitivity import (
    compute_weighted_sensitivities,
    sort_weighted_sensitivities,
)


def calculate_girr_delta_capital(
    sensitivities: tuple[SaCvaSensitivity, ...],
    *,
    hedges: tuple[CvaHedge, ...] = (),
    m_cva: float = 1.0,
    reporting_currency: str = "USD",
    profile: CvaRegulatoryProfile | str = CvaRegulatoryProfile.BASEL_MAR50_2020,
) -> SaCvaRiskClassCapital:
    """Calculate SA-CVA GIRR delta capital for supported sensitivities."""

    if not sensitivities:
        raise CvaInputError("GIRR delta requires at least one sensitivity", field="sensitivities")

    validated = validate_sa_cva_sensitivities(sensitivities)
    validated_hedges = validate_cva_hedges(hedges)
    eligible_ids = eligible_sa_cva_hedge_ids(validated_hedges)
    weighted = sort_weighted_sensitivities(
        compute_weighted_sensitivities(
            validated,
            eligible_hedge_ids=eligible_ids,
            reporting_currency=reporting_currency,
            profile=profile,
        )
    )
    return aggregate_weighted_sensitivities(weighted, m_cva=m_cva, profile=profile)


__all__ = ["calculate_girr_delta_capital"]
