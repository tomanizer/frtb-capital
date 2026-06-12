"""Compatibility exports for RRAO reference-data lookups.

RRAO citations and profile rule tables are split into package-private
reference modules by family. This module preserves the public lookup import
path and deterministic profile payload assembly.
"""

from __future__ import annotations

from frtb_common import UnsupportedRegulatoryFeatureError

from frtb_rrao._reference_citations import (
    PROFILE_CITATIONS,
)
from frtb_rrao._reference_evidence_rules import (
    PROFILE_EVIDENCE_RULES,
    PROFILE_INVESTMENT_FUND_RULES,
)
from frtb_rrao._reference_exclusion_rules import PROFILE_EXCLUSION_RULES
from frtb_rrao._reference_risk_weight_rules import PROFILE_RISK_WEIGHT_RULES
from frtb_rrao._reference_rule_types import (
    RraoEvidenceRule,
    RraoExclusionRule,
    RraoInvestmentFundRule,
    RraoRiskWeightRule,
)
from frtb_rrao.data_models import (
    RraoCitation,
    RraoEvidenceType,
    RraoExclusionReason,
    RraoInvestmentFundExposureType,
    RraoRegulatoryProfile,
)
from frtb_rrao.validation import RraoInputError


def citations_for_profile(
    profile: RraoRegulatoryProfile | str,
) -> dict[str, RraoCitation]:
    """Return citations for a supported RRAO profile.
    Parameters
    ----------
    profile : RraoRegulatoryProfile | str
        Profile.

    Returns
    -------
    dict[str, RraoCitation]
        Result of the operation.
    """

    resolved = _resolve_supported_profile(profile)
    return dict(PROFILE_CITATIONS[resolved])


def evidence_rules_for_profile(
    profile: RraoRegulatoryProfile | str,
) -> tuple[RraoEvidenceRule, ...]:
    """Return supported evidence rules for a profile.
    Parameters
    ----------
    profile : RraoRegulatoryProfile | str
        Profile.

    Returns
    -------
    tuple[RraoEvidenceRule, ...]
        Result of the operation.
    """

    resolved = _resolve_supported_profile(profile)
    return PROFILE_EVIDENCE_RULES[resolved]


def exclusion_rules_for_profile(
    profile: RraoRegulatoryProfile | str,
) -> tuple[RraoExclusionRule, ...]:
    """Return supported exclusion rules for a profile.
    Parameters
    ----------
    profile : RraoRegulatoryProfile | str
        Profile.

    Returns
    -------
    tuple[RraoExclusionRule, ...]
        Result of the operation.
    """

    resolved = _resolve_supported_profile(profile)
    return PROFILE_EXCLUSION_RULES[resolved]


def investment_fund_rules_for_profile(
    profile: RraoRegulatoryProfile | str,
) -> tuple[RraoInvestmentFundRule, ...]:
    """Return supported investment-fund inclusion rules for a profile.
    Parameters
    ----------
    profile : RraoRegulatoryProfile | str
        Profile.

    Returns
    -------
    tuple[RraoInvestmentFundRule, ...]
        Result of the operation.
    """

    resolved = _resolve_supported_profile(profile)
    return PROFILE_INVESTMENT_FUND_RULES[resolved]


def risk_weight_rules_for_profile(
    profile: RraoRegulatoryProfile | str,
) -> tuple[RraoRiskWeightRule, ...]:
    """Return supported risk-weight rules for a profile.
    Parameters
    ----------
    profile : RraoRegulatoryProfile | str
        Profile.

    Returns
    -------
    tuple[RraoRiskWeightRule, ...]
        Result of the operation.
    """

    resolved = _resolve_supported_profile(profile)
    return PROFILE_RISK_WEIGHT_RULES[resolved]


def evidence_rule_for(
    profile: RraoRegulatoryProfile | str,
    evidence_type: RraoEvidenceType,
) -> RraoEvidenceRule:
    """Return the profile rule for a classification evidence type.
    Parameters
    ----------
    profile : RraoRegulatoryProfile | str
        Profile.
    evidence_type : RraoEvidenceType
        Evidence type.

    Returns
    -------
    RraoEvidenceRule
        Result of the operation.
    """

    for rule in evidence_rules_for_profile(profile):
        if rule.evidence_type is evidence_type:
            return rule
    raise RraoInputError(
        f"no RRAO evidence rule for {evidence_type.value}",
        field="evidence_type",
    )


def exclusion_rule_for(
    profile: RraoRegulatoryProfile | str,
    exclusion_reason: RraoExclusionReason,
) -> RraoExclusionRule:
    """Return the profile rule for an exclusion reason.
    Parameters
    ----------
    profile : RraoRegulatoryProfile | str
        Profile.
    exclusion_reason : RraoExclusionReason
        Exclusion reason.

    Returns
    -------
    RraoExclusionRule
        Result of the operation.
    """

    for rule in exclusion_rules_for_profile(profile):
        if rule.exclusion_reason is exclusion_reason:
            return rule
    raise RraoInputError(
        f"no RRAO exclusion rule for {exclusion_reason.value}",
        field="exclusion_reason",
    )


def investment_fund_rule_for(
    profile: RraoRegulatoryProfile | str,
    included_exposure_type: RraoInvestmentFundExposureType,
) -> RraoInvestmentFundRule:
    """Return the profile rule for an investment-fund included exposure type.
    Parameters
    ----------
    profile : RraoRegulatoryProfile | str
        Profile.
    included_exposure_type : RraoInvestmentFundExposureType
        Included exposure type.

    Returns
    -------
    RraoInvestmentFundRule
        Result of the operation.
    """

    for rule in investment_fund_rules_for_profile(profile):
        if rule.included_exposure_type is included_exposure_type:
            return rule
    raise RraoInputError(
        f"no RRAO investment-fund rule for {included_exposure_type.value}",
        field="investment_fund_descriptor.included_exposure_type",
    )


def risk_weight_rule_for(
    profile: RraoRegulatoryProfile | str,
    risk_weight_key: str,
) -> RraoRiskWeightRule:
    """Return the profile rule for a risk-weight key.
    Parameters
    ----------
    profile : RraoRegulatoryProfile | str
        Profile.
    risk_weight_key : str
        Risk weight key.

    Returns
    -------
    RraoRiskWeightRule
        Result of the operation.
    """

    for rule in risk_weight_rules_for_profile(profile):
        if rule.key == risk_weight_key:
            return rule
    raise RraoInputError(f"no RRAO risk-weight rule for {risk_weight_key}", field="risk_weight_key")


def profile_reference_payload(profile: RraoRegulatoryProfile | str) -> dict[str, object]:
    """Return a deterministic, JSON-serialisable payload for profile hashing.
    Parameters
    ----------
    profile : RraoRegulatoryProfile | str
        Profile.

    Returns
    -------
    dict[str, object]
        Result of the operation.
    """

    resolved = _resolve_supported_profile(profile)
    citations = citations_for_profile(resolved)
    return {
        "profile": resolved.value,
        "citations": {
            citation_id: {
                "source_id": citation.source_id,
                "paragraph": citation.paragraph,
                "url": citation.url,
                "note": citation.note,
            }
            for citation_id, citation in sorted(citations.items())
        },
        "evidence_rules": [
            {
                "evidence_type": rule.evidence_type.value,
                "classification": rule.classification.value,
                "risk_weight_key": rule.risk_weight_key,
                "reason_code": rule.reason_code,
                "citation_id": rule.citation_id,
            }
            for rule in sorted(
                evidence_rules_for_profile(resolved), key=lambda item: item.reason_code
            )
        ],
        "exclusion_rules": [
            {
                "exclusion_reason": rule.exclusion_reason.value,
                "risk_weight_key": rule.risk_weight_key,
                "reason_code": rule.reason_code,
                "citation_id": rule.citation_id,
            }
            for rule in sorted(
                exclusion_rules_for_profile(resolved), key=lambda item: item.reason_code
            )
        ],
        "investment_fund_rules": [
            {
                "included_exposure_type": rule.included_exposure_type.value,
                "classification": rule.classification.value,
                "risk_weight_key": rule.risk_weight_key,
                "reason_code": rule.reason_code,
                "citation_ids": list(rule.citation_ids),
            }
            for rule in sorted(
                investment_fund_rules_for_profile(resolved),
                key=lambda item: item.reason_code,
            )
        ],
        "risk_weight_rules": [
            {
                "key": rule.key,
                "classification": rule.classification.value,
                "risk_weight": rule.risk_weight,
                "citation_id": rule.citation_id,
            }
            for rule in sorted(risk_weight_rules_for_profile(resolved), key=lambda item: item.key)
        ],
    }


def _resolve_supported_profile(profile: RraoRegulatoryProfile | str) -> RraoRegulatoryProfile:
    try:
        resolved = RraoRegulatoryProfile(profile)
    except ValueError as exc:
        raise RraoInputError(
            f"unknown RRAO regulatory profile: {profile!r}", field="profile"
        ) from exc

    if resolved not in PROFILE_CITATIONS:
        raise UnsupportedRegulatoryFeatureError(
            f"RRAO profile {resolved.value} is unsupported until mapped and fixture-tested."
        )
    return resolved


__all__ = [
    "RraoEvidenceRule",
    "RraoExclusionRule",
    "RraoInvestmentFundRule",
    "RraoRiskWeightRule",
    "citations_for_profile",
    "evidence_rule_for",
    "evidence_rules_for_profile",
    "exclusion_rule_for",
    "exclusion_rules_for_profile",
    "investment_fund_rule_for",
    "investment_fund_rules_for_profile",
    "profile_reference_payload",
    "risk_weight_rule_for",
    "risk_weight_rules_for_profile",
]
