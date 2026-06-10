"""
Validation helpers for canonical RRAO inputs.

Regulatory traceability:
    See docs/REGULATORY_TRACEABILITY.md rows for validation.py, Basel MAR23.8,
    and U.S. NPR 2.0 proposed section __.211(c)(2).
"""

from __future__ import annotations

import math
from typing import Literal

from frtb_rrao._investment_fund_validation import (
    InvestmentFundRuleFailure,
    InvestmentFundRuleValues,
    validate_investment_fund_rule_values,
)
from frtb_rrao._validation_rules import (
    BACK_TO_BACK_CROSS_REFERENCE_MESSAGE,
    BACK_TO_BACK_MATCHING_CURRENCY_MESSAGE,
    BACK_TO_BACK_MATCHING_NOTIONAL_MESSAGE,
    BACK_TO_BACK_ONLY_FOR_EXACT_EXCLUSION_MESSAGE,
    BACK_TO_BACK_SELF_MATCH_MESSAGE,
    BACK_TO_BACK_SHARED_EVIDENCE_MESSAGE,
    EXACT_BACK_TO_BACK_REQUIRES_MATCH_MESSAGE,
    EXCLUDED_CLASSIFICATION_REQUIRES_REASON_MESSAGE,
    EXCLUSION_REASON_REQUIRES_EXPLICIT_EVIDENCE_MESSAGE,
    EXPLICIT_EXCLUSION_REQUIRES_REASON_MESSAGE,
    GROSS_NOTIONAL_NON_NEGATIVE_MESSAGE,
    SOURCE_LINEAGE_REQUIRED_MESSAGE,
    UNDERLYING_COUNT_INTEGER_MESSAGE,
    UNDERLYING_COUNT_NON_NEGATIVE_MESSAGE,
    UNSUPPORTED_CLASSIFICATION_MESSAGE,
    back_to_back_match_requires_exact_exclusion,
    exact_back_to_back_requires_match,
    excluded_classification_requires_reason,
    exclusion_reason_requires_explicit_evidence,
    explicit_exclusion_requires_reason,
    investment_fund_path_required,
    is_unsupported_classification_hint,
    is_valid_underlying_count,
    supervisor_directive_required,
)
from frtb_rrao.data_models import (
    RraoBackToBackMatch,
    RraoClassification,
    RraoEvidenceType,
    RraoExclusionReason,
    RraoInvestmentFundDescriptor,
    RraoInvestmentFundExposureType,
    RraoInvestmentFundMethod,
    RraoPosition,
    RraoSourceLineage,
)
from frtb_rrao.numeric import is_reconciled

NotionalSignConvention = Literal["gross", "signed_absolute"]


class RraoInputError(ValueError):
    """Raised when canonical RRAO inputs fail deterministic validation."""

    def __init__(self, message: str, *, field: str = "", position_id: str = "") -> None:
        self.field = field
        self.position_id = position_id
        prefix = f"position {position_id}: " if position_id else ""
        suffix = f" [{field}]" if field else ""
        super().__init__(f"{prefix}{message}{suffix}")


def normalise_gross_effective_notional(
    value: float,
    *,
    source_sign_convention: NotionalSignConvention = "gross",
) -> float:
    """Return a finite non-negative gross effective notional."""

    if source_sign_convention not in {"gross", "signed_absolute"}:
        raise RraoInputError(
            "source_sign_convention must be 'gross' or 'signed_absolute'",
            field="source_sign_convention",
        )
    notional = _finite_float(value, field="gross_effective_notional")
    if notional < 0:
        if source_sign_convention == "signed_absolute":
            return abs(notional)
        raise RraoInputError(
            GROSS_NOTIONAL_NON_NEGATIVE_MESSAGE,
            field="gross_effective_notional",
        )
    return notional


def validate_rrao_positions(positions: object) -> tuple[RraoPosition, ...]:
    """Validate canonical RRAO positions and return them as a tuple."""

    if isinstance(positions, RraoPosition):
        raise RraoInputError("positions must be an iterable of RraoPosition objects")
    try:
        candidates: tuple[object, ...] = tuple(positions)  # type: ignore[arg-type]
    except TypeError as exc:
        raise RraoInputError("positions must be an iterable of RraoPosition objects") from exc

    seen_position_ids: set[str] = set()
    validated: list[RraoPosition] = []
    for candidate in candidates:
        if not isinstance(candidate, RraoPosition):
            raise RraoInputError("positions must contain only RraoPosition objects")
        position = candidate
        _validate_position(position, seen_position_ids)
        seen_position_ids.add(position.position_id)
        validated.append(position)
    validated_positions = tuple(validated)
    _validate_back_to_back_match_groups(validated_positions)
    return validated_positions


def _validate_position_without_back_to_back_groups(
    position: RraoPosition,
    seen_position_ids: set[str],
) -> None:
    """Validate one row before batch-level back-to-back matching is available."""

    _validate_position(position, seen_position_ids)
    _validate_back_to_back_match_fields(position)


def _validate_position(position: RraoPosition, seen_position_ids: set[str]) -> None:
    position_id = _require_text(position.position_id, "position_id")
    if position_id in seen_position_ids:
        raise RraoInputError(
            "duplicate position id",
            field="position_id",
            position_id=position_id,
        )

    _require_text(position.source_row_id, "source_row_id", position_id)
    _require_text(position.desk_id, "desk_id", position_id)
    _require_text(position.legal_entity, "legal_entity", position_id)
    _require_text(position.currency, "currency", position_id)
    _require_text(position.evidence_label, "evidence_label", position_id)
    _require_text(position.notional_source, "notional_source", position_id)
    normalise_gross_effective_notional(position.gross_effective_notional)

    if not isinstance(position.evidence_type, RraoEvidenceType):
        raise RraoInputError(
            "invalid evidence type", field="evidence_type", position_id=position_id
        )
    if position.classification_hint is not None and not isinstance(
        position.classification_hint,
        RraoClassification,
    ):
        raise RraoInputError(
            "invalid classification hint",
            field="classification_hint",
            position_id=position_id,
        )
    if is_unsupported_classification_hint(position.classification_hint):
        raise RraoInputError(
            UNSUPPORTED_CLASSIFICATION_MESSAGE,
            field="classification_hint",
            position_id=position_id,
        )
    if position.exclusion_reason is not None and not isinstance(
        position.exclusion_reason,
        RraoExclusionReason,
    ):
        raise RraoInputError(
            "invalid exclusion reason",
            field="exclusion_reason",
            position_id=position_id,
        )

    _validate_lineage(position.lineage, position_id)
    _validate_optional_fields(position)
    _validate_evidence_requirements(position)


def _validate_lineage(lineage: RraoSourceLineage | None, position_id: str) -> None:
    if lineage is None:
        raise RraoInputError(
            SOURCE_LINEAGE_REQUIRED_MESSAGE, field="lineage", position_id=position_id
        )
    if not isinstance(lineage, RraoSourceLineage):
        raise RraoInputError("invalid source lineage", field="lineage", position_id=position_id)

    _require_text(lineage.source_system, "lineage.source_system", position_id)
    _require_text(lineage.source_file, "lineage.source_file", position_id)
    _require_text(lineage.source_row_id, "lineage.source_row_id", position_id)
    for mapping in lineage.source_column_map:
        if not isinstance(mapping, tuple) or len(mapping) != 2:
            raise RraoInputError(
                "source column map entries must be field pairs",
                field="lineage.source_column_map",
                position_id=position_id,
            )
        source_field, canonical_field = mapping
        _require_text(source_field, "lineage.source_column_map.source", position_id)
        _require_text(canonical_field, "lineage.source_column_map.canonical", position_id)


def _validate_optional_fields(position: RraoPosition) -> None:
    if position.underlying_count is not None:
        if not isinstance(position.underlying_count, int) or isinstance(
            position.underlying_count,
            bool,
        ):
            raise RraoInputError(
                UNDERLYING_COUNT_INTEGER_MESSAGE,
                field="underlying_count",
                position_id=position.position_id,
            )
        if not is_valid_underlying_count(position.underlying_count):
            raise RraoInputError(
                UNDERLYING_COUNT_NON_NEGATIVE_MESSAGE,
                field="underlying_count",
                position_id=position.position_id,
            )

    for field_name in (
        "is_path_dependent",
        "has_maturity",
        "has_strike_or_barrier",
        "has_multiple_strikes_or_barriers",
    ):
        value = getattr(position, field_name)
        if value is not None and not isinstance(value, bool):
            raise RraoInputError(
                f"{field_name} must be a bool when provided",
                field=field_name,
                position_id=position.position_id,
            )

    for field_name in ("is_ctp_hedge", "is_investment_fund_exposure"):
        if not isinstance(getattr(position, field_name), bool):
            raise RraoInputError(
                f"{field_name} must be a bool",
                field=field_name,
                position_id=position.position_id,
            )
    _validate_investment_fund_fields(position)
    for citation in position.citations:
        _require_text(citation, "citations", position.position_id)


def _validate_evidence_requirements(position: RraoPosition) -> None:
    if supervisor_directive_required(position.evidence_type, position.classification_hint):
        _require_text(
            position.supervisor_directive_id,
            "supervisor_directive_id",
            position.position_id,
        )
    if excluded_classification_requires_reason(
        position.classification_hint,
        position.exclusion_reason,
    ):
        raise RraoInputError(
            EXCLUDED_CLASSIFICATION_REQUIRES_REASON_MESSAGE,
            field="exclusion_reason",
            position_id=position.position_id,
        )
    if position.exclusion_reason is not None:
        if exclusion_reason_requires_explicit_evidence(
            position.exclusion_reason,
            position.evidence_type,
        ):
            raise RraoInputError(
                EXCLUSION_REASON_REQUIRES_EXPLICIT_EVIDENCE_MESSAGE,
                field="evidence_type",
                position_id=position.position_id,
            )
        _require_text(position.exclusion_evidence_id, "exclusion_evidence_id", position.position_id)
    if exact_back_to_back_requires_match(
        position.exclusion_reason,
        position.back_to_back_match is not None,
    ):
        raise RraoInputError(
            EXACT_BACK_TO_BACK_REQUIRES_MATCH_MESSAGE,
            field="back_to_back_match",
            position_id=position.position_id,
        )
    if back_to_back_match_requires_exact_exclusion(
        position.exclusion_reason,
        position.back_to_back_match is not None,
    ):
        raise RraoInputError(
            BACK_TO_BACK_ONLY_FOR_EXACT_EXCLUSION_MESSAGE,
            field="back_to_back_match",
            position_id=position.position_id,
        )
    if explicit_exclusion_requires_reason(position.evidence_type, position.exclusion_reason):
        raise RraoInputError(
            EXPLICIT_EXCLUSION_REQUIRES_REASON_MESSAGE,
            field="exclusion_reason",
            position_id=position.position_id,
        )
    if position.evidence_type is RraoEvidenceType.EXPLICIT_EXCLUSION:
        _require_text(position.exclusion_evidence_id, "exclusion_evidence_id", position.position_id)


def _validate_back_to_back_match_groups(positions: tuple[RraoPosition, ...]) -> None:
    positions_by_id = {position.position_id: position for position in positions}
    match_groups: dict[str, list[tuple[RraoPosition, RraoBackToBackMatch]]] = {}

    for position in positions:
        match_fields = _validate_back_to_back_match_fields(position)
        if match_fields is None:
            continue
        match_group_id, matched_position_id, match = match_fields
        if matched_position_id not in positions_by_id:
            raise RraoInputError(
                "back-to-back matched position is missing from input",
                field="back_to_back_match.matched_position_id",
                position_id=position.position_id,
            )
        match_groups.setdefault(match_group_id, []).append((position, match))

    for match_group_id in sorted(match_groups):
        group_entries = match_groups[match_group_id]
        if len(group_entries) != 2:
            joined = ", ".join(position.position_id for position, _ in group_entries)
            raise RraoInputError(
                (f"exact back-to-back match group must contain exactly two transactions: {joined}"),
                field="back_to_back_match.match_group_id",
                position_id=group_entries[0][0].position_id,
            )
        (left, left_match), (right, right_match) = group_entries
        _validate_exact_back_to_back_pair(left, left_match, right, right_match)


def _validate_back_to_back_match_fields(
    position: RraoPosition,
) -> tuple[str, str, RraoBackToBackMatch] | None:
    match = position.back_to_back_match
    if match is None:
        return None
    if not isinstance(match, RraoBackToBackMatch):
        raise RraoInputError(
            "invalid back-to-back match evidence",
            field="back_to_back_match",
            position_id=position.position_id,
        )
    match_group_id = _require_text(
        match.match_group_id,
        "back_to_back_match.match_group_id",
        position.position_id,
    )
    matched_position_id = _require_text(
        match.matched_position_id,
        "back_to_back_match.matched_position_id",
        position.position_id,
    )
    if matched_position_id == position.position_id:
        raise RraoInputError(
            BACK_TO_BACK_SELF_MATCH_MESSAGE,
            field="back_to_back_match.matched_position_id",
            position_id=position.position_id,
        )
    return match_group_id, matched_position_id, match


def _validate_exact_back_to_back_pair(
    left: RraoPosition,
    left_match: RraoBackToBackMatch,
    right: RraoPosition,
    right_match: RraoBackToBackMatch,
) -> None:
    if left_match.matched_position_id != right.position_id:
        raise RraoInputError(
            BACK_TO_BACK_CROSS_REFERENCE_MESSAGE,
            field="back_to_back_match.matched_position_id",
            position_id=left.position_id,
        )
    if right_match.matched_position_id != left.position_id:
        raise RraoInputError(
            BACK_TO_BACK_CROSS_REFERENCE_MESSAGE,
            field="back_to_back_match.matched_position_id",
            position_id=right.position_id,
        )
    if left.exclusion_evidence_id != right.exclusion_evidence_id:
        raise RraoInputError(
            BACK_TO_BACK_SHARED_EVIDENCE_MESSAGE,
            field="exclusion_evidence_id",
            position_id=right.position_id,
        )
    if left.currency != right.currency:
        raise RraoInputError(
            BACK_TO_BACK_MATCHING_CURRENCY_MESSAGE,
            field="currency",
            position_id=right.position_id,
        )
    if not is_reconciled(
        left.gross_effective_notional,
        right.gross_effective_notional,
    ):
        raise RraoInputError(
            BACK_TO_BACK_MATCHING_NOTIONAL_MESSAGE,
            field="gross_effective_notional",
            position_id=right.position_id,
        )


def _validate_investment_fund_fields(position: RraoPosition) -> None:
    is_fund_path = investment_fund_path_required(
        is_investment_fund_exposure=position.is_investment_fund_exposure,
        evidence_type=position.evidence_type,
        descriptor_present=position.investment_fund_descriptor is not None,
    )
    if not is_fund_path:
        return

    _raise_investment_fund_failure(
        validate_investment_fund_rule_values(
            InvestmentFundRuleValues(
                position_id=position.position_id,
                gross_effective_notional=position.gross_effective_notional,
                is_investment_fund_exposure=position.is_investment_fund_exposure,
                evidence_type=position.evidence_type,
                descriptor_present=position.investment_fund_descriptor is not None,
                section_205_method_value=None,
                fund_gross_effective_notional=None,
                included_exposure_ratio=None,
                look_through_available=None,
                mandate_allows_rrao_exposures=None,
            ),
            check_descriptor_values=False,
        )
    )

    descriptor = position.investment_fund_descriptor
    if descriptor is None:
        return
    if not isinstance(descriptor, RraoInvestmentFundDescriptor):
        raise RraoInputError(
            "invalid investment fund descriptor",
            field="investment_fund_descriptor",
            position_id=position.position_id,
        )

    _require_text(descriptor.fund_id, "investment_fund_descriptor.fund_id", position.position_id)
    _require_text(
        descriptor.mandate_evidence_id,
        "investment_fund_descriptor.mandate_evidence_id",
        position.position_id,
    )
    _require_text(
        descriptor.section_205_evidence_id,
        "investment_fund_descriptor.section_205_evidence_id",
        position.position_id,
    )
    if not isinstance(descriptor.section_205_method, RraoInvestmentFundMethod):
        raise RraoInputError(
            "invalid investment fund method",
            field="investment_fund_descriptor.section_205_method",
            position_id=position.position_id,
        )
    if not isinstance(descriptor.included_exposure_type, RraoInvestmentFundExposureType):
        raise RraoInputError(
            "invalid investment fund exposure type",
            field="investment_fund_descriptor.included_exposure_type",
            position_id=position.position_id,
        )
    if not isinstance(descriptor.look_through_available, bool):
        raise RraoInputError(
            "look-through availability must be a bool",
            field="investment_fund_descriptor.look_through_available",
            position_id=position.position_id,
        )
    if not isinstance(descriptor.mandate_allows_rrao_exposures, bool):
        raise RraoInputError(
            "mandate RRAO exposure flag must be a bool",
            field="investment_fund_descriptor.mandate_allows_rrao_exposures",
            position_id=position.position_id,
        )

    fund_notional = _finite_float(
        descriptor.fund_gross_effective_notional,
        field="investment_fund_descriptor.fund_gross_effective_notional",
    )
    ratio = _finite_float(
        descriptor.included_exposure_ratio,
        field="investment_fund_descriptor.included_exposure_ratio",
    )
    _raise_investment_fund_failure(
        validate_investment_fund_rule_values(
            InvestmentFundRuleValues(
                position_id=position.position_id,
                gross_effective_notional=position.gross_effective_notional,
                is_investment_fund_exposure=position.is_investment_fund_exposure,
                evidence_type=position.evidence_type,
                descriptor_present=True,
                section_205_method_value=descriptor.section_205_method.value,
                fund_gross_effective_notional=fund_notional,
                included_exposure_ratio=ratio,
                look_through_available=descriptor.look_through_available,
                mandate_allows_rrao_exposures=descriptor.mandate_allows_rrao_exposures,
            )
        )
    )


def _raise_investment_fund_failure(failure: InvestmentFundRuleFailure | None) -> None:
    if failure is not None:
        raise RraoInputError(
            failure.message,
            field=failure.field,
            position_id=failure.position_id,
        )


def _finite_float(value: object, *, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise RraoInputError("value must be numeric", field=field)
    number = float(value)
    if not math.isfinite(number):
        raise RraoInputError("value must be finite", field=field)
    return number


def _require_text(value: object, field: str, position_id: str = "") -> str:
    if not isinstance(value, str) or not value.strip():
        raise RraoInputError("non-empty text is required", field=field, position_id=position_id)
    return value


__all__ = [
    "NotionalSignConvention",
    "RraoInputError",
    "normalise_gross_effective_notional",
    "validate_rrao_positions",
]
