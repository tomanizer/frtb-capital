"""
SBM regulatory profile selection and hashing.

Regulatory traceability:
    See docs/REGULATORY_TRACEABILITY.md rows for regimes.py, Basel MAR21,
    U.S. NPR 2.0 section V.A.7.a, and SBM-FUNC-005.
"""

from __future__ import annotations

from datetime import date

from frtb_common import UnsupportedRegulatoryFeatureError

from frtb_sbm.assembly.hashes import profile_content_hash_from_parts
from frtb_sbm.data_models import (
    SbmRegulatoryProfile,
    SbmRiskClass,
    SbmRiskMeasure,
    SbmRuleProfile,
)
from frtb_sbm.reference_data import citations_for_profile
from frtb_sbm.validation import SbmInputError

SUPPORTED_PROFILE_METADATA: dict[SbmRegulatoryProfile, dict[str, object]] = {
    SbmRegulatoryProfile.BASEL_MAR21: {
        "regulator": "Basel Committee on Banking Supervision",
        "version": "Basel Framework MAR21",
        "publication_date": date(2019, 1, 14),
        "status": "supported_canonical_girr_fx_equity_commodity_csr_delta_curvature_slice",
        "effective_date": None,
    },
    SbmRegulatoryProfile.US_NPR_2_0: (
        {
            "regulator": (
                "Office of the Comptroller of the Currency, Board of Governors of the "
                "Federal Reserve System, and Federal Deposit Insurance Corporation"
            ),
            "version": "Federal Register 91 FR 14952 proposed market-risk rule",
            "publication_date": date(2026, 3, 27),
            "status": "supported_us_npr_girr_delta_comparison_slice",
            "effective_date": None,
        }
    ),
    SbmRegulatoryProfile.EU_CRR3: {
        "regulator": "European Parliament and Council of the European Union",
        "version": "Regulation (EU) 2024/1623 CRR3 market-risk amendments",
        "publication_date": date(2024, 6, 19),
        "status": "supported_eu_crr3_sbm_comparison_slice",
        "effective_date": None,
    },
    SbmRegulatoryProfile.PRA_UK_CRR: (
        {
            "regulator": "Prudential Regulation Authority",
            "version": (
                "PRA PS1/26 Appendix 1 / PRA2026/1 Market Risk: Advanced "
                "Standardised Approach (CRR) Part"
            ),
            "publication_date": date(2026, 1, 20),
            "status": "supported_pra_uk_crr_girr_delta_comparison_slice",
            "effective_date": date(2027, 1, 1),
        }
    ),
}

UNSUPPORTED_PROFILE_REASONS: dict[SbmRegulatoryProfile, str] = {}

PROFILE_SUPPORTED_MEASURES: dict[
    SbmRegulatoryProfile, dict[SbmRiskClass, frozenset[SbmRiskMeasure]]
] = {
    SbmRegulatoryProfile.BASEL_MAR21: {
        SbmRiskClass.GIRR: frozenset(
            {SbmRiskMeasure.DELTA, SbmRiskMeasure.VEGA, SbmRiskMeasure.CURVATURE}
        ),
        SbmRiskClass.FX: frozenset(
            {SbmRiskMeasure.DELTA, SbmRiskMeasure.VEGA, SbmRiskMeasure.CURVATURE}
        ),
        SbmRiskClass.EQUITY: frozenset(
            {SbmRiskMeasure.DELTA, SbmRiskMeasure.VEGA, SbmRiskMeasure.CURVATURE}
        ),
        SbmRiskClass.COMMODITY: frozenset(
            {SbmRiskMeasure.DELTA, SbmRiskMeasure.VEGA, SbmRiskMeasure.CURVATURE}
        ),
        SbmRiskClass.CSR_NONSEC: frozenset(
            {SbmRiskMeasure.DELTA, SbmRiskMeasure.VEGA, SbmRiskMeasure.CURVATURE}
        ),
        SbmRiskClass.CSR_SEC_NONCTP: frozenset(
            {SbmRiskMeasure.DELTA, SbmRiskMeasure.VEGA, SbmRiskMeasure.CURVATURE}
        ),
        SbmRiskClass.CSR_SEC_CTP: frozenset(
            {SbmRiskMeasure.DELTA, SbmRiskMeasure.VEGA, SbmRiskMeasure.CURVATURE}
        ),
    },
    SbmRegulatoryProfile.US_NPR_2_0: {
        SbmRiskClass.GIRR: frozenset({SbmRiskMeasure.DELTA}),
    },
    SbmRegulatoryProfile.EU_CRR3: {
        SbmRiskClass.GIRR: frozenset(
            {SbmRiskMeasure.DELTA, SbmRiskMeasure.VEGA, SbmRiskMeasure.CURVATURE}
        ),
        SbmRiskClass.FX: frozenset(
            {SbmRiskMeasure.DELTA, SbmRiskMeasure.VEGA, SbmRiskMeasure.CURVATURE}
        ),
        SbmRiskClass.EQUITY: frozenset({SbmRiskMeasure.DELTA}),
        SbmRiskClass.COMMODITY: frozenset({SbmRiskMeasure.DELTA}),
    },
    SbmRegulatoryProfile.PRA_UK_CRR: {
        SbmRiskClass.GIRR: frozenset({SbmRiskMeasure.DELTA}),
    },
}


def get_sbm_rule_profile(profile: SbmRegulatoryProfile | str) -> SbmRuleProfile:
    """Return supported SBM profile metadata or fail closed.
    Parameters
    ----------
    profile : SbmRegulatoryProfile | str
        See signature.

    Returns
    -------
    SbmRuleProfile
    """

    resolved = resolve_sbm_profile(profile)
    metadata = SUPPORTED_PROFILE_METADATA[resolved]
    supported_measures = PROFILE_SUPPORTED_MEASURES[resolved]
    citations = citations_for_profile(resolved)
    return SbmRuleProfile(
        profile_id=resolved.value,
        regulator=str(metadata["regulator"]),
        version=str(metadata["version"]),
        publication_date=_metadata_date(metadata["publication_date"], "publication_date"),
        effective_date=_metadata_optional_date(metadata["effective_date"], "effective_date"),
        supported_risk_classes=frozenset(supported_measures),
        supported_measures=supported_measures,
        citations=citations,
        content_hash=profile_content_hash_from_parts(
            profile=resolved,
            metadata=metadata,
            supported_measures=supported_measures,
        ),
    )


def resolve_sbm_profile(profile: SbmRegulatoryProfile | str) -> SbmRegulatoryProfile:
    """Normalise and reject unsupported SBM profiles.
    Parameters
    ----------
    profile : SbmRegulatoryProfile | str
        See signature.

    Returns
    -------
    SbmRegulatoryProfile
    """

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
    """Return the deterministic content hash for a supported profile.
    Parameters
    ----------
    profile : SbmRegulatoryProfile | str
        See signature.

    Returns
    -------
    str
    """

    return get_sbm_rule_profile(profile).content_hash


def profile_supports_risk_class_measure(
    profile: SbmRegulatoryProfile | str,
    risk_class: SbmRiskClass | str,
    risk_measure: SbmRiskMeasure | str,
) -> bool:
    """Return whether the profile supports a risk-class and measure path.
    Parameters
    ----------
    profile : SbmRegulatoryProfile | str
        See signature.
    risk_class : SbmRiskClass | str
        See signature.
    risk_measure : SbmRiskMeasure | str
        See signature.

    Returns
    -------
    bool
    """

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
    """Raise when a profile/risk-class/measure path is unsupported.
    Parameters
    ----------
    profile : SbmRegulatoryProfile | str
        See signature.
    risk_class : SbmRiskClass | str
        See signature.
    risk_measure : SbmRiskMeasure | str
        See signature.
    """

    from frtb_sbm.validation import ensure_sbm_risk_class_measure_supported

    resolved = resolve_sbm_profile(profile)
    ensure_sbm_risk_class_measure_supported(
        resolved.value,
        risk_class,
        risk_measure,
    )


def supported_risk_class_measures(
    profile: SbmRegulatoryProfile | str,
) -> frozenset[tuple[SbmRiskClass, SbmRiskMeasure]]:
    """Return the supported risk-class and measure pairs for a profile.
    Parameters
    ----------
    profile : SbmRegulatoryProfile | str
        See signature.

    Returns
    -------
    frozenset[tuple[SbmRiskClass, SbmRiskMeasure]]
    """

    resolved = resolve_sbm_profile(profile)
    supported: set[tuple[SbmRiskClass, SbmRiskMeasure]] = set()
    for risk_class, measures in PROFILE_SUPPORTED_MEASURES[resolved].items():
        supported.update((risk_class, measure) for measure in measures)
    return frozenset(supported)


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
