"""CVA regulatory profile helpers and reference payload assembly."""

from __future__ import annotations

from frtb_common import UnsupportedRegulatoryFeatureError

from frtb_cva._profile_citations import PROFILE_CITATION_ID_MAP
from frtb_cva._reference_citations import (
    BASEL_MAR50_CITATIONS,
    BASEL_PROFILE_CITATIONS,
    PROFILE_CITATIONS,
)
from frtb_cva.data_models import CreditQuality, CvaCitation, CvaRegulatoryProfile, CvaSector
from frtb_cva.validation import CvaInputError


def profile_citation_id(
    citation_id: str,
    profile: CvaRegulatoryProfile | str,
) -> str:
    """Return the active profile's citation id for a Basel-aligned rule cell.

    Parameters
    ----------
    citation_id :
        Basel-aligned citation cell key mapped through the active profile.

    profile :
        Optional ``CvaRegulatoryProfile`` or profile label; default Basel MAR50 (2020).

    Returns
    -------
    str
        Active profile citation id mapped from the Basel-aligned cell key."""

    resolved = _resolve_supported_profile(profile)
    if citation_id in PROFILE_CITATIONS[resolved]:
        return citation_id
    if resolved is CvaRegulatoryProfile.BASEL_MAR50_2020:
        return citation_id
    citation_map = PROFILE_CITATION_ID_MAP.get(resolved)
    if citation_map is None:
        raise UnsupportedRegulatoryFeatureError(
            f"CVA profile {resolved.value} has no citation map defined."
        )
    try:
        return citation_map[citation_id]
    except KeyError as exc:
        raise UnsupportedRegulatoryFeatureError(
            f"CVA citation {citation_id!r} is unmapped for profile {resolved.value}."
        ) from exc


def profile_citation_ids(
    citation_ids: tuple[str, ...],
    profile: CvaRegulatoryProfile | str,
) -> tuple[str, ...]:
    """Map citation ids to the active profile and preserve first-seen order.

    Parameters
    ----------
    citation_ids :
        Basel-aligned citation cell keys mapped in first-seen order.

    profile :
        Optional ``CvaRegulatoryProfile`` or profile label; default Basel MAR50 (2020).

    Returns
    -------
    tuple[str, ...]
        Profile-mapped citation ids preserving first-seen order."""

    mapped: list[str] = []
    seen: set[str] = set()
    for citation_id in citation_ids:
        active_id = profile_citation_id(citation_id, profile)
        if active_id not in seen:
            mapped.append(active_id)
            seen.add(active_id)
    return tuple(mapped)


def citations_for_profile(
    profile: CvaRegulatoryProfile | str,
) -> dict[str, CvaCitation]:
    """Return citations for a supported CVA profile.

    Parameters
    ----------
    profile :
        Optional ``CvaRegulatoryProfile`` or profile label; default Basel MAR50 (2020).

    Returns
    -------
    dict[str, CvaCitation]
        Citation registry for the resolved supported profile."""

    resolved = _resolve_supported_profile(profile)
    return dict(PROFILE_CITATIONS[resolved])


def profile_reference_payload(profile: CvaRegulatoryProfile | str) -> dict[str, object]:
    """Return a deterministic, JSON-serialisable payload for profile hashing.

    Parameters
    ----------
    profile :
        Optional ``CvaRegulatoryProfile`` or profile label; default Basel MAR50 (2020).

    Returns
    -------
    dict[str, object]
        Result of ``profile_reference_payload`` for audit replay."""

    resolved = _resolve_supported_profile(profile)
    from frtb_cva._ba_reference_data import _ba_cva_reference_payload
    from frtb_cva._girr_reference_data import _girr_delta_reference_payload
    from frtb_cva.sa_cva_reference_data import sa_cva_reference_payload

    return {
        "profile": resolved.value,
        "citations": _citation_reference_payload(resolved),
        "ba_cva": _ba_cva_reference_payload(resolved),
        "sa_cva_girr_delta": _girr_delta_reference_payload(resolved),
        "sa_cva_reference_tables": sa_cva_reference_payload(resolved),
    }


def _citation_reference_payload(profile: CvaRegulatoryProfile) -> dict[str, object]:
    citations = citations_for_profile(profile)
    return {
        citation_id: {
            "source_id": citation.source_id,
            "paragraph": citation.paragraph,
            "url": citation.url,
            "note": citation.note,
        }
        for citation_id, citation in sorted(citations.items())
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
    "BASEL_MAR50_CITATIONS",
    "BASEL_PROFILE_CITATIONS",
    "PROFILE_CITATIONS",
    "citations_for_profile",
    "profile_citation_id",
    "profile_citation_ids",
    "profile_reference_payload",
]
