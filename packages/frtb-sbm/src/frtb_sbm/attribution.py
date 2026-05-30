"""
Attribution placeholder consuming audited SBM capital graphs.

Regulatory traceability:
    SBM-FUNC-022 — contribution readiness without unsupported Euler math.
"""

from __future__ import annotations

from dataclasses import dataclass

from frtb_common import UnsupportedRegulatoryFeatureError

from frtb_sbm.data_models import SbmCapitalResult


@dataclass(frozen=True)
class SbmAttributionPlaceholder:
    """Structured placeholder for future analytical Euler contribution support."""

    status: str
    reason: str
    requirement_id: str = "SBM-FUNC-022"


def attribution_placeholder_for_result(result: SbmCapitalResult) -> SbmAttributionPlaceholder:
    """Return an explicit unsupported attribution placeholder for one capital result."""

    del result
    return SbmAttributionPlaceholder(
        status="unsupported",
        reason=(
            "Analytical Euler contribution is not implemented; the audited capital graph "
            "preserves stable ids and branch metadata for future attribution work."
        ),
    )


def ensure_sbm_attribution_unsupported(result: SbmCapitalResult) -> None:
    """Fail closed when callers request unsupported Euler attribution."""

    del result
    raise UnsupportedRegulatoryFeatureError(
        "frtb-sbm analytical Euler attribution is unsupported (SBM-FUNC-022)"
    )


__all__ = [
    "SbmAttributionPlaceholder",
    "attribution_placeholder_for_result",
    "ensure_sbm_attribution_unsupported",
]
