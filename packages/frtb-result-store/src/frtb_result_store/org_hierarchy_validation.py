"""Validation helpers for organisational hierarchy read models."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping, Sequence
from datetime import date

from frtb_result_store.model_enums import ResultStoreContractError
from frtb_result_store.model_validation import _require_non_empty_text, _require_plain_date
from frtb_result_store.org_hierarchy_model import (
    KEY_LEVELS,
    OPTIONAL_KEY_FIELDS,
    OrgCapitalResultRow,
    OrgHierarchy,
    OrgHierarchyLevel,
    OrgHierarchyNode,
    OrgSliceKeys,
    node_level,
)


def validate_org_hierarchy(
    hierarchy: OrgHierarchy,
    rows: Sequence[OrgCapitalResultRow] = (),
    *,
    as_of_date: date | None = None,
) -> None:
    """Validate organisation nodes and optional row mappings.

    Parameters
    ----------
    hierarchy:
        Versioned hierarchy to validate.
    rows:
        Optional capital rows whose organisation keys must resolve into the
        hierarchy.
    as_of_date:
        Optional run date that must resolve to exactly one hierarchy version.
    """

    nodes_by_version = _nodes_by_version(hierarchy)
    for version_key, nodes in nodes_by_version.items():
        _validate_version_nodes(version_key, nodes)
    if as_of_date is not None:
        resolve_org_hierarchy_version(hierarchy, as_of_date)
    node_index = _node_index(hierarchy.nodes)
    version_node_maps = {
        version_key: single_version_node_map(nodes)
        for version_key, nodes in nodes_by_version.items()
    }
    for row in rows:
        _validate_row_mapping(row, node_index, version_node_maps)


def resolve_org_hierarchy_version(hierarchy: OrgHierarchy, as_of_date: date) -> str:
    """Return the one hierarchy version active for ``as_of_date``.

    Parameters
    ----------
    hierarchy:
        Versioned hierarchy to inspect.
    as_of_date:
        Run date used to select the effective hierarchy version.

    Returns
    -------
    str
        Active hierarchy version identifier.
    """

    _require_plain_date(as_of_date, "as_of_date")
    roots = [
        node
        for node in hierarchy.nodes
        if (
            node_level(node) is OrgHierarchyLevel.TOH
            and node.parent_id is None
            and node.active_on(as_of_date)
        )
    ]
    version_ids = sorted({node.version_id for node in roots})
    if len(version_ids) != 1:
        raise ResultStoreContractError(
            "as_of_date must resolve to exactly one hierarchy version",
            field="as_of_date",
        )
    return version_ids[0]


def nodes_by_version(
    hierarchy: OrgHierarchy,
) -> dict[tuple[str, str], tuple[OrgHierarchyNode, ...]]:
    """Return hierarchy nodes grouped by hierarchy and version.

    Parameters
    ----------
    hierarchy:
        Versioned hierarchy to group.

    Returns
    -------
    dict[tuple[str, str], tuple[OrgHierarchyNode, ...]]
        Nodes keyed by ``(hierarchy_id, version_id)``.
    """

    return _nodes_by_version(hierarchy)


def single_version_node_map(nodes: Sequence[OrgHierarchyNode]) -> dict[str, OrgHierarchyNode]:
    """Return a node-id map for one hierarchy version.

    Parameters
    ----------
    nodes:
        Nodes from one hierarchy version.

    Returns
    -------
    dict[str, OrgHierarchyNode]
        Nodes keyed by ``node_id``.
    """

    return {node.node_id: node for node in nodes}


def ancestor_chain(
    node_id: str,
    node_map: Mapping[str, OrgHierarchyNode],
) -> tuple[OrgHierarchyNode, ...]:
    """Return the root-to-node ancestor chain for ``node_id``.

    Parameters
    ----------
    node_id:
        Leaf or intermediate node to resolve.
    node_map:
        Nodes from one hierarchy version keyed by ``node_id``.

    Returns
    -------
    tuple[OrgHierarchyNode, ...]
        Root-to-node chain including the requested node.
    """

    if node_id not in node_map:
        raise ResultStoreContractError(
            f"org hierarchy node not found: {node_id}",
            field="node_id",
        )
    chain_reversed: list[OrgHierarchyNode] = []
    visiting: set[str] = set()
    current_id: str | None = node_id
    while current_id is not None:
        if current_id in visiting:
            raise ResultStoreContractError("org hierarchy contains a cycle", field="nodes")
        visiting.add(current_id)
        node = node_map[current_id]
        chain_reversed.append(node)
        current_id = node.parent_id
        if current_id is not None and current_id not in node_map:
            raise ResultStoreContractError(
                f"parent node not found: {current_id}",
                field="parent_id",
            )
    return tuple(reversed(chain_reversed))


def deepest_node_id(keys: OrgSliceKeys) -> str:
    """Return the lowest supplied organisation key.

    Parameters
    ----------
    keys:
        Organisation slice keys for one source row.

    Returns
    -------
    str
        Deepest supplied node identifier.
    """

    for field_name in (
        "book_id",
        "volcker_desk_id",
        "desk_id",
        "business_line_id",
        "business_division_id",
        "legal_entity_id",
        "toh_id",
    ):
        node_id = getattr(keys, field_name)
        if isinstance(node_id, str):
            return node_id
    return keys.toh_id


def _nodes_by_version(
    hierarchy: OrgHierarchy,
) -> dict[tuple[str, str], tuple[OrgHierarchyNode, ...]]:
    grouped: dict[tuple[str, str], list[OrgHierarchyNode]] = defaultdict(list)
    for node in hierarchy.nodes:
        grouped[(node.hierarchy_id, node.version_id)].append(node)
    return {version_key: tuple(nodes) for version_key, nodes in grouped.items()}


def _node_index(
    nodes: Sequence[OrgHierarchyNode],
) -> dict[tuple[str, str, str], OrgHierarchyNode]:
    return {(node.hierarchy_id, node.version_id, node.node_id): node for node in nodes}


def _validate_version_nodes(
    version_key: tuple[str, str],
    nodes: Sequence[OrgHierarchyNode],
) -> None:
    seen: set[str] = set()
    duplicate_ids_set: set[str] = set()
    for node in nodes:
        if node.node_id in seen:
            duplicate_ids_set.add(node.node_id)
        else:
            seen.add(node.node_id)
    duplicate_ids = sorted(duplicate_ids_set)
    if duplicate_ids:
        raise ResultStoreContractError(
            f"duplicate org hierarchy nodes: {', '.join(duplicate_ids)}",
            field="nodes",
        )
    roots = [
        node
        for node in nodes
        if node_level(node) is OrgHierarchyLevel.TOH and node.parent_id is None
    ]
    if len(roots) != 1:
        raise ResultStoreContractError(
            "each hierarchy version must have exactly one TOH root",
            field="nodes",
        )
    node_map = single_version_node_map(nodes)
    for node in nodes:
        if node_level(node) is OrgHierarchyLevel.TOH:
            if node.parent_id is not None:
                raise ResultStoreContractError(
                    "TOH root must not have a parent",
                    field="parent_id",
                )
            continue
        if node.parent_id not in node_map:
            raise ResultStoreContractError(
                f"parent node not found in hierarchy version {version_key[1]}: {node.parent_id}",
                field="parent_id",
            )
    for node in nodes:
        ancestor_chain(node.node_id, node_map)


def _validate_row_mapping(
    row: OrgCapitalResultRow,
    node_index: Mapping[tuple[str, str, str], OrgHierarchyNode],
    version_node_maps: Mapping[tuple[str, str], Mapping[str, OrgHierarchyNode]],
) -> None:
    if not isinstance(row, OrgCapitalResultRow):
        raise ResultStoreContractError("rows must contain OrgCapitalResultRow values", field="rows")
    keys = row.org_keys
    supplied_ids = _supplied_node_ids(keys)
    for field_name, node_id in supplied_ids.items():
        node = node_index.get((keys.hierarchy_id, keys.version_id, node_id))
        if node is None:
            raise ResultStoreContractError(
                f"{field_name} does not identify an org hierarchy node: {node_id}",
                field=field_name,
            )
        expected_level = KEY_LEVELS[field_name]
        if node_level(node) is not expected_level:
            raise ResultStoreContractError(
                f"{field_name} must identify a {expected_level.value} node",
                field=field_name,
            )
    node_map = version_node_maps.get((keys.hierarchy_id, keys.version_id))
    if node_map is None:
        raise ResultStoreContractError(
            f"hierarchy version not found: {keys.version_id}",
            field="version_id",
        )
    chain_ids = {node.node_id for node in ancestor_chain(deepest_node_id(keys), node_map)}
    for field_name, node_id in supplied_ids.items():
        if node_id not in chain_ids:
            raise ResultStoreContractError(
                f"{field_name} is not an ancestor of the mapped source row grain",
                field=field_name,
            )


def _supplied_node_ids(keys: OrgSliceKeys) -> dict[str, str]:
    _require_non_empty_text(keys.toh_id, "toh_id")
    supplied = {"toh_id": keys.toh_id}
    for field_name in OPTIONAL_KEY_FIELDS:
        node_id = getattr(keys, field_name)
        if node_id is not None:
            supplied[field_name] = node_id
    return supplied


__all__ = [
    "ancestor_chain",
    "deepest_node_id",
    "nodes_by_version",
    "resolve_org_hierarchy_version",
    "single_version_node_map",
    "validate_org_hierarchy",
]
