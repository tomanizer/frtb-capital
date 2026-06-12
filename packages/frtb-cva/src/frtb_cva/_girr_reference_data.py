"""SA-CVA GIRR delta reference tables and lookup helpers."""

from __future__ import annotations

from dataclasses import dataclass

from frtb_cva._reference_profile_data import (
    _require_text,
    _resolve_supported_profile,
    profile_citation_id,
)
from frtb_cva.data_models import CvaRegulatoryProfile
from frtb_cva.validation import CvaInputError

GIRR_SPECIFIED_CURRENCIES = frozenset({"USD", "EUR", "GBP", "AUD", "CAD", "SEK", "JPY"})
GIRR_INTER_BUCKET_CORRELATION = 0.5
GIRR_OTHER_CURRENCY_RISK_WEIGHT_SCALAR = 1.4


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


def girr_delta_risk_weight_rule(
    tenor: str,
    *,
    profile: CvaRegulatoryProfile | str = CvaRegulatoryProfile.BASEL_MAR50_2020,
) -> SaCvaGirrDeltaRiskWeightRule:
    """Return the cited SA-CVA GIRR delta risk-weight rule for a tenor.

    Parameters
    ----------
    tenor :
        GIRR delta tenor label for risk-weight and correlation lookup.

    profile, optional :
        Optional ``CvaRegulatoryProfile`` or profile label; default Basel MAR50 (2020).

    Returns
    -------
    SaCvaGirrDeltaRiskWeightRule
        Result of ``girr_delta_risk_weight_rule`` for audit replay."""

    resolved_profile = _resolve_supported_profile(profile)
    normalised = _require_text(tenor, "tenor")
    for rule in BASEL_GIRR_DELTA_RISK_WEIGHTS:
        if rule.tenor == normalised:
            return SaCvaGirrDeltaRiskWeightRule(
                tenor=rule.tenor,
                risk_weight=rule.risk_weight,
                citation_id=profile_citation_id(rule.citation_id, resolved_profile),
            )
    for special_rule in BASEL_GIRR_SPECIAL_RISK_FACTORS:
        if special_rule.risk_factor == normalised:
            return SaCvaGirrDeltaRiskWeightRule(
                tenor=special_rule.risk_factor,
                risk_weight=special_rule.risk_weight,
                citation_id=profile_citation_id(special_rule.citation_id, resolved_profile),
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
    """Return the cited SA-CVA GIRR delta risk weight and citation id.

    Parameters
    ----------
    tenor :
        GIRR delta tenor label for risk-weight and correlation lookup.

    profile, optional :
        Optional ``CvaRegulatoryProfile`` or profile label; default Basel MAR50 (2020).

    Returns
    -------
    tuple[float, str]
        Regulatory scalar and the profile-specific citation id for audit replay."""

    rule = girr_delta_risk_weight_rule(tenor, profile=profile)
    return rule.risk_weight, rule.citation_id


def girr_delta_intra_bucket_correlation(
    tenor1: str,
    tenor2: str,
    *,
    profile: CvaRegulatoryProfile | str = CvaRegulatoryProfile.BASEL_MAR50_2020,
) -> tuple[float, str]:
    """Return the cited SA-CVA GIRR delta intra-bucket correlation.

    Parameters
    ----------
    tenor1 :
        Input for ``girr_delta_intra_bucket_correlation`` used in the CVA capital path.

    tenor2 :
        Input for ``girr_delta_intra_bucket_correlation`` used in the CVA capital path.

    profile, optional :
        Optional ``CvaRegulatoryProfile`` or profile label; default Basel MAR50 (2020).

    Returns
    -------
    tuple[float, str]
        Regulatory scalar and the profile-specific citation id for audit replay."""

    resolved_profile = _resolve_supported_profile(profile)
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
    return (
        BASEL_GIRR_DELTA_CORRELATIONS[key],
        profile_citation_id(citation_id, resolved_profile),
    )


def girr_inter_bucket_correlation(
    profile: CvaRegulatoryProfile | str = CvaRegulatoryProfile.BASEL_MAR50_2020,
) -> tuple[float, str]:
    """Return the cited SA-CVA GIRR cross-bucket correlation gamma_bc.

    Parameters
    ----------
    profile, optional :
        Optional ``CvaRegulatoryProfile`` or profile label; default Basel MAR50 (2020).

    Returns
    -------
    tuple[float, str]
        Regulatory scalar and the profile-specific citation id for audit replay."""

    resolved_profile = _resolve_supported_profile(profile)
    return GIRR_INTER_BUCKET_CORRELATION, profile_citation_id(
        "basel_mar50_55",
        resolved_profile,
    )


def girr_specified_currencies() -> frozenset[str]:
    """Return the cited SA-CVA GIRR specified currency bucket set.

    Returns
    -------
    frozenset[str]
        Result of ``girr_specified_currencies`` for audit replay."""

    return GIRR_SPECIFIED_CURRENCIES


def girr_is_specified_currency(currency: str, *, reporting_currency: str) -> bool:
    """Return whether a currency uses specified-currency GIRR delta tables.

    Parameters
    ----------
    currency :
        GIRR currency code evaluated against specified-currency lists.

    reporting_currency :
        Input for ``girr_is_specified_currency`` used in the CVA capital path.

    Returns
    -------
    bool
        Result of ``girr_is_specified_currency`` for audit replay."""

    normalised = _require_text(currency, "currency").upper()
    reporting = _require_text(reporting_currency, "reporting_currency").upper()
    if normalised == reporting:
        return True
    return normalised in GIRR_SPECIFIED_CURRENCIES


def girr_other_currency_risk_weight_scalar(
    profile: CvaRegulatoryProfile | str = CvaRegulatoryProfile.BASEL_MAR50_2020,
) -> tuple[float, str]:
    """Return the cited MAR50.57 scalar for non-specified GIRR currency buckets.

    Parameters
    ----------
    profile, optional :
        Optional ``CvaRegulatoryProfile`` or profile label; default Basel MAR50 (2020).

    Returns
    -------
    tuple[float, str]
        Regulatory scalar and the profile-specific citation id for audit replay."""

    resolved_profile = _resolve_supported_profile(profile)
    return GIRR_OTHER_CURRENCY_RISK_WEIGHT_SCALAR, profile_citation_id(
        "basel_mar50_57",
        resolved_profile,
    )


def girr_delta_tenors(
    profile: CvaRegulatoryProfile | str = CvaRegulatoryProfile.BASEL_MAR50_2020,
) -> tuple[str, ...]:
    """Return the cited SA-CVA GIRR delta tenor labels.

    Parameters
    ----------
    profile, optional :
        Optional ``CvaRegulatoryProfile`` or profile label; default Basel MAR50 (2020).

    Returns
    -------
    tuple[str, ...]
        Result of ``girr_delta_tenors`` for audit replay."""

    _resolve_supported_profile(profile)
    return tuple(tenor_definition.tenor for tenor_definition in BASEL_GIRR_TENORS)


def girr_tenor_definition(
    tenor: str,
    *,
    profile: CvaRegulatoryProfile | str = CvaRegulatoryProfile.BASEL_MAR50_2020,
) -> SaCvaGirrTenorDefinition:
    """Return the cited SA-CVA GIRR tenor definition.

    Parameters
    ----------
    tenor :
        GIRR delta tenor label for risk-weight and correlation lookup.

    profile, optional :
        Optional ``CvaRegulatoryProfile`` or profile label; default Basel MAR50 (2020).

    Returns
    -------
    SaCvaGirrTenorDefinition
        Result of ``girr_tenor_definition`` for audit replay."""

    resolved_profile = _resolve_supported_profile(profile)
    normalised = _require_text(tenor, "tenor")
    for tenor_definition in BASEL_GIRR_TENORS:
        if tenor_definition.tenor == normalised:
            return SaCvaGirrTenorDefinition(
                tenor=tenor_definition.tenor,
                maturity_years=tenor_definition.maturity_years,
                citation_id=profile_citation_id(tenor_definition.citation_id, resolved_profile),
            )
    raise CvaInputError(
        f"no SA-CVA GIRR tenor definition for tenor {normalised}",
        field="tenor",
    )


def _girr_delta_reference_payload(profile: CvaRegulatoryProfile) -> dict[str, object]:
    return {
        "specified_currencies": sorted(GIRR_SPECIFIED_CURRENCIES),
        "tenors": [
            {
                "tenor": tenor_definition.tenor,
                "maturity_years": tenor_definition.maturity_years,
                "citation_id": profile_citation_id(tenor_definition.citation_id, profile),
            }
            for tenor_definition in BASEL_GIRR_TENORS
        ],
        "risk_weights": [
            {
                "tenor": rule.tenor,
                "risk_weight": rule.risk_weight,
                "citation_id": profile_citation_id(rule.citation_id, profile),
            }
            for rule in BASEL_GIRR_DELTA_RISK_WEIGHTS
        ],
        "special_risk_factors": [
            {
                "risk_factor": rule.risk_factor,
                "risk_weight": rule.risk_weight,
                "citation_id": profile_citation_id(rule.citation_id, profile),
            }
            for rule in BASEL_GIRR_SPECIAL_RISK_FACTORS
        ],
        "correlations": [
            {
                "tenor1": tenor1,
                "tenor2": tenor2,
                "correlation": correlation,
                "citation_id": profile_citation_id(
                    _girr_correlation_citation_id(tenor1, tenor2),
                    profile,
                ),
            }
            for (tenor1, tenor2), correlation in sorted(BASEL_GIRR_DELTA_CORRELATIONS.items())
        ],
        "inter_bucket_correlation": GIRR_INTER_BUCKET_CORRELATION,
        "inter_bucket_correlation_citation_id": profile_citation_id(
            "basel_mar50_55",
            profile,
        ),
        "other_currency_risk_weight_scalar": GIRR_OTHER_CURRENCY_RISK_WEIGHT_SCALAR,
        "other_currency_risk_weight_scalar_citation_id": profile_citation_id(
            "basel_mar50_57",
            profile,
        ),
    }


def _girr_correlation_citation_id(tenor1: str, tenor2: str) -> str:
    if "PARALLEL" in {tenor1, tenor2}:
        return "basel_mar50_57"
    return "basel_mar50_56"


__all__ = [
    "BASEL_GIRR_DELTA_CORRELATIONS",
    "BASEL_GIRR_DELTA_RISK_WEIGHTS",
    "BASEL_GIRR_SPECIAL_RISK_FACTORS",
    "BASEL_GIRR_TENORS",
    "GIRR_INTER_BUCKET_CORRELATION",
    "GIRR_OTHER_CURRENCY_RISK_WEIGHT_SCALAR",
    "GIRR_SPECIFIED_CURRENCIES",
    "SaCvaGirrDeltaRiskWeightRule",
    "SaCvaGirrSpecialRiskFactorRule",
    "SaCvaGirrTenorDefinition",
    "girr_delta_intra_bucket_correlation",
    "girr_delta_risk_weight",
    "girr_delta_risk_weight_rule",
    "girr_delta_tenors",
    "girr_inter_bucket_correlation",
    "girr_is_specified_currency",
    "girr_other_currency_risk_weight_scalar",
    "girr_specified_currencies",
    "girr_tenor_definition",
]
