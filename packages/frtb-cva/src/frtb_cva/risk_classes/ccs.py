"""
SA-CVA counterparty credit spread (CCS) delta risk-class calculation.

MAR50.45 and MAR50.63: no CCS vega capital.
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
from frtb_cva.sa_cva_reference_data import (
    ccs_delta_intra_bucket_correlation,
    ccs_inter_bucket_correlation,
    parse_ccs_entity_key,
)
from frtb_cva.validation import CvaInputError


def _ccs_gamma_bucket(bucket_id: str) -> str:
    """Map CCS bucket ids (including 1a/1b) to gamma table keys."""

    if bucket_id in {"1a", "1b"}:
        return "1"
    return bucket_id


def _ccs_intra_bucket_correlation(
    left: SaCvaWeightedSensitivity,
    right: SaCvaWeightedSensitivity,
    *,
    profile: CvaRegulatoryProfile | str,
) -> tuple[float, str]:
    left_entity, left_quality, left_legal = parse_ccs_entity_key(
        left.risk_factor_key.risk_factor_key
    )
    right_entity, right_quality, right_legal = parse_ccs_entity_key(
        right.risk_factor_key.risk_factor_key
    )
    same_entity = left_entity == right_entity
    legally_related = not same_entity and left_legal is not None and left_legal == right_legal
    same_credit_quality = left_quality == right_quality
    left_tenor = left.risk_factor_key.tenor
    right_tenor = right.risk_factor_key.tenor
    if left_tenor is None or right_tenor is None:
        raise CvaInputError("CCS delta requires tenor on weighted sensitivities", field="tenor")
    same_tenor = left_tenor == right_tenor
    return ccs_delta_intra_bucket_correlation(
        same_entity=same_entity,
        legally_related=legally_related,
        same_credit_quality=same_credit_quality,
        same_tenor=same_tenor,
        profile=profile,
    )


def _ccs_inter_bucket_gamma(
    left_bucket: str,
    right_bucket: str,
    *,
    profile: CvaRegulatoryProfile | str,
) -> tuple[float, str]:
    return ccs_inter_bucket_correlation(
        _ccs_gamma_bucket(left_bucket),
        _ccs_gamma_bucket(right_bucket),
        profile=profile,
    )


def _ccs_delta_config(
    profile: CvaRegulatoryProfile | str,
) -> SaCvaAggregationConfig:
    def _intra(
        left: SaCvaWeightedSensitivity, right: SaCvaWeightedSensitivity
    ) -> tuple[float, str]:
        return _ccs_intra_bucket_correlation(left, right, profile=profile)

    def _gamma(left_bucket: str, right_bucket: str) -> tuple[float, str]:
        return _ccs_inter_bucket_gamma(left_bucket, right_bucket, profile=profile)

    return SaCvaAggregationConfig(
        risk_class=SaCvaRiskClass.COUNTERPARTY_CREDIT_SPREAD,
        risk_measure=SaCvaRiskMeasure.DELTA,
        intra_bucket_correlation=_intra,
        inter_bucket_gamma=_gamma,
        intra_bucket_citations=(
            profile_citation_id("basel_mar50_53", profile),
            profile_citation_id("basel_mar50_65", profile),
        ),
    )


def calculate_ccs_delta_capital(
    sensitivities: tuple[SaCvaSensitivity, ...],
    *,
    hedges: tuple[CvaHedge, ...] = (),
    m_cva: float = 1.0,
    reporting_currency: str = "USD",
    profile: CvaRegulatoryProfile | str = CvaRegulatoryProfile.BASEL_MAR50_2020,
) -> SaCvaRiskClassCapital:
    """Calculate SA-CVA CCS delta capital per MAR50.63-MAR50.65.

    Parameters
    ----------
    sensitivities :
        Raw SA-CVA sensitivities prior to weighting.

    hedges, optional :
        Declared BA-CVA or SA-CVA hedge records assessed for eligibility.

    m_cva, optional :
        SA-CVA multiplier ``M_CVA`` applied after inter-bucket aggregation (MAR50.53).

    reporting_currency, optional :
        Input for ``calculate_ccs_delta_capital`` used in the CVA capital path.

    profile, optional :
        Optional ``CvaRegulatoryProfile`` or profile label; default Basel MAR50 (2020).

    Returns
    -------
    SaCvaRiskClassCapital
        Result of ``calculate_ccs_delta_capital`` for audit and downstream aggregation."""

    del reporting_currency
    if not sensitivities:
        raise CvaInputError("CCS delta requires at least one sensitivity", field="sensitivities")
    return calculate_risk_class_capital(
        sensitivities,
        aggregation_config=_ccs_delta_config(profile),
        hedges=hedges,
        m_cva=m_cva,
        profile=profile,
    )


__all__ = ["calculate_ccs_delta_capital"]
