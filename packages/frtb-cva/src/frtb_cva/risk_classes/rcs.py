"""
SA-CVA reference credit spread (RCS) delta and vega risk-class calculation.
"""

from __future__ import annotations

from frtb_cva.aggregation import SaCvaAggregationConfig
from frtb_cva.data_models import (
    CvaHedge,
    CvaRegulatoryProfile,
    SaCvaRiskClass,
    SaCvaRiskClassCapital,
    SaCvaRiskMeasure,
    SaCvaSensitivity,
    SaCvaWeightedSensitivity,
)
from frtb_cva.reference_data import profile_citation_id
from frtb_cva.risk_classes._common import calculate_risk_class_capital
from frtb_cva.sa_cva_reference_data import rcs_inter_bucket_correlation
from frtb_cva.validation import CvaInputError


def _rcs_intra_bucket_correlation(
    left: SaCvaWeightedSensitivity,
    right: SaCvaWeightedSensitivity,
) -> tuple[float, str]:
    # MAR50.68: rho_kl = 1 if same reference name, 0.50 otherwise.
    same_name = left.risk_factor_key.risk_factor_key == right.risk_factor_key.risk_factor_key
    rho = 1.0 if same_name else 0.50
    return rho, "basel_mar50_68"


def _rcs_config(
    risk_measure: SaCvaRiskMeasure,
    *,
    profile: CvaRegulatoryProfile | str,
) -> SaCvaAggregationConfig:
    def _gamma(left_bucket: str, right_bucket: str) -> tuple[float, str]:
        return rcs_inter_bucket_correlation(left_bucket, right_bucket, profile=profile)

    citation = "basel_mar50_69" if risk_measure is SaCvaRiskMeasure.VEGA else "basel_mar50_68"
    return SaCvaAggregationConfig(
        risk_class=SaCvaRiskClass.REFERENCE_CREDIT_SPREAD,
        risk_measure=risk_measure,
        intra_bucket_correlation=_rcs_intra_bucket_correlation,
        inter_bucket_gamma=_gamma,
        intra_bucket_citations=(
            profile_citation_id("basel_mar50_53", profile),
            profile_citation_id(citation, profile),
        ),
    )


def calculate_rcs_delta_capital(
    sensitivities: tuple[SaCvaSensitivity, ...],
    *,
    hedges: tuple[CvaHedge, ...] = (),
    m_cva: float = 1.0,
    reporting_currency: str = "USD",
    profile: CvaRegulatoryProfile | str = CvaRegulatoryProfile.BASEL_MAR50_2020,
) -> SaCvaRiskClassCapital:
    """Calculate SA-CVA RCS delta capital per MAR50.66-MAR50.68.

Parameters
----------
sensitivities :
    Raw SA-CVA sensitivities prior to weighting.

hedges, optional :
    Declared BA-CVA or SA-CVA hedge records assessed for eligibility.

m_cva, optional :
    SA-CVA multiplier ``M_CVA`` applied after inter-bucket aggregation (MAR50.53).

reporting_currency, optional :
    Input for ``calculate_rcs_delta_capital`` used in the CVA capital path.

profile, optional :
    Optional regulatory profile label or ``CvaRegulatoryProfile`` value; defaults to Basel MAR50 (2020).

Returns
-------
SaCvaRiskClassCapital
    Result of ``calculate_rcs_delta_capital`` for audit and downstream aggregation."""

    del reporting_currency
    if not sensitivities:
        raise CvaInputError("RCS delta requires at least one sensitivity", field="sensitivities")
    return calculate_risk_class_capital(
        sensitivities,
        aggregation_config=_rcs_config(SaCvaRiskMeasure.DELTA, profile=profile),
        hedges=hedges,
        m_cva=m_cva,
        profile=profile,
    )


def calculate_rcs_vega_capital(
    sensitivities: tuple[SaCvaSensitivity, ...],
    *,
    hedges: tuple[CvaHedge, ...] = (),
    m_cva: float = 1.0,
    reporting_currency: str = "USD",
    profile: CvaRegulatoryProfile | str = CvaRegulatoryProfile.BASEL_MAR50_2020,
) -> SaCvaRiskClassCapital:
    """Calculate SA-CVA RCS vega capital per MAR50.69.

Parameters
----------
sensitivities :
    Raw SA-CVA sensitivities prior to weighting.

hedges, optional :
    Declared BA-CVA or SA-CVA hedge records assessed for eligibility.

m_cva, optional :
    SA-CVA multiplier ``M_CVA`` applied after inter-bucket aggregation (MAR50.53).

reporting_currency, optional :
    Input for ``calculate_rcs_vega_capital`` used in the CVA capital path.

profile, optional :
    Optional regulatory profile label or ``CvaRegulatoryProfile`` value; defaults to Basel MAR50 (2020).

Returns
-------
SaCvaRiskClassCapital
    Result of ``calculate_rcs_vega_capital`` for audit and downstream aggregation."""

    del reporting_currency
    if not sensitivities:
        raise CvaInputError("RCS vega requires at least one sensitivity", field="sensitivities")
    return calculate_risk_class_capital(
        sensitivities,
        aggregation_config=_rcs_config(SaCvaRiskMeasure.VEGA, profile=profile),
        hedges=hedges,
        m_cva=m_cva,
        profile=profile,
    )


__all__ = ["calculate_rcs_delta_capital", "calculate_rcs_vega_capital"]
