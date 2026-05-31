"""
SA-CVA commodity delta and vega risk-class calculation.
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
from frtb_cva.risk_classes._common import calculate_risk_class_capital
from frtb_cva.sa_cva_reference_data import commodity_inter_bucket_correlation
from frtb_cva.validation import CvaInputError


def _commodity_intra_bucket_correlation(
    left: SaCvaWeightedSensitivity,
    right: SaCvaWeightedSensitivity,
) -> tuple[float, str]:
    # MAR50.76: rho_kl = 1 if same commodity name, 0.20 otherwise.
    same_name = left.risk_factor_key.risk_factor_key == right.risk_factor_key.risk_factor_key
    rho = 1.0 if same_name else 0.20
    return rho, "basel_mar50_76"


def _commodity_config(
    risk_measure: SaCvaRiskMeasure,
    *,
    profile: CvaRegulatoryProfile | str,
) -> SaCvaAggregationConfig:
    def _gamma(left_bucket: str, right_bucket: str) -> tuple[float, str]:
        return commodity_inter_bucket_correlation(left_bucket, right_bucket, profile=profile)

    citation = "basel_mar50_77" if risk_measure is SaCvaRiskMeasure.VEGA else "basel_mar50_76"
    return SaCvaAggregationConfig(
        risk_class=SaCvaRiskClass.COMMODITY,
        risk_measure=risk_measure,
        intra_bucket_correlation=_commodity_intra_bucket_correlation,
        inter_bucket_gamma=_gamma,
        intra_bucket_citations=("basel_mar50_53", citation),
    )


def calculate_commodity_delta_capital(
    sensitivities: tuple[SaCvaSensitivity, ...],
    *,
    hedges: tuple[CvaHedge, ...] = (),
    m_cva: float = 1.0,
    reporting_currency: str = "USD",
    profile: CvaRegulatoryProfile | str = CvaRegulatoryProfile.BASEL_MAR50_2020,
) -> SaCvaRiskClassCapital:
    """Calculate SA-CVA commodity delta capital per MAR50.74-MAR50.76."""

    del reporting_currency
    if not sensitivities:
        raise CvaInputError(
            "commodity delta requires at least one sensitivity",
            field="sensitivities",
        )
    return calculate_risk_class_capital(
        sensitivities,
        aggregation_config=_commodity_config(SaCvaRiskMeasure.DELTA, profile=profile),
        hedges=hedges,
        m_cva=m_cva,
        profile=profile,
    )


def calculate_commodity_vega_capital(
    sensitivities: tuple[SaCvaSensitivity, ...],
    *,
    hedges: tuple[CvaHedge, ...] = (),
    m_cva: float = 1.0,
    reporting_currency: str = "USD",
    profile: CvaRegulatoryProfile | str = CvaRegulatoryProfile.BASEL_MAR50_2020,
) -> SaCvaRiskClassCapital:
    """Calculate SA-CVA commodity vega capital per MAR50.77."""

    del reporting_currency
    if not sensitivities:
        raise CvaInputError(
            "commodity vega requires at least one sensitivity",
            field="sensitivities",
        )
    return calculate_risk_class_capital(
        sensitivities,
        aggregation_config=_commodity_config(SaCvaRiskMeasure.VEGA, profile=profile),
        hedges=hedges,
        m_cva=m_cva,
        profile=profile,
    )


__all__ = ["calculate_commodity_delta_capital", "calculate_commodity_vega_capital"]
