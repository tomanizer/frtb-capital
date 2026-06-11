"""Back-to-back exclusion validation for RRAO position rows."""

from __future__ import annotations

from frtb_rrao._validation_rules import (
    BACK_TO_BACK_CROSS_REFERENCE_MESSAGE,
    BACK_TO_BACK_MATCHING_CURRENCY_MESSAGE,
    BACK_TO_BACK_MATCHING_NOTIONAL_MESSAGE,
    BACK_TO_BACK_SELF_MATCH_MESSAGE,
    BACK_TO_BACK_SHARED_EVIDENCE_MESSAGE,
)
from frtb_rrao.data_models import RraoBackToBackMatch, RraoPosition
from frtb_rrao.numeric import is_reconciled
from frtb_rrao.validation._common import _require_text
from frtb_rrao.validation._errors import RraoInputError


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
                f"exact back-to-back match group must contain exactly two transactions: {joined}",
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
    if not is_reconciled(left.gross_effective_notional, right.gross_effective_notional):
        raise RraoInputError(
            BACK_TO_BACK_MATCHING_NOTIONAL_MESSAGE,
            field="gross_effective_notional",
            position_id=right.position_id,
        )
