"""
RRAO classification and exclusion decisions.

Regulatory traceability:
    See docs/REGULATORY_TRACEABILITY.md rows for classification.py, Basel
    MAR23.2-MAR23.7, U.S. NPR 2.0 proposed section __.211(a)-__.211(b),
    and Delegated Regulation (EU) 2022/2328 Articles 1-3.
"""

from __future__ import annotations

from frtb_rrao.data_models import (
    RraoClassification,
    RraoClassificationDecision,
    RraoEvidenceType,
    RraoPosition,
    RraoRegulatoryProfile,
)
from frtb_rrao.reference_data import (
    evidence_rule_for,
    exclusion_rule_for,
    investment_fund_rule_for,
)
from frtb_rrao.regimes import get_rrao_rule_profile
from frtb_rrao.validation import RraoInputError, validate_rrao_positions


def classify_rrao_positions(
    positions: object,
    *,
    profile: RraoRegulatoryProfile | str = RraoRegulatoryProfile.US_NPR_2_0,
) -> tuple[RraoClassificationDecision, ...]:
    """Classify validated RRAO positions for a supported rule profile."""

    rule_profile = get_rrao_rule_profile(profile)
    validated = validate_rrao_positions(positions)
    return _classify_validated_rrao_positions(validated, profile=rule_profile.profile)


def _classify_validated_rrao_positions(
    positions: tuple[RraoPosition, ...],
    *,
    profile: RraoRegulatoryProfile,
) -> tuple[RraoClassificationDecision, ...]:
    """Classify an already validated tuple of RRAO positions."""

    return tuple(_classify_validated_position(position, profile=profile) for position in positions)


def classify_rrao_position(
    position: RraoPosition,
    *,
    profile: RraoRegulatoryProfile | str = RraoRegulatoryProfile.US_NPR_2_0,
) -> RraoClassificationDecision:
    """Classify one canonical RRAO position for a supported rule profile."""

    rule_profile = get_rrao_rule_profile(profile)
    validated = validate_rrao_positions((position,))[0]
    return _classify_validated_position(validated, profile=rule_profile.profile)


def _classify_validated_position(
    position: RraoPosition,
    profile: RraoRegulatoryProfile,
) -> RraoClassificationDecision:
    if _is_exclusion_path(position):
        return _excluded_decision(position, profile)
    if position.evidence_type is RraoEvidenceType.INVESTMENT_FUND_EXPOSURE:
        return _investment_fund_decision(position, profile)

    rule = evidence_rule_for(profile, position.evidence_type)
    _check_hint_compatibility(position, rule.classification)
    return RraoClassificationDecision(
        position_id=position.position_id,
        classification=rule.classification,
        evidence_type=position.evidence_type,
        reason_code=rule.reason_code,
        risk_weight_key=rule.risk_weight_key,
        citations=_merged_citation_ids((rule.citation_id,), position.citations),
        supervisor_directive_id=position.supervisor_directive_id,
    )


def _excluded_decision(
    position: RraoPosition,
    profile: RraoRegulatoryProfile,
) -> RraoClassificationDecision:
    if position.exclusion_reason is None:
        raise RraoInputError(
            "excluded classification requires an exclusion reason",
            field="exclusion_reason",
            position_id=position.position_id,
        )
    rule = exclusion_rule_for(profile, position.exclusion_reason)
    return RraoClassificationDecision(
        position_id=position.position_id,
        classification=RraoClassification.EXCLUDED,
        evidence_type=position.evidence_type,
        reason_code=rule.reason_code,
        risk_weight_key=rule.risk_weight_key,
        citations=_merged_citation_ids((rule.citation_id,), position.citations),
        exclusion_reason=position.exclusion_reason,
        exclusion_evidence_id=position.exclusion_evidence_id,
    )


def _investment_fund_decision(
    position: RraoPosition,
    profile: RraoRegulatoryProfile,
) -> RraoClassificationDecision:
    if position.investment_fund_descriptor is None:
        raise RraoInputError(
            "investment fund descriptor is required",
            field="investment_fund_descriptor",
            position_id=position.position_id,
        )
    rule = investment_fund_rule_for(
        profile,
        position.investment_fund_descriptor.included_exposure_type,
    )
    _check_hint_compatibility(position, rule.classification)
    return RraoClassificationDecision(
        position_id=position.position_id,
        classification=rule.classification,
        evidence_type=position.evidence_type,
        reason_code=rule.reason_code,
        risk_weight_key=rule.risk_weight_key,
        citations=_merged_citation_ids(rule.citation_ids, position.citations),
    )


def _check_hint_compatibility(
    position: RraoPosition,
    classification: RraoClassification,
) -> None:
    if position.classification_hint is None:
        return
    if position.classification_hint is classification:
        return
    raise RraoInputError(
        (
            "classification hint conflicts with profile evidence rule: "
            f"{position.classification_hint.value} != {classification.value}"
        ),
        field="classification_hint",
        position_id=position.position_id,
    )


def _is_exclusion_path(position: RraoPosition) -> bool:
    return (
        position.classification_hint is RraoClassification.EXCLUDED
        or position.exclusion_reason is not None
        or position.evidence_type is RraoEvidenceType.EXPLICIT_EXCLUSION
    )


def _merged_citation_ids(*citation_groups: tuple[str, ...]) -> tuple[str, ...]:
    merged: list[str] = []
    seen: set[str] = set()
    for group in citation_groups:
        for citation_id in group:
            if citation_id not in seen:
                merged.append(citation_id)
                seen.add(citation_id)
    return tuple(merged)


__all__ = [
    "classify_rrao_position",
    "classify_rrao_positions",
]
