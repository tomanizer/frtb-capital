"""GIRR delta reference-data lookups for SBM.

Regulatory traceability:
    See docs/REGULATORY_TRACEABILITY.md rows for reference_data.py, Basel
    MAR21.38-MAR21.50, and SBM-REF-001.
"""

from __future__ import annotations

from frtb_common import UnsupportedRegulatoryFeatureError

from frtb_sbm._text import require_text as _require_text
from frtb_sbm.data_models import SbmRegulatoryProfile
from frtb_sbm.girr_reference_tables import (
    BASEL_GIRR_BUCKETS,
    BASEL_GIRR_DELTA_RISK_WEIGHTS,
    BASEL_GIRR_SPECIAL_RISK_FACTORS,
    BASEL_GIRR_TENORS,
    GIRR_DELTA_INTRA_BUCKET_CONSTANT,
    GIRR_DIFFERENT_CURVE_CORRELATION,
    GIRR_INFLATION_DIFFERENT_TENOR_CORRELATION,
    GIRR_INFLATION_SAME_TENOR_CORRELATION,
    GIRR_INTER_BUCKET_CORRELATION,
    GIRR_INTRA_BUCKET_CORRELATION_FLOOR,
    GIRR_SAME_CURVE_CORRELATION,
    LIQUID_GIRR_CURRENCIES,
    PROFILE_GIRR_BUCKETS,
    PROFILE_GIRR_DELTA_INTER_BUCKET_CITATION_IDS,
    PROFILE_GIRR_DELTA_INTRA_BUCKET_CITATION_IDS,
    PROFILE_GIRR_DELTA_RISK_WEIGHTS,
    PROFILE_GIRR_DELTA_SQRT2_CITATION_IDS,
    PROFILE_GIRR_SPECIAL_RISK_FACTORS,
    PROFILE_GIRR_TENORS,
    SQRT2,
    US_NPR_GIRR_BUCKETS,
    US_NPR_GIRR_DELTA_RISK_WEIGHTS,
    US_NPR_GIRR_SPECIAL_RISK_FACTORS,
    US_NPR_GIRR_TENORS,
)
from frtb_sbm.reference_citation_routing import ensure_profile_in_reference_map
from frtb_sbm.reference_profiles import _resolve_supported_profile
from frtb_sbm.reference_types import (
    SbmGirrBucketDefinition,
    SbmGirrRiskWeightRule,
    SbmGirrTenorDefinition,
)
from frtb_sbm.validation import SbmInputError


def girr_buckets_for_profile(
    profile: SbmRegulatoryProfile | str,
) -> tuple[SbmGirrBucketDefinition, ...]:
    """Return GIRR bucket definitions for a supported profile.
    Parameters
    ----------
    profile : SbmRegulatoryProfile | str
        See signature.

    Returns
    -------
    tuple[SbmGirrBucketDefinition, ...]
    """

    resolved = _resolve_supported_profile(profile)
    return PROFILE_GIRR_BUCKETS[resolved]


def girr_tenors_for_profile(
    profile: SbmRegulatoryProfile | str,
) -> tuple[SbmGirrTenorDefinition, ...]:
    """Return the prescribed GIRR tenor set for a supported profile.
    Parameters
    ----------
    profile : SbmRegulatoryProfile | str
        See signature.

    Returns
    -------
    tuple[SbmGirrTenorDefinition, ...]
    """

    resolved = _resolve_supported_profile(profile)
    return PROFILE_GIRR_TENORS[resolved]


def girr_bucket_for_currency(
    profile: SbmRegulatoryProfile | str,
    currency: str,
) -> SbmGirrBucketDefinition:
    """Return the GIRR bucket definition for a currency code.
    Parameters
    ----------
    profile : SbmRegulatoryProfile | str
        See signature.
    currency : str
        See signature.

    Returns
    -------
    SbmGirrBucketDefinition
    """

    normalised = _require_currency(currency)
    for bucket in girr_buckets_for_profile(profile):
        if bucket.currency == normalised:
            return bucket
    raise SbmInputError(
        f"no GIRR bucket for currency {normalised}",
        field="currency",
    )


def girr_bucket_definition(
    profile: SbmRegulatoryProfile | str,
    bucket_id: str,
) -> SbmGirrBucketDefinition:
    """Return the GIRR bucket definition for a bucket id.
    Parameters
    ----------
    profile : SbmRegulatoryProfile | str
        See signature.
    bucket_id : str
        See signature.

    Returns
    -------
    SbmGirrBucketDefinition
    """

    normalised = _require_text(bucket_id, "bucket_id")
    for bucket in girr_buckets_for_profile(profile):
        if bucket.bucket_id == normalised:
            return bucket
    raise SbmInputError(
        f"no GIRR bucket definition for bucket_id {normalised}",
        field="bucket_id",
    )


def girr_tenor_definition(
    profile: SbmRegulatoryProfile | str,
    tenor: str,
) -> SbmGirrTenorDefinition:
    """Return the GIRR tenor definition for a canonical tenor label.
    Parameters
    ----------
    profile : SbmRegulatoryProfile | str
        See signature.
    tenor : str
        See signature.

    Returns
    -------
    SbmGirrTenorDefinition
    """

    normalised = _require_text(tenor, "tenor")
    for tenor_definition in girr_tenors_for_profile(profile):
        if tenor_definition.tenor == normalised:
            return tenor_definition
    raise SbmInputError(
        f"no GIRR tenor definition for tenor {normalised}",
        field="tenor",
    )


def girr_delta_risk_weight_rule(
    profile: SbmRegulatoryProfile | str,
    tenor: str,
) -> SbmGirrRiskWeightRule:
    """Return the cited base GIRR delta risk-weight rule for a tenor.
    Parameters
    ----------
    profile : SbmRegulatoryProfile | str
        See signature.
    tenor : str
        See signature.

    Returns
    -------
    SbmGirrRiskWeightRule
    """

    normalised = _require_text(tenor, "tenor")
    for rule in PROFILE_GIRR_DELTA_RISK_WEIGHTS[_resolve_supported_profile(profile)]:
        if rule.tenor == normalised:
            return rule
    for special_rule in PROFILE_GIRR_SPECIAL_RISK_FACTORS[_resolve_supported_profile(profile)]:
        if special_rule.risk_factor == normalised:
            return SbmGirrRiskWeightRule(
                tenor=special_rule.risk_factor,
                risk_weight=special_rule.risk_weight,
                citation_id=special_rule.citation_id,
            )
    raise SbmInputError(
        f"no GIRR delta risk weight for tenor {normalised}",
        field="tenor",
    )


def girr_delta_risk_weight(
    profile: SbmRegulatoryProfile | str,
    *,
    tenor: str,
    currency: str,
    reporting_currency: str,
) -> tuple[float, tuple[str, ...]]:
    """Return the cited GIRR delta risk weight and citation ids.
    Parameters
    ----------
    profile, tenor, currency, reporting_currency :
        See function signature for types and defaults.

    Returns
    -------
    tuple[float, tuple[str, ...]]
    """

    _ensure_girr_delta_supported(profile)
    resolved = _resolve_supported_profile(profile)
    rule = girr_delta_risk_weight_rule(profile, tenor)
    normalised_currency = _require_currency(currency)
    normalised_reporting = _require_currency(reporting_currency)
    citation_ids: list[str] = [rule.citation_id]
    risk_weight = rule.risk_weight
    if _apply_sqrt2_adjustment(
        tenor=rule.tenor,
        currency=normalised_currency,
        reporting_currency=normalised_reporting,
    ):
        risk_weight /= SQRT2
        citation_ids.append(PROFILE_GIRR_DELTA_SQRT2_CITATION_IDS[resolved])
    return risk_weight, tuple(citation_ids)


def _ensure_girr_supported(profile: SbmRegulatoryProfile | str) -> None:
    ensure_profile_in_reference_map(
        profile,
        PROFILE_GIRR_BUCKETS,
        feature_label="GIRR",
    )


def _ensure_girr_delta_supported(profile: SbmRegulatoryProfile | str) -> None:
    resolved = _resolve_supported_profile(profile)
    if resolved not in PROFILE_GIRR_DELTA_RISK_WEIGHTS:
        raise UnsupportedRegulatoryFeatureError(
            f"GIRR delta reference data is unsupported for profile {resolved.value}"
        )


def _ensure_girr_vega_supported(profile: SbmRegulatoryProfile | str) -> None:
    from frtb_sbm.vega_reference_data import PROFILE_GIRR_VEGA_LIQUIDITY_HORIZON_DAYS

    ensure_profile_in_reference_map(
        profile,
        PROFILE_GIRR_VEGA_LIQUIDITY_HORIZON_DAYS,
        feature_label="GIRR vega",
    )


def _apply_sqrt2_adjustment(*, tenor: str, currency: str, reporting_currency: str) -> bool:
    if tenor in {"INFL", "XCCY"}:
        return False
    return currency == reporting_currency or currency in LIQUID_GIRR_CURRENCIES


def _require_currency(value: str) -> str:
    normalised = _require_text(value, "currency")
    if len(normalised) != 3 or not normalised.isalpha():
        raise SbmInputError(
            "currency must be a three-letter alphabetic code",
            field="currency",
        )
    return normalised.upper()


__all__ = [
    "BASEL_GIRR_BUCKETS",
    "BASEL_GIRR_DELTA_RISK_WEIGHTS",
    "BASEL_GIRR_SPECIAL_RISK_FACTORS",
    "BASEL_GIRR_TENORS",
    "GIRR_DELTA_INTRA_BUCKET_CONSTANT",
    "GIRR_DIFFERENT_CURVE_CORRELATION",
    "GIRR_INFLATION_DIFFERENT_TENOR_CORRELATION",
    "GIRR_INFLATION_SAME_TENOR_CORRELATION",
    "GIRR_INTER_BUCKET_CORRELATION",
    "GIRR_INTRA_BUCKET_CORRELATION_FLOOR",
    "GIRR_SAME_CURVE_CORRELATION",
    "LIQUID_GIRR_CURRENCIES",
    "PROFILE_GIRR_BUCKETS",
    "PROFILE_GIRR_DELTA_INTER_BUCKET_CITATION_IDS",
    "PROFILE_GIRR_DELTA_INTRA_BUCKET_CITATION_IDS",
    "PROFILE_GIRR_DELTA_RISK_WEIGHTS",
    "PROFILE_GIRR_DELTA_SQRT2_CITATION_IDS",
    "PROFILE_GIRR_SPECIAL_RISK_FACTORS",
    "PROFILE_GIRR_TENORS",
    "US_NPR_GIRR_BUCKETS",
    "US_NPR_GIRR_DELTA_RISK_WEIGHTS",
    "US_NPR_GIRR_SPECIAL_RISK_FACTORS",
    "US_NPR_GIRR_TENORS",
    "girr_bucket_definition",
    "girr_bucket_for_currency",
    "girr_buckets_for_profile",
    "girr_delta_risk_weight",
    "girr_delta_risk_weight_rule",
    "girr_tenor_definition",
    "girr_tenors_for_profile",
]
