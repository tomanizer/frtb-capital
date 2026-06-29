"""Profile-aware Basel vs comparison-profile citation routing for SBM reference data."""

from __future__ import annotations

from collections.abc import Mapping

from frtb_common import UnsupportedRegulatoryFeatureError

from frtb_sbm.comparison_profile_support import COMPARISON_PROFILE_CITATION_MAPS
from frtb_sbm.data_models import SbmRegulatoryProfile
from frtb_sbm.reference_profiles import _resolve_supported_profile
from frtb_sbm.us_npr_citation_map import (
    BASEL_TO_US_NPR_CITATION_IDS as _BASEL_TO_US_NPR_CITATION_IDS,
)

_CURVATURE_REQUIRED_BASEL_IDS: tuple[str, ...] = (
    "basel_mar21_curvature",
    "basel_mar21_96",
    "basel_mar21_97",
    "basel_mar21_98",
    "basel_mar21_99",
    "basel_mar21_100",
    "basel_mar21_101",
)

_SCENARIO_CITATION_BASEL_IDS: tuple[str, ...] = (
    "basel_mar21_6_correlation_scenarios",
    "basel_mar21_7_scenario_selection",
)


def profile_citation_id(profile: SbmRegulatoryProfile | str, basel_citation_id: str) -> str:
    """Return the profile-owned citation id for a Basel comparison anchor.

    Parameters
    ----------
    profile : SbmRegulatoryProfile | str
        Active SBM regulatory profile.
    basel_citation_id : str
        Basel citation id used as the comparison-profile routing anchor.

    Returns
    -------
    str
        Citation id owned by the active profile.
    """

    resolved = _resolve_supported_profile(profile)
    if resolved is SbmRegulatoryProfile.BASEL_MAR21:
        return basel_citation_id
    if resolved in COMPARISON_PROFILE_CITATION_MAPS:
        citation_map = COMPARISON_PROFILE_CITATION_MAPS[resolved]
        try:
            return citation_map[basel_citation_id]
        except KeyError as exc:
            raise UnsupportedRegulatoryFeatureError(
                f"{resolved.value} citation routing is undefined for "
                f"basel_citation_id={basel_citation_id}"
            ) from exc
    raise UnsupportedRegulatoryFeatureError(
        f"profile citation routing is unsupported for profile={resolved.value}"
    )


def profile_citation_ids(
    profile: SbmRegulatoryProfile | str,
    basel_citation_ids: tuple[str, ...],
) -> tuple[str, ...]:
    """Map a tuple of Basel citation ids to the active profile.

    Parameters
    ----------
    profile : SbmRegulatoryProfile | str
        Active SBM regulatory profile.
    basel_citation_ids : tuple[str, ...]
        Basel citation ids used as comparison-profile routing anchors.

    Returns
    -------
    tuple[str, ...]
        Citation ids owned by the active profile.
    """

    return tuple(profile_citation_id(profile, citation_id) for citation_id in basel_citation_ids)


def profile_scenario_citation_ids(profile: SbmRegulatoryProfile | str) -> tuple[str, ...]:
    """Return correlation-scenario citation ids for aggregation paths.

    Parameters
    ----------
    profile : SbmRegulatoryProfile | str
        Active SBM regulatory profile.

    Returns
    -------
    tuple[str, ...]
        Profile-owned correlation-scenario and scenario-selection citation ids.
    """

    return profile_citation_ids(profile, _SCENARIO_CITATION_BASEL_IDS)


def profile_curvature_required_citation_ids(
    profile: SbmRegulatoryProfile | str,
) -> tuple[str, ...]:
    """Return ordered curvature contract citation ids for a profile.

    Parameters
    ----------
    profile : SbmRegulatoryProfile | str
        Active SBM regulatory profile.

    Returns
    -------
    tuple[str, ...]
        Profile-owned curvature contract citation ids.
    """

    return profile_citation_ids(profile, _CURVATURE_REQUIRED_BASEL_IDS)


def ensure_profile_in_reference_map(
    profile: SbmRegulatoryProfile | str,
    reference_map: Mapping[SbmRegulatoryProfile, object],
    *,
    feature_label: str,
) -> SbmRegulatoryProfile:
    """Fail closed when a profile has no cited reference-data tables.

    Parameters
    ----------
    profile : SbmRegulatoryProfile | str
        Active SBM regulatory profile.
    reference_map : Mapping[SbmRegulatoryProfile, object]
        Profile-keyed reference-data table or parameter map.
    feature_label : str
        Human-readable feature name for unsupported-feature errors.

    Returns
    -------
    SbmRegulatoryProfile
        Resolved profile when reference data exists.
    """

    resolved = _resolve_supported_profile(profile)
    if resolved not in reference_map:
        raise UnsupportedRegulatoryFeatureError(
            f"{feature_label} reference data is unsupported for profile {resolved.value}"
        )
    return resolved


__all__ = [
    "BASEL_TO_US_NPR_CITATION_IDS",
    "ensure_profile_in_reference_map",
    "profile_citation_id",
    "profile_citation_ids",
    "profile_curvature_required_citation_ids",
    "profile_scenario_citation_ids",
]

BASEL_TO_US_NPR_CITATION_IDS = _BASEL_TO_US_NPR_CITATION_IDS
