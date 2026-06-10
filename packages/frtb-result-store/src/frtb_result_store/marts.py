"""Persisted reporting mart generation for the Parquet result store."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence

from frtb_common import AttributionMethod

from frtb_result_store._row_codecs import (
    metadata_json as _metadata_json,
)
from frtb_result_store._row_codecs import (
    stored_value as _stored_value,
)
from frtb_result_store.mart_component_rows import (
    _cva_counterparty_contributor_rows,
    _drc_issuer_contributor_rows,
    _ima_desk_dashboard_rows,
    _rrao_exposure_summary_rows,
    _sbm_bucket_ladder_rows,
)
from frtb_result_store.mart_row_codecs import (
    capital_summary_from_row as _capital_summary_from_row,
)
from frtb_result_store.mart_row_codecs import (
    capital_tree_mart_from_row as _capital_tree_mart_from_row,
)
from frtb_result_store.mart_row_codecs import (
    component_breakdown_from_row as _component_breakdown_from_row,
)
from frtb_result_store.mart_row_codecs import (
    movement_summary_from_row as _movement_summary_from_row,
)
from frtb_result_store.mart_summary_rows import (
    _capital_summary_row,
    _regime_comparison_row,
)
from frtb_result_store.model import (
    CapitalAttributionRecord,
    CapitalNode,
    CapitalSummaryRow,
    CapitalTreeMartRow,
    ComponentBreakdownRow,
    FrtbComponent,
    MovementResult,
    MovementSummaryRow,
    ResultBundle,
    ResultStoreContractError,
    RunStatus,
)

__all__ = [
    "capital_summary_from_row",
    "capital_tree_mart_from_row",
    "component_breakdown_from_row",
    "mart_rows_for_bundle",
    "movement_summary_from_row",
]


def mart_rows_for_bundle(
    bundle: ResultBundle,
    *,
    lifecycle_status: RunStatus,
) -> dict[str, list[dict[str, object]]]:
    return {
        "capital_summary": [_capital_summary_row(bundle, lifecycle_status=lifecycle_status)],
        "capital_tree": _capital_tree_rows(bundle),
        "top_contributors": _top_contributor_rows(bundle),
        "residual_attribution": _residual_attribution_rows(bundle),
        "unsupported_attribution": _unsupported_attribution_rows(bundle),
        "movement_summary": _movement_summary_rows(bundle),
        "regime_comparison": [_regime_comparison_row(bundle, lifecycle_status=lifecycle_status)],
        "component_breakdown": _component_breakdown_rows(bundle),
        "ima_desk_dashboard": _ima_desk_dashboard_rows(bundle),
        "sbm_bucket_ladder": _sbm_bucket_ladder_rows(bundle),
        "drc_issuer_contributors": _drc_issuer_contributor_rows(bundle),
        "cva_counterparty_contributors": _cva_counterparty_contributor_rows(bundle),
        "rrao_exposure_summary": _rrao_exposure_summary_rows(bundle),
    }


def capital_summary_from_row(row: Sequence[object]) -> CapitalSummaryRow:
    return _capital_summary_from_row(row)


def capital_tree_mart_from_row(row: Sequence[object]) -> CapitalTreeMartRow:
    return _capital_tree_mart_from_row(row)


def component_breakdown_from_row(row: Sequence[object]) -> ComponentBreakdownRow:
    return _component_breakdown_from_row(row)


def movement_summary_from_row(row: Sequence[object]) -> MovementSummaryRow:
    return _movement_summary_from_row(row)


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


def _component_breakdown_rows(bundle: ResultBundle) -> list[dict[str, object]]:
    nodes_by_component: dict[FrtbComponent, list[CapitalNode]] = {}
    for node in bundle.nodes:
        component = FrtbComponent(node.component)
        if component is FrtbComponent.TOP_OF_HOUSE:
            continue
        nodes_by_component.setdefault(component, []).append(node)
    rows: list[dict[str, object]] = []
    for component in sorted(nodes_by_component, key=lambda item: item.value):
        node_ids = {node.node_id for node in nodes_by_component[component]}
        measures = [
            measure
            for measure in bundle.measures
            if measure.node_id in node_ids and measure.measure_name == "capital"
        ]
        currency = measures[0].currency if measures else bundle.run.base_currency
        row = ComponentBreakdownRow(
            run_id=bundle.run.run_id,
            component=component,
            amount=sum(measure.amount for measure in measures),
            currency=currency,
            node_count=len(node_ids),
            measure_count=len(measures),
        )
        rows.append(
            {
                "run_id": row.run_id,
                "component": _stored_value(row.component),
                "amount": row.amount,
                "currency": row.currency,
                "node_count": row.node_count,
                "measure_count": row.measure_count,
            }
        )
    return rows


def _movement_summary_rows(bundle: ResultBundle) -> list[dict[str, object]]:
    return [
        _movement_summary_row(movement)
        for movement in sorted(
            bundle.movement_results,
            key=lambda item: (
                item.node_id,
                item.movement_type,
                item.driver_type,
                item.driver_id,
                item.movement_id,
            ),
        )
    ]


def _movement_summary_row(movement: MovementResult) -> dict[str, object]:
    row = MovementSummaryRow(
        run_id=movement.run_id,
        baseline_run_id=movement.baseline_run_id,
        movement_id=movement.movement_id,
        node_id=movement.node_id,
        movement_type=movement.movement_type,
        from_amount=movement.from_amount,
        to_amount=movement.to_amount,
        delta_amount=movement.delta_amount,
        base_currency=movement.base_currency,
        driver_type=movement.driver_type,
        driver_id=movement.driver_id,
        attribution_method=movement.attribution_method,
        artifact_id=movement.artifact_id,
    )
    return {
        "run_id": row.run_id,
        "baseline_run_id": row.baseline_run_id,
        "movement_id": row.movement_id,
        "node_id": row.node_id,
        "movement_type": row.movement_type,
        "from_amount": row.from_amount,
        "to_amount": row.to_amount,
        "delta_amount": row.delta_amount,
        "base_currency": row.base_currency,
        "driver_type": row.driver_type,
        "driver_id": row.driver_id,
        "attribution_method": None
        if row.attribution_method is None
        else _stored_value(row.attribution_method),
        "artifact_id": row.artifact_id,
    }


def _top_contributor_rows(bundle: ResultBundle) -> list[dict[str, object]]:
    return _attribution_projection_rows(bundle, predicate=lambda _: True)


def _residual_attribution_rows(bundle: ResultBundle) -> list[dict[str, object]]:
    return _attribution_projection_rows(
        bundle,
        predicate=lambda attribution: (
            AttributionMethod(attribution.method) is AttributionMethod.RESIDUAL
            or attribution.residual != 0.0
        ),
    )


def _unsupported_attribution_rows(bundle: ResultBundle) -> list[dict[str, object]]:
    return _attribution_projection_rows(
        bundle,
        predicate=lambda attribution: (
            AttributionMethod(attribution.method) is AttributionMethod.UNSUPPORTED
        ),
    )


def _attribution_projection_rows(
    bundle: ResultBundle,
    *,
    predicate: Callable[[CapitalAttributionRecord], bool],
) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    component_by_node = {node.node_id: FrtbComponent(node.component) for node in bundle.nodes}
    for rank, attribution in enumerate(
        sorted(
            (item for item in bundle.attributions if predicate(item)),
            key=lambda item: (
                -abs(_attribution_amount(item)),
                item.node_id,
                item.source_level,
                item.source_id,
                item.attribution_id,
            ),
        ),
        start=1,
    ):
        rows.append(
            {
                "run_id": attribution.run_id,
                "rank": rank,
                "node_id": attribution.node_id,
                "component": _stored_value(
                    component_by_node.get(attribution.node_id, FrtbComponent.TOP_OF_HOUSE)
                ),
                "attribution_id": attribution.attribution_id,
                "target_type": attribution.target_type,
                "target_id": attribution.target_id,
                "source_id": attribution.source_id,
                "source_level": attribution.source_level,
                "category": attribution.category,
                "bucket_key": attribution.bucket_key,
                "base_amount": attribution.base_amount,
                "contribution": attribution.contribution,
                "residual": attribution.residual,
                "method": _stored_value(attribution.method),
                "unsupported_reason": attribution.unsupported_reason,
                "artifact_id": attribution.artifact_id,
            }
        )
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


def _attribution_amount(attribution: CapitalAttributionRecord) -> float:
    return (0.0 if attribution.contribution is None else float(attribution.contribution)) + float(
        attribution.residual
    )


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
