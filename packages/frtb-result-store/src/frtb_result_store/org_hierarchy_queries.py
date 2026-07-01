"""Hierarchy-node query contracts for Navigator read APIs."""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from datetime import date

from frtb_result_store.model_enums import FrtbComponent, ResultStoreContractError
from frtb_result_store.model_validation import _require_non_empty_text, _require_plain_date
from frtb_result_store.org_hierarchy_model import (
    OrgAggregateRow,
    OrgCapitalResultRow,
    OrgHierarchy,
    OrgHierarchyLevel,
    OrgHierarchyNode,
    component_value,
    generate_org_aggregate_row_id,
    node_level,
)
from frtb_result_store.org_hierarchy_query_helpers import (
    component_breakdown,
    component_filter,
    single_currency,
    validate_measure,
    validate_page,
)
from frtb_result_store.org_hierarchy_query_model import (
    OrgHierarchyEdge,
    OrgHierarchySnapshot,
    OrgNodeAggregateResult,
    OrgQueryStatus,
    OrgSourceRowPage,
)
from frtb_result_store.org_hierarchy_validation import (
    ancestor_chain,
    deepest_node_id,
    resolve_org_hierarchy_version,
    single_version_node_map,
    validate_org_hierarchy,
)

_ORG_LEVEL_SORT: Mapping[OrgHierarchyLevel, int] = {
    OrgHierarchyLevel.TOH: 0,
    OrgHierarchyLevel.LEGAL_ENTITY: 1,
    OrgHierarchyLevel.BUSINESS_DIVISION: 2,
    OrgHierarchyLevel.BUSINESS_LINE: 3,
    OrgHierarchyLevel.VOLCKER_DESK: 4,
    OrgHierarchyLevel.DESK: 5,
    OrgHierarchyLevel.BOOK: 6,
}


def list_org_hierarchy(
    hierarchy: OrgHierarchy,
    *,
    as_of_date: date,
) -> OrgHierarchySnapshot:
    """Return the effective hierarchy snapshot for a run date.

    Parameters
    ----------
    hierarchy:
        Versioned organisation hierarchy.
    as_of_date:
        Run date used to select one effective hierarchy version.

    Returns
    -------
    OrgHierarchySnapshot
        Active nodes and parent-child edges in deterministic traversal order.
    """

    active_hierarchy, version_id, node_map = _active_hierarchy(hierarchy, as_of_date)
    nodes = _ordered_nodes(node_map)
    edges = tuple(
        OrgHierarchyEdge(
            hierarchy_id=node.hierarchy_id,
            version_id=node.version_id,
            parent_node_id=node.parent_id,
            child_node_id=node.node_id,
        )
        for node in nodes
        if node.parent_id is not None
    )
    return OrgHierarchySnapshot(
        hierarchy_id=active_hierarchy.hierarchy_id,
        version_id=version_id,
        as_of_date=as_of_date,
        nodes=nodes,
        edges=edges,
    )


def org_node_children(
    hierarchy: OrgHierarchy,
    node_id: str,
    *,
    as_of_date: date,
) -> tuple[OrgHierarchyNode, ...]:
    """Return direct children for one hierarchy node.

    Parameters
    ----------
    hierarchy:
        Versioned organisation hierarchy.
    node_id:
        Selected hierarchy node.
    as_of_date:
        Run date used to select one effective hierarchy version.

    Returns
    -------
    tuple[OrgHierarchyNode, ...]
        Direct children in deterministic display order.
    """

    _require_non_empty_text(node_id, "node_id")
    _, _, node_map = _active_hierarchy(hierarchy, as_of_date)
    if node_id not in node_map:
        raise ResultStoreContractError(f"org hierarchy node not found: {node_id}", field="node_id")
    return _sorted_siblings(node for node in node_map.values() if node.parent_id == node_id)


def aggregate_org_node(
    rows: Sequence[OrgCapitalResultRow],
    hierarchy: OrgHierarchy,
    *,
    run_id: str,
    node_id: str,
    as_of_date: date,
    framework: str | None = None,
    measure: str = "capital",
) -> OrgNodeAggregateResult:
    """Return the capital aggregate for one selected organisation node.

    Parameters
    ----------
    rows:
        Candidate organisation-mapped capital rows.
    hierarchy:
        Versioned organisation hierarchy.
    run_id:
        Calculation run identifier used to scope source rows.
    node_id:
        Selected hierarchy node.
    as_of_date:
        Run date used to select one effective hierarchy version.
    framework:
        Optional FRTB component/framework filter such as ``IMA`` or ``CVA``.
    measure:
        Measure name. Only ``capital`` is currently supported by the org row
        contract.

    Returns
    -------
    OrgNodeAggregateResult
        Status plus a deterministic aggregate row when data exists.
    """

    validate_measure(measure)
    components, unsupported = component_filter(framework)
    if unsupported:
        return OrgNodeAggregateResult(
            run_id=run_id,
            node_id=node_id,
            status=OrgQueryStatus.UNSUPPORTED,
            aggregate=None,
            source_row_count=0,
            component_filter=(),
            message=unsupported,
        )

    node, node_map, source_rows = _source_rows_for_node(
        rows,
        hierarchy,
        run_id=run_id,
        node_id=node_id,
        as_of_date=as_of_date,
        components=components,
    )
    output_filter = tuple(component_value(component) for component in components)
    if not source_rows:
        return OrgNodeAggregateResult(
            run_id=run_id,
            node_id=node_id,
            status=OrgQueryStatus.NO_DATA,
            aggregate=None,
            source_row_count=0,
            component_filter=output_filter,
            message="no mapped source rows for selected hierarchy node",
        )

    return OrgNodeAggregateResult(
        run_id=run_id,
        node_id=node_id,
        status=OrgQueryStatus.OK,
        aggregate=_aggregate_row_for_node(node, node_map, source_rows),
        source_row_count=len(source_rows),
        component_filter=output_filter,
    )


def source_rows_for_org_node(
    rows: Sequence[OrgCapitalResultRow],
    hierarchy: OrgHierarchy,
    *,
    run_id: str,
    node_id: str,
    as_of_date: date,
    framework: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> OrgSourceRowPage:
    """Return paginated source rows backing a selected organisation node.

    Parameters
    ----------
    rows:
        Candidate organisation-mapped capital rows.
    hierarchy:
        Versioned organisation hierarchy.
    run_id:
        Calculation run identifier used to scope source rows.
    node_id:
        Selected hierarchy node.
    as_of_date:
        Run date used to select one effective hierarchy version.
    framework:
        Optional FRTB component/framework filter such as ``IMA`` or ``CVA``.
    limit:
        Maximum source rows to return.
    offset:
        Zero-based row offset.

    Returns
    -------
    OrgSourceRowPage
        Stable source-row page including total count and next offset.
    """

    validate_page(limit, offset)
    components, unsupported = component_filter(framework)
    output_filter = tuple(component_value(component) for component in components)
    if unsupported:
        return OrgSourceRowPage(
            run_id=run_id,
            node_id=node_id,
            status=OrgQueryStatus.UNSUPPORTED,
            rows=(),
            total_row_count=0,
            limit=limit,
            offset=offset,
            next_offset=None,
            component_filter=(),
            message=unsupported,
        )

    _, _, source_rows = _source_rows_for_node(
        rows,
        hierarchy,
        run_id=run_id,
        node_id=node_id,
        as_of_date=as_of_date,
        components=components,
    )
    total = len(source_rows)
    page_rows = tuple(source_rows[offset : offset + limit])
    next_offset = offset + limit if offset + limit < total else None
    return OrgSourceRowPage(
        run_id=run_id,
        node_id=node_id,
        status=OrgQueryStatus.OK if total else OrgQueryStatus.NO_DATA,
        rows=page_rows,
        total_row_count=total,
        limit=limit,
        offset=offset,
        next_offset=next_offset,
        component_filter=output_filter,
        message="" if total else "no mapped source rows for selected hierarchy node",
    )


def _active_hierarchy(
    hierarchy: OrgHierarchy,
    as_of_date: date,
) -> tuple[OrgHierarchy, str, dict[str, OrgHierarchyNode]]:
    _require_plain_date(as_of_date, "as_of_date")
    version_id = resolve_org_hierarchy_version(hierarchy, as_of_date)
    nodes = tuple(
        node
        for node in hierarchy.nodes
        if node.version_id == version_id and node.active_on(as_of_date)
    )
    active_hierarchy = OrgHierarchy(hierarchy_id=hierarchy.hierarchy_id, nodes=nodes)
    validate_org_hierarchy(active_hierarchy, as_of_date=as_of_date)
    return active_hierarchy, version_id, single_version_node_map(nodes)


def _source_rows_for_node(
    rows: Sequence[OrgCapitalResultRow],
    hierarchy: OrgHierarchy,
    *,
    run_id: str,
    node_id: str,
    as_of_date: date,
    components: Sequence[FrtbComponent],
) -> tuple[
    OrgHierarchyNode,
    Mapping[str, OrgHierarchyNode],
    tuple[OrgCapitalResultRow, ...],
]:
    _require_non_empty_text(run_id, "run_id")
    _require_non_empty_text(node_id, "node_id")
    active_hierarchy, version_id, node_map = _active_hierarchy(hierarchy, as_of_date)
    if node_id not in node_map:
        raise ResultStoreContractError(f"org hierarchy node not found: {node_id}", field="node_id")
    component_values = {component_value(component) for component in components}
    scoped_rows = tuple(
        row
        for row in rows
        if row.run_id == run_id
        and row.org_keys.hierarchy_id == hierarchy.hierarchy_id
        and row.org_keys.version_id == version_id
        and (not component_values or component_value(row.component) in component_values)
    )
    validate_org_hierarchy(active_hierarchy, scoped_rows, as_of_date=as_of_date)
    source_rows = tuple(
        sorted(
            (
                row
                for row in scoped_rows
                if any(
                    node.node_id == node_id
                    for node in ancestor_chain(deepest_node_id(row.org_keys), node_map)
                )
            ),
            key=lambda row: row.source_row_id,
        )
    )
    return node_map[node_id], node_map, source_rows


def _aggregate_row_for_node(
    node: OrgHierarchyNode,
    node_map: Mapping[str, OrgHierarchyNode],
    source_rows: Sequence[OrgCapitalResultRow],
) -> OrgAggregateRow:
    parent_id = (
        generate_org_aggregate_row_id(node_map[node.parent_id])
        if node.parent_id is not None
        else None
    )
    return OrgAggregateRow(
        row_id=generate_org_aggregate_row_id(node),
        parent_id=parent_id,
        label=node.label,
        level=node.level,
        node_id=node.node_id,
        group_path=tuple(item.node_id for item in ancestor_chain(node.node_id, node_map)),
        capital=sum(row.capital for row in source_rows),
        currency=single_currency(source_rows),
        source_row_count=len(source_rows),
        component_breakdown=component_breakdown(source_rows),
        metadata=node.metadata,
    )


def _ordered_nodes(node_map: Mapping[str, OrgHierarchyNode]) -> tuple[OrgHierarchyNode, ...]:
    roots = [node for node in node_map.values() if node.parent_id is None]
    ordered: list[OrgHierarchyNode] = []
    for root in _sorted_siblings(roots):
        _append_preorder(root, node_map, ordered)
    return tuple(ordered)


def _append_preorder(
    node: OrgHierarchyNode,
    node_map: Mapping[str, OrgHierarchyNode],
    ordered: list[OrgHierarchyNode],
) -> None:
    ordered.append(node)
    children = (item for item in node_map.values() if item.parent_id == node.node_id)
    for child in _sorted_siblings(children):
        _append_preorder(child, node_map, ordered)


def _sorted_siblings(nodes: Iterable[OrgHierarchyNode]) -> tuple[OrgHierarchyNode, ...]:
    return tuple(
        sorted(
            nodes,
            key=lambda node: (_ORG_LEVEL_SORT[node_level(node)], node.label, node.node_id),
        )
    )


__all__ = [
    "OrgHierarchyEdge",
    "OrgHierarchySnapshot",
    "OrgNodeAggregateResult",
    "OrgQueryStatus",
    "OrgSourceRowPage",
    "aggregate_org_node",
    "list_org_hierarchy",
    "org_node_children",
    "source_rows_for_org_node",
]
