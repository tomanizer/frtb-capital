"""Organisational hierarchy model contracts."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import date
from enum import StrEnum

from frtb_common.hashing import stable_json_hash

from frtb_result_store.model_enums import FrtbComponent, ResultStoreContractError
from frtb_result_store.model_validation import (
    _coerce_enum,
    _freeze_mapping,
    _freeze_metadata,
    _normalize_identity_text,
    _require_finite_number,
    _require_plain_date,
    _validate_optional_text,
)


class OrgHierarchyLevel(StrEnum):
    """Supported enterprise hierarchy levels for result-store rollups."""

    TOH = "TOH"
    LEGAL_ENTITY = "LEGAL_ENTITY"
    BUSINESS_DIVISION = "BUSINESS_DIVISION"
    BUSINESS_LINE = "BUSINESS_LINE"
    DESK = "DESK"
    VOLCKER_DESK = "VOLCKER_DESK"
    BOOK = "BOOK"


@dataclass(frozen=True, slots=True)
class OrgHierarchyNode:
    """One effective-dated organisational hierarchy node."""

    hierarchy_id: str
    version_id: str
    node_id: str
    parent_id: str | None
    level: OrgHierarchyLevel | str
    label: str
    effective_from: date
    effective_to: date | None
    metadata: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for field_name in ("hierarchy_id", "version_id", "node_id", "label"):
            object.__setattr__(
                self,
                field_name,
                _normalize_identity_text(getattr(self, field_name)),
            )
        _validate_optional_text(self.parent_id, "parent_id")
        if self.parent_id is not None:
            object.__setattr__(
                self,
                "parent_id",
                _normalize_identity_text(self.parent_id),
            )
        object.__setattr__(self, "level", coerce_org_level(self.level, "level"))
        _require_plain_date(self.effective_from, "effective_from")
        if self.effective_to is not None:
            _require_plain_date(self.effective_to, "effective_to")
            if self.effective_to < self.effective_from:
                raise ResultStoreContractError(
                    "effective_to must be on or after effective_from",
                    field="effective_to",
                )
        _freeze_metadata(self, self.metadata)

    def active_on(self, as_of_date: date) -> bool:
        """Return whether this node is active for ``as_of_date``.

        Parameters
        ----------
        as_of_date:
            Run date used to test the node effective-dating window.

        Returns
        -------
        bool
            ``True`` when ``as_of_date`` falls inside the node date range.
        """

        _require_plain_date(as_of_date, "as_of_date")
        return self.effective_from <= as_of_date and (
            self.effective_to is None or as_of_date <= self.effective_to
        )


@dataclass(frozen=True, slots=True)
class OrgSliceKeys:
    """Stable organisational references for one stored capital fact."""

    hierarchy_id: str
    version_id: str
    toh_id: str
    legal_entity_id: str | None = None
    business_division_id: str | None = None
    business_line_id: str | None = None
    desk_id: str | None = None
    volcker_desk_id: str | None = None
    book_id: str | None = None

    def __post_init__(self) -> None:
        for field_name in ("hierarchy_id", "version_id", "toh_id"):
            object.__setattr__(
                self,
                field_name,
                _normalize_identity_text(getattr(self, field_name)),
            )
        for field_name in OPTIONAL_KEY_FIELDS:
            value = getattr(self, field_name)
            _validate_optional_text(value, field_name)
            if value is not None:
                object.__setattr__(self, field_name, _normalize_identity_text(value))


@dataclass(frozen=True, slots=True)
class OrgCapitalResultRow:
    """Synthetic read-model capital fact mapped to an organisation slice."""

    source_row_id: str
    run_id: str
    component: FrtbComponent | str
    capital: float
    currency: str
    org_keys: OrgSliceKeys
    source_hash: str | None = None
    metadata: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for field_name in ("source_row_id", "run_id", "currency"):
            object.__setattr__(
                self,
                field_name,
                _normalize_identity_text(getattr(self, field_name)),
            )
        object.__setattr__(self, "currency", self.currency.upper())
        object.__setattr__(
            self,
            "component",
            _coerce_enum(self.component, FrtbComponent, "component"),
        )
        object.__setattr__(self, "capital", _require_finite_number(self.capital, "capital"))
        if not isinstance(self.org_keys, OrgSliceKeys):
            raise ResultStoreContractError("org_keys must be OrgSliceKeys", field="org_keys")
        _validate_optional_text(self.source_hash, "source_hash")
        _freeze_metadata(self, self.metadata)


@dataclass(frozen=True, slots=True)
class OrgAggregateRow:
    """One deterministic organisation aggregate row for dashboard read APIs."""

    row_id: str
    parent_id: str | None
    label: str
    level: OrgHierarchyLevel | str
    node_id: str
    group_path: tuple[str, ...]
    capital: float | None
    currency: str
    source_row_count: int
    component_breakdown: Mapping[str, float]
    metadata: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for field_name in ("row_id", "label", "node_id", "currency"):
            object.__setattr__(
                self,
                field_name,
                _normalize_identity_text(getattr(self, field_name)),
            )
        _validate_optional_text(self.parent_id, "parent_id")
        object.__setattr__(self, "level", coerce_org_level(self.level, "level"))
        if not isinstance(self.group_path, tuple) or not all(
            isinstance(item, str) and item for item in self.group_path
        ):
            raise ResultStoreContractError(
                "group_path must be a tuple of non-empty text",
                field="group_path",
            )
        if self.capital is not None:
            object.__setattr__(self, "capital", _require_finite_number(self.capital, "capital"))
        if self.source_row_count < 0:
            raise ResultStoreContractError(
                "source_row_count must be non-negative",
                field="source_row_count",
            )
        _freeze_mapping(self, "component_breakdown", self.component_breakdown)
        _freeze_metadata(self, self.metadata)


@dataclass(frozen=True, slots=True)
class OrgHierarchy:
    """Versioned organisational hierarchy node set."""

    hierarchy_id: str
    nodes: tuple[OrgHierarchyNode, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "hierarchy_id", _normalize_identity_text(self.hierarchy_id))
        if not isinstance(self.nodes, tuple) or not self.nodes:
            raise ResultStoreContractError("nodes must be a non-empty tuple", field="nodes")
        for node in self.nodes:
            if not isinstance(node, OrgHierarchyNode):
                raise ResultStoreContractError(
                    "nodes must contain OrgHierarchyNode values",
                    field="nodes",
                )
            if node.hierarchy_id != self.hierarchy_id:
                raise ResultStoreContractError(
                    "node hierarchy_id must match hierarchy",
                    field="nodes",
                )


OPTIONAL_KEY_FIELDS = (
    "legal_entity_id",
    "business_division_id",
    "business_line_id",
    "desk_id",
    "volcker_desk_id",
    "book_id",
)
KEY_LEVELS: Mapping[str, OrgHierarchyLevel] = {
    "toh_id": OrgHierarchyLevel.TOH,
    "legal_entity_id": OrgHierarchyLevel.LEGAL_ENTITY,
    "business_division_id": OrgHierarchyLevel.BUSINESS_DIVISION,
    "business_line_id": OrgHierarchyLevel.BUSINESS_LINE,
    "desk_id": OrgHierarchyLevel.DESK,
    "volcker_desk_id": OrgHierarchyLevel.VOLCKER_DESK,
    "book_id": OrgHierarchyLevel.BOOK,
}


def coerce_org_level(value: OrgHierarchyLevel | str, field_name: str) -> OrgHierarchyLevel:
    """Coerce a public level value to ``OrgHierarchyLevel``.

    Parameters
    ----------
    value:
        Enum value or raw string supplied by a caller.
    field_name:
        Field name to include in validation errors.

    Returns
    -------
    OrgHierarchyLevel
        Canonical hierarchy level enum value.
    """

    if isinstance(value, OrgHierarchyLevel):
        return value
    try:
        return OrgHierarchyLevel(value)
    except ValueError as exc:
        allowed = ", ".join(level.value for level in OrgHierarchyLevel)
        raise ResultStoreContractError(
            f"{field_name} must be one of: {allowed}",
            field=field_name,
        ) from exc


def org_level_value(value: OrgHierarchyLevel | str) -> str:
    """Return the canonical string value for an org level.

    Parameters
    ----------
    value:
        Enum value or raw string supplied by a caller.

    Returns
    -------
    str
        Stable hierarchy level value.
    """

    return coerce_org_level(value, "level").value


def node_level(node: OrgHierarchyNode) -> OrgHierarchyLevel:
    """Return the canonical level for an org node.

    Parameters
    ----------
    node:
        Organisational hierarchy node to inspect.

    Returns
    -------
    OrgHierarchyLevel
        Canonical node level enum value.
    """

    return coerce_org_level(node.level, "level")


def component_value(value: FrtbComponent | str) -> str:
    """Return the canonical component string for an org capital row.

    Parameters
    ----------
    value:
        Component enum value or raw component string.

    Returns
    -------
    str
        Stable FRTB component value.
    """

    return _coerce_enum(value, FrtbComponent, "component").value


def generate_org_aggregate_row_id(node: OrgHierarchyNode) -> str:
    """Return a deterministic URL-safe aggregate row ID for ``node``.

    Parameters
    ----------
    node:
        Hierarchy node represented by the aggregate row.

    Returns
    -------
    str
        URL-safe deterministic aggregate row identifier.
    """

    payload = {
        "hierarchy_id": node.hierarchy_id,
        "version_id": node.version_id,
        "node_id": node.node_id,
        "level": org_level_value(node.level),
    }
    return f"orgagg_{stable_json_hash(payload)}"


__all__ = [
    "KEY_LEVELS",
    "OPTIONAL_KEY_FIELDS",
    "OrgAggregateRow",
    "OrgCapitalResultRow",
    "OrgHierarchy",
    "OrgHierarchyLevel",
    "OrgHierarchyNode",
    "OrgSliceKeys",
    "coerce_org_level",
    "component_value",
    "generate_org_aggregate_row_id",
    "node_level",
    "org_level_value",
]
