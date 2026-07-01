"""
Commodity delta reference data for BASEL_MAR21.

Regulatory traceability:
    Basel MAR21.13 — commodity delta and vega risk factors and tenors.
    Basel MAR21.81-MAR21.85 — buckets (Table 11), weights, correlations (Table 12).
"""

from __future__ import annotations

from dataclasses import dataclass

from frtb_common import UnsupportedRegulatoryFeatureError

from frtb_sbm._text import require_text as _require_text
from frtb_sbm.data_models import SbmRegulatoryProfile
from frtb_sbm.validation import SbmInputError, ensure_sbm_profile_known

BASEL_MAR21_URL = "https://www.bis.org/basel_framework/chapter/MAR/21.htm"

COMMODITY_TENOR_CORRELATION = 0.99
COMMODITY_LOCATION_CORRELATION = 0.999
COMMODITY_OTHER_BUCKET = "11"

_COMMODITY_BUCKET_CITATION = "basel_mar21_81"
_COMMODITY_WEIGHT_CITATION = "basel_mar21_82"
_COMMODITY_INTRA_CITATION = "basel_mar21_83"
_COMMODITY_INTER_CITATION = "basel_mar21_85"

_US_NPR_COMMODITY_BUCKET_CITATION = "us_npr_91_fr_14952_va7a_commodity_delta_buckets"
_US_NPR_COMMODITY_WEIGHT_CITATION = "us_npr_91_fr_14952_va7a_commodity_delta_weights"
_US_NPR_COMMODITY_INTRA_CITATION = "us_npr_91_fr_14952_va7a_commodity_delta_intra"
_US_NPR_COMMODITY_INTER_CITATION = "us_npr_91_fr_14952_va7a_commodity_delta_inter"


@dataclass(frozen=True)
class SbmCommodityBucketDefinition:
    """Profile-specific commodity bucket metadata."""

    bucket_id: str
    label: str
    risk_weight: float
    commodity_correlation: float
    citation_id: str


_BASEL_COMMODITY_BUCKETS: tuple[SbmCommodityBucketDefinition, ...] = (
    SbmCommodityBucketDefinition("1", "energy_solid", 0.30, 0.55, _COMMODITY_BUCKET_CITATION),
    SbmCommodityBucketDefinition("2", "energy_liquid", 0.35, 0.95, _COMMODITY_BUCKET_CITATION),
    SbmCommodityBucketDefinition(
        "3", "energy_electricity_carbon", 0.60, 0.40, _COMMODITY_BUCKET_CITATION
    ),
    SbmCommodityBucketDefinition("4", "freight", 0.80, 0.80, _COMMODITY_BUCKET_CITATION),
    SbmCommodityBucketDefinition(
        "5", "metals_non_precious", 0.40, 0.60, _COMMODITY_BUCKET_CITATION
    ),
    SbmCommodityBucketDefinition(
        "6", "gaseous_combustibles", 0.45, 0.65, _COMMODITY_BUCKET_CITATION
    ),
    SbmCommodityBucketDefinition("7", "precious_metals", 0.20, 0.55, _COMMODITY_BUCKET_CITATION),
    SbmCommodityBucketDefinition("8", "grains_oilseed", 0.35, 0.45, _COMMODITY_BUCKET_CITATION),
    SbmCommodityBucketDefinition("9", "livestock_dairy", 0.25, 0.15, _COMMODITY_BUCKET_CITATION),
    SbmCommodityBucketDefinition(
        "10", "softs_agriculturals", 0.35, 0.40, _COMMODITY_BUCKET_CITATION
    ),
    SbmCommodityBucketDefinition("11", "other_commodity", 0.50, 0.15, _COMMODITY_BUCKET_CITATION),
)

_US_NPR_COMMODITY_BUCKETS: tuple[SbmCommodityBucketDefinition, ...] = (
    SbmCommodityBucketDefinition(
        "1", "energy_solid_combustibles", 0.30, 0.55, _US_NPR_COMMODITY_BUCKET_CITATION
    ),
    SbmCommodityBucketDefinition(
        "2", "energy_liquid_combustibles", 0.35, 0.95, _US_NPR_COMMODITY_BUCKET_CITATION
    ),
    SbmCommodityBucketDefinition(
        "3", "energy_carbon_trading", 0.60, 0.40, _US_NPR_COMMODITY_BUCKET_CITATION
    ),
    SbmCommodityBucketDefinition("4", "freight", 0.80, 0.80, _US_NPR_COMMODITY_BUCKET_CITATION),
    SbmCommodityBucketDefinition(
        "5", "metals_non_precious", 0.40, 0.60, _US_NPR_COMMODITY_BUCKET_CITATION
    ),
    SbmCommodityBucketDefinition(
        "6",
        "gaseous_combustibles_electricity",
        0.45,
        0.65,
        _US_NPR_COMMODITY_BUCKET_CITATION,
    ),
    SbmCommodityBucketDefinition(
        "7", "precious_metals", 0.20, 0.55, _US_NPR_COMMODITY_BUCKET_CITATION
    ),
    SbmCommodityBucketDefinition(
        "8", "grains_oilseed", 0.35, 0.45, _US_NPR_COMMODITY_BUCKET_CITATION
    ),
    SbmCommodityBucketDefinition(
        "9", "livestock_dairy", 0.25, 0.15, _US_NPR_COMMODITY_BUCKET_CITATION
    ),
    SbmCommodityBucketDefinition(
        "10", "forestry_agriculturals", 0.35, 0.40, _US_NPR_COMMODITY_BUCKET_CITATION
    ),
    SbmCommodityBucketDefinition(
        "11", "other_commodity", 0.50, 0.15, _US_NPR_COMMODITY_BUCKET_CITATION
    ),
    SbmCommodityBucketDefinition(
        "12", "commodity_index", 0.30, 0.50, _US_NPR_COMMODITY_BUCKET_CITATION
    ),
)

_PROFILE_COMMODITY_BUCKETS: dict[SbmRegulatoryProfile, tuple[SbmCommodityBucketDefinition, ...]] = {
    SbmRegulatoryProfile.BASEL_MAR21: _BASEL_COMMODITY_BUCKETS,
    SbmRegulatoryProfile.US_NPR_2_0: _US_NPR_COMMODITY_BUCKETS,
}

_PROFILE_COMMODITY_WEIGHT_CITATION_IDS: dict[SbmRegulatoryProfile, tuple[str, ...]] = {
    SbmRegulatoryProfile.BASEL_MAR21: (_COMMODITY_WEIGHT_CITATION,),
    SbmRegulatoryProfile.US_NPR_2_0: (_US_NPR_COMMODITY_WEIGHT_CITATION,),
}

_PROFILE_COMMODITY_INTRA_CITATION_IDS: dict[SbmRegulatoryProfile, tuple[str, ...]] = {
    SbmRegulatoryProfile.BASEL_MAR21: (_COMMODITY_INTRA_CITATION,),
    SbmRegulatoryProfile.US_NPR_2_0: (_US_NPR_COMMODITY_INTRA_CITATION,),
}

_PROFILE_COMMODITY_INTER_CITATION_IDS: dict[SbmRegulatoryProfile, tuple[str, ...]] = {
    SbmRegulatoryProfile.BASEL_MAR21: (_COMMODITY_INTER_CITATION,),
    SbmRegulatoryProfile.US_NPR_2_0: (_US_NPR_COMMODITY_INTER_CITATION,),
}


def commodity_buckets_for_profile(
    profile: SbmRegulatoryProfile | str,
) -> tuple[SbmCommodityBucketDefinition, ...]:
    """Return cited commodity bucket definitions for a supported profile.
    Parameters
    ----------
    profile : SbmRegulatoryProfile | str
        See signature.

    Returns
    -------
    tuple[SbmCommodityBucketDefinition, ...]
    """

    resolved = ensure_sbm_profile_known(profile if isinstance(profile, str) else profile.value)
    _ensure_commodity_delta_supported(profile)
    return _PROFILE_COMMODITY_BUCKETS[resolved]


def commodity_bucket_definition(
    profile: SbmRegulatoryProfile | str,
    bucket_id: str,
) -> SbmCommodityBucketDefinition:
    """Return the commodity bucket definition for a canonical bucket id.
    Parameters
    ----------
    profile : SbmRegulatoryProfile | str
        See signature.
    bucket_id : str
        See signature.

    Returns
    -------
    SbmCommodityBucketDefinition
    """

    _ensure_commodity_delta_supported(profile)
    normalised = _require_text(bucket_id, "bucket_id")
    resolved = ensure_sbm_profile_known(profile if isinstance(profile, str) else profile.value)
    for bucket in _PROFILE_COMMODITY_BUCKETS[resolved]:
        if bucket.bucket_id == normalised:
            return bucket
    raise SbmInputError(
        f"no commodity bucket definition for bucket_id {normalised}",
        field="bucket_id",
    )


def commodity_delta_risk_weight(
    profile: SbmRegulatoryProfile | str,
    *,
    bucket_id: str,
) -> tuple[float, tuple[str, ...]]:
    """Return the cited commodity delta risk weight for one bucket.
    Parameters
    ----------
    profile : SbmRegulatoryProfile | str
        See signature.
    bucket_id : str
        See signature.

    Returns
    -------
    tuple[float, tuple[str, ...]]
    """

    resolved = ensure_sbm_profile_known(profile if isinstance(profile, str) else profile.value)
    bucket = commodity_bucket_definition(profile, bucket_id)
    return bucket.risk_weight, _PROFILE_COMMODITY_WEIGHT_CITATION_IDS[resolved]


def commodity_delta_intra_bucket_correlation(
    profile: SbmRegulatoryProfile | str,
    *,
    bucket_id: str,
    commodity_a: str,
    commodity_b: str,
    tenor_a: str,
    tenor_b: str,
    location_a: str,
    location_b: str,
) -> tuple[float, tuple[str, ...]]:
    """Return MAR21.83 intra-bucket correlation as rho_cty * rho_tenor * rho_location.
    Parameters
    ----------
    profile, bucket_id, commodity_a, commodity_b, tenor_a, tenor_b, location_a, location_b :
        See function signature for types and defaults.

    Returns
    -------
    tuple[float, tuple[str, ...]]
    """

    _ensure_commodity_delta_supported(profile)
    resolved = ensure_sbm_profile_known(profile if isinstance(profile, str) else profile.value)
    bucket = commodity_bucket_definition(profile, bucket_id)
    commodity_a_norm = _require_text(commodity_a, "risk_factor")
    commodity_b_norm = _require_text(commodity_b, "risk_factor")
    tenor_a_norm = _require_text(tenor_a, "tenor")
    tenor_b_norm = _require_text(tenor_b, "tenor")
    location_a_norm = _require_text(location_a, "qualifier")
    location_b_norm = _require_text(location_b, "qualifier")

    if commodity_a_norm == commodity_b_norm:
        rho_cty = 1.0
    else:
        rho_cty = bucket.commodity_correlation

    rho_tenor = 1.0 if tenor_a_norm == tenor_b_norm else COMMODITY_TENOR_CORRELATION
    rho_location = 1.0 if location_a_norm == location_b_norm else COMMODITY_LOCATION_CORRELATION
    return rho_cty * rho_tenor * rho_location, _PROFILE_COMMODITY_INTRA_CITATION_IDS[resolved]


def commodity_delta_intra_bucket_citation_ids(
    profile: SbmRegulatoryProfile | str,
) -> tuple[str, ...]:
    """Return profile-owned commodity delta intra-bucket correlation citation ids.

    Parameters
    ----------
    profile : SbmRegulatoryProfile | str
        Regulatory profile that owns the commodity delta intra-bucket correlation rule.

    Returns
    -------
    tuple[str, ...]
        Citation identifiers for commodity delta intra-bucket correlations.
    """

    _ensure_commodity_delta_supported(profile)
    resolved = ensure_sbm_profile_known(profile if isinstance(profile, str) else profile.value)
    return _PROFILE_COMMODITY_INTRA_CITATION_IDS[resolved]


def commodity_inter_bucket_correlation(
    profile: SbmRegulatoryProfile | str,
    *,
    bucket1: str,
    bucket2: str,
) -> tuple[float, tuple[str, ...]]:
    """Return MAR21.85 inter-bucket gamma for two commodity buckets.
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

    _ensure_commodity_delta_supported(profile)
    resolved = ensure_sbm_profile_known(profile if isinstance(profile, str) else profile.value)
    b1 = _require_commodity_bucket_number(bucket1)
    b2 = _require_commodity_bucket_number(bucket2)
    commodity_bucket_definition(profile, str(b1))
    commodity_bucket_definition(profile, str(b2))
    citation_ids = _PROFILE_COMMODITY_INTER_CITATION_IDS[resolved]
    if b1 == b2:
        return 1.0, citation_ids
    if b1 == 11 or b2 == 11:
        return 0.0, citation_ids
    return 0.20, citation_ids


def commodity_inter_bucket_citation_ids(profile: SbmRegulatoryProfile | str) -> tuple[str, ...]:
    """Return profile-owned commodity delta inter-bucket correlation citation ids.

    Parameters
    ----------
    profile : SbmRegulatoryProfile | str
        Regulatory profile that owns the commodity delta inter-bucket correlation rule.

    Returns
    -------
    tuple[str, ...]
        Citation identifiers for commodity delta inter-bucket correlations.
    """

    _ensure_commodity_delta_supported(profile)
    resolved = ensure_sbm_profile_known(profile if isinstance(profile, str) else profile.value)
    return _PROFILE_COMMODITY_INTER_CITATION_IDS[resolved]


def commodity_reference_payload(profile: SbmRegulatoryProfile | str) -> dict[str, object]:
    """Return commodity tables for profile hashing.
    Parameters
    ----------
    profile : SbmRegulatoryProfile | str
        See signature.

    Returns
    -------
    dict[str, object]
    """

    resolved = ensure_sbm_profile_known(profile if isinstance(profile, str) else profile.value)
    _ensure_commodity_delta_supported(profile)
    return {
        "commodity_buckets": [
            {
                "bucket_id": bucket.bucket_id,
                "label": bucket.label,
                "risk_weight": bucket.risk_weight,
                "commodity_correlation": bucket.commodity_correlation,
                "citation_id": bucket.citation_id,
            }
            for bucket in _PROFILE_COMMODITY_BUCKETS[resolved]
        ],
        "commodity_tenor_correlation": COMMODITY_TENOR_CORRELATION,
        "commodity_location_correlation": COMMODITY_LOCATION_CORRELATION,
    }


def _ensure_commodity_delta_supported(profile: SbmRegulatoryProfile | str) -> None:
    resolved = ensure_sbm_profile_known(profile if isinstance(profile, str) else profile.value)
    if resolved not in _PROFILE_COMMODITY_BUCKETS:
        raise UnsupportedRegulatoryFeatureError(
            f"commodity delta reference data is unsupported for profile {resolved.value}"
        )


def _require_commodity_bucket_number(bucket_id: str) -> int:
    normalised = _require_text(bucket_id, "bucket_id")
    try:
        bucket_number = int(normalised)
    except ValueError as exc:
        raise SbmInputError(
            "commodity bucket_id must be a numeric bucket label",
            field="bucket_id",
        ) from exc
    if bucket_number < 1 or bucket_number > 12:
        raise SbmInputError(
            "commodity bucket_id must be between 1 and 12",
            field="bucket_id",
        )
    return bucket_number


COMMODITY_BASEL_CITATIONS = {
    "basel_mar21_13": {
        "source_id": "basel_mar21_sensitivities_based_method",
        "location": "MAR21.13",
        "url": BASEL_MAR21_URL,
        "note": "Commodity delta and vega risk-factor definitions and tenors.",
    },
    "basel_mar21_81": {
        "source_id": "basel_mar21_sensitivities_based_method",
        "location": "MAR21.81",
        "url": BASEL_MAR21_URL,
        "note": "Commodity delta bucket assignment (Table 11).",
    },
    "basel_mar21_82": {
        "source_id": "basel_mar21_sensitivities_based_method",
        "location": "MAR21.82",
        "url": BASEL_MAR21_URL,
        "note": "Commodity delta risk weights (Table 11).",
    },
    "basel_mar21_83": {
        "source_id": "basel_mar21_sensitivities_based_method",
        "location": "MAR21.83",
        "url": BASEL_MAR21_URL,
        "note": "Commodity delta intra-bucket correlation parameters (Table 12).",
    },
    "basel_mar21_85": {
        "source_id": "basel_mar21_sensitivities_based_method",
        "location": "MAR21.85",
        "url": BASEL_MAR21_URL,
        "note": "Commodity delta inter-bucket correlation parameters.",
    },
}


__all__ = [
    "COMMODITY_LOCATION_CORRELATION",
    "COMMODITY_OTHER_BUCKET",
    "COMMODITY_TENOR_CORRELATION",
    "SbmCommodityBucketDefinition",
    "commodity_bucket_definition",
    "commodity_buckets_for_profile",
    "commodity_delta_intra_bucket_citation_ids",
    "commodity_delta_intra_bucket_correlation",
    "commodity_delta_risk_weight",
    "commodity_inter_bucket_citation_ids",
    "commodity_inter_bucket_correlation",
    "commodity_reference_payload",
]
