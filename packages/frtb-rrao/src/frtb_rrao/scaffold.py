"""Public boundary for the RRAO calculation package."""

from __future__ import annotations

from datetime import date

from frtb_common import (
    CapitalComponentMetadata,
    ImplementationStatus,
    ValidationStatus,
)

from frtb_rrao.audit import input_hash_for_positions, validate_rrao_result_reconciliation
from frtb_rrao.capital import (
    build_rrao_capital_lines,
    build_rrao_subtotals,
    included_rrao_total,
)
from frtb_rrao.data_models import (
    RraoCalculationContext,
    RraoCapitalLine,
    RraoCapitalResult,
    RraoRegulatoryProfile,
)
from frtb_rrao.regimes import get_rrao_rule_profile
from frtb_rrao.validation import RraoInputError, validate_rrao_positions

PACKAGE_METADATA = CapitalComponentMetadata(
    package_name="frtb-rrao",
    import_name="frtb_rrao",
    component_name="Standardised Approach residual risk add-on",
    implementation_status=ImplementationStatus.PARTIAL,
    validation_status=ValidationStatus.PENDING,
)


def calculate_rrao_capital(
    positions: object | None = None,
    *,
    context: RraoCalculationContext | None = None,
) -> RraoCapitalResult:
    """Calculate a supported canonical-input RRAO capital result."""

    if positions is None:
        raise RraoInputError("positions are required", field="positions")
    if context is None:
        raise RraoInputError("calculation context is required", field="context")

    _validate_context(context)
    rule_profile = get_rrao_rule_profile(context.profile)
    validated_positions = validate_rrao_positions(positions)
    all_lines = build_rrao_capital_lines(validated_positions, profile=rule_profile.profile)
    included_lines, excluded_lines = _partition_lines(all_lines)
    result = RraoCapitalResult(
        run_id=context.run_id,
        calculation_date=context.calculation_date,
        base_currency=context.base_currency,
        profile_id=rule_profile.profile.value,
        profile_hash=rule_profile.content_hash,
        input_hash=input_hash_for_positions(validated_positions),
        lines=included_lines,
        excluded_lines=excluded_lines,
        subtotals=build_rrao_subtotals(all_lines),
        total_rrao=included_rrao_total(all_lines),
        citations=_collect_line_citations(all_lines),
        warnings=_profile_warnings(rule_profile.profile),
    )
    validate_rrao_result_reconciliation(result)
    return result


def _validate_context(context: RraoCalculationContext) -> None:
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


def _partition_lines(
    lines: tuple[RraoCapitalLine, ...],
) -> tuple[tuple[RraoCapitalLine, ...], tuple[RraoCapitalLine, ...]]:
    included = tuple(line for line in lines if not line.is_excluded)
    excluded = tuple(line for line in lines if line.is_excluded)
    return included, excluded


def _collect_line_citations(lines: tuple[RraoCapitalLine, ...]) -> tuple[str, ...]:
    citation_ids: list[str] = []
    seen: set[str] = set()
    for line in lines:
        for citation_id in line.citations:
            if citation_id not in seen:
                citation_ids.append(citation_id)
                seen.add(citation_id)
    return tuple(citation_ids)


def _profile_warnings(profile: RraoRegulatoryProfile) -> tuple[str, ...]:
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
