"""Hierarchy and capital-node identity dataclasses."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime

from frtb_result_store.model_enums import (
    CapitalNodeFamily,
    FrtbComponent,
    ResultStoreContractError,
)
from frtb_result_store.model_validation import (
    _coerce_enum,
    _freeze_metadata,
    _normalize_identity_text,
    _require_int,
    _require_non_empty_text,
    _validate_optional_text,
)


@dataclass(frozen=True, slots=True)
class HierarchyLevel:
    """One configured business hierarchy level."""

    level_name: str
    dimension: str
    level_order: int

    def __post_init__(self) -> None:
        object.__setattr__(self, "level_name", _normalize_identity_text(self.level_name))
        object.__setattr__(self, "dimension", _normalize_identity_text(self.dimension))
        _require_int(self.level_order, "level_order")
        if self.level_order < 0:
            raise ResultStoreContractError("level_order must be non-negative", field="level_order")


@dataclass(frozen=True, slots=True)
class HierarchyDefinition:
    """Configured hierarchy shape used to generate deterministic hierarchy nodes."""

    hierarchy_id: str
    hierarchy_version: str
    hierarchy_name: str
    leaf_level: str
    levels: tuple[HierarchyLevel, ...]
    created_at: datetime
    metadata: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "hierarchy_id", _normalize_identity_text(self.hierarchy_id))
        object.__setattr__(
            self, "hierarchy_version", _normalize_identity_text(self.hierarchy_version)
        )
        object.__setattr__(self, "hierarchy_name", _normalize_identity_text(self.hierarchy_name))
        object.__setattr__(self, "leaf_level", _normalize_identity_text(self.leaf_level))
        if not isinstance(self.created_at, datetime):
            raise ResultStoreContractError("created_at must be a datetime", field="created_at")
        if self.created_at.tzinfo is None:
            raise ResultStoreContractError("created_at must be timezone-aware", field="created_at")
        ordered_levels = tuple(sorted(self.levels, key=lambda level: level.level_order))
        if not ordered_levels:
            raise ResultStoreContractError("levels must be non-empty", field="levels")
        level_names = [level.level_name for level in ordered_levels]
        if len(set(level_names)) != len(level_names):
            raise ResultStoreContractError("level names must be unique", field="levels")
        if self.leaf_level not in level_names:
            raise ResultStoreContractError(
                "leaf_level must name a hierarchy level",
                field="leaf_level",
            )
        object.__setattr__(self, "levels", ordered_levels)
        _freeze_metadata(self, self.metadata)

    @property
    def leaf_dimension(self) -> str:
        """Return the dimension that supplies the configured hierarchy leaf."""

        return next(level.dimension for level in self.levels if level.level_name == self.leaf_level)


@dataclass(frozen=True, slots=True)
class HierarchyNode:
    """One generated business hierarchy node."""

    hierarchy_id: str
    hierarchy_version: str
    hierarchy_node_id: str
    parent_hierarchy_node_id: str | None
    level_name: str
    level_order: int
    business_key: str
    label: str
    path: tuple[tuple[str, str], ...]
    metadata: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _require_non_empty_text(self.hierarchy_node_id, "hierarchy_node_id")
        _validate_optional_text(self.parent_hierarchy_node_id, "parent_hierarchy_node_id")
        for field_name in (
            "hierarchy_id",
            "hierarchy_version",
            "level_name",
            "business_key",
            "label",
        ):
            object.__setattr__(
                self,
                field_name,
                _normalize_identity_text(getattr(self, field_name)),
            )
        _require_int(self.level_order, "level_order")
        if not isinstance(self.path, tuple) or not self.path:
            raise ResultStoreContractError("path must be a non-empty tuple", field="path")
        normalized_path: list[tuple[str, str]] = []
        for level_name, business_key in self.path:
            normalized_path.append(
                (_normalize_identity_text(level_name), _normalize_identity_text(business_key))
            )
        object.__setattr__(self, "path", tuple(normalized_path))
        _freeze_metadata(self, self.metadata)


@dataclass(frozen=True, slots=True)
class CapitalNodeSpec:
    """Normalized dimensions used to generate one canonical capital node."""

    node_family: CapitalNodeFamily | str
    component: FrtbComponent | str
    label: str
    risk_class: str | None = None
    risk_measure: str | None = None
    bucket: str | None = None
    issuer_id: str | None = None
    counterparty_id: str | None = None
    hedge_set_id: str | None = None
    residual_risk_type: str | None = None
    exposure_category: str | None = None
    risk_factor_id: str | None = None
    risk_factor_set_id: str | None = None
    position_id: str | None = None
    calculation_branch: str | None = None
    regulatory_rule_id: str | None = None
    sort_key: int = 0
    metadata: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "node_family",
            _coerce_enum(self.node_family, CapitalNodeFamily, "node_family"),
        )
        object.__setattr__(
            self, "component", _coerce_enum(self.component, FrtbComponent, "component")
        )
        object.__setattr__(self, "label", _normalize_identity_text(self.label))
        for field_name in (
            "risk_class",
            "risk_measure",
            "bucket",
            "issuer_id",
            "counterparty_id",
            "hedge_set_id",
            "residual_risk_type",
            "exposure_category",
            "risk_factor_id",
            "risk_factor_set_id",
            "position_id",
            "calculation_branch",
            "regulatory_rule_id",
        ):
            value = getattr(self, field_name)
            if value is not None:
                object.__setattr__(self, field_name, _normalize_identity_text(value))
        _require_int(self.sort_key, "sort_key")
        _freeze_metadata(self, self.metadata)
