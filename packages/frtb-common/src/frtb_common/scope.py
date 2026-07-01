"""Shared organisation identifiers and calculation scope metadata.

This module defines package-neutral identifiers that component packages may
preserve on inputs, outputs, and audit records.  It deliberately does not
encode hierarchy traversal, parent-child edges, or rollup rules; those belong
to result-store read models and orchestration layers.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from types import MappingProxyType
from typing import NewType, TypeVar

from frtb_common.serialization import dataclass_as_dict

LegalEntityId = NewType("LegalEntityId", str)
BusinessDivisionId = NewType("BusinessDivisionId", str)
BusinessLineId = NewType("BusinessLineId", str)
DeskId = NewType("DeskId", str)
VolckerDeskId = NewType("VolckerDeskId", str)
BookId = NewType("BookId", str)
TradingBookId = NewType("TradingBookId", str)
PortfolioId = NewType("PortfolioId", str)
HierarchyNodeId = NewType("HierarchyNodeId", str)
ModelApprovalScopeId = NewType("ModelApprovalScopeId", str)

_EnumT = TypeVar("_EnumT", bound=StrEnum)


class CalculationScopeLevel(StrEnum):
    """Package-neutral level at which a calculation or stored view is scoped."""

    TOP_OF_HOUSE = "TOP_OF_HOUSE"
    LEGAL_ENTITY = "LEGAL_ENTITY"
    BUSINESS_DIVISION = "BUSINESS_DIVISION"
    BUSINESS_LINE = "BUSINESS_LINE"
    DESK = "DESK"
    VOLCKER_DESK = "VOLCKER_DESK"
    BOOK = "BOOK"
    TRADING_BOOK = "TRADING_BOOK"
    PORTFOLIO = "PORTFOLIO"
    MODEL_APPROVAL_SCOPE = "MODEL_APPROVAL_SCOPE"
    HIERARCHY_NODE = "HIERARCHY_NODE"


@dataclass(frozen=True, slots=True)
class CalculationScope:
    """Stable metadata identifying the organisational scope of a calculation.

    Components may attach this object, or its serialized fields, to records so
    downstream result-store views can aggregate by legal entity, division, desk,
    Volcker desk, book, trading book, or hierarchy node.  A scope is metadata
    only; it contains no parent-child graph and performs no rollup traversal.
    """

    level: CalculationScopeLevel | str
    legal_entity_id: str | None = None
    business_division_id: str | None = None
    business_line_id: str | None = None
    desk_id: str | None = None
    volcker_desk_id: str | None = None
    book_id: str | None = None
    trading_book_id: str | None = None
    portfolio_id: str | None = None
    hierarchy_node_id: str | None = None
    model_approval_scope_id: str | None = None
    metadata: Mapping[str, str] | None = field(default_factory=dict)

    def __post_init__(self) -> None:
        level = _coerce_enum(self.level, CalculationScopeLevel, "level")
        object.__setattr__(self, "level", level)
        for field_name in _IDENTIFIER_FIELDS:
            object.__setattr__(
                self,
                field_name,
                _optional_identifier(getattr(self, field_name), field_name),
            )
        object.__setattr__(self, "metadata", _freeze_metadata(self.metadata))
        _require_scope_identifier(self)

    def as_dict(self) -> dict[str, object]:
        """Return a JSON-serialisable dictionary representation.

        Returns
        -------
        dict[str, object]
            Dataclass field names mapped through
            :func:`frtb_common.serialization.jsonable`.
        """

        return dataclass_as_dict(self)


_IDENTIFIER_FIELDS = (
    "legal_entity_id",
    "business_division_id",
    "business_line_id",
    "desk_id",
    "volcker_desk_id",
    "book_id",
    "trading_book_id",
    "portfolio_id",
    "hierarchy_node_id",
    "model_approval_scope_id",
)

_SCOPE_REQUIRED_IDENTIFIERS: Mapping[CalculationScopeLevel, tuple[str, ...]] = {
    CalculationScopeLevel.LEGAL_ENTITY: ("legal_entity_id",),
    CalculationScopeLevel.BUSINESS_DIVISION: ("business_division_id",),
    CalculationScopeLevel.BUSINESS_LINE: ("business_line_id",),
    CalculationScopeLevel.DESK: ("desk_id",),
    CalculationScopeLevel.VOLCKER_DESK: ("volcker_desk_id",),
    CalculationScopeLevel.BOOK: ("book_id",),
    CalculationScopeLevel.TRADING_BOOK: ("trading_book_id",),
    CalculationScopeLevel.PORTFOLIO: ("portfolio_id",),
    CalculationScopeLevel.MODEL_APPROVAL_SCOPE: ("model_approval_scope_id",),
    CalculationScopeLevel.HIERARCHY_NODE: ("hierarchy_node_id",),
}


def _coerce_enum(value: _EnumT | str, enum_type: type[_EnumT], field_name: str) -> _EnumT:
    if isinstance(value, enum_type):
        return value
    try:
        return enum_type(value)
    except ValueError as exc:
        allowed = ", ".join(item.value for item in enum_type)
        raise ValueError(f"{field_name} must be one of: {allowed}") from exc


def _optional_identifier(value: object, field_name: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or isinstance(value, bool):
        raise TypeError(f"{field_name} must be text when supplied")
    if not value:
        raise ValueError(f"{field_name} must not be empty")
    if value != value.strip():
        raise ValueError(f"{field_name} must not contain leading or trailing whitespace")
    return value


def _freeze_metadata(metadata: object) -> Mapping[str, str]:
    if metadata is None:
        return MappingProxyType({})
    if not isinstance(metadata, Mapping):
        raise TypeError("metadata must be a mapping of strings to strings")
    frozen: dict[str, str] = {}
    for key, value in metadata.items():
        if not isinstance(key, str) or not key:
            raise ValueError("metadata keys must be non-empty text")
        if not isinstance(value, str):
            raise TypeError("metadata values must be text")
        frozen[key] = value
    return MappingProxyType(dict(sorted(frozen.items())))


def _require_scope_identifier(scope: CalculationScope) -> None:
    level = _coerce_enum(scope.level, CalculationScopeLevel, "level")
    required_fields = _SCOPE_REQUIRED_IDENTIFIERS.get(level, ())
    if required_fields and not any(getattr(scope, field_name) for field_name in required_fields):
        names = " or ".join(required_fields)
        raise ValueError(f"{level.value} scope requires {names}")
