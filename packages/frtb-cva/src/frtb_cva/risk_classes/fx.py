"""
SA-CVA FX delta and vega risk-class calculation.
"""

from __future__ import annotations

from frtb_cva.aggregation import SaCvaAggregationConfig, uniform_inter_bucket_gamma
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
from frtb_cva.sa_cva_reference_data import fx_inter_bucket_correlation
from frtb_cva.validation import CvaInputError


def _single_factor_correlation(
    left: SaCvaWeightedSensitivity,
    right: SaCvaWeightedSensitivity,
) -> tuple[float, str]:
    del left, right
    return 1.0, "basel_mar50_61"


def _fx_delta_config(
    profile: CvaRegulatoryProfile | str,
) -> SaCvaAggregationConfig:
    gamma_bc, gamma_citation = fx_inter_bucket_correlation(profile=profile)
    return SaCvaAggregationConfig(
        risk_class=SaCvaRiskClass.FX,
        risk_measure=SaCvaRiskMeasure.DELTA,
        intra_bucket_correlation=_single_factor_correlation,
        inter_bucket_gamma=uniform_inter_bucket_gamma(gamma_bc, gamma_citation),
        intra_bucket_citations=(
            profile_citation_id("basel_mar50_53", profile),
            profile_citation_id("basel_mar50_61", profile),
        ),
    )


def _fx_vega_config(
    profile: CvaRegulatoryProfile | str,
) -> SaCvaAggregationConfig:
    gamma_bc, gamma_citation = fx_inter_bucket_correlation(profile=profile)
    return SaCvaAggregationConfig(
        risk_class=SaCvaRiskClass.FX,
        risk_measure=SaCvaRiskMeasure.VEGA,
        intra_bucket_correlation=_single_factor_correlation,
        inter_bucket_gamma=uniform_inter_bucket_gamma(gamma_bc, gamma_citation),
        intra_bucket_citations=(
            profile_citation_id("basel_mar50_53", profile),
            profile_citation_id("basel_mar50_62", profile),
        ),
    )


def calculate_fx_delta_capital(
    sensitivities: tuple[SaCvaSensitivity, ...],
    *,
    hedges: tuple[CvaHedge, ...] = (),
    m_cva: float = 1.0,
    reporting_currency: str = "USD",
    profile: CvaRegulatoryProfile | str = CvaRegulatoryProfile.BASEL_MAR50_2020,
) -> SaCvaRiskClassCapital:
    """Calculate SA-CVA FX delta capital per MAR50.59-MAR50.61."""

    if not sensitivities:
        raise CvaInputError("FX delta requires at least one sensitivity", field="sensitivities")
    return calculate_risk_class_capital(
        sensitivities,
        aggregation_config=_fx_delta_config(profile),
        hedges=hedges,
        m_cva=m_cva,
        reporting_currency=reporting_currency,
        profile=profile,
    )


def calculate_fx_vega_capital(
    sensitivities: tuple[SaCvaSensitivity, ...],
    *,
    hedges: tuple[CvaHedge, ...] = (),
    m_cva: float = 1.0,
    reporting_currency: str = "USD",
    profile: CvaRegulatoryProfile | str = CvaRegulatoryProfile.BASEL_MAR50_2020,
) -> SaCvaRiskClassCapital:
    """Calculate SA-CVA FX vega capital per MAR50.62."""

    if not sensitivities:
        raise CvaInputError("FX vega requires at least one sensitivity", field="sensitivities")
    return calculate_risk_class_capital(
        sensitivities,
        aggregation_config=_fx_vega_config(profile),
        hedges=hedges,
        m_cva=m_cva,
        reporting_currency=reporting_currency,
        profile=profile,
    )


__all__ = ["calculate_fx_delta_capital", "calculate_fx_vega_capital"]
