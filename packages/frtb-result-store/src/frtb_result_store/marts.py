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
from frtb_result_store.model import (
    ArtifactRef,
    ArtifactType,
    CapitalAttributionRecord,
    CapitalMeasure,
    CapitalNode,
    CapitalSummaryRow,
    CapitalTreeMartRow,
    ComponentBreakdownRow,
    FrtbComponent,
    MovementResult,
    MovementSummaryRow,
    ResultBundle,
    ResultEvent,
    ResultEventSeverity,
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
        "drc_issuer_contributors": _component_identifier_rows(
            bundle,
            component=FrtbComponent.DRC,
            identifier_field="issuer_id",
            artifact_type=ArtifactType.DRC_JTD_TABLE,
        ),
        "cva_counterparty_contributors": _component_identifier_rows(
            bundle,
            component=FrtbComponent.CVA,
            identifier_field="counterparty_id",
            artifact_type=ArtifactType.CVA_EXPOSURE_TABLE,
        ),
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


def _capital_summary_row(
    bundle: ResultBundle,
    *,
    lifecycle_status: RunStatus,
) -> dict[str, object]:
    total_measure = _measure_for_node(bundle.measures, node_id="total")
    currency = total_measure.currency if total_measure is not None else bundle.run.base_currency
    row = CapitalSummaryRow(
        run_id=bundle.run.run_id,
        as_of_date=bundle.run.as_of_date,
        regime_id=bundle.run.regime_id,
        base_currency=bundle.run.base_currency,
        lifecycle_status=lifecycle_status,
        suggested_status=_suggested_status(bundle.events),
        total_capital=0.0 if total_measure is None else total_measure.amount,
        currency=currency,
        node_count=len(bundle.nodes),
        measure_count=len(bundle.measures),
        component_count=len(_components(bundle.nodes)),
    )
    return {
        "run_id": row.run_id,
        "as_of_date": row.as_of_date.isoformat(),
        "regime_id": row.regime_id,
        "base_currency": row.base_currency,
        "lifecycle_status": _stored_value(row.lifecycle_status),
        "suggested_status": None
        if row.suggested_status is None
        else _stored_value(row.suggested_status),
        "total_capital": row.total_capital,
        "currency": row.currency,
        "node_count": row.node_count,
        "measure_count": row.measure_count,
        "component_count": row.component_count,
    }


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


def _regime_comparison_row(
    bundle: ResultBundle,
    *,
    lifecycle_status: RunStatus,
) -> dict[str, object]:
    total_measure = _measure_for_node(bundle.measures, node_id="total")
    currency = total_measure.currency if total_measure is not None else bundle.run.base_currency
    return {
        "run_group_id": bundle.run.run_group_id or f"run:{bundle.run.run_id}",
        "run_id": bundle.run.run_id,
        "as_of_date": bundle.run.as_of_date.isoformat(),
        "regime_id": bundle.run.regime_id,
        "base_currency": bundle.run.base_currency,
        "lifecycle_status": _stored_value(lifecycle_status),
        "suggested_status": _stored_value(_suggested_status(bundle.events)),
        "total_capital": 0.0 if total_measure is None else total_measure.amount,
        "currency": currency,
        "component_count": len(_components(bundle.nodes)),
    }


def _ima_desk_dashboard_rows(bundle: ResultBundle) -> list[dict[str, object]]:
    groups: dict[str, list[CapitalNode]] = {}
    for node in bundle.nodes:
        if FrtbComponent(node.component) == FrtbComponent.IMA and node.desk_id:
            groups.setdefault(node.desk_id, []).append(node)
    capital_by_node = _capital_amount_by_node(bundle.measures)
    currency_by_node = _currency_by_node(bundle.measures, bundle.run.base_currency)
    rows: list[dict[str, object]] = []
    for desk_id, nodes in sorted(groups.items()):
        node_ids = {node.node_id for node in nodes}
        rows.append(
            {
                "run_id": bundle.run.run_id,
                "desk_id": desk_id,
                "portfolio_count": len({node.portfolio_id for node in nodes if node.portfolio_id}),
                "book_count": len({node.book_id for node in nodes if node.book_id}),
                "node_count": len(node_ids),
                "capital": sum(capital_by_node.get(node_id, 0.0) for node_id in node_ids),
                "currency": _first_currency(nodes, currency_by_node, bundle.run.base_currency),
            }
        )
    return rows


def _sbm_bucket_ladder_rows(bundle: ResultBundle) -> list[dict[str, object]]:
    groups: dict[tuple[str, str], list[CapitalNode]] = {}
    for node in bundle.nodes:
        if FrtbComponent(node.component) == FrtbComponent.SBM and node.risk_class and node.bucket:
            groups.setdefault((node.risk_class, node.bucket), []).append(node)
    capital_by_node = _capital_amount_by_node(bundle.measures)
    currency_by_node = _currency_by_node(bundle.measures, bundle.run.base_currency)
    rows: list[dict[str, object]] = []
    for (risk_class, bucket), nodes in sorted(groups.items()):
        node_ids = {node.node_id for node in nodes}
        rows.append(
            {
                "run_id": bundle.run.run_id,
                "risk_class": risk_class,
                "bucket": bucket,
                "node_count": len(node_ids),
                "capital": sum(capital_by_node.get(node_id, 0.0) for node_id in node_ids),
                "currency": _first_currency(nodes, currency_by_node, bundle.run.base_currency),
            }
        )
    return rows


def _component_identifier_rows(
    bundle: ResultBundle,
    *,
    component: FrtbComponent,
    identifier_field: str,
    artifact_type: ArtifactType,
) -> list[dict[str, object]]:
    capital_by_node = _capital_amount_by_node(bundle.measures)
    currency_by_node = _currency_by_node(bundle.measures, bundle.run.base_currency)
    artifact_id = _artifact_id(bundle.artifacts, component=component, artifact_type=artifact_type)
    rows: list[dict[str, object]] = []
    for node in sorted(bundle.nodes, key=lambda item: (item.sort_key, item.node_id)):
        if FrtbComponent(node.component) != component:
            continue
        identifier = getattr(node, identifier_field)
        if not identifier:
            continue
        rows.append(
            {
                "run_id": bundle.run.run_id,
                identifier_field: identifier,
                "node_id": node.node_id,
                "capital": capital_by_node.get(node.node_id, 0.0),
                "currency": currency_by_node.get(node.node_id, bundle.run.base_currency),
                "artifact_id": artifact_id,
            }
        )
    return rows


def _rrao_exposure_summary_rows(bundle: ResultBundle) -> list[dict[str, object]]:
    capital_by_node = _capital_amount_by_node(bundle.measures)
    currency_by_node = _currency_by_node(bundle.measures, bundle.run.base_currency)
    artifact_id = _artifact_id(
        bundle.artifacts,
        component=FrtbComponent.RRAO,
        artifact_type=ArtifactType.RRAO_EXPOSURE_TABLE,
    )
    rows: list[dict[str, object]] = []
    for node in sorted(bundle.nodes, key=lambda item: (item.sort_key, item.node_id)):
        if FrtbComponent(node.component) != FrtbComponent.RRAO:
            continue
        rows.append(
            {
                "run_id": bundle.run.run_id,
                "node_id": node.node_id,
                "exposure_class": node.calculation_branch or node.label,
                "capital": capital_by_node.get(node.node_id, 0.0),
                "currency": currency_by_node.get(node.node_id, bundle.run.base_currency),
                "artifact_id": artifact_id,
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


def _measure_for_node(
    measures: Sequence[CapitalMeasure],
    *,
    node_id: str,
) -> CapitalMeasure | None:
    for measure in measures:
        if measure.node_id == node_id and measure.measure_name == "capital":
            return measure
    return None


def _capital_amount_by_node(measures: Sequence[CapitalMeasure]) -> dict[str, float]:
    return {
        measure.node_id: measure.amount for measure in measures if measure.measure_name == "capital"
    }


def _currency_by_node(
    measures: Sequence[CapitalMeasure],
    default_currency: str,
) -> dict[str, str]:
    return {
        measure.node_id: measure.currency or default_currency
        for measure in measures
        if measure.measure_name == "capital"
    }


def _first_currency(
    nodes: Sequence[CapitalNode],
    currency_by_node: Mapping[str, str],
    default_currency: str,
) -> str:
    for node in sorted(nodes, key=lambda item: (item.sort_key, item.node_id)):
        if node.node_id in currency_by_node:
            return currency_by_node[node.node_id]
    return default_currency


def _artifact_id(
    artifacts: Sequence[ArtifactRef],
    *,
    component: FrtbComponent,
    artifact_type: ArtifactType,
) -> str | None:
    for artifact in sorted(artifacts, key=lambda item: item.artifact_id):
        if artifact.component == component and artifact.artifact_type == artifact_type:
            return artifact.artifact_id
    return None


def _attribution_amount(attribution: CapitalAttributionRecord) -> float:
    return (0.0 if attribution.contribution is None else float(attribution.contribution)) + float(
        attribution.residual
    )


def _suggested_status(events: Sequence[ResultEvent]) -> RunStatus:
    if any(event.severity is ResultEventSeverity.ERROR for event in events):
        return RunStatus.REJECTED
    return RunStatus.VALIDATED


def _components(nodes: Sequence[CapitalNode]) -> tuple[FrtbComponent, ...]:
    return tuple(
        sorted(
            {
                component
                for node in nodes
                if (component := FrtbComponent(node.component)) is not FrtbComponent.TOP_OF_HOUSE
            },
            key=lambda item: item.value,
        )
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
