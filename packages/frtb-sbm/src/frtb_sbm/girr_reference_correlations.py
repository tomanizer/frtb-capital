"""GIRR correlation reference-data lookups for SBM.

Regulatory traceability:
    Basel MAR21.45-MAR21.50 and matching U.S. NPR 2.0 comparison-profile citations.
"""

from __future__ import annotations

import math

from frtb_sbm._text import require_text as _require_text
from frtb_sbm.data_models import SbmRegulatoryProfile
from frtb_sbm.girr_reference_data import (
    _ensure_girr_delta_supported,
    girr_bucket_definition,
    girr_tenor_definition,
)
from frtb_sbm.girr_reference_tables import (
    GIRR_DELTA_INTRA_BUCKET_CONSTANT,
    GIRR_DIFFERENT_CURVE_CORRELATION,
    GIRR_INFLATION_DIFFERENT_TENOR_CORRELATION,
    GIRR_INFLATION_SAME_TENOR_CORRELATION,
    GIRR_INTER_BUCKET_CORRELATION,
    GIRR_INTRA_BUCKET_CORRELATION_FLOOR,
    GIRR_SAME_CURVE_CORRELATION,
    PROFILE_GIRR_DELTA_INTER_BUCKET_CITATION_IDS,
    PROFILE_GIRR_DELTA_INTRA_BUCKET_CITATION_IDS,
)
from frtb_sbm.reference_profiles import _resolve_supported_profile


def girr_delta_intra_bucket_correlation(
    profile: SbmRegulatoryProfile | str,
    *,
    tenor1: str,
    tenor2: str,
    same_curve: bool,
) -> tuple[float, tuple[str, ...]]:
    """Return the cited GIRR delta intra-bucket correlation and citation ids.
    Parameters
    ----------
    profile, tenor1, tenor2, same_curve :
        See function signature for types and defaults.

    Returns
    -------
    tuple[float, tuple[str, ...]]
    """

    _ensure_girr_delta_supported(profile)
    resolved = _resolve_supported_profile(profile)
    normalised_tenor1 = _require_text(tenor1, "tenor1")
    normalised_tenor2 = _require_text(tenor2, "tenor2")
    citation_ids = (PROFILE_GIRR_DELTA_INTRA_BUCKET_CITATION_IDS[resolved],)

    if normalised_tenor1 == "XCCY" or normalised_tenor2 == "XCCY":
        if normalised_tenor1 == normalised_tenor2:
            return GIRR_SAME_CURVE_CORRELATION, citation_ids
        return 0.0, citation_ids

    if normalised_tenor1 == "INFL" or normalised_tenor2 == "INFL":
        if normalised_tenor1 == normalised_tenor2:
            return GIRR_INFLATION_SAME_TENOR_CORRELATION, citation_ids
        return GIRR_INFLATION_DIFFERENT_TENOR_CORRELATION, citation_ids

    maturity1 = girr_tenor_definition(profile, normalised_tenor1).maturity_years
    maturity2 = girr_tenor_definition(profile, normalised_tenor2).maturity_years
    tenor_correlation = _exponential_tenor_correlation(
        maturity1,
        maturity2,
        constant=GIRR_DELTA_INTRA_BUCKET_CONSTANT,
        floor=GIRR_INTRA_BUCKET_CORRELATION_FLOOR,
    )
    curve_correlation = (
        GIRR_SAME_CURVE_CORRELATION if same_curve else GIRR_DIFFERENT_CURVE_CORRELATION
    )
    return curve_correlation * tenor_correlation, citation_ids


def girr_inter_bucket_correlation(
    profile: SbmRegulatoryProfile | str,
    *,
    bucket1: str,
    bucket2: str,
) -> tuple[float, tuple[str, ...]]:
    """Return the cited GIRR inter-bucket correlation and citation ids.
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

    _ensure_girr_delta_supported(profile)
    resolved = _resolve_supported_profile(profile)
    normalised_bucket1 = _require_text(bucket1, "bucket1")
    normalised_bucket2 = _require_text(bucket2, "bucket2")
    girr_bucket_definition(profile, normalised_bucket1)
    girr_bucket_definition(profile, normalised_bucket2)
    citation_ids = (PROFILE_GIRR_DELTA_INTER_BUCKET_CITATION_IDS[resolved],)
    if normalised_bucket1 == normalised_bucket2:
        return GIRR_SAME_CURVE_CORRELATION, citation_ids
    return GIRR_INTER_BUCKET_CORRELATION, citation_ids


def _exponential_tenor_correlation(
    tenor1_years: float,
    tenor2_years: float,
    *,
    constant: float,
    floor: float | None,
) -> float:
    if tenor1_years <= 0.0 or tenor2_years <= 0.0:
        return GIRR_SAME_CURVE_CORRELATION
    minimum_tenor = min(tenor1_years, tenor2_years)
    exponent = -constant * abs(tenor1_years - tenor2_years) / minimum_tenor
    correlation = math.exp(exponent)
    if floor is None:
        return correlation
    return max(correlation, floor)


__all__ = [
    "girr_delta_intra_bucket_correlation",
    "girr_inter_bucket_correlation",
]
