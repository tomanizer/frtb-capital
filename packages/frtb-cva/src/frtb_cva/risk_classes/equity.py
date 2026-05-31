"""
SA-CVA equity delta and vega risk-class calculation.
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
from frtb_cva.sa_cva_reference_data import equity_inter_bucket_correlation
from frtb_cva.validation import CvaInputError


def _equity_intra_bucket_correlation(
    left: SaCvaWeightedSensitivity,
    right: SaCvaWeightedSensitivity,
) -> tuple[float, str]:
    # MAR50.72: rho_kl = 1 if same name; 0.15 (buckets 1-10) or 0.25 (buckets 11-13) otherwise.
    if left.risk_factor_key.risk_factor_key == right.risk_factor_key.risk_factor_key:
        return 1.0, "basel_mar50_72"
    rho = 0.25 if left.risk_factor_key.bucket_id in {"11", "12", "13"} else 0.15
    return rho, "basel_mar50_72"


def _equity_config(
    risk_measure: SaCvaRiskMeasure,
    *,
    profile: CvaRegulatoryProfile | str,
) -> SaCvaAggregationConfig:
    def _gamma(left_bucket: str, right_bucket: str) -> tuple[float, str]:
        return equity_inter_bucket_correlation(left_bucket, right_bucket, profile=profile)

    citation = "basel_mar50_73" if risk_measure is SaCvaRiskMeasure.VEGA else "basel_mar50_72"
    return SaCvaAggregationConfig(
        risk_class=SaCvaRiskClass.EQUITY,
        risk_measure=risk_measure,
        intra_bucket_correlation=_equity_intra_bucket_correlation,
        inter_bucket_gamma=_gamma,
        intra_bucket_citations=("basel_mar50_53", citation),
    )


def calculate_equity_delta_capital(
    sensitivities: tuple[SaCvaSensitivity, ...],
    *,
    hedges: tuple[CvaHedge, ...] = (),
    m_cva: float = 1.0,
    reporting_currency: str = "USD",
    profile: CvaRegulatoryProfile | str = CvaRegulatoryProfile.BASEL_MAR50_2020,
) -> SaCvaRiskClassCapital:
    """Calculate SA-CVA equity delta capital per MAR50.70-MAR50.72."""

    del reporting_currency
    if not sensitivities:
        raise CvaInputError("equity delta requires at least one sensitivity", field="sensitivities")
    return calculate_risk_class_capital(
        sensitivities,
        aggregation_config=_equity_config(SaCvaRiskMeasure.DELTA, profile=profile),
        hedges=hedges,
        m_cva=m_cva,
        profile=profile,
    )


def calculate_equity_vega_capital(
    sensitivities: tuple[SaCvaSensitivity, ...],
    *,
    hedges: tuple[CvaHedge, ...] = (),
    m_cva: float = 1.0,
    reporting_currency: str = "USD",
    profile: CvaRegulatoryProfile | str = CvaRegulatoryProfile.BASEL_MAR50_2020,
) -> SaCvaRiskClassCapital:
    """Calculate SA-CVA equity vega capital per MAR50.73."""

    del reporting_currency
    if not sensitivities:
        raise CvaInputError("equity vega requires at least one sensitivity", field="sensitivities")
    return calculate_risk_class_capital(
        sensitivities,
        aggregation_config=_equity_config(SaCvaRiskMeasure.VEGA, profile=profile),
        hedges=hedges,
        m_cva=m_cva,
        profile=profile,
    )


__all__ = ["calculate_equity_delta_capital", "calculate_equity_vega_capital"]
