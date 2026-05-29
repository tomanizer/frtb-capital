"""
SBM regulatory profile selection and hashing.

Regulatory traceability:
    See docs/REGULATORY_TRACEABILITY.md rows for regimes.py, Basel MAR21,
    U.S. NPR 2.0 section V.A.7.a, and SBM-FUNC-005.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from datetime import date

from frtb_common import UnsupportedRegulatoryFeatureError

from frtb_sbm.data_models import (
    SbmRegulatoryProfile,
    SbmRiskClass,
    SbmRiskMeasure,
    SbmRuleProfile,
)
from frtb_sbm.reference_data import citations_for_profile, profile_reference_payload
from frtb_sbm.validation import SbmInputError

SUPPORTED_PROFILE_METADATA: dict[SbmRegulatoryProfile, dict[str, object]] = {
    SbmRegulatoryProfile.BASEL_MAR21: {
        "regulator": "Basel Committee on Banking Supervision",
        "version": "Basel Framework MAR21",
        "publication_date": date(2019, 1, 14),
        "status": "supported_canonical_girr_delta_slice",
        "effective_date": None,
    },
}

UNSUPPORTED_PROFILE_REASONS: dict[SbmRegulatoryProfile, str] = {
    SbmRegulatoryProfile.US_NPR_2_0: (
        "U.S. NPR 2.0 SBM profile is unsupported until cited reference data and fixtures are added."
    ),
    SbmRegulatoryProfile.EU_CRR3: (
        "EU CRR3 SBM profile is unsupported until cited reference data and fixtures are added."
    ),
    SbmRegulatoryProfile.PRA_UK_CRR: (
        "PRA UK CRR SBM profile is unsupported until UK-specific source mapping "
        "and fixtures are added."
    ),
}

PROFILE_SUPPORTED_MEASURES: dict[
    SbmRegulatoryProfile, dict[SbmRiskClass, frozenset[SbmRiskMeasure]]
] = {
    SbmRegulatoryProfile.BASEL_MAR21: {
        SbmRiskClass.GIRR: frozenset({SbmRiskMeasure.DELTA}),
    },
}


def get_sbm_rule_profile(profile: SbmRegulatoryProfile | str) -> SbmRuleProfile:
    """Return supported SBM profile metadata or fail closed."""

    resolved = resolve_sbm_profile(profile)
    metadata = SUPPORTED_PROFILE_METADATA[resolved]
    supported_measures = PROFILE_SUPPORTED_MEASURES[resolved]
    citations = citations_for_profile(resolved)
    payload = {
        "metadata": {
            key: value.isoformat() if isinstance(value, date) else value
            for key, value in sorted(metadata.items())
        },
        "supported_measures": {
            risk_class.value: sorted(measure.value for measure in measures)
            for risk_class, measures in sorted(
                supported_measures.items(),
                key=lambda item: item[0].value,
            )
        },
        "reference_data": profile_reference_payload(resolved),
    }
    return SbmRuleProfile(
        profile_id=resolved.value,
        regulator=str(metadata["regulator"]),
        version=str(metadata["version"]),
        publication_date=_metadata_date(metadata["publication_date"], "publication_date"),
        effective_date=_metadata_optional_date(metadata["effective_date"], "effective_date"),
        supported_risk_classes=frozenset(supported_measures),
        supported_measures=supported_measures,
        citations=citations,
        content_hash=_hash_payload(payload),
    )


def resolve_sbm_profile(profile: SbmRegulatoryProfile | str) -> SbmRegulatoryProfile:
    """Normalise and reject unsupported SBM profiles."""

    try:
        resolved = SbmRegulatoryProfile(profile)
    except ValueError as exc:
        raise SbmInputError(
            f"unknown SBM regulatory profile: {profile!r}",
            field="profile_id",
        ) from exc

    if resolved in UNSUPPORTED_PROFILE_REASONS:
        raise UnsupportedRegulatoryFeatureError(UNSUPPORTED_PROFILE_REASONS[resolved])
    if resolved not in SUPPORTED_PROFILE_METADATA:
        raise UnsupportedRegulatoryFeatureError(
            f"SBM profile {resolved.value} has no supported metadata."
        )
    return resolved


def profile_content_hash(profile: SbmRegulatoryProfile | str) -> str:
    """Return the deterministic content hash for a supported profile."""

    return get_sbm_rule_profile(profile).content_hash


def profile_supports_risk_class_measure(
    profile: SbmRegulatoryProfile | str,
    risk_class: SbmRiskClass | str,
    risk_measure: SbmRiskMeasure | str,
) -> bool:
    """Return whether the profile supports a risk-class and measure path."""

    resolved = resolve_sbm_profile(profile)
    resolved_risk_class = _coerce_risk_class(risk_class)
    resolved_measure = _coerce_risk_measure(risk_measure)
    supported_measures = PROFILE_SUPPORTED_MEASURES.get(resolved, {})
    return resolved_measure in supported_measures.get(resolved_risk_class, frozenset())


def ensure_profile_supports_risk_class_measure(
    profile: SbmRegulatoryProfile | str,
    risk_class: SbmRiskClass | str,
    risk_measure: SbmRiskMeasure | str,
) -> None:
    """Raise when a profile/risk-class/measure path is unsupported."""

    resolved = resolve_sbm_profile(profile)
    resolved_risk_class = _coerce_risk_class(risk_class)
    resolved_measure = _coerce_risk_measure(risk_measure)
    if profile_supports_risk_class_measure(resolved, resolved_risk_class, resolved_measure):
        return
    raise UnsupportedRegulatoryFeatureError(
        "frtb-sbm does not support "
        f"profile={resolved.value}, risk_class={resolved_risk_class.value}, "
        f"risk_measure={resolved_measure.value}"
    )


def supported_risk_class_measures(
    profile: SbmRegulatoryProfile | str,
) -> frozenset[tuple[SbmRiskClass, SbmRiskMeasure]]:
    """Return the supported risk-class and measure pairs for a profile."""

    resolved = resolve_sbm_profile(profile)
    supported: set[tuple[SbmRiskClass, SbmRiskMeasure]] = set()
    for risk_class, measures in PROFILE_SUPPORTED_MEASURES[resolved].items():
        supported.update((risk_class, measure) for measure in measures)
    return frozenset(supported)


def _hash_payload(payload: Mapping[str, object]) -> str:
    encoded = bytes(json.dumps(payload, sort_keys=True, separators=(",", ":")), "utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _metadata_date(value: object, field: str) -> date:
    if not isinstance(value, date):
        raise SbmInputError(f"profile metadata {field} must be a date", field=field)
    return value


def _metadata_optional_date(value: object, field: str) -> date | None:
    if value is None:
        return None
    return _metadata_date(value, field)


def _coerce_risk_class(value: SbmRiskClass | str) -> SbmRiskClass:
    if isinstance(value, SbmRiskClass):
        return value
    try:
        return SbmRiskClass(value)
    except ValueError as exc:
        allowed = ", ".join(item.value for item in SbmRiskClass)
        raise SbmInputError(
            f"risk_class must be one of: {allowed}",
            field="risk_class",
        ) from exc


def _coerce_risk_measure(value: SbmRiskMeasure | str) -> SbmRiskMeasure:
    if isinstance(value, SbmRiskMeasure):
        return value
    try:
        return SbmRiskMeasure(value)
    except ValueError as exc:
        allowed = ", ".join(item.value for item in SbmRiskMeasure)
        raise SbmInputError(
            f"risk_measure must be one of: {allowed}",
            field="risk_measure",
        ) from exc


__all__ = [
    "PROFILE_SUPPORTED_MEASURES",
    "SUPPORTED_PROFILE_METADATA",
    "UNSUPPORTED_PROFILE_REASONS",
    "ensure_profile_supports_risk_class_measure",
    "get_sbm_rule_profile",
    "profile_content_hash",
    "profile_supports_risk_class_measure",
    "resolve_sbm_profile",
    "supported_risk_class_measures",
]
