"""BA-CVA reference tables and scalar lookup helpers."""

from __future__ import annotations

import math
from dataclasses import dataclass

from frtb_cva._reference_profile_data import (
    _resolve_credit_quality,
    _resolve_sector,
    _resolve_supported_profile,
    profile_citation_id,
)
from frtb_cva.data_models import (
    CreditQuality,
    CvaRegulatoryProfile,
    CvaSector,
    HedgeReferenceRelation,
)
from frtb_cva.validation import CvaInputError

BA_CVA_ALPHA = 1.4
BA_CVA_RHO = 0.5
BA_CVA_BETA = 0.25
BA_CVA_INDEX_RW_SCALAR = 0.7
D_BA_CVA = 0.65
NON_IMM_DISCOUNT_RATE = 0.05

_HEDGE_REFERENCE_CORRELATIONS: dict[HedgeReferenceRelation, float] = {
    HedgeReferenceRelation.DIRECT: 1.0,
    HedgeReferenceRelation.LEGAL_RELATION: 0.8,
    HedgeReferenceRelation.SAME_SECTOR_AND_REGION: 0.5,
}


@dataclass(frozen=True)
class BaCvaRiskWeightRule:
    """Profile-specific BA-CVA Table 1 risk-weight entry."""

    sector: CvaSector
    credit_quality: CreditQuality
    risk_weight: float
    citation_id: str


_TABLE_1_RISK_WEIGHTS: dict[tuple[CvaSector, CreditQuality], float] = {
    (CvaSector.SOVEREIGN, CreditQuality.INVESTMENT_GRADE): 0.005,
    (CvaSector.SOVEREIGN, CreditQuality.HIGH_YIELD): 0.02,
    (CvaSector.SOVEREIGN, CreditQuality.NOT_RATED): 0.02,
    (CvaSector.LOCAL_GOVERNMENT, CreditQuality.INVESTMENT_GRADE): 0.01,
    (CvaSector.LOCAL_GOVERNMENT, CreditQuality.HIGH_YIELD): 0.04,
    (CvaSector.LOCAL_GOVERNMENT, CreditQuality.NOT_RATED): 0.04,
    (CvaSector.FINANCIALS, CreditQuality.INVESTMENT_GRADE): 0.05,
    (CvaSector.FINANCIALS, CreditQuality.HIGH_YIELD): 0.12,
    (CvaSector.FINANCIALS, CreditQuality.NOT_RATED): 0.12,
    (CvaSector.BASIC_MATERIALS_ENERGY_INDUSTRIALS, CreditQuality.INVESTMENT_GRADE): 0.03,
    (CvaSector.BASIC_MATERIALS_ENERGY_INDUSTRIALS, CreditQuality.HIGH_YIELD): 0.07,
    (CvaSector.BASIC_MATERIALS_ENERGY_INDUSTRIALS, CreditQuality.NOT_RATED): 0.07,
    (CvaSector.CONSUMER_TRANSPORT_ADMIN, CreditQuality.INVESTMENT_GRADE): 0.03,
    (CvaSector.CONSUMER_TRANSPORT_ADMIN, CreditQuality.HIGH_YIELD): 0.085,
    (CvaSector.CONSUMER_TRANSPORT_ADMIN, CreditQuality.NOT_RATED): 0.085,
    (CvaSector.TECHNOLOGY_TELECOM, CreditQuality.INVESTMENT_GRADE): 0.02,
    (CvaSector.TECHNOLOGY_TELECOM, CreditQuality.HIGH_YIELD): 0.055,
    (CvaSector.TECHNOLOGY_TELECOM, CreditQuality.NOT_RATED): 0.055,
    (CvaSector.HEALTH_UTILITIES_PROFESSIONAL, CreditQuality.INVESTMENT_GRADE): 0.015,
    (CvaSector.HEALTH_UTILITIES_PROFESSIONAL, CreditQuality.HIGH_YIELD): 0.05,
    (CvaSector.HEALTH_UTILITIES_PROFESSIONAL, CreditQuality.NOT_RATED): 0.05,
    (CvaSector.OTHER, CreditQuality.INVESTMENT_GRADE): 0.05,
    (CvaSector.OTHER, CreditQuality.HIGH_YIELD): 0.12,
    (CvaSector.OTHER, CreditQuality.NOT_RATED): 0.12,
}

BASEL_BA_CVA_RISK_WEIGHT_RULES: tuple[BaCvaRiskWeightRule, ...] = tuple(
    BaCvaRiskWeightRule(
        sector=sector,
        credit_quality=credit_quality,
        risk_weight=risk_weight,
        citation_id="basel_mar50_16",
    )
    for (sector, credit_quality), risk_weight in sorted(
        _TABLE_1_RISK_WEIGHTS.items(),
        key=lambda item: (item[0][0].value, item[0][1].value),
    )
)


def ba_cva_risk_weight(
    sector: CvaSector | str,
    credit_quality: CreditQuality | str,
    *,
    profile: CvaRegulatoryProfile | str = CvaRegulatoryProfile.BASEL_MAR50_2020,
) -> tuple[float, str]:
    """Return the cited BA-CVA Table 1 risk weight and citation id.

    Parameters
    ----------
    sector :
        Counterparty sector bucket for BA-CVA Table 1 risk weights.

    credit_quality :
        Counterparty credit-quality bucket for BA-CVA Table 1.

    profile, optional :
        Optional ``CvaRegulatoryProfile`` or profile label; default Basel MAR50 (2020).

    Returns
    -------
    tuple[float, str]
        Regulatory scalar and the profile-specific citation id for audit replay."""

    resolved_profile = _resolve_supported_profile(profile)
    resolved_sector = _resolve_sector(sector)
    resolved_quality = _resolve_credit_quality(credit_quality)
    key = (resolved_sector, resolved_quality)
    if key not in _TABLE_1_RISK_WEIGHTS:
        raise CvaInputError(
            f"no BA-CVA risk weight for {resolved_sector.value}/{resolved_quality.value}",
            field="risk_weight",
        )
    return _TABLE_1_RISK_WEIGHTS[key], profile_citation_id("basel_mar50_16", resolved_profile)


def ba_cva_alpha(
    profile: CvaRegulatoryProfile | str = CvaRegulatoryProfile.BASEL_MAR50_2020,
) -> tuple[float, str]:
    """Return the cited BA-CVA supervisory multiplier alpha.

    Parameters
    ----------
    profile, optional :
        Optional ``CvaRegulatoryProfile`` or profile label; default Basel MAR50 (2020).

    Returns
    -------
    tuple[float, str]
        Regulatory scalar and the profile-specific citation id for audit replay."""

    resolved_profile = _resolve_supported_profile(profile)
    return BA_CVA_ALPHA, profile_citation_id("basel_mar50_15", resolved_profile)


def ba_cva_beta(
    profile: CvaRegulatoryProfile | str = CvaRegulatoryProfile.BASEL_MAR50_2020,
) -> tuple[float, str]:
    """Return the cited full BA-CVA floor beta.

    Parameters
    ----------
    profile, optional :
        Optional ``CvaRegulatoryProfile`` or profile label; default Basel MAR50 (2020).

    Returns
    -------
    tuple[float, str]
        Regulatory scalar and the profile-specific citation id for audit replay."""

    resolved_profile = _resolve_supported_profile(profile)
    return BA_CVA_BETA, profile_citation_id("basel_mar50_20", resolved_profile)


def ba_cva_hedge_counterparty_correlation(
    relation: HedgeReferenceRelation,
    *,
    profile: CvaRegulatoryProfile | str = CvaRegulatoryProfile.BASEL_MAR50_2020,
) -> tuple[float, str]:
    """Return Table 2 hedge-counterparty correlation r_hc (MAR50.26).

    Parameters
    ----------
    relation :
        Hedge-to-reference relation for Table 2 counterparty correlation (MAR50.26).

    profile, optional :
        Optional ``CvaRegulatoryProfile`` or profile label; default Basel MAR50 (2020).

    Returns
    -------
    tuple[float, str]
        Regulatory scalar and the profile-specific citation id for audit replay."""

    resolved_profile = _resolve_supported_profile(profile)
    if relation not in _HEDGE_REFERENCE_CORRELATIONS:
        raise CvaInputError(
            f"unsupported hedge reference relation {relation.value}",
            field="reference_relation",
        )
    return (
        _HEDGE_REFERENCE_CORRELATIONS[relation],
        profile_citation_id("basel_mar50_26", resolved_profile),
    )


def ba_cva_index_risk_weight_scalar(
    *,
    profile: CvaRegulatoryProfile | str = CvaRegulatoryProfile.BASEL_MAR50_2020,
) -> tuple[float, str]:
    """Return the cited index hedge diversification scalar (MAR50.24(4)).

    Parameters
    ----------
    profile, optional :
        Optional ``CvaRegulatoryProfile`` or profile label; default Basel MAR50 (2020).

    Returns
    -------
    tuple[float, str]
        Regulatory scalar and the profile-specific citation id for audit replay."""

    resolved_profile = _resolve_supported_profile(profile)
    return BA_CVA_INDEX_RW_SCALAR, profile_citation_id("basel_mar50_24", resolved_profile)


def ba_cva_rho(
    profile: CvaRegulatoryProfile | str = CvaRegulatoryProfile.BASEL_MAR50_2020,
) -> tuple[float, str]:
    """Return the cited BA-CVA portfolio correlation rho.

    Parameters
    ----------
    profile, optional :
        Optional ``CvaRegulatoryProfile`` or profile label; default Basel MAR50 (2020).

    Returns
    -------
    tuple[float, str]
        Regulatory scalar and the profile-specific citation id for audit replay."""

    resolved_profile = _resolve_supported_profile(profile)
    return BA_CVA_RHO, profile_citation_id("basel_mar50_14", resolved_profile)


def ba_cva_discount_scalar(
    profile: CvaRegulatoryProfile | str = CvaRegulatoryProfile.BASEL_MAR50_2020,
) -> tuple[float, str]:
    """Return the cited reduced BA-CVA discount scalar D_BA-CVA.

    Parameters
    ----------
    profile, optional :
        Optional ``CvaRegulatoryProfile`` or profile label; default Basel MAR50 (2020).

    Returns
    -------
    tuple[float, str]
        Regulatory scalar and the profile-specific citation id for audit replay."""

    resolved_profile = _resolve_supported_profile(profile)
    return D_BA_CVA, profile_citation_id("basel_mar50_14", resolved_profile)


def compute_non_imm_discount_factor(maturity: float) -> tuple[float, str]:
    """Return the cited non-IMM discount factor for effective maturity M.

    Parameters
    ----------
    maturity :
        Instrument maturity used for non-IMM discount-factor approximation.

    Returns
    -------
    tuple[float, str]
        Regulatory scalar and the profile-specific citation id for audit replay."""

    maturity_value = float(maturity)
    if maturity_value <= 0.0:
        return 1.0, "basel_mar50_15_4"
    rate_times_maturity = NON_IMM_DISCOUNT_RATE * maturity_value
    if rate_times_maturity == 0.0:
        return 1.0, "basel_mar50_15_4"
    discount_factor = (1.0 - math.exp(-rate_times_maturity)) / rate_times_maturity
    return discount_factor, "basel_mar50_15_4"


def resolve_netting_set_discount_factor(
    *,
    uses_imm_ead: bool,
    effective_maturity: float,
    supplied_discount_factor: float,
    discount_factor_explicit: bool = False,
    profile: CvaRegulatoryProfile | str = CvaRegulatoryProfile.BASEL_MAR50_2020,
) -> tuple[float, str, bool]:
    """Return discount factor, citation id, and whether the supplied value was used.

    When ``discount_factor_explicit=True`` the caller signals that the supplied
    value should be used verbatim, even when it equals 1.0.  Without this flag
    the sentinel-equals-1.0 pattern would silently override a legitimately
    supplied discount factor of 1.0 with the computed non-IMM formula.

    Parameters
    ----------
    uses_imm_ead :
        Input for ``resolve_netting_set_discount_factor`` used in the CVA capital path.

    effective_maturity :
        Input for ``resolve_netting_set_discount_factor`` used in the CVA capital path.

    supplied_discount_factor :
        Input for ``resolve_netting_set_discount_factor`` used in the CVA capital path.

    discount_factor_explicit, optional :
        Input for ``resolve_netting_set_discount_factor`` used in the CVA capital path.

    profile, optional :
        Optional ``CvaRegulatoryProfile`` or profile label; default Basel MAR50 (2020).

    Returns
    -------
    tuple[float, str, bool]
        Result of ``resolve_netting_set_discount_factor`` for audit replay."""

    resolved_profile = _resolve_supported_profile(profile)
    if uses_imm_ead:
        return 1.0, profile_citation_id("basel_mar50_15_4", resolved_profile), False
    if discount_factor_explicit:
        return (
            supplied_discount_factor,
            profile_citation_id("basel_mar50_15_4", resolved_profile),
            True,
        )
    computed, citation_id = compute_non_imm_discount_factor(effective_maturity)
    return computed, profile_citation_id(citation_id, resolved_profile), False


def _ba_cva_reference_payload(profile: CvaRegulatoryProfile) -> dict[str, object]:
    return {
        "alpha": BA_CVA_ALPHA,
        "alpha_citation_id": profile_citation_id("basel_mar50_15", profile),
        "rho": BA_CVA_RHO,
        "rho_citation_id": profile_citation_id("basel_mar50_14", profile),
        "beta": BA_CVA_BETA,
        "beta_citation_id": profile_citation_id("basel_mar50_20", profile),
        "d_ba_cva": D_BA_CVA,
        "d_ba_cva_citation_id": profile_citation_id("basel_mar50_14", profile),
        "non_imm_discount_rate": NON_IMM_DISCOUNT_RATE,
        "non_imm_discount_citation_id": profile_citation_id("basel_mar50_15_4", profile),
        "risk_weights": [
            {
                "sector": rule.sector.value,
                "credit_quality": rule.credit_quality.value,
                "risk_weight": rule.risk_weight,
                "citation_id": profile_citation_id(rule.citation_id, profile),
            }
            for rule in BASEL_BA_CVA_RISK_WEIGHT_RULES
        ],
    }


__all__ = [
    "BASEL_BA_CVA_RISK_WEIGHT_RULES",
    "BA_CVA_ALPHA",
    "BA_CVA_BETA",
    "BA_CVA_INDEX_RW_SCALAR",
    "BA_CVA_RHO",
    "D_BA_CVA",
    "NON_IMM_DISCOUNT_RATE",
    "BaCvaRiskWeightRule",
    "ba_cva_alpha",
    "ba_cva_beta",
    "ba_cva_discount_scalar",
    "ba_cva_hedge_counterparty_correlation",
    "ba_cva_index_risk_weight_scalar",
    "ba_cva_rho",
    "ba_cva_risk_weight",
    "compute_non_imm_discount_factor",
    "resolve_netting_set_discount_factor",
]
