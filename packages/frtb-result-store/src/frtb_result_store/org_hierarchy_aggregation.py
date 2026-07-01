"""Aggregation helpers for organisational hierarchy read models."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Sequence
from datetime import date

from frtb_result_store.model_enums import ResultStoreContractError
from frtb_result_store.model_validation import _require_non_empty_text
from frtb_result_store.org_hierarchy_model import (
    OrgAggregateRow,
    OrgCapitalResultRow,
    OrgHierarchy,
    OrgHierarchyLevel,
    OrgHierarchyNode,
    coerce_org_level,
    component_value,
    generate_org_aggregate_row_id,
    node_level,
    org_level_value,
)
from frtb_result_store.org_hierarchy_validation import (
    ancestor_chain,
    deepest_node_id,
    resolve_org_hierarchy_version,
    single_version_node_map,
    validate_org_hierarchy,
)


def aggregate_by_org_hierarchy(
    rows: Sequence[OrgCapitalResultRow],
    hierarchy: OrgHierarchy,
    grouping: Sequence[OrgHierarchyLevel | str],
    *,
    as_of_date: date,
) -> list[OrgAggregateRow]:
    """Aggregate source rows by requested organisation levels.

    Parameters
    ----------
    rows:
        Capital source rows mapped with organisation slice keys.
    hierarchy:
        Versioned hierarchy used to resolve ancestors and parent rows.
    grouping:
        Organisation levels to project into aggregate rows.
    as_of_date:
        Run date used to select the effective hierarchy version.

    Returns
    -------
    list[OrgAggregateRow]
        Deterministic aggregate rows with parent IDs and source counts.
    """

    selected_levels = tuple(coerce_org_level(level, "grouping") for level in grouping)
    if not selected_levels:
        raise ResultStoreContractError("grouping must be non-empty", field="grouping")
    version_id = resolve_org_hierarchy_version(hierarchy, as_of_date)
    active_nodes = tuple(
        node
        for node in hierarchy.nodes
        if node.version_id == version_id and node.active_on(as_of_date)
    )
    scoped_rows = tuple(
        row
        for row in rows
        if row.org_keys.hierarchy_id == hierarchy.hierarchy_id
        and row.org_keys.version_id == version_id
    )
    active_hierarchy = OrgHierarchy(hierarchy_id=hierarchy.hierarchy_id, nodes=active_nodes)
    validate_org_hierarchy(active_hierarchy, scoped_rows, as_of_date=as_of_date)

    node_map = single_version_node_map(active_nodes)
    contribution_rows: dict[str, list[OrgCapitalResultRow]] = defaultdict(list)
    for row in scoped_rows:
        chain = ancestor_chain(deepest_node_id(row.org_keys), node_map)
        for node in chain:
            if any(
                _node_matches_grouping_level(node_level(node), level) for level in selected_levels
            ):
                contribution_rows[node.node_id].append(row)

    aggregates = _aggregate_rows(contribution_rows, node_map, selected_levels)
    return sorted(
        aggregates,
        key=lambda row: (row.group_path, org_level_value(row.level), row.node_id),
    )


def source_rows_for_org_aggregate(
    aggregate_row_id: str,
    rows: Sequence[OrgCapitalResultRow],
    hierarchy: OrgHierarchy,
) -> list[OrgCapitalResultRow]:
    """Return source rows that contribute to an organisation aggregate row.

    Parameters
    ----------
    aggregate_row_id:
        Deterministic aggregate row identifier returned by aggregation.
    rows:
        Candidate source rows to filter.
    hierarchy:
        Versioned hierarchy used to identify descendant rows.

    Returns
    -------
    list[OrgCapitalResultRow]
        Source rows under the selected aggregate branch.
    """

    _require_non_empty_text(aggregate_row_id, "aggregate_row_id")
    validate_org_hierarchy(hierarchy)
    target_node = next(
        (
            node
            for node in hierarchy.nodes
            if generate_org_aggregate_row_id(node) == aggregate_row_id
        ),
        None,
    )
    if target_node is None:
        raise ResultStoreContractError(
            "aggregate_row_id does not identify an organisation aggregate",
            field="aggregate_row_id",
        )
    scoped_nodes = tuple(
        node for node in hierarchy.nodes if node.version_id == target_node.version_id
    )
    candidate_rows = tuple(
        row
        for row in rows
        if row.org_keys.hierarchy_id == target_node.hierarchy_id
        and row.org_keys.version_id == target_node.version_id
    )
    target_hierarchy = OrgHierarchy(
        hierarchy_id=target_node.hierarchy_id,
        nodes=scoped_nodes,
    )
    validate_org_hierarchy(target_hierarchy, candidate_rows)
    node_map = single_version_node_map(scoped_nodes)
    scoped_rows: list[OrgCapitalResultRow] = []
    for row in candidate_rows:
        chain = ancestor_chain(deepest_node_id(row.org_keys), node_map)
        if any(node.node_id == target_node.node_id for node in chain):
            scoped_rows.append(row)
    return sorted(scoped_rows, key=lambda row: row.source_row_id)


def _aggregate_rows(
    contribution_rows: dict[str, list[OrgCapitalResultRow]],
    node_map: dict[str, OrgHierarchyNode],
    selected_levels: Sequence[OrgHierarchyLevel],
) -> list[OrgAggregateRow]:
    aggregates: list[OrgAggregateRow] = []
    for node_id in sorted(contribution_rows):
        node = node_map[node_id]
        source_rows = tuple(sorted(contribution_rows[node_id], key=lambda item: item.source_row_id))
        parent = _nearest_selected_parent(node, node_map, selected_levels)
        aggregates.append(
            OrgAggregateRow(
                row_id=generate_org_aggregate_row_id(node),
                parent_id=generate_org_aggregate_row_id(parent) if parent else None,
                label=node.label,
                level=node.level,
                node_id=node.node_id,
                group_path=tuple(
                    item.node_id for item in _selected_chain(node, node_map, selected_levels)
                ),
                capital=sum(row.capital for row in source_rows),
                currency=_single_currency(source_rows),
                source_row_count=len(source_rows),
                component_breakdown=_component_breakdown(source_rows),
                metadata=node.metadata,
            )
        )
    return aggregates


def _node_matches_grouping_level(
    node_level_value: OrgHierarchyLevel,
    grouping_level: OrgHierarchyLevel,
) -> bool:
    return node_level_value is grouping_level or (
        grouping_level is OrgHierarchyLevel.DESK
        and node_level_value is OrgHierarchyLevel.VOLCKER_DESK
    )


def _nearest_selected_parent(
    node: OrgHierarchyNode,
    node_map: dict[str, OrgHierarchyNode],
    selected_levels: Sequence[OrgHierarchyLevel],
) -> OrgHierarchyNode | None:
    current_id = node.parent_id
    while current_id is not None:
        parent = node_map[current_id]
        if any(
            _node_matches_grouping_level(node_level(parent), level) for level in selected_levels
        ):
            return parent
        current_id = parent.parent_id
    return None


def _selected_chain(
    node: OrgHierarchyNode,
    node_map: dict[str, OrgHierarchyNode],
    selected_levels: Sequence[OrgHierarchyLevel],
) -> tuple[OrgHierarchyNode, ...]:
    chain = ancestor_chain(node.node_id, node_map)
    return tuple(
        item
        for item in chain
        if any(_node_matches_grouping_level(node_level(item), level) for level in selected_levels)
    )


def _single_currency(rows: Sequence[OrgCapitalResultRow]) -> str:
    currencies = sorted({row.currency for row in rows})
    if len(currencies) != 1:
        raise ResultStoreContractError(
            "org aggregate rows must not mix currencies",
            field="currency",
        )
    return currencies[0]


def _component_breakdown(rows: Sequence[OrgCapitalResultRow]) -> dict[str, float]:
    breakdown: dict[str, float] = defaultdict(float)
    for row in rows:
        breakdown[component_value(row.component)] += row.capital
    return dict(sorted(breakdown.items()))


__all__ = [
    "aggregate_by_org_hierarchy",
    "source_rows_for_org_aggregate",
]
