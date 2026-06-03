"""Standard FRTB capital edge generation."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from frtb_result_store.model import (
    CapitalEdge,
    CapitalNode,
    CapitalNodeFamily,
    EdgeType,
    FrtbComponent,
    ResultStoreContractError,
)

__all__ = ["build_standard_capital_edges"]


def build_standard_capital_edges(
    *,
    run_id: str,
    hierarchy_leaf_node_id: str,
    nodes: Sequence[CapitalNode],
) -> tuple[CapitalEdge, ...]:
    """Generate the first-pass standard capital drilldown edges."""

    ordered_nodes = tuple(sorted(nodes, key=lambda node: (node.sort_key, node.node_id)))
    component_nodes, risk_class_nodes, bucket_nodes = _index_parent_nodes(ordered_nodes)
    edges: list[CapitalEdge] = []
    for sort_key, (parent_id, child_id) in enumerate(
        _standard_parent_child_pairs(
            ordered_nodes,
            hierarchy_leaf_node_id,
            component_nodes,
            risk_class_nodes,
            bucket_nodes,
        )
    ):
        edges.append(
            CapitalEdge(
                run_id=run_id,
                parent_node_id=parent_id,
                child_node_id=child_id,
                edge_type=EdgeType.DRILLDOWN,
                sort_key=sort_key,
            )
        )
    return tuple(edges)


def _index_parent_nodes(
    nodes: Sequence[CapitalNode],
) -> tuple[
    dict[tuple[str, str | None], CapitalNode],
    dict[tuple[str, str, str | None, str | None], CapitalNode],
    dict[tuple[str, str, str | None, str, str | None], CapitalNode],
]:
    component_nodes: dict[tuple[str, str | None], CapitalNode] = {}
    risk_class_nodes: dict[tuple[str, str, str | None, str | None], CapitalNode] = {}
    bucket_nodes: dict[tuple[str, str, str | None, str, str | None], CapitalNode] = {}
    for node in nodes:
        family = node.metadata.get("node_family")
        component_value = FrtbComponent(node.component).value
        branch = node.calculation_branch
        if family == CapitalNodeFamily.COMPONENT.value:
            component_nodes[(component_value, branch)] = node
        elif family == CapitalNodeFamily.RISK_CLASS.value and node.risk_class is not None:
            risk_measure = _optional_metadata_text(node.metadata.get("risk_measure"))
            risk_class_nodes[(component_value, node.risk_class, risk_measure, branch)] = node
        elif family == CapitalNodeFamily.BUCKET.value and node.risk_class and node.bucket:
            risk_measure = _optional_metadata_text(node.metadata.get("risk_measure"))
            bucket_nodes[(component_value, node.risk_class, risk_measure, node.bucket, branch)] = (
                node
            )
    return component_nodes, risk_class_nodes, bucket_nodes


def _standard_parent_child_pairs(
    nodes: Sequence[CapitalNode],
    hierarchy_leaf_node_id: str,
    component_nodes: Mapping[tuple[str, str | None], CapitalNode],
    risk_class_nodes: Mapping[tuple[str, str, str | None, str | None], CapitalNode],
    bucket_nodes: Mapping[tuple[str, str, str | None, str, str | None], CapitalNode],
) -> tuple[tuple[str, str], ...]:
    pairs: list[tuple[str, str]] = []
    for node in nodes:
        parent_id = _parent_node_id(
            node,
            hierarchy_leaf_node_id,
            component_nodes,
            risk_class_nodes,
            bucket_nodes,
        )
        if parent_id is not None:
            pairs.append((parent_id, node.node_id))
    return tuple(pairs)


def _parent_node_id(
    node: CapitalNode,
    hierarchy_leaf_node_id: str,
    component_nodes: Mapping[tuple[str, str | None], CapitalNode],
    risk_class_nodes: Mapping[tuple[str, str, str | None, str | None], CapitalNode],
    bucket_nodes: Mapping[tuple[str, str, str | None, str, str | None], CapitalNode],
) -> str | None:
    family = node.metadata.get("node_family")
    component_value = FrtbComponent(node.component).value
    branch = node.calculation_branch
    if family == CapitalNodeFamily.COMPONENT.value:
        return hierarchy_leaf_node_id
    if family == CapitalNodeFamily.RISK_CLASS.value and node.risk_class is not None:
        parent = component_nodes.get((component_value, branch))
        return None if parent is None else parent.node_id
    if family == CapitalNodeFamily.BUCKET.value and node.risk_class and node.bucket:
        risk_measure = _optional_metadata_text(node.metadata.get("risk_measure"))
        parent = risk_class_nodes.get((component_value, node.risk_class, risk_measure, branch))
        return None if parent is None else parent.node_id
    if family == CapitalNodeFamily.ISSUER.value and node.risk_class and node.bucket:
        parent = bucket_nodes.get((component_value, node.risk_class, None, node.bucket, branch))
        return None if parent is None else parent.node_id
    return None


def _optional_metadata_text(value: object) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ResultStoreContractError("metadata value must be text")
    return value
