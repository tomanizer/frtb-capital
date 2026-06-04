"""
SA-CVA GIRR delta and vega risk-class calculation.
"""

from __future__ import annotations

from frtb_cva.aggregation import (
    girr_delta_aggregation_config,
    girr_vega_aggregation_config,
)
from frtb_cva.data_models import (
    CvaHedge,
    CvaRegulatoryProfile,
    SaCvaRiskClassCapital,
    SaCvaSensitivity,
)
from frtb_cva.risk_classes._common import calculate_risk_class_capital
from frtb_cva.validation import CvaInputError


def calculate_girr_delta_capital(
    sensitivities: tuple[SaCvaSensitivity, ...],
    *,
    hedges: tuple[CvaHedge, ...] = (),
    m_cva: float = 1.0,
    reporting_currency: str = "USD",
    profile: CvaRegulatoryProfile | str = CvaRegulatoryProfile.BASEL_MAR50_2020,
) -> SaCvaRiskClassCapital:
    """Calculate SA-CVA GIRR delta capital for supported sensitivities.

Parameters
----------
sensitivities :
    Raw SA-CVA sensitivities prior to weighting.

hedges, optional :
    Declared BA-CVA or SA-CVA hedge records assessed for eligibility.

m_cva, optional :
    SA-CVA multiplier ``M_CVA`` applied after inter-bucket aggregation (MAR50.53).

reporting_currency, optional :
    Input for ``calculate_girr_delta_capital`` used in the CVA capital path.

profile, optional :
    Optional regulatory profile label or ``CvaRegulatoryProfile`` value; defaults to Basel MAR50 (2020).

Returns
-------
SaCvaRiskClassCapital
    Result of ``calculate_girr_delta_capital`` for audit and downstream aggregation."""

    if not sensitivities:
        raise CvaInputError("GIRR delta requires at least one sensitivity", field="sensitivities")
    return calculate_risk_class_capital(
        sensitivities,
        aggregation_config=girr_delta_aggregation_config(profile=profile),
        hedges=hedges,
        m_cva=m_cva,
        reporting_currency=reporting_currency,
        profile=profile,
    )


def calculate_girr_vega_capital(
    sensitivities: tuple[SaCvaSensitivity, ...],
    *,
    hedges: tuple[CvaHedge, ...] = (),
    m_cva: float = 1.0,
    reporting_currency: str = "USD",
    profile: CvaRegulatoryProfile | str = CvaRegulatoryProfile.BASEL_MAR50_2020,
) -> SaCvaRiskClassCapital:
    """Calculate SA-CVA GIRR vega capital per MAR50.58.

Parameters
----------
sensitivities :
    Raw SA-CVA sensitivities prior to weighting.

hedges, optional :
    Declared BA-CVA or SA-CVA hedge records assessed for eligibility.

m_cva, optional :
    SA-CVA multiplier ``M_CVA`` applied after inter-bucket aggregation (MAR50.53).

reporting_currency, optional :
    Input for ``calculate_girr_vega_capital`` used in the CVA capital path.

profile, optional :
    Optional regulatory profile label or ``CvaRegulatoryProfile`` value; defaults to Basel MAR50 (2020).

Returns
-------
SaCvaRiskClassCapital
    Result of ``calculate_girr_vega_capital`` for audit and downstream aggregation."""

    if not sensitivities:
        raise CvaInputError("GIRR vega requires at least one sensitivity", field="sensitivities")
    return calculate_risk_class_capital(
        sensitivities,
        aggregation_config=girr_vega_aggregation_config(profile=profile),
        hedges=hedges,
        m_cva=m_cva,
        reporting_currency=reporting_currency,
        profile=profile,
    )


__all__ = ["calculate_girr_delta_capital", "calculate_girr_vega_capital"]
