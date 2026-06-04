"""
CVA regulatory profile selection and hashing.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from frtb_common import UnsupportedRegulatoryFeatureError

from frtb_cva._payloads import hash_payload as _hash_payload
from frtb_cva.data_models import CvaMethod, CvaRegulatoryProfile, SaCvaRiskClass
from frtb_cva.reference_data import citations_for_profile, profile_reference_payload
from frtb_cva.validation import CvaInputError


@dataclass(frozen=True)
class CvaRuleProfile:
    """Immutable profile metadata and support declaration."""

    profile: CvaRegulatoryProfile
    regulator: str
    version: str
    publication_date: date
    status: str
    supported_methods: frozenset[CvaMethod]
    supported_sa_cva_risk_classes: frozenset[SaCvaRiskClass]
    citation_ids: tuple[str, ...]
    content_hash: str
    effective_date: date | None = None


SUPPORTED_PROFILE_METADATA: dict[CvaRegulatoryProfile, dict[str, object]] = {
    CvaRegulatoryProfile.BASEL_MAR50_2020: {
        "regulator": "Basel Committee on Banking Supervision",
        "version": "Basel Framework MAR50 (July 2020 calibration)",
        "publication_date": date(2020, 7, 8),
        "status": "supported_ba_cva_reduced_and_sa_cva_risk_classes",
        "effective_date": None,
    },
}

UNSUPPORTED_PROFILE_REASONS: dict[CvaRegulatoryProfile, str] = {
    CvaRegulatoryProfile.US_NPR20_VB: (
        "CVA profile US_NPR20_VB is unsupported until U.S. NPR 2.0 proposed section mapping "
        "and fixtures are added."
    ),
    CvaRegulatoryProfile.EU_CRR3_CVA: (
        "CVA profile EU_CRR3_CVA is unsupported until Articles 382-386 mapping "
        "and fixtures are added."
    ),
    CvaRegulatoryProfile.UK_PRA_CVA: (
        "CVA profile UK_PRA_CVA is unsupported until UK-specific source mapping "
        "and fixtures are added."
    ),
}

_BASEL_SUPPORTED_METHODS = frozenset(CvaMethod)
_BASEL_SUPPORTED_SA_CVA_RISK_CLASSES = frozenset(SaCvaRiskClass)


def get_cva_rule_profile(profile: CvaRegulatoryProfile | str) -> CvaRuleProfile:
    """Return supported CVA profile metadata or fail closed."""

    resolved = resolve_cva_profile(profile)
    metadata = SUPPORTED_PROFILE_METADATA[resolved]
    citation_ids = tuple(sorted(citations_for_profile(resolved)))
    payload = {
        "metadata": {
            key: value.isoformat() if isinstance(value, date) else value
            for key, value in sorted(metadata.items())
        },
        "reference_data": profile_reference_payload(resolved),
    }
    return CvaRuleProfile(
        profile=resolved,
        regulator=str(metadata["regulator"]),
        version=str(metadata["version"]),
        publication_date=_metadata_date(metadata["publication_date"], "publication_date"),
        effective_date=_metadata_optional_date(metadata["effective_date"], "effective_date"),
        status=str(metadata["status"]),
        supported_methods=_BASEL_SUPPORTED_METHODS,
        supported_sa_cva_risk_classes=_BASEL_SUPPORTED_SA_CVA_RISK_CLASSES,
        citation_ids=citation_ids,
        content_hash=_hash_payload(payload),
    )


def resolve_cva_profile(profile: CvaRegulatoryProfile | str) -> CvaRegulatoryProfile:
    """Normalise and reject unsupported CVA profiles."""

    try:
        resolved = CvaRegulatoryProfile(profile)
    except ValueError as exc:
        raise CvaInputError(
            f"unknown CVA regulatory profile: {profile!r}",
            field="profile",
        ) from exc

    if resolved in UNSUPPORTED_PROFILE_REASONS:
        raise UnsupportedRegulatoryFeatureError(UNSUPPORTED_PROFILE_REASONS[resolved])
    if resolved not in SUPPORTED_PROFILE_METADATA:
        raise UnsupportedRegulatoryFeatureError(
            f"CVA profile {resolved.value} has no supported metadata."
        )
    return resolved


def profile_content_hash(profile: CvaRegulatoryProfile | str) -> str:
    """Return the deterministic content hash for a supported profile."""

    return get_cva_rule_profile(profile).content_hash


def _metadata_date(value: object, field: str) -> date:
    if not isinstance(value, date):
        raise CvaInputError(f"profile metadata {field} must be a date", field=field)
    return value


def _metadata_optional_date(value: object, field: str) -> date | None:
    if value is None:
        return None
    return _metadata_date(value, field)


__all__ = [
    "SUPPORTED_PROFILE_METADATA",
    "UNSUPPORTED_PROFILE_REASONS",
    "CvaRuleProfile",
    "get_cva_rule_profile",
    "profile_content_hash",
    "resolve_cva_profile",
]
