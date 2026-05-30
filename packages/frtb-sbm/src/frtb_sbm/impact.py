"""
Impact-analysis placeholder consuming audited SBM capital graphs.

Regulatory traceability:
    SBM-FUNC-022 — baseline-vs-candidate impact readiness without placeholder capital.
"""

from __future__ import annotations

from dataclasses import dataclass

from frtb_common import UnsupportedRegulatoryFeatureError

from frtb_sbm.data_models import SbmCapitalResult


@dataclass(frozen=True)
class SbmImpactPlaceholder:
    """Structured placeholder for future capital impact analysis."""

    status: str
    reason: str
    requirement_id: str = "SBM-FUNC-022"


def impact_placeholder_for_results(
    baseline: SbmCapitalResult,
    candidate: SbmCapitalResult,
) -> SbmImpactPlaceholder:
    """Return an explicit unsupported impact placeholder for two capital results."""

    del baseline, candidate
    return SbmImpactPlaceholder(
        status="unsupported",
        reason=(
            "Finite-difference capital impact is not implemented; baseline and candidate "
            "results retain deterministic hashes for future impact analysis."
        ),
    )


def ensure_sbm_impact_unsupported(
    baseline: SbmCapitalResult,
    candidate: SbmCapitalResult,
) -> None:
    """Fail closed when callers request unsupported capital impact analysis."""

    del baseline, candidate
    raise UnsupportedRegulatoryFeatureError(
        "frtb-sbm capital impact analysis is unsupported (SBM-FUNC-022)"
    )


__all__ = [
    "SbmImpactPlaceholder",
    "ensure_sbm_impact_unsupported",
    "impact_placeholder_for_results",
]
