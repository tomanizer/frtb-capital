"""
Reference data for CVA rule profiles.

Regulatory traceability:
    Basel MAR50.14-MAR50.16 (BA-CVA reduced), MAR50.54-MAR50.57 (SA-CVA GIRR delta).
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from frtb_common import UnsupportedRegulatoryFeatureError

from frtb_cva.data_models import (
    CreditQuality,
    CvaCitation,
    CvaRegulatoryProfile,
    CvaSector,
    HedgeReferenceRelation,
)
from frtb_cva.validation import CvaInputError

BASEL_MAR50_URL = "https://www.bis.org/basel_framework/chapter/MAR/50.htm"

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

GIRR_SPECIFIED_CURRENCIES = frozenset({"USD", "EUR", "GBP", "AUD", "CAD", "SEK", "JPY"})
GIRR_INTER_BUCKET_CORRELATION = 0.5
GIRR_OTHER_CURRENCY_RISK_WEIGHT_SCALAR = 1.4


@dataclass(frozen=True)
class BaCvaRiskWeightRule:
    """Profile-specific BA-CVA Table 1 risk-weight entry."""

    sector: CvaSector
    credit_quality: CreditQuality
    risk_weight: float
    citation_id: str


@dataclass(frozen=True)
class SaCvaGirrTenorDefinition:
    """SA-CVA GIRR delta tenor label and maturity in years."""

    tenor: str
    maturity_years: float
    citation_id: str


@dataclass(frozen=True)
class SaCvaGirrDeltaRiskWeightRule:
    """SA-CVA GIRR delta risk-weight lookup entry."""

    tenor: str
    risk_weight: float
    citation_id: str


@dataclass(frozen=True)
class SaCvaGirrSpecialRiskFactorRule:
    """SA-CVA GIRR inflation or parallel-curve risk factor."""

    risk_factor: str
    risk_weight: float
    citation_id: str


BASEL_MAR50_CITATIONS: dict[str, CvaCitation] = {
    "basel_mar50_14": CvaCitation(
        source_id="basel_mar50_cva_framework",
        paragraph="MAR50.14",
        url=BASEL_MAR50_URL,
        note="Reduced BA-CVA portfolio aggregation and D_BA-CVA scalar.",
    ),
    "basel_mar50_15": CvaCitation(
        source_id="basel_mar50_cva_framework",
        paragraph="MAR50.15",
        url=BASEL_MAR50_URL,
        note="Stand-alone counterparty capital multiplier, maturity, EAD, and DF.",
    ),
    "basel_mar50_15_4": CvaCitation(
        source_id="basel_mar50_cva_framework",
        paragraph="MAR50.15(4)",
        url=BASEL_MAR50_URL,
        note="Non-IMM discount factor formula and IMM DF=1 branch.",
    ),
    "basel_mar50_16": CvaCitation(
        source_id="basel_mar50_cva_framework",
        paragraph="MAR50.16",
        url=BASEL_MAR50_URL,
        note="BA-CVA Table 1 sector and credit-quality risk weights.",
    ),
    "basel_mar50_20": CvaCitation(
        source_id="basel_mar50_cva_framework",
        paragraph="MAR50.20",
        url=BASEL_MAR50_URL,
        note="Full BA-CVA supervisory floor with beta=0.25.",
    ),
    "basel_mar50_32_1": CvaCitation(
        source_id="basel_mar50_cva_framework",
        paragraph="MAR50.32(1)",
        url=BASEL_MAR50_URL,
        note="Positive regulatory CVA convention for SA-CVA sensitivity inputs.",
    ),
    "basel_mar50_52": CvaCitation(
        source_id="basel_mar50_cva_framework",
        paragraph="MAR50.52",
        url=BASEL_MAR50_URL,
        note="SA-CVA weighted sensitivity netting of CVA and eligible hedge sensitivities.",
    ),
    "basel_mar50_54": CvaCitation(
        source_id="basel_mar50_cva_framework",
        paragraph="MAR50.54",
        url=BASEL_MAR50_URL,
        note="SA-CVA GIRR currency buckets.",
    ),
    "basel_mar50_55": CvaCitation(
        source_id="basel_mar50_cva_framework",
        paragraph="MAR50.55",
        url=BASEL_MAR50_URL,
        note="SA-CVA GIRR cross-bucket correlation gamma_bc=0.5.",
    ),
    "basel_mar50_56": CvaCitation(
        source_id="basel_mar50_cva_framework",
        paragraph="MAR50.56",
        url=BASEL_MAR50_URL,
        note="SA-CVA GIRR delta risk factors, weights, and correlations for specified currencies.",
    ),
    "basel_mar50_57": CvaCitation(
        source_id="basel_mar50_cva_framework",
        paragraph="MAR50.57",
        url=BASEL_MAR50_URL,
        note="SA-CVA GIRR delta risk factors for other currencies.",
    ),
    "basel_mar50_58": CvaCitation(
        source_id="basel_mar50_cva_framework",
        paragraph="MAR50.58",
        url=BASEL_MAR50_URL,
        note="SA-CVA GIRR vega risk factors and RW_sigma.",
    ),
    "basel_mar50_59": CvaCitation(
        source_id="basel_mar50_cva_framework",
        paragraph="MAR50.59",
        url=BASEL_MAR50_URL,
        note="SA-CVA FX currency buckets excluding reporting currency.",
    ),
    "basel_mar50_60": CvaCitation(
        source_id="basel_mar50_cva_framework",
        paragraph="MAR50.60",
        url=BASEL_MAR50_URL,
        note="SA-CVA FX cross-bucket gamma_bc=0.6.",
    ),
    "basel_mar50_61": CvaCitation(
        source_id="basel_mar50_cva_framework",
        paragraph="MAR50.61",
        url=BASEL_MAR50_URL,
        note="SA-CVA FX delta risk factors and 11% risk weight.",
    ),
    "basel_mar50_62": CvaCitation(
        source_id="basel_mar50_cva_framework",
        paragraph="MAR50.62",
        url=BASEL_MAR50_URL,
        note="SA-CVA FX vega risk factors and RW_sigma.",
    ),
    "basel_mar50_63": CvaCitation(
        source_id="basel_mar50_cva_framework",
        paragraph="MAR50.63",
        url=BASEL_MAR50_URL,
        note="SA-CVA CCS delta buckets; no CCS vega.",
    ),
    "basel_mar50_64": CvaCitation(
        source_id="basel_mar50_cva_framework",
        paragraph="MAR50.64",
        url=BASEL_MAR50_URL,
        note="SA-CVA CCS cross-bucket gamma_bc table.",
    ),
    "basel_mar50_65": CvaCitation(
        source_id="basel_mar50_cva_framework",
        paragraph="MAR50.65",
        url=BASEL_MAR50_URL,
        note="SA-CVA CCS delta risk weights and rho_kl.",
    ),
    "basel_mar50_66": CvaCitation(
        source_id="basel_mar50_cva_framework",
        paragraph="MAR50.66",
        url=BASEL_MAR50_URL,
        note="SA-CVA RCS delta and vega buckets.",
    ),
    "basel_mar50_67": CvaCitation(
        source_id="basel_mar50_cva_framework",
        paragraph="MAR50.67",
        url=BASEL_MAR50_URL,
        note="SA-CVA RCS cross-bucket gamma_bc with cross-quality halving.",
    ),
    "basel_mar50_68": CvaCitation(
        source_id="basel_mar50_cva_framework",
        paragraph="MAR50.68",
        url=BASEL_MAR50_URL,
        note="SA-CVA RCS delta risk weights.",
    ),
    "basel_mar50_69": CvaCitation(
        source_id="basel_mar50_cva_framework",
        paragraph="MAR50.69",
        url=BASEL_MAR50_URL,
        note="SA-CVA RCS vega risk weights.",
    ),
    "basel_mar50_70": CvaCitation(
        source_id="basel_mar50_cva_framework",
        paragraph="MAR50.70",
        url=BASEL_MAR50_URL,
        note="SA-CVA equity buckets by size, region, and sector.",
    ),
    "basel_mar50_71": CvaCitation(
        source_id="basel_mar50_cva_framework",
        paragraph="MAR50.71",
        url=BASEL_MAR50_URL,
        note="SA-CVA equity cross-bucket gamma_bc rules.",
    ),
    "basel_mar50_72": CvaCitation(
        source_id="basel_mar50_cva_framework",
        paragraph="MAR50.72",
        url=BASEL_MAR50_URL,
        note="SA-CVA equity delta risk weights.",
    ),
    "basel_mar50_73": CvaCitation(
        source_id="basel_mar50_cva_framework",
        paragraph="MAR50.73",
        url=BASEL_MAR50_URL,
        note="SA-CVA equity vega risk weights.",
    ),
    "basel_mar50_74": CvaCitation(
        source_id="basel_mar50_cva_framework",
        paragraph="MAR50.74",
        url=BASEL_MAR50_URL,
        note="SA-CVA commodity buckets.",
    ),
    "basel_mar50_75": CvaCitation(
        source_id="basel_mar50_cva_framework",
        paragraph="MAR50.75",
        url=BASEL_MAR50_URL,
        note="SA-CVA commodity cross-bucket gamma_bc rules.",
    ),
    "basel_mar50_76": CvaCitation(
        source_id="basel_mar50_cva_framework",
        paragraph="MAR50.76",
        url=BASEL_MAR50_URL,
        note="SA-CVA commodity delta risk weights.",
    ),
    "basel_mar50_77": CvaCitation(
        source_id="basel_mar50_cva_framework",
        paragraph="MAR50.77",
        url=BASEL_MAR50_URL,
        note="SA-CVA commodity vega risk weights.",
    ),
}

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

BASEL_GIRR_TENORS: tuple[SaCvaGirrTenorDefinition, ...] = (
    SaCvaGirrTenorDefinition("1y", 1.0, "basel_mar50_56"),
    SaCvaGirrTenorDefinition("2y", 2.0, "basel_mar50_56"),
    SaCvaGirrTenorDefinition("5y", 5.0, "basel_mar50_56"),
    SaCvaGirrTenorDefinition("10y", 10.0, "basel_mar50_56"),
    SaCvaGirrTenorDefinition("30y", 30.0, "basel_mar50_56"),
)

BASEL_GIRR_DELTA_RISK_WEIGHTS: tuple[SaCvaGirrDeltaRiskWeightRule, ...] = (
    SaCvaGirrDeltaRiskWeightRule("1y", 0.0111, "basel_mar50_56"),
    SaCvaGirrDeltaRiskWeightRule("2y", 0.0093, "basel_mar50_56"),
    SaCvaGirrDeltaRiskWeightRule("5y", 0.0074, "basel_mar50_56"),
    SaCvaGirrDeltaRiskWeightRule("10y", 0.0074, "basel_mar50_56"),
    SaCvaGirrDeltaRiskWeightRule("30y", 0.0074, "basel_mar50_56"),
)

BASEL_GIRR_SPECIAL_RISK_FACTORS: tuple[SaCvaGirrSpecialRiskFactorRule, ...] = (
    SaCvaGirrSpecialRiskFactorRule("INFL", 0.0111, "basel_mar50_56"),
    SaCvaGirrSpecialRiskFactorRule("PARALLEL", 0.0158, "basel_mar50_57"),
)

BASEL_GIRR_DELTA_CORRELATIONS: dict[tuple[str, str], float] = {
    ("1y", "1y"): 1.0,
    ("1y", "2y"): 0.91,
    ("1y", "5y"): 0.72,
    ("1y", "10y"): 0.55,
    ("1y", "30y"): 0.31,
    ("1y", "INFL"): 0.40,
    ("2y", "2y"): 1.0,
    ("2y", "5y"): 0.87,
    ("2y", "10y"): 0.72,
    ("2y", "30y"): 0.45,
    ("2y", "INFL"): 0.40,
    ("5y", "5y"): 1.0,
    ("5y", "10y"): 0.91,
    ("5y", "30y"): 0.68,
    ("5y", "INFL"): 0.40,
    ("10y", "10y"): 1.0,
    ("10y", "30y"): 0.83,
    ("10y", "INFL"): 0.40,
    ("30y", "30y"): 1.0,
    ("30y", "INFL"): 0.40,
    ("PARALLEL", "INFL"): 0.40,
    ("INFL", "PARALLEL"): 0.40,
    ("PARALLEL", "PARALLEL"): 1.0,
}

PROFILE_CITATIONS: dict[CvaRegulatoryProfile, dict[str, CvaCitation]] = {
    CvaRegulatoryProfile.BASEL_MAR50_2020: BASEL_MAR50_CITATIONS,
}


def citations_for_profile(
    profile: CvaRegulatoryProfile | str,
) -> dict[str, CvaCitation]:
    """Return citations for a supported CVA profile."""

    resolved = _resolve_supported_profile(profile)
    return dict(PROFILE_CITATIONS[resolved])


def ba_cva_risk_weight(
    sector: CvaSector | str,
    credit_quality: CreditQuality | str,
    *,
    profile: CvaRegulatoryProfile | str = CvaRegulatoryProfile.BASEL_MAR50_2020,
) -> tuple[float, str]:
    """Return the cited BA-CVA Table 1 risk weight and citation id."""

    _resolve_supported_profile(profile)
    resolved_sector = _resolve_sector(sector)
    resolved_quality = _resolve_credit_quality(credit_quality)
    key = (resolved_sector, resolved_quality)
    if key not in _TABLE_1_RISK_WEIGHTS:
        raise CvaInputError(
            f"no BA-CVA risk weight for {resolved_sector.value}/{resolved_quality.value}",
            field="risk_weight",
        )
    return _TABLE_1_RISK_WEIGHTS[key], "basel_mar50_16"


def ba_cva_alpha(
    profile: CvaRegulatoryProfile | str = CvaRegulatoryProfile.BASEL_MAR50_2020,
) -> tuple[float, str]:
    """Return the cited BA-CVA supervisory multiplier alpha."""

    _resolve_supported_profile(profile)
    return BA_CVA_ALPHA, "basel_mar50_15"


def ba_cva_beta(
    profile: CvaRegulatoryProfile | str = CvaRegulatoryProfile.BASEL_MAR50_2020,
) -> tuple[float, str]:
    """Return the cited full BA-CVA floor beta."""

    _resolve_supported_profile(profile)
    return BA_CVA_BETA, "basel_mar50_20"


def ba_cva_hedge_counterparty_correlation(
    relation: HedgeReferenceRelation,
    *,
    profile: CvaRegulatoryProfile | str = CvaRegulatoryProfile.BASEL_MAR50_2020,
) -> tuple[float, str]:
    """Return Table 2 hedge-counterparty correlation r_hc (MAR50.26)."""

    _resolve_supported_profile(profile)
    if relation not in _HEDGE_REFERENCE_CORRELATIONS:
        raise CvaInputError(
            f"unsupported hedge reference relation {relation.value}",
            field="reference_relation",
        )
    return _HEDGE_REFERENCE_CORRELATIONS[relation], "basel_mar50_26"


def ba_cva_index_risk_weight_scalar(
    *,
    profile: CvaRegulatoryProfile | str = CvaRegulatoryProfile.BASEL_MAR50_2020,
) -> tuple[float, str]:
    """Return the cited index hedge diversification scalar (MAR50.24(4))."""

    _resolve_supported_profile(profile)
    return BA_CVA_INDEX_RW_SCALAR, "basel_mar50_24"


def ba_cva_rho(
    profile: CvaRegulatoryProfile | str = CvaRegulatoryProfile.BASEL_MAR50_2020,
) -> tuple[float, str]:
    """Return the cited BA-CVA portfolio correlation rho."""

    _resolve_supported_profile(profile)
    return BA_CVA_RHO, "basel_mar50_14"


def ba_cva_discount_scalar(
    profile: CvaRegulatoryProfile | str = CvaRegulatoryProfile.BASEL_MAR50_2020,
) -> tuple[float, str]:
    """Return the cited reduced BA-CVA discount scalar D_BA-CVA."""

    _resolve_supported_profile(profile)
    return D_BA_CVA, "basel_mar50_14"


def compute_non_imm_discount_factor(maturity: float) -> tuple[float, str]:
    """Return the cited non-IMM discount factor for effective maturity M."""

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
    """

    _resolve_supported_profile(profile)
    if uses_imm_ead:
        return 1.0, "basel_mar50_15_4", False
    if discount_factor_explicit:
        return supplied_discount_factor, "basel_mar50_15_4", True
    computed, citation_id = compute_non_imm_discount_factor(effective_maturity)
    return computed, citation_id, False


def girr_delta_risk_weight_rule(
    tenor: str,
    *,
    profile: CvaRegulatoryProfile | str = CvaRegulatoryProfile.BASEL_MAR50_2020,
) -> SaCvaGirrDeltaRiskWeightRule:
    """Return the cited SA-CVA GIRR delta risk-weight rule for a tenor."""

    _resolve_supported_profile(profile)
    normalised = _require_text(tenor, "tenor")
    for rule in BASEL_GIRR_DELTA_RISK_WEIGHTS:
        if rule.tenor == normalised:
            return rule
    for special_rule in BASEL_GIRR_SPECIAL_RISK_FACTORS:
        if special_rule.risk_factor == normalised:
            return SaCvaGirrDeltaRiskWeightRule(
                tenor=special_rule.risk_factor,
                risk_weight=special_rule.risk_weight,
                citation_id=special_rule.citation_id,
            )
    raise CvaInputError(
        f"no SA-CVA GIRR delta risk weight for tenor {normalised}",
        field="tenor",
    )


def girr_delta_risk_weight(
    tenor: str,
    *,
    profile: CvaRegulatoryProfile | str = CvaRegulatoryProfile.BASEL_MAR50_2020,
) -> tuple[float, str]:
    """Return the cited SA-CVA GIRR delta risk weight and citation id."""

    rule = girr_delta_risk_weight_rule(tenor, profile=profile)
    return rule.risk_weight, rule.citation_id


def girr_delta_intra_bucket_correlation(
    tenor1: str,
    tenor2: str,
    *,
    profile: CvaRegulatoryProfile | str = CvaRegulatoryProfile.BASEL_MAR50_2020,
) -> tuple[float, str]:
    """Return the cited SA-CVA GIRR delta intra-bucket correlation."""

    _resolve_supported_profile(profile)
    normalised_tenor1 = _require_text(tenor1, "tenor1")
    normalised_tenor2 = _require_text(tenor2, "tenor2")
    key = (normalised_tenor1, normalised_tenor2)
    if key not in BASEL_GIRR_DELTA_CORRELATIONS:
        key = (normalised_tenor2, normalised_tenor1)
    if key not in BASEL_GIRR_DELTA_CORRELATIONS:
        raise CvaInputError(
            f"no SA-CVA GIRR delta correlation for {normalised_tenor1}/{normalised_tenor2}",
            field="correlation",
        )
    citation_id = (
        "basel_mar50_57"
        if "PARALLEL" in {normalised_tenor1, normalised_tenor2}
        else "basel_mar50_56"
    )
    return BASEL_GIRR_DELTA_CORRELATIONS[key], citation_id


def girr_inter_bucket_correlation(
    profile: CvaRegulatoryProfile | str = CvaRegulatoryProfile.BASEL_MAR50_2020,
) -> tuple[float, str]:
    """Return the cited SA-CVA GIRR cross-bucket correlation gamma_bc."""

    _resolve_supported_profile(profile)
    return GIRR_INTER_BUCKET_CORRELATION, "basel_mar50_55"


def girr_specified_currencies() -> frozenset[str]:
    """Return the cited SA-CVA GIRR specified currency bucket set."""

    return GIRR_SPECIFIED_CURRENCIES


def girr_is_specified_currency(currency: str, *, reporting_currency: str) -> bool:
    """Return whether a currency uses specified-currency GIRR delta tables."""

    normalised = _require_text(currency, "currency").upper()
    reporting = _require_text(reporting_currency, "reporting_currency").upper()
    if normalised == reporting:
        return True
    return normalised in GIRR_SPECIFIED_CURRENCIES


def girr_other_currency_risk_weight_scalar(
    profile: CvaRegulatoryProfile | str = CvaRegulatoryProfile.BASEL_MAR50_2020,
) -> tuple[float, str]:
    """Return the cited MAR50.57 scalar for non-specified GIRR currency buckets."""

    _resolve_supported_profile(profile)
    return GIRR_OTHER_CURRENCY_RISK_WEIGHT_SCALAR, "basel_mar50_57"


def girr_delta_tenors(
    profile: CvaRegulatoryProfile | str = CvaRegulatoryProfile.BASEL_MAR50_2020,
) -> tuple[str, ...]:
    """Return the cited SA-CVA GIRR delta tenor labels."""

    _resolve_supported_profile(profile)
    return tuple(tenor_definition.tenor for tenor_definition in BASEL_GIRR_TENORS)


def girr_tenor_definition(
    tenor: str,
    *,
    profile: CvaRegulatoryProfile | str = CvaRegulatoryProfile.BASEL_MAR50_2020,
) -> SaCvaGirrTenorDefinition:
    """Return the cited SA-CVA GIRR tenor definition."""

    _resolve_supported_profile(profile)
    normalised = _require_text(tenor, "tenor")
    for tenor_definition in BASEL_GIRR_TENORS:
        if tenor_definition.tenor == normalised:
            return tenor_definition
    raise CvaInputError(
        f"no SA-CVA GIRR tenor definition for tenor {normalised}",
        field="tenor",
    )


def profile_reference_payload(profile: CvaRegulatoryProfile | str) -> dict[str, object]:
    """Return a deterministic, JSON-serialisable payload for profile hashing."""

    resolved = _resolve_supported_profile(profile)
    citations = citations_for_profile(resolved)
    return {
        "profile": resolved.value,
        "citations": {
            citation_id: {
                "source_id": citation.source_id,
                "paragraph": citation.paragraph,
                "url": citation.url,
                "note": citation.note,
            }
            for citation_id, citation in sorted(citations.items())
        },
        "ba_cva": {
            "alpha": BA_CVA_ALPHA,
            "alpha_citation_id": "basel_mar50_15",
            "rho": BA_CVA_RHO,
            "rho_citation_id": "basel_mar50_14",
            "beta": BA_CVA_BETA,
            "beta_citation_id": "basel_mar50_20",
            "d_ba_cva": D_BA_CVA,
            "d_ba_cva_citation_id": "basel_mar50_14",
            "non_imm_discount_rate": NON_IMM_DISCOUNT_RATE,
            "non_imm_discount_citation_id": "basel_mar50_15_4",
            "risk_weights": [
                {
                    "sector": rule.sector.value,
                    "credit_quality": rule.credit_quality.value,
                    "risk_weight": rule.risk_weight,
                    "citation_id": rule.citation_id,
                }
                for rule in BASEL_BA_CVA_RISK_WEIGHT_RULES
            ],
        },
        "sa_cva_girr_delta": {
            "specified_currencies": sorted(GIRR_SPECIFIED_CURRENCIES),
            "tenors": [
                {
                    "tenor": tenor_definition.tenor,
                    "maturity_years": tenor_definition.maturity_years,
                    "citation_id": tenor_definition.citation_id,
                }
                for tenor_definition in BASEL_GIRR_TENORS
            ],
            "risk_weights": [
                {
                    "tenor": rule.tenor,
                    "risk_weight": rule.risk_weight,
                    "citation_id": rule.citation_id,
                }
                for rule in BASEL_GIRR_DELTA_RISK_WEIGHTS
            ],
            "special_risk_factors": [
                {
                    "risk_factor": rule.risk_factor,
                    "risk_weight": rule.risk_weight,
                    "citation_id": rule.citation_id,
                }
                for rule in BASEL_GIRR_SPECIAL_RISK_FACTORS
            ],
            "correlations": [
                {
                    "tenor1": tenor1,
                    "tenor2": tenor2,
                    "correlation": correlation,
                    "citation_id": "basel_mar50_57"
                    if "PARALLEL" in {tenor1, tenor2}
                    else "basel_mar50_56",
                }
                for (tenor1, tenor2), correlation in sorted(BASEL_GIRR_DELTA_CORRELATIONS.items())
            ],
            "inter_bucket_correlation": GIRR_INTER_BUCKET_CORRELATION,
            "inter_bucket_correlation_citation_id": "basel_mar50_55",
            "other_currency_risk_weight_scalar": GIRR_OTHER_CURRENCY_RISK_WEIGHT_SCALAR,
            "other_currency_risk_weight_scalar_citation_id": "basel_mar50_57",
        },
    }


def _resolve_supported_profile(profile: CvaRegulatoryProfile | str) -> CvaRegulatoryProfile:
    try:
        resolved = CvaRegulatoryProfile(profile)
    except ValueError as exc:
        raise CvaInputError(
            f"unknown CVA regulatory profile: {profile!r}",
            field="profile",
        ) from exc
    if resolved not in PROFILE_CITATIONS:
        raise UnsupportedRegulatoryFeatureError(
            f"CVA profile {resolved.value} is unsupported until mapped and fixture-tested."
        )
    return resolved


def _resolve_sector(sector: CvaSector | str) -> CvaSector:
    if isinstance(sector, CvaSector):
        return sector
    try:
        return CvaSector(sector)
    except ValueError as exc:
        raise CvaInputError(f"unknown sector: {sector!r}", field="sector") from exc


def _resolve_credit_quality(credit_quality: CreditQuality | str) -> CreditQuality:
    if isinstance(credit_quality, CreditQuality):
        return credit_quality
    try:
        return CreditQuality(credit_quality)
    except ValueError as exc:
        raise CvaInputError(
            f"unknown credit quality: {credit_quality!r}",
            field="credit_quality",
        ) from exc


def _require_text(value: object, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise CvaInputError("non-empty text is required", field=field)
    return value


__all__ = [
    "BASEL_BA_CVA_RISK_WEIGHT_RULES",
    "BASEL_GIRR_DELTA_CORRELATIONS",
    "BASEL_GIRR_DELTA_RISK_WEIGHTS",
    "BASEL_GIRR_SPECIAL_RISK_FACTORS",
    "BASEL_GIRR_TENORS",
    "BASEL_MAR50_CITATIONS",
    "BA_CVA_ALPHA",
    "BA_CVA_BETA",
    "BA_CVA_INDEX_RW_SCALAR",
    "BA_CVA_RHO",
    "D_BA_CVA",
    "GIRR_INTER_BUCKET_CORRELATION",
    "GIRR_OTHER_CURRENCY_RISK_WEIGHT_SCALAR",
    "GIRR_SPECIFIED_CURRENCIES",
    "NON_IMM_DISCOUNT_RATE",
    "BaCvaRiskWeightRule",
    "SaCvaGirrDeltaRiskWeightRule",
    "SaCvaGirrSpecialRiskFactorRule",
    "SaCvaGirrTenorDefinition",
    "ba_cva_alpha",
    "ba_cva_beta",
    "ba_cva_discount_scalar",
    "ba_cva_hedge_counterparty_correlation",
    "ba_cva_index_risk_weight_scalar",
    "ba_cva_rho",
    "ba_cva_risk_weight",
    "citations_for_profile",
    "compute_non_imm_discount_factor",
    "girr_delta_intra_bucket_correlation",
    "girr_delta_risk_weight",
    "girr_delta_risk_weight_rule",
    "girr_delta_tenors",
    "girr_inter_bucket_correlation",
    "girr_is_specified_currency",
    "girr_other_currency_risk_weight_scalar",
    "girr_specified_currencies",
    "girr_tenor_definition",
    "profile_reference_payload",
    "resolve_netting_set_discount_factor",
]
