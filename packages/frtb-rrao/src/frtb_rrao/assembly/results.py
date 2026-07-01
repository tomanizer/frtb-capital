"""Shared RRAO result assembly helpers."""

from __future__ import annotations

from datetime import date

from frtb_rrao._citations import merged_citation_ids
from frtb_rrao.data_models import (
    RraoCalculationContext,
    RraoCapitalLine,
    RraoRegulatoryProfile,
)
from frtb_rrao.org_scope import validate_scope_metadata
from frtb_rrao.validation import RraoInputError


def validate_context(context: RraoCalculationContext) -> None:
    """Validate public RRAO calculation context fields.
    Parameters
    ----------
    context : RraoCalculationContext
        Context.
    """

    if not isinstance(context, RraoCalculationContext):
        raise RraoInputError("calculation context must be RraoCalculationContext", field="context")
    _require_text(context.run_id, "run_id")
    _require_text(context.base_currency, "base_currency")
    if not isinstance(context.calculation_date, date):
        raise RraoInputError("calculation date must be a date", field="calculation_date")
    try:
        RraoRegulatoryProfile(context.profile)
    except ValueError as exc:
        raise RraoInputError("invalid regulatory profile", field="profile") from exc
    if context.desk_id:
        _require_text(context.desk_id, "desk_id")
    if context.legal_entity:
        _require_text(context.legal_entity, "legal_entity")
    _require_text(context.citation_policy, "citation_policy")
    validate_scope_metadata(context.calculation_scope, field="calculation_scope")


def partition_lines(
    lines: tuple[RraoCapitalLine, ...],
) -> tuple[tuple[RraoCapitalLine, ...], tuple[RraoCapitalLine, ...]]:
    """Split included and excluded capital lines without reordering.
    Parameters
    ----------
    lines : tuple[RraoCapitalLine, ...]
        Lines.

    Returns
    -------
    tuple[tuple[RraoCapitalLine, ...], tuple[RraoCapitalLine, ...]]
        Result of the operation.
    """

    included: list[RraoCapitalLine] = []
    excluded: list[RraoCapitalLine] = []
    for line in lines:
        if line.is_excluded:
            excluded.append(line)
        else:
            included.append(line)
    return tuple(included), tuple(excluded)


def collect_line_citations(lines: tuple[RraoCapitalLine, ...]) -> tuple[str, ...]:
    """Collect line citations while preserving first-seen order.
    Parameters
    ----------
    lines : tuple[RraoCapitalLine, ...]
        Lines.

    Returns
    -------
    tuple[str, ...]
        Result of the operation.
    """

    return merged_citation_ids(*(line.citations for line in lines))


def profile_warnings(profile: RraoRegulatoryProfile) -> tuple[str, ...]:
    """Return public warnings for a supported RRAO profile.
    Parameters
    ----------
    profile : RraoRegulatoryProfile
        Profile.

    Returns
    -------
    tuple[str, ...]
        Result of the operation.
    """

    if profile is RraoRegulatoryProfile.US_NPR_2_0:
        return (
            "US_NPR_2_0 is proposed-rule material; do not present outputs as final "
            "regulatory capital.",
        )
    return ()


def _require_text(value: object, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise RraoInputError("non-empty text is required", field=field)
    return value


__all__ = [
    "collect_line_citations",
    "partition_lines",
    "profile_warnings",
    "validate_context",
]
