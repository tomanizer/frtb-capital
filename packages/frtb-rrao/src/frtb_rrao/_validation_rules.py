"""Shared RRAO validation rule predicates and messages."""

from __future__ import annotations

import math

from frtb_rrao.data_models import (
    RraoClassification,
    RraoEvidenceType,
    RraoExclusionReason,
)

GROSS_NOTIONAL_NON_NEGATIVE_MESSAGE = "gross effective notional must be non-negative"
GROSS_NOTIONAL_MATCHES_FUND_PORTION_MESSAGE = (
    "gross effective notional must equal the cited investment-fund included portion"
)
UNSUPPORTED_CLASSIFICATION_MESSAGE = "unsupported classification path"
SOURCE_LINEAGE_REQUIRED_MESSAGE = "source lineage is required"
UNDERLYING_COUNT_INTEGER_MESSAGE = "underlying count must be an integer"
UNDERLYING_COUNT_NON_NEGATIVE_MESSAGE = "underlying count must be non-negative"

EXCLUDED_CLASSIFICATION_REQUIRES_REASON_MESSAGE = (
    "excluded classification requires an exclusion reason"
)
EXCLUSION_REASON_REQUIRES_EXPLICIT_EVIDENCE_MESSAGE = (
    "exclusion reason requires explicit exclusion evidence type"
)
EXPLICIT_EXCLUSION_REQUIRES_REASON_MESSAGE = (
    "explicit exclusion evidence requires an exclusion reason"
)
EXACT_BACK_TO_BACK_REQUIRES_MATCH_MESSAGE = "exact back-to-back exclusion requires match evidence"
BACK_TO_BACK_ONLY_FOR_EXACT_EXCLUSION_MESSAGE = (
    "back-to-back match evidence is only valid for exact back-to-back exclusions"
)
BACK_TO_BACK_SELF_MATCH_MESSAGE = "back-to-back match must reference the opposite transaction"
BACK_TO_BACK_MISSING_MATCH_MESSAGE = "back-to-back matched position is missing from input"
BACK_TO_BACK_REQUIRES_EVIDENCED_COUNTERPART_MESSAGE = (
    "back-to-back matched position must also carry back-to-back evidence"
)
BACK_TO_BACK_CROSS_REFERENCE_MESSAGE = (
    "back-to-back match group does not cross-reference the paired transaction"
)
BACK_TO_BACK_SHARED_EVIDENCE_MESSAGE = (
    "exact back-to-back pair must share the same exclusion evidence id"
)
BACK_TO_BACK_MATCHING_CURRENCY_MESSAGE = "exact back-to-back pair must have matching currency"
BACK_TO_BACK_MATCHING_NOTIONAL_MESSAGE = (
    "exact back-to-back pair must have matching gross effective notional"
)

INVESTMENT_FUND_FLAG_REQUIRED_MESSAGE = "investment fund exposure flag is required"
INVESTMENT_FUND_EVIDENCE_TYPE_REQUIRED_MESSAGE = (
    "investment fund exposure requires investment-fund evidence type"
)
INVESTMENT_FUND_DESCRIPTOR_REQUIRED_MESSAGE = "investment fund descriptor is required"
INVESTMENT_FUND_BACKSTOP_METHOD_REQUIRED_MESSAGE = (
    "investment fund RRAO inclusion requires the __.205(e)(3)(iii) backstop method"
)
INVESTMENT_FUND_NON_LOOK_THROUGH_MESSAGE = (
    "investment fund RRAO inclusion requires a non-look-through portion"
)
INVESTMENT_FUND_MANDATE_ALLOWS_RRAO_MESSAGE = (
    "investment fund mandate evidence must permit RRAO exposure types"
)
FUND_GROSS_NOTIONAL_POSITIVE_MESSAGE = "fund gross effective notional must be positive"
INCLUDED_EXPOSURE_RATIO_RANGE_MESSAGE = (
    "included exposure ratio must be greater than zero and no more than one"
)

NOTIONAL_RECONCILIATION_REL_TOL = 1e-12
NOTIONAL_RECONCILIATION_ABS_TOL = 1e-9


def is_valid_underlying_count(value: object) -> bool:
    """Return whether an optional underlying count is an integer count.
    Parameters
    ----------
    value : object
        Value.

    Returns
    -------
    bool
        Result of the operation.
    """

    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def is_unsupported_classification_hint(value: object) -> bool:
    """Return whether a classification hint names an unsupported path.
    Parameters
    ----------
    value : object
        Value.

    Returns
    -------
    bool
        Result of the operation.
    """

    return value == RraoClassification.UNSUPPORTED or value == RraoClassification.UNSUPPORTED.value


def supervisor_directive_required(
    evidence_type: RraoEvidenceType,
    classification_hint: RraoClassification | None,
) -> bool:
    """Return whether supervisor directive evidence id is required.
    Parameters
    ----------
    evidence_type : RraoEvidenceType
        Evidence type.
    classification_hint : RraoClassification | None
        Classification hint.

    Returns
    -------
    bool
        Result of the operation.
    """

    return (
        evidence_type is RraoEvidenceType.SUPERVISOR_DIRECTIVE
        or classification_hint is RraoClassification.SUPERVISOR_DIRECTED
    )


def excluded_classification_requires_reason(
    classification_hint: RraoClassification | None,
    exclusion_reason: RraoExclusionReason | None,
) -> bool:
    """Return whether an excluded hint is missing its exclusion reason.
    Parameters
    ----------
    classification_hint : RraoClassification | None
        Classification hint.
    exclusion_reason : RraoExclusionReason | None
        Exclusion reason.

    Returns
    -------
    bool
        Result of the operation.
    """

    return classification_hint is RraoClassification.EXCLUDED and exclusion_reason is None


def exclusion_reason_requires_explicit_evidence(
    exclusion_reason: RraoExclusionReason | None,
    evidence_type: RraoEvidenceType,
) -> bool:
    """Return whether an exclusion reason is paired with the wrong evidence type.
    Parameters
    ----------
    exclusion_reason : RraoExclusionReason | None
        Exclusion reason.
    evidence_type : RraoEvidenceType
        Evidence type.

    Returns
    -------
    bool
        Result of the operation.
    """

    return exclusion_reason is not None and evidence_type is not RraoEvidenceType.EXPLICIT_EXCLUSION


def explicit_exclusion_requires_reason(
    evidence_type: RraoEvidenceType,
    exclusion_reason: RraoExclusionReason | None,
) -> bool:
    """Return whether explicit exclusion evidence is missing its exclusion reason.
    Parameters
    ----------
    evidence_type : RraoEvidenceType
        Evidence type.
    exclusion_reason : RraoExclusionReason | None
        Exclusion reason.

    Returns
    -------
    bool
        Result of the operation.
    """

    return evidence_type is RraoEvidenceType.EXPLICIT_EXCLUSION and exclusion_reason is None


def exact_back_to_back_requires_match(
    exclusion_reason: RraoExclusionReason | None,
    match_present: bool,
) -> bool:
    """Return whether exact back-to-back evidence is missing its match object.
    Parameters
    ----------
    exclusion_reason : RraoExclusionReason | None
        Exclusion reason.
    match_present : bool
        Match present.

    Returns
    -------
    bool
        Result of the operation.
    """

    return (
        exclusion_reason is RraoExclusionReason.EXACT_THIRD_PARTY_BACK_TO_BACK and not match_present
    )


def back_to_back_match_requires_exact_exclusion(
    exclusion_reason: RraoExclusionReason | None,
    match_present: bool,
) -> bool:
    """Return whether match evidence appears outside the exact back-to-back exclusion.
    Parameters
    ----------
    exclusion_reason : RraoExclusionReason | None
        Exclusion reason.
    match_present : bool
        Match present.

    Returns
    -------
    bool
        Result of the operation.
    """

    return (
        match_present and exclusion_reason is not RraoExclusionReason.EXACT_THIRD_PARTY_BACK_TO_BACK
    )


def investment_fund_path_required(
    *,
    is_investment_fund_exposure: bool,
    evidence_type: RraoEvidenceType,
    descriptor_present: bool,
) -> bool:
    """Return whether investment-fund validation rules apply.
    Parameters
    ----------
    is_investment_fund_exposure : bool
        Is investment fund exposure.
    evidence_type : RraoEvidenceType
        Evidence type.
    descriptor_present : bool
        Descriptor present.

    Returns
    -------
    bool
        Result of the operation.
    """

    return (
        is_investment_fund_exposure
        or evidence_type is RraoEvidenceType.INVESTMENT_FUND_EXPOSURE
        or descriptor_present
    )


def included_exposure_ratio_is_valid(ratio: float) -> bool:
    """Return whether an investment-fund included-exposure ratio is in range.
    Parameters
    ----------
    ratio : float
        Ratio.

    Returns
    -------
    bool
        Result of the operation.
    """

    return math.isfinite(ratio) and 0.0 < ratio <= 1.0


def fund_gross_notional_is_positive(notional: float) -> bool:
    """Return whether a fund gross effective notional is finite and positive.
    Parameters
    ----------
    notional : float
        Notional.

    Returns
    -------
    bool
        Result of the operation.
    """

    return math.isfinite(notional) and notional > 0.0


def gross_notional_matches_included_fund_portion(
    gross_effective_notional: float,
    fund_gross_effective_notional: float,
    included_exposure_ratio: float,
) -> bool:
    """Return whether gross notional equals the cited included fund portion.
    Parameters
    ----------
    gross_effective_notional : float
        Gross effective notional.
    fund_gross_effective_notional : float
        Fund gross effective notional.
    included_exposure_ratio : float
        Included exposure ratio.

    Returns
    -------
    bool
        Result of the operation.
    """

    return math.isclose(
        gross_effective_notional,
        fund_gross_effective_notional * included_exposure_ratio,
        rel_tol=NOTIONAL_RECONCILIATION_REL_TOL,
        abs_tol=NOTIONAL_RECONCILIATION_ABS_TOL,
    )


__all__ = [
    "BACK_TO_BACK_CROSS_REFERENCE_MESSAGE",
    "BACK_TO_BACK_MATCHING_CURRENCY_MESSAGE",
    "BACK_TO_BACK_MATCHING_NOTIONAL_MESSAGE",
    "BACK_TO_BACK_MISSING_MATCH_MESSAGE",
    "BACK_TO_BACK_ONLY_FOR_EXACT_EXCLUSION_MESSAGE",
    "BACK_TO_BACK_REQUIRES_EVIDENCED_COUNTERPART_MESSAGE",
    "BACK_TO_BACK_SELF_MATCH_MESSAGE",
    "BACK_TO_BACK_SHARED_EVIDENCE_MESSAGE",
    "EXACT_BACK_TO_BACK_REQUIRES_MATCH_MESSAGE",
    "EXCLUDED_CLASSIFICATION_REQUIRES_REASON_MESSAGE",
    "EXCLUSION_REASON_REQUIRES_EXPLICIT_EVIDENCE_MESSAGE",
    "EXPLICIT_EXCLUSION_REQUIRES_REASON_MESSAGE",
    "FUND_GROSS_NOTIONAL_POSITIVE_MESSAGE",
    "GROSS_NOTIONAL_MATCHES_FUND_PORTION_MESSAGE",
    "GROSS_NOTIONAL_NON_NEGATIVE_MESSAGE",
    "INCLUDED_EXPOSURE_RATIO_RANGE_MESSAGE",
    "INVESTMENT_FUND_BACKSTOP_METHOD_REQUIRED_MESSAGE",
    "INVESTMENT_FUND_DESCRIPTOR_REQUIRED_MESSAGE",
    "INVESTMENT_FUND_EVIDENCE_TYPE_REQUIRED_MESSAGE",
    "INVESTMENT_FUND_FLAG_REQUIRED_MESSAGE",
    "INVESTMENT_FUND_MANDATE_ALLOWS_RRAO_MESSAGE",
    "INVESTMENT_FUND_NON_LOOK_THROUGH_MESSAGE",
    "NOTIONAL_RECONCILIATION_ABS_TOL",
    "NOTIONAL_RECONCILIATION_REL_TOL",
    "SOURCE_LINEAGE_REQUIRED_MESSAGE",
    "UNDERLYING_COUNT_INTEGER_MESSAGE",
    "UNDERLYING_COUNT_NON_NEGATIVE_MESSAGE",
    "UNSUPPORTED_CLASSIFICATION_MESSAGE",
    "back_to_back_match_requires_exact_exclusion",
    "exact_back_to_back_requires_match",
    "excluded_classification_requires_reason",
    "exclusion_reason_requires_explicit_evidence",
    "explicit_exclusion_requires_reason",
    "fund_gross_notional_is_positive",
    "gross_notional_matches_included_fund_portion",
    "included_exposure_ratio_is_valid",
    "investment_fund_path_required",
    "is_unsupported_classification_hint",
    "is_valid_underlying_count",
    "supervisor_directive_required",
]
