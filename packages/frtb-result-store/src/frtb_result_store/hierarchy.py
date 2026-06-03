"""Canonical business hierarchy construction helpers."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime

from frtb_common.hashing import stable_json_hash

from frtb_result_store.model import (
    HierarchyDefinition,
    HierarchyLevel,
    HierarchyNode,
    ResultStoreContractError,
    _normalize_identity_text,
    _normalize_identity_value,
)

__all__ = [
    "build_hierarchy_nodes",
    "default_hierarchy_definition",
    "generate_hierarchy_node_id",
]

DEFAULT_HIERARCHY_LEVELS = (
    ("firm", "firm_id", 0),
    ("legal_entity", "legal_entity_id", 1),
    ("business_line", "business_line_id", 2),
    ("desk", "desk_id", 3),
    ("portfolio", "portfolio_id", 4),
    ("book", "book_id", 5),
)


def default_hierarchy_definition(*, created_at: datetime) -> HierarchyDefinition:
    """Return the default firm-to-book hierarchy definition."""

    return HierarchyDefinition(
        hierarchy_id="default",
        hierarchy_version="1",
        hierarchy_name="Default firm-to-book hierarchy",
        leaf_level="book",
        levels=tuple(HierarchyLevel(*level) for level in DEFAULT_HIERARCHY_LEVELS),
        created_at=created_at,
    )


def generate_hierarchy_node_id(
    *,
    hierarchy_id: str,
    hierarchy_version: str,
    level_name: str,
    path: Sequence[tuple[str, object]],
) -> str:
    """Generate a canonical hierarchy node id from a structured path payload."""

    if not path:
        raise ResultStoreContractError("path must be non-empty", field="path")
    payload = {
        "node_family": "hierarchy",
        "schema_version": 1,
        "hierarchy_id": _normalize_identity_text(hierarchy_id),
        "hierarchy_version": _normalize_identity_text(hierarchy_version),
        "level_name": _normalize_identity_text(level_name),
        "path": _normalized_path(path),
    }
    return f"hierarchy:{stable_json_hash(payload)}"


def build_hierarchy_nodes(
    definition: HierarchyDefinition,
    dimensions: Mapping[str, object],
    *,
    labels: Mapping[str, str] | None = None,
) -> tuple[HierarchyNode, ...]:
    """Generate hierarchy nodes and parent links from business dimensions."""

    if not isinstance(definition, HierarchyDefinition):
        raise ResultStoreContractError(
            "definition must be a HierarchyDefinition",
            field="definition",
        )
    label_by_dimension = {} if labels is None else dict(labels)
    path: list[tuple[str, str]] = []
    nodes: list[HierarchyNode] = []
    parent_id: str | None = None
    for level in definition.levels:
        business_key = _business_key_for_level(level, dimensions)
        path.append((level.level_name, business_key))
        node_id = generate_hierarchy_node_id(
            hierarchy_id=definition.hierarchy_id,
            hierarchy_version=definition.hierarchy_version,
            level_name=level.level_name,
            path=path,
        )
        nodes.append(
            HierarchyNode(
                hierarchy_id=definition.hierarchy_id,
                hierarchy_version=definition.hierarchy_version,
                hierarchy_node_id=node_id,
                parent_hierarchy_node_id=parent_id,
                level_name=level.level_name,
                level_order=level.level_order,
                business_key=business_key,
                label=label_by_dimension.get(level.dimension, business_key),
                path=tuple(path),
            )
        )
        parent_id = node_id
        if level.level_name == definition.leaf_level:
            break
    return tuple(nodes)


def _business_key_for_level(
    level: HierarchyLevel,
    dimensions: Mapping[str, object],
) -> str:
    if level.dimension not in dimensions:
        raise ResultStoreContractError(
            f"missing hierarchy dimension: {level.dimension}",
            field=level.dimension,
        )
    business_key = _normalize_identity_value(dimensions[level.dimension], level.dimension)
    if not isinstance(business_key, str):
        raise ResultStoreContractError(
            f"{level.dimension} must normalize to text",
            field=level.dimension,
        )
    return business_key


def _normalized_path(path: Sequence[tuple[str, object]]) -> tuple[dict[str, object], ...]:
    return tuple(
        {
            "level_name": _normalize_identity_text(path_level),
            "business_key": _normalize_identity_value(path_value, "business_key"),
        }
        for path_level, path_value in path
    )
