"""Public boundary for the RRAO calculation package."""

from __future__ import annotations

from frtb_common import (
    CapitalComponentMetadata,
    ImplementationStatus,
    ValidationStatus,
)

from frtb_rrao._result_assembly import (
    collect_line_citations,
    partition_lines,
    profile_warnings,
    validate_context,
)
from frtb_rrao.audit import _input_hash_for_validated_positions, validate_rrao_result_reconciliation
from frtb_rrao.capital import (
    _build_rrao_capital_lines_from_validated,
    build_rrao_subtotals,
    included_rrao_total,
)
from frtb_rrao.data_models import (
    RraoCalculationContext,
    RraoCapitalResult,
)
from frtb_rrao.regimes import get_rrao_rule_profile
from frtb_rrao.validation import RraoInputError, validate_rrao_positions

PACKAGE_METADATA = CapitalComponentMetadata(
    package_name="frtb-rrao",
    import_name="frtb_rrao",
    component_name="Standardised Approach residual risk add-on",
    implementation_status=ImplementationStatus.IMPLEMENTED,
    validation_status=ValidationStatus.AVAILABLE,
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

    validate_context(context)
    rule_profile = get_rrao_rule_profile(context.profile)
    validated_positions = validate_rrao_positions(positions)
    all_lines = _build_rrao_capital_lines_from_validated(
        validated_positions,
        profile=rule_profile.profile,
    )
    included_lines, excluded_lines = partition_lines(all_lines)
    result_lines = included_lines + excluded_lines
    result = RraoCapitalResult(
        run_id=context.run_id,
        calculation_date=context.calculation_date,
        base_currency=context.base_currency,
        profile_id=rule_profile.profile.value,
        profile_hash=rule_profile.content_hash,
        input_hash=_input_hash_for_validated_positions(validated_positions),
        lines=included_lines,
        excluded_lines=excluded_lines,
        subtotals=build_rrao_subtotals(result_lines),
        total_rrao=included_rrao_total(result_lines),
        citations=collect_line_citations(result_lines),
        warnings=profile_warnings(rule_profile.profile),
    )
    validate_rrao_result_reconciliation(result)
    return result
