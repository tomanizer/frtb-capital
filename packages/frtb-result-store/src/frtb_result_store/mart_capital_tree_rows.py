"""Capital-tree reporting mart row builders for result-store bundles."""

from __future__ import annotations

from collections.abc import Mapping

from frtb_result_store._row_codecs import (
    metadata_json as _metadata_json,
)
from frtb_result_store._row_codecs import (
    stored_value as _stored_value,
)
from frtb_result_store.model import (
    CapitalTreeMartRow,
    ResultBundle,
    ResultStoreContractError,
)


def _capital_tree_rows(bundle: ResultBundle) -> list[dict[str, object]]:
    parent_by_child = _parent_by_child(bundle)
    depth_by_node = _depth_by_node(parent_by_child)
    rows: list[dict[str, object]] = []
    for node in sorted(
        bundle.nodes,
        key=lambda item: (depth_by_node.get(item.node_id, 0), item.sort_key, item.node_id),
    ):
        row = CapitalTreeMartRow(
            run_id=node.run_id,
            node_id=node.node_id,
            parent_node_id=parent_by_child.get(node.node_id),
            depth=depth_by_node.get(node.node_id, 0),
            node_type=node.node_type,
            component=node.component,
            label=node.label,
            desk_id=node.desk_id,
            portfolio_id=node.portfolio_id,
            book_id=node.book_id,
            risk_class=node.risk_class,
            bucket=node.bucket,
            issuer_id=node.issuer_id,
            counterparty_id=node.counterparty_id,
            calculation_branch=node.calculation_branch,
            regulatory_rule_id=node.regulatory_rule_id,
            sort_key=node.sort_key,
            metadata=node.metadata,
        )
        rows.append(_capital_tree_row(row))
    return rows


def _capital_tree_row(row: CapitalTreeMartRow) -> dict[str, object]:
    return {
        "run_id": row.run_id,
        "node_id": row.node_id,
        "parent_node_id": row.parent_node_id,
        "depth": row.depth,
        "node_type": _stored_value(row.node_type),
        "component": _stored_value(row.component),
        "label": row.label,
        "desk_id": row.desk_id,
        "portfolio_id": row.portfolio_id,
        "book_id": row.book_id,
        "risk_class": row.risk_class,
        "bucket": row.bucket,
        "issuer_id": row.issuer_id,
        "counterparty_id": row.counterparty_id,
        "calculation_branch": row.calculation_branch,
        "regulatory_rule_id": row.regulatory_rule_id,
        "sort_key": row.sort_key,
        "metadata_json": _metadata_json(row.metadata),
    }


def _parent_by_child(bundle: ResultBundle) -> dict[str, str]:
    return {
        edge.child_node_id: edge.parent_node_id
        for edge in sorted(bundle.edges, key=lambda item: (item.sort_key, item.parent_node_id))
    }


def _depth_by_node(parent_by_child: Mapping[str, str]) -> dict[str, int]:
    depth_by_node: dict[str, int] = {}
    visiting: set[str] = set()

    def depth(node_id: str) -> int:
        if node_id in depth_by_node:
            return depth_by_node[node_id]
        if node_id in visiting:
            raise ResultStoreContractError(
                f"cycle detected in capital tree at node: {node_id}",
                field="edges",
            )
        visiting.add(node_id)
        parent = parent_by_child.get(node_id)
        depth_by_node[node_id] = 0 if parent is None else depth(parent) + 1
        visiting.remove(node_id)
        return depth_by_node[node_id]

    for node_id in set(parent_by_child) | set(parent_by_child.values()):
        depth(node_id)
    return depth_by_node


__all__ = [
    "_capital_tree_row",
    "_capital_tree_rows",
    "_depth_by_node",
    "_parent_by_child",
]
