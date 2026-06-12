"""Shared EU/PRA RRAO reference rule expansion sets."""

from __future__ import annotations

from frtb_rrao.data_models import RraoEvidenceType, RraoExclusionReason

_EU_ARTICLE_2_EVIDENCE_TYPES = (
    RraoEvidenceType.PATH_DEPENDENT_OPTION,
    RraoEvidenceType.FORWARD_START_UNDETERMINED_STRIKE_OPTION,
    RraoEvidenceType.OPTION_ON_OPTION,
    RraoEvidenceType.DISCONTINUOUS_PAYOFF_OPTION,
    RraoEvidenceType.HOLDER_MODIFIABLE_OPTION,
    RraoEvidenceType.FINITE_EXERCISE_DATES_OPTION,
    RraoEvidenceType.CROSS_CURRENCY_SETTLED_OPTION,
    RraoEvidenceType.MULTI_UNDERLYING_OPTION,
    RraoEvidenceType.BEHAVIOURAL_OPTION,
)

_EU_ARTICLE_3_EXCLUSION_REASONS = (
    RraoExclusionReason.EU_ARTICLE_3_DELIVERABLE_RANGE,
    RraoExclusionReason.EU_ARTICLE_3_RELATIVE_IMPLIED_VOLATILITY,
    RraoExclusionReason.EU_ARTICLE_3_INDEX_OPTION_CORRELATION,
    RraoExclusionReason.EU_ARTICLE_3_CIU_INDEX_OPTION_CORRELATION,
    RraoExclusionReason.EU_ARTICLE_3_DIVIDEND_RISK,
)

__all__ = [
    "_EU_ARTICLE_2_EVIDENCE_TYPES",
    "_EU_ARTICLE_3_EXCLUSION_REASONS",
]
