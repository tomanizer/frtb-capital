"""Shared SA-CVA risk-class calculation helpers."""

from __future__ import annotations

from frtb_cva.aggregation import SaCvaAggregationConfig, aggregate_weighted_sensitivities
from frtb_cva.data_models import (
    CvaHedge,
    CvaRegulatoryProfile,
    SaCvaRiskClassCapital,
    SaCvaSensitivity,
)
from frtb_cva.hedges import eligible_sa_cva_hedge_ids
from frtb_cva.validation import validate_cva_hedges, validate_sa_cva_sensitivities
from frtb_cva.weighted_sensitivity import (
    compute_weighted_sensitivities,
    sort_weighted_sensitivities,
)


def calculate_risk_class_capital(
    sensitivities: tuple[SaCvaSensitivity, ...],
    *,
    aggregation_config: SaCvaAggregationConfig,
    hedges: tuple[CvaHedge, ...] = (),
    m_cva: float = 1.0,
    reporting_currency: str = "USD",
    profile: CvaRegulatoryProfile | str = CvaRegulatoryProfile.BASEL_MAR50_2020,
) -> SaCvaRiskClassCapital:
    """Validate, weight, and aggregate sensitivities for one risk class.

    Parameters
    ----------
    sensitivities :
        Raw SA-CVA sensitivities prior to weighting.

    aggregation_config :
        Input for ``calculate_risk_class_capital`` used in the CVA capital path.

    hedges, optional :
        Declared BA-CVA or SA-CVA hedge records assessed for eligibility.

    m_cva, optional :
        SA-CVA multiplier ``M_CVA`` applied after inter-bucket aggregation (MAR50.53).

    reporting_currency, optional :
        Input for ``calculate_risk_class_capital`` used in the CVA capital path.

    profile, optional :
        Optional ``CvaRegulatoryProfile`` or profile label; default Basel MAR50 (2020).

    Returns
    -------
    SaCvaRiskClassCapital
        Result of ``calculate_risk_class_capital`` for audit and downstream aggregation."""

    validated = validate_sa_cva_sensitivities(sensitivities)
    validated_hedges = validate_cva_hedges(hedges)
    eligible_ids = eligible_sa_cva_hedge_ids(validated_hedges, profile=profile)
    weighted = sort_weighted_sensitivities(
        compute_weighted_sensitivities(
            validated,
            hedges=validated_hedges,
            eligible_hedge_ids=eligible_ids,
            reporting_currency=reporting_currency,
            profile=profile,
        )
    )
    return aggregate_weighted_sensitivities(
        weighted,
        config=aggregation_config,
        m_cva=m_cva,
        profile=profile,
    )


__all__ = ["calculate_risk_class_capital"]
