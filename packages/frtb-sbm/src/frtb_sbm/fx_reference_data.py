"""FX delta reference-data lookups for SBM.

Regulatory traceability:
    See docs/REGULATORY_TRACEABILITY.md rows for reference_data.py, Basel
    MAR21.86-MAR21.89, and SBM-REF-001.
"""

from __future__ import annotations

from dataclasses import replace

from frtb_common import UnsupportedRegulatoryFeatureError

from frtb_sbm.data_models import SbmRegulatoryProfile
from frtb_sbm.girr_reference_data import _require_currency
from frtb_sbm.girr_reference_tables import SQRT2
from frtb_sbm.reference_citations_eu_crr3 import eu_crr3_citation_id_for_basel
from frtb_sbm.reference_profiles import _resolve_supported_profile
from frtb_sbm.reference_types import SbmFxBucketDefinition

FX_DELTA_RISK_WEIGHT = 0.15
FX_INTER_BUCKET_CORRELATION = 0.60
FX_INTRA_BUCKET_CORRELATION = 1.0

BASEL_FX_SPECIFIED_CURRENCIES: frozenset[str] = frozenset(
    {
        "USD",
        "EUR",
        "JPY",
        "GBP",
        "AUD",
        "CAD",
        "CHF",
        "MXN",
        "CNY",
        "NZD",
        "RUB",
        "HKD",
        "SGD",
        "TRY",
        "KRW",
        "SEK",
        "ZAR",
        "NOK",
        "INR",
        "BRL",
    }
)

BASEL_FX_BUCKETS: tuple[SbmFxBucketDefinition, ...] = tuple(
    SbmFxBucketDefinition(currency, currency, "basel_mar21_86")
    for currency in sorted(BASEL_FX_SPECIFIED_CURRENCIES)
)

US_NPR_FX_SPECIFIED_CURRENCIES = BASEL_FX_SPECIFIED_CURRENCIES
US_NPR_FX_BUCKETS: tuple[SbmFxBucketDefinition, ...] = tuple(
    SbmFxBucketDefinition(
        currency,
        currency,
        "us_npr_91_fr_14952_va7a_fx_reporting_currency",
    )
    for currency in sorted(US_NPR_FX_SPECIFIED_CURRENCIES)
)

EU_CRR3_FX_BUCKETS: tuple[SbmFxBucketDefinition, ...] = tuple(
    replace(bucket, citation_id=eu_crr3_citation_id_for_basel(bucket.citation_id))
    for bucket in BASEL_FX_BUCKETS
)
PRA_UK_CRR_FX_BUCKETS: tuple[SbmFxBucketDefinition, ...] = tuple(
    replace(bucket, citation_id="pra_uk_crr_325av_fx_delta_buckets") for bucket in BASEL_FX_BUCKETS
)

PROFILE_FX_BUCKETS: dict[SbmRegulatoryProfile, tuple[SbmFxBucketDefinition, ...]] = {
    SbmRegulatoryProfile.BASEL_MAR21: BASEL_FX_BUCKETS,
    SbmRegulatoryProfile.US_NPR_2_0: US_NPR_FX_BUCKETS,
    SbmRegulatoryProfile.EU_CRR3: EU_CRR3_FX_BUCKETS,
    SbmRegulatoryProfile.PRA_UK_CRR: PRA_UK_CRR_FX_BUCKETS,
}

PROFILE_FX_SPECIFIED_CURRENCIES: dict[SbmRegulatoryProfile, frozenset[str]] = {
    SbmRegulatoryProfile.BASEL_MAR21: BASEL_FX_SPECIFIED_CURRENCIES,
    SbmRegulatoryProfile.US_NPR_2_0: US_NPR_FX_SPECIFIED_CURRENCIES,
    SbmRegulatoryProfile.EU_CRR3: BASEL_FX_SPECIFIED_CURRENCIES,
    SbmRegulatoryProfile.PRA_UK_CRR: BASEL_FX_SPECIFIED_CURRENCIES,
}

_PROFILE_FX_BUCKET_CITATION_IDS: dict[SbmRegulatoryProfile, str] = {
    SbmRegulatoryProfile.BASEL_MAR21: "basel_mar21_86",
    SbmRegulatoryProfile.US_NPR_2_0: "us_npr_91_fr_14952_va7a_fx_delta_intra",
    SbmRegulatoryProfile.EU_CRR3: eu_crr3_citation_id_for_basel("basel_mar21_86"),
    SbmRegulatoryProfile.PRA_UK_CRR: "pra_uk_crr_325av_fx_delta_buckets",
}

_PROFILE_FX_WEIGHT_CITATION_IDS: dict[SbmRegulatoryProfile, str] = {
    SbmRegulatoryProfile.BASEL_MAR21: "basel_mar21_87",
    SbmRegulatoryProfile.US_NPR_2_0: "us_npr_91_fr_14952_va7a_fx_delta_weights",
    SbmRegulatoryProfile.EU_CRR3: eu_crr3_citation_id_for_basel("basel_mar21_87"),
    SbmRegulatoryProfile.PRA_UK_CRR: "pra_uk_crr_325av_fx_delta_weights",
}

_PROFILE_FX_SQRT2_CITATION_IDS: dict[SbmRegulatoryProfile, str] = {
    SbmRegulatoryProfile.BASEL_MAR21: "basel_mar21_88",
    SbmRegulatoryProfile.US_NPR_2_0: "us_npr_91_fr_14952_va7a_fx_delta_sqrt2",
    SbmRegulatoryProfile.EU_CRR3: eu_crr3_citation_id_for_basel("basel_mar21_88"),
    SbmRegulatoryProfile.PRA_UK_CRR: "pra_uk_crr_325av_fx_delta_sqrt2",
}

_PROFILE_FX_INTER_CITATION_IDS: dict[SbmRegulatoryProfile, str] = {
    SbmRegulatoryProfile.BASEL_MAR21: "basel_mar21_89",
    SbmRegulatoryProfile.US_NPR_2_0: "us_npr_91_fr_14952_va7a_fx_delta_inter",
    SbmRegulatoryProfile.EU_CRR3: eu_crr3_citation_id_for_basel("basel_mar21_89"),
    SbmRegulatoryProfile.PRA_UK_CRR: "pra_uk_crr_325aw_fx_delta_inter",
}

PROFILE_FX_DELTA_RISK_WEIGHT_CITATION_IDS = _PROFILE_FX_WEIGHT_CITATION_IDS
PROFILE_FX_DELTA_SQRT2_CITATION_IDS = _PROFILE_FX_SQRT2_CITATION_IDS
PROFILE_FX_DELTA_INTRA_BUCKET_CITATION_IDS = _PROFILE_FX_BUCKET_CITATION_IDS
PROFILE_FX_DELTA_INTER_BUCKET_CITATION_IDS = _PROFILE_FX_INTER_CITATION_IDS


def fx_buckets_for_profile(
    profile: SbmRegulatoryProfile | str,
) -> tuple[SbmFxBucketDefinition, ...]:
    """Return cited FX bucket definitions for a supported profile.
    Parameters
    ----------
    profile : SbmRegulatoryProfile | str
        See signature.

    Returns
    -------
    tuple[SbmFxBucketDefinition, ...]
    """

    resolved = _resolve_supported_profile(profile)
    _ensure_fx_delta_supported(profile)
    return PROFILE_FX_BUCKETS[resolved]


def fx_specified_currencies_for_profile(
    profile: SbmRegulatoryProfile | str,
) -> frozenset[str]:
    """Return the cited FX specified-currency set for a supported profile.
    Parameters
    ----------
    profile : SbmRegulatoryProfile | str
        See signature.

    Returns
    -------
    frozenset[str]
    """

    resolved = _resolve_supported_profile(profile)
    _ensure_fx_delta_supported(profile)
    return PROFILE_FX_SPECIFIED_CURRENCIES[resolved]


def normalise_fx_delta_currency_code(currency: str) -> str:
    """Map FX delta currency codes to MAR21.88 canonical bucket codes (ADR 0017).
    Parameters
    ----------
    currency : str
        See signature.

    Returns
    -------
    str
    """

    normalised = _require_currency(currency)
    if normalised == "CNH":
        return "CNY"
    return normalised


def fx_bucket_definition(
    profile: SbmRegulatoryProfile | str,
    bucket_id: str,
) -> SbmFxBucketDefinition:
    """Return the FX bucket definition for a currency bucket id.
    Parameters
    ----------
    profile : SbmRegulatoryProfile | str
        See signature.
    bucket_id : str
        See signature.

    Returns
    -------
    SbmFxBucketDefinition
    """

    _ensure_fx_delta_supported(profile)
    normalised = normalise_fx_delta_currency_code(bucket_id)
    for bucket in PROFILE_FX_BUCKETS[_resolve_supported_profile(profile)]:
        if bucket.bucket_id == normalised:
            return bucket
    resolved = _resolve_supported_profile(profile)
    return SbmFxBucketDefinition(
        bucket_id=normalised,
        currency=normalised,
        citation_id=_PROFILE_FX_BUCKET_CITATION_IDS[resolved],
    )


def fx_delta_risk_weight(
    profile: SbmRegulatoryProfile | str,
    *,
    currency: str,
    reporting_currency: str,
) -> tuple[float, tuple[str, ...]]:
    """Return the cited FX delta risk weight and citation ids.
    Parameters
    ----------
    profile : SbmRegulatoryProfile | str
        See signature.
    currency : str
        See signature.
    reporting_currency : str
        See signature.

    Returns
    -------
    tuple[float, tuple[str, ...]]
    """

    _ensure_fx_delta_supported(profile)
    normalised_currency = normalise_fx_delta_currency_code(currency)
    normalised_reporting = normalise_fx_delta_currency_code(reporting_currency)
    resolved = _resolve_supported_profile(profile)
    if normalised_currency == normalised_reporting:
        return 0.0, (_PROFILE_FX_WEIGHT_CITATION_IDS[resolved],)
    citation_ids: list[str] = [_PROFILE_FX_WEIGHT_CITATION_IDS[resolved]]
    risk_weight = FX_DELTA_RISK_WEIGHT
    if _apply_fx_sqrt2_adjustment(
        currency=normalised_currency,
        reporting_currency=normalised_reporting,
        profile=profile,
    ):
        risk_weight /= SQRT2
        citation_ids.append(_PROFILE_FX_SQRT2_CITATION_IDS[resolved])
    return risk_weight, tuple(citation_ids)


def fx_delta_intra_bucket_correlation(
    profile: SbmRegulatoryProfile | str,
    *,
    bucket1: str,
    bucket2: str,
) -> tuple[float, tuple[str, ...]]:
    """Return the cited FX delta intra-bucket correlation and citation ids.
    Parameters
    ----------
    profile : SbmRegulatoryProfile | str
        See signature.
    bucket1 : str
        See signature.
    bucket2 : str
        See signature.

    Returns
    -------
    tuple[float, tuple[str, ...]]
    """

    _ensure_fx_delta_supported(profile)
    normalised_bucket1 = normalise_fx_delta_currency_code(bucket1)
    normalised_bucket2 = normalise_fx_delta_currency_code(bucket2)
    fx_bucket_definition(profile, normalised_bucket1)
    fx_bucket_definition(profile, normalised_bucket2)
    del normalised_bucket1, normalised_bucket2
    resolved = _resolve_supported_profile(profile)
    return FX_INTRA_BUCKET_CORRELATION, (_PROFILE_FX_BUCKET_CITATION_IDS[resolved],)


def fx_inter_bucket_correlation(
    profile: SbmRegulatoryProfile | str,
    *,
    bucket1: str,
    bucket2: str,
) -> tuple[float, tuple[str, ...]]:
    """Return the cited FX inter-bucket correlation and citation ids.
    Parameters
    ----------
    profile : SbmRegulatoryProfile | str
        See signature.
    bucket1 : str
        See signature.
    bucket2 : str
        See signature.

    Returns
    -------
    tuple[float, tuple[str, ...]]
    """

    _ensure_fx_delta_supported(profile)
    normalised_bucket1 = normalise_fx_delta_currency_code(bucket1)
    normalised_bucket2 = normalise_fx_delta_currency_code(bucket2)
    fx_bucket_definition(profile, normalised_bucket1)
    fx_bucket_definition(profile, normalised_bucket2)
    resolved = _resolve_supported_profile(profile)
    if normalised_bucket1 == normalised_bucket2:
        return FX_INTRA_BUCKET_CORRELATION, (_PROFILE_FX_INTER_CITATION_IDS[resolved],)
    return FX_INTER_BUCKET_CORRELATION, (_PROFILE_FX_INTER_CITATION_IDS[resolved],)


def _ensure_fx_delta_supported(profile: SbmRegulatoryProfile | str) -> None:
    resolved = _resolve_supported_profile(profile)
    if resolved not in PROFILE_FX_BUCKETS:
        raise UnsupportedRegulatoryFeatureError(
            f"FX delta reference data is unsupported for profile {resolved.value}"
        )


def _apply_fx_sqrt2_adjustment(
    *,
    currency: str,
    reporting_currency: str,
    profile: SbmRegulatoryProfile | str,
) -> bool:
    if currency == reporting_currency:
        return False
    specified = fx_specified_currencies_for_profile(profile)
    return currency in specified and reporting_currency in specified


__all__ = [
    "BASEL_FX_BUCKETS",
    "BASEL_FX_SPECIFIED_CURRENCIES",
    "EU_CRR3_FX_BUCKETS",
    "FX_DELTA_RISK_WEIGHT",
    "FX_INTER_BUCKET_CORRELATION",
    "FX_INTRA_BUCKET_CORRELATION",
    "PRA_UK_CRR_FX_BUCKETS",
    "PROFILE_FX_BUCKETS",
    "PROFILE_FX_DELTA_INTER_BUCKET_CITATION_IDS",
    "PROFILE_FX_DELTA_INTRA_BUCKET_CITATION_IDS",
    "PROFILE_FX_DELTA_RISK_WEIGHT_CITATION_IDS",
    "PROFILE_FX_DELTA_SQRT2_CITATION_IDS",
    "PROFILE_FX_SPECIFIED_CURRENCIES",
    "US_NPR_FX_BUCKETS",
    "US_NPR_FX_SPECIFIED_CURRENCIES",
    "fx_bucket_definition",
    "fx_buckets_for_profile",
    "fx_delta_intra_bucket_correlation",
    "fx_delta_risk_weight",
    "fx_inter_bucket_correlation",
    "fx_specified_currencies_for_profile",
    "normalise_fx_delta_currency_code",
]
