"""Row-field projection helpers for RRAO batch ingress."""

from __future__ import annotations

import numpy as np

from frtb_rrao._validation_rules import (
    UNDERLYING_COUNT_INTEGER_MESSAGE,
    UNDERLYING_COUNT_NON_NEGATIVE_MESSAGE,
    is_valid_underlying_count,
)
from frtb_rrao.data_models import (
    RraoBackToBackMatch,
    RraoInvestmentFundDescriptor,
    RraoPosition,
    RraoSourceLineage,
)
from frtb_rrao.validation._errors import RraoInputError


def _lineage_source_system(position: RraoPosition) -> str:
    """Return validated lineage source-system text for batch columns."""

    lineage = _lineage(position)
    return (
        ""
        if lineage is None
        else _required_row_text(
            lineage.source_system,
            "lineage.source_system",
            position,
        )
    )


def _lineage_source_file(position: RraoPosition) -> str:
    """Return validated lineage source-file text for batch columns."""

    lineage = _lineage(position)
    return (
        ""
        if lineage is None
        else _required_row_text(
            lineage.source_file,
            "lineage.source_file",
            position,
        )
    )


def _lineage_source_row_id(position: RraoPosition) -> str:
    """Return validated lineage source-row text for batch columns."""

    lineage = _lineage(position)
    return (
        ""
        if lineage is None
        else _required_row_text(
            lineage.source_row_id,
            "lineage.source_row_id",
            position,
        )
    )


def _source_column_map(position: RraoPosition) -> tuple[tuple[str, str], ...]:
    """Return validated lineage source-column mappings for batch columns."""

    lineage = _lineage(position)
    if lineage is None:
        return ()
    pairs: list[tuple[str, str]] = []
    for mapping in lineage.source_column_map:
        if not isinstance(mapping, tuple) or len(mapping) != 2:
            raise RraoInputError(
                "source column map entries must be field pairs",
                field="lineage.source_column_map",
                position_id=_position_id(position),
            )
        source, target = mapping
        pairs.append(
            (
                _required_row_text(source, "lineage.source_column_map.source", position),
                _required_row_text(target, "lineage.source_column_map.canonical", position),
            )
        )
    return tuple(pairs)


def _investment_fund_id(position: RraoPosition) -> str | None:
    """Return validated investment-fund id for batch columns."""

    descriptor = _investment_fund_descriptor(position)
    if descriptor is None:
        return None
    return _required_row_text(descriptor.fund_id, "investment_fund_descriptor.fund_id", position)


def _investment_fund_mandate_evidence_id(position: RraoPosition) -> str | None:
    """Return validated investment-fund mandate evidence id."""

    descriptor = _investment_fund_descriptor(position)
    if descriptor is None:
        return None
    return _required_row_text(
        descriptor.mandate_evidence_id,
        "investment_fund_descriptor.mandate_evidence_id",
        position,
    )


def _investment_fund_section_205_evidence_id(position: RraoPosition) -> str | None:
    """Return validated investment-fund section 205 evidence id."""

    descriptor = _investment_fund_descriptor(position)
    if descriptor is None:
        return None
    return _required_row_text(
        descriptor.section_205_evidence_id,
        "investment_fund_descriptor.section_205_evidence_id",
        position,
    )


def _investment_fund_gross_effective_notional(position: RraoPosition) -> float | None:
    """Return investment-fund gross effective notional for batch columns."""

    descriptor = _investment_fund_descriptor(position)
    if descriptor is None:
        return None
    return descriptor.fund_gross_effective_notional


def _investment_fund_included_exposure_ratio(position: RraoPosition) -> float | None:
    """Return investment-fund included exposure ratio for batch columns."""

    descriptor = _investment_fund_descriptor(position)
    if descriptor is None:
        return None
    return descriptor.included_exposure_ratio


def _investment_fund_look_through_available(position: RraoPosition) -> bool:
    """Return validated investment-fund look-through flag."""

    descriptor = _investment_fund_descriptor(position)
    if descriptor is None:
        return False
    _require_row_bool(
        descriptor.look_through_available,
        "investment_fund_descriptor.look_through_available",
        position,
    )
    return descriptor.look_through_available


def _investment_fund_mandate_allows_rrao_exposures(position: RraoPosition) -> bool:
    """Return validated investment-fund mandate flag."""

    descriptor = _investment_fund_descriptor(position)
    if descriptor is None:
        return True
    _require_row_bool(
        descriptor.mandate_allows_rrao_exposures,
        "investment_fund_descriptor.mandate_allows_rrao_exposures",
        position,
    )
    return descriptor.mandate_allows_rrao_exposures


def _back_to_back_match_group_id(position: RraoPosition) -> str | None:
    """Return validated back-to-back match group id."""

    match = _back_to_back_match(position)
    if match is None:
        return None
    return _required_row_text(match.match_group_id, "back_to_back_match.match_group_id", position)


def _back_to_back_matched_position_id(position: RraoPosition) -> str | None:
    """Return validated back-to-back matched position id."""

    match = _back_to_back_match(position)
    if match is None:
        return None
    return _required_row_text(
        match.matched_position_id,
        "back_to_back_match.matched_position_id",
        position,
    )


def _required_row_text(value: object | None, field: str, position: RraoPosition) -> str:
    """Return non-empty canonical text or raise a row-shaped input error."""

    if value is None:
        raise RraoInputError(
            "non-empty text is required",
            field=field,
            position_id=_position_id(position),
        )
    text = str(value).strip()
    if not text:
        raise RraoInputError(
            "non-empty text is required",
            field=field,
            position_id=_position_id(position),
        )
    return text


def _enum_value(
    value: object,
    enum_type: type,
    *,
    field: str,
    position: RraoPosition,
) -> str:
    """Return an enum wire value or raise a row-shaped input error."""

    if not isinstance(value, enum_type):
        message = f"invalid {field.replace('_', ' ')}"
        if field == "investment_fund_descriptor.included_exposure_type":
            message = "invalid investment fund exposure type"
        raise RraoInputError(
            message,
            field=field,
            position_id=_position_id(position),
        )
    return value.value  # type: ignore[no-any-return]


def _optional_row_int(value: object | None, field: str, position: RraoPosition) -> int | None:
    """Return an optional integer field using row-compatible error messages."""

    if value is None:
        return None
    if isinstance(value, (bool, np.bool_)) or not isinstance(value, (int, np.integer)):
        raise RraoInputError(
            UNDERLYING_COUNT_INTEGER_MESSAGE,
            field=field,
            position_id=_position_id(position),
        )
    integer = int(value)
    if not is_valid_underlying_count(integer):
        raise RraoInputError(
            UNDERLYING_COUNT_NON_NEGATIVE_MESSAGE,
            field=field,
            position_id=_position_id(position),
        )
    return integer


def _optional_row_bool(value: object | None, field: str, position: RraoPosition) -> bool | None:
    """Return an optional boolean field using row-compatible error messages."""

    if value is None:
        return None
    return _require_row_bool(value, field, position)


def _require_row_bool(value: object, field: str, position: RraoPosition) -> bool:
    """Return a boolean field using row-compatible error messages."""

    if not isinstance(value, (bool, np.bool_)):
        message = f"{field} must be a bool"
        if field == "investment_fund_descriptor.look_through_available":
            message = "look-through availability must be a bool"
        elif field == "investment_fund_descriptor.mandate_allows_rrao_exposures":
            message = "mandate RRAO exposure flag must be a bool"
        raise RraoInputError(
            message,
            field=field,
            position_id=_position_id(position),
        )
    return bool(value)


def _citations(position: RraoPosition) -> tuple[str, ...]:
    """Return validated citation labels for batch columns."""

    return tuple(
        _required_row_text(citation, "citations", position) for citation in position.citations
    )


def _back_to_back_match(position: RraoPosition) -> RraoBackToBackMatch | None:
    """Return validated back-to-back match payload when present."""

    match = position.back_to_back_match
    if match is None:
        return None
    if not isinstance(match, RraoBackToBackMatch):
        raise RraoInputError(
            "invalid back-to-back match evidence",
            field="back_to_back_match",
            position_id=_position_id(position),
        )
    return match


def _investment_fund_descriptor(position: RraoPosition) -> RraoInvestmentFundDescriptor | None:
    """Return validated investment-fund descriptor when present."""

    descriptor = position.investment_fund_descriptor
    if descriptor is None:
        return None
    if not isinstance(descriptor, RraoInvestmentFundDescriptor):
        raise RraoInputError(
            "invalid investment fund descriptor",
            field="investment_fund_descriptor",
            position_id=_position_id(position),
        )
    return descriptor


def _lineage(position: RraoPosition) -> RraoSourceLineage | None:
    lineage = position.lineage
    if lineage is None:
        return None
    if not isinstance(lineage, RraoSourceLineage):
        raise RraoInputError(
            "invalid source lineage",
            field="lineage",
            position_id=_position_id(position),
        )
    return lineage


def _position_id(position: RraoPosition) -> str:
    return str(position.position_id) if position.position_id is not None else ""
