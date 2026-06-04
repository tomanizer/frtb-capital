"""
RRAO regulatory profile selection and hashing.

Regulatory traceability:
    See docs/REGULATORY_TRACEABILITY.md rows for regimes.py, Basel MAR23, U.S.
    NPR 2.0 proposed section __.211, EU Article 325u, and UK CRR Article 325u
    profile handling.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from frtb_common import UnsupportedRegulatoryFeatureError

from frtb_rrao._payloads import hash_payload
from frtb_rrao.data_models import (
    RraoClassification,
    RraoEvidenceType,
    RraoExclusionReason,
    RraoRegulatoryProfile,
)
from frtb_rrao.reference_data import (
    citations_for_profile,
    evidence_rules_for_profile,
    exclusion_rules_for_profile,
    profile_reference_payload,
)
from frtb_rrao.validation import RraoInputError


@dataclass(frozen=True)
class RraoRuleProfile:
    """Immutable profile metadata and support declaration."""

    profile: RraoRegulatoryProfile
    regulator: str
    version: str
    publication_date: date
    status: str
    supported_classifications: frozenset[RraoClassification]
    supported_evidence_types: frozenset[RraoEvidenceType]
    supported_exclusions: frozenset[RraoExclusionReason]
    citation_ids: tuple[str, ...]
    content_hash: str
    effective_date: date | None = None


SUPPORTED_PROFILE_METADATA: dict[RraoRegulatoryProfile, dict[str, object]] = {
    RraoRegulatoryProfile.BASEL_MAR23: {
        "regulator": "Basel Committee on Banking Supervision",
        "version": "Basel Framework MAR23",
        "publication_date": date(2019, 1, 14),
        "status": "supported_canonical_input_slice",
        "effective_date": None,
    },
    RraoRegulatoryProfile.US_NPR_2_0: {
        "regulator": "U.S. banking agencies",
        "version": "91 FR 14952 proposed section __.211",
        "publication_date": date(2026, 3, 27),
        "status": "supported_proposed_rule_canonical_input_slice",
        "effective_date": None,
    },
    RraoRegulatoryProfile.EU_CRR3: {
        "regulator": "European Union",
        "version": "Article 325u and Delegated Regulation (EU) 2022/2328",
        "publication_date": date(2022, 11, 29),
        "status": "supported_comparison_canonical_input_slice",
        "effective_date": date(2022, 12, 19),
    },
    RraoRegulatoryProfile.PRA_UK_CRR: {
        "regulator": "PRA / UK CRR",
        "version": "UK CRR Article 325u and UK retained DR (EU) 2022/2328",
        "publication_date": date(2026, 1, 20),
        "status": "supported_uk_canonical_input_slice",
        "effective_date": date(2027, 1, 1),
    },
}

UNSUPPORTED_PROFILE_REASONS: dict[RraoRegulatoryProfile, str] = {}


def get_rrao_rule_profile(profile: RraoRegulatoryProfile | str) -> RraoRuleProfile:
    """Return supported RRAO profile metadata or fail closed.
    Parameters
    ----------
    profile : RraoRegulatoryProfile | str
        Profile.

    Returns
    -------
    RraoRuleProfile
        Result of the operation.
    """

    resolved = resolve_rrao_profile(profile)
    metadata = SUPPORTED_PROFILE_METADATA[resolved]
    evidence_rules = evidence_rules_for_profile(resolved)
    exclusion_rules = exclusion_rules_for_profile(resolved)
    citation_ids = tuple(sorted(citations_for_profile(resolved)))
    payload = {
        "metadata": {
            key: value.isoformat() if isinstance(value, date) else value
            for key, value in sorted(metadata.items())
        },
        "reference_data": profile_reference_payload(resolved),
    }
    return RraoRuleProfile(
        profile=resolved,
        regulator=str(metadata["regulator"]),
        version=str(metadata["version"]),
        publication_date=_metadata_date(metadata["publication_date"], "publication_date"),
        effective_date=_metadata_optional_date(metadata["effective_date"], "effective_date"),
        status=str(metadata["status"]),
        supported_classifications=frozenset(rule.classification for rule in evidence_rules)
        | frozenset({RraoClassification.EXCLUDED}),
        supported_evidence_types=frozenset(rule.evidence_type for rule in evidence_rules),
        supported_exclusions=frozenset(rule.exclusion_reason for rule in exclusion_rules),
        citation_ids=citation_ids,
        content_hash=hash_payload(payload),
    )


def resolve_rrao_profile(profile: RraoRegulatoryProfile | str) -> RraoRegulatoryProfile:
    """Normalise and reject unsupported RRAO profiles.
    Parameters
    ----------
    profile : RraoRegulatoryProfile | str
        Profile.

    Returns
    -------
    RraoRegulatoryProfile
        Result of the operation.
    """

    try:
        resolved = RraoRegulatoryProfile(profile)
    except ValueError as exc:
        raise RraoInputError(
            f"unknown RRAO regulatory profile: {profile!r}", field="profile"
        ) from exc

    if resolved in UNSUPPORTED_PROFILE_REASONS:
        raise UnsupportedRegulatoryFeatureError(UNSUPPORTED_PROFILE_REASONS[resolved])
    if resolved not in SUPPORTED_PROFILE_METADATA:
        raise UnsupportedRegulatoryFeatureError(
            f"RRAO profile {resolved.value} has no supported metadata."
        )
    return resolved


def profile_content_hash(profile: RraoRegulatoryProfile | str) -> str:
    """Return the deterministic content hash for a supported profile.
    Parameters
    ----------
    profile : RraoRegulatoryProfile | str
        Profile.

    Returns
    -------
    str
        Result of the operation.
    """

    return get_rrao_rule_profile(profile).content_hash


def _metadata_date(value: object, field: str) -> date:
    if not isinstance(value, date):
        raise RraoInputError(f"profile metadata {field} must be a date", field=field)
    return value


def _metadata_optional_date(value: object, field: str) -> date | None:
    if value is None:
        return None
    return _metadata_date(value, field)


__all__ = [
    "SUPPORTED_PROFILE_METADATA",
    "UNSUPPORTED_PROFILE_REASONS",
    "RraoRuleProfile",
    "get_rrao_rule_profile",
    "profile_content_hash",
    "resolve_rrao_profile",
]
