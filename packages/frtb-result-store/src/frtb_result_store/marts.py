"""Persisted reporting mart generation for the Parquet result store."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import date

from frtb_result_store._row_codecs import (
    float_value as _float_value,
)
from frtb_result_store._row_codecs import (
    int_value as _int_value,
)
from frtb_result_store._row_codecs import (
    json_mapping as _json_mapping,
)
from frtb_result_store._row_codecs import (
    metadata_json as _metadata_json,
)
from frtb_result_store._row_codecs import (
    optional_text as _optional_text,
)
from frtb_result_store._row_codecs import (
    stored_value as _stored_value,
)
from frtb_result_store.model import (
    CapitalMeasure,
    CapitalNode,
    CapitalSummaryRow,
    CapitalTreeMartRow,
    ComponentBreakdownRow,
    FrtbComponent,
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
]


def mart_rows_for_bundle(
    bundle: ResultBundle,
    *,
    lifecycle_status: RunStatus,
) -> dict[str, list[dict[str, object]]]:
    return {
        "capital_summary": [_capital_summary_row(bundle, lifecycle_status=lifecycle_status)],
        "capital_tree": _capital_tree_rows(bundle),
        "component_breakdown": _component_breakdown_rows(bundle),
    }


def capital_summary_from_row(row: Sequence[object]) -> CapitalSummaryRow:
    return CapitalSummaryRow(
        run_id=str(row[0]),
        as_of_date=_date_from_storage(row[1]),
        regime_id=str(row[2]),
        base_currency=str(row[3]),
        lifecycle_status=str(row[4]),
        suggested_status=_optional_text(row[5]),
        total_capital=_float_value(row[6]),
        currency=str(row[7]),
        node_count=_int_value(row[8]),
        measure_count=_int_value(row[9]),
        component_count=_int_value(row[10]),
    )


def capital_tree_mart_from_row(row: Sequence[object]) -> CapitalTreeMartRow:
    return CapitalTreeMartRow(
        run_id=str(row[0]),
        node_id=str(row[1]),
        parent_node_id=_optional_text(row[2]),
        depth=_int_value(row[3]),
        node_type=str(row[4]),
        component=str(row[5]),
        label=str(row[6]),
        desk_id=_optional_text(row[7]),
        portfolio_id=_optional_text(row[8]),
        book_id=_optional_text(row[9]),
        risk_class=_optional_text(row[10]),
        bucket=_optional_text(row[11]),
        issuer_id=_optional_text(row[12]),
        counterparty_id=_optional_text(row[13]),
        calculation_branch=_optional_text(row[14]),
        regulatory_rule_id=_optional_text(row[15]),
        sort_key=_int_value(row[16]),
        metadata=_json_mapping(row[17]),
    )


def component_breakdown_from_row(row: Sequence[object]) -> ComponentBreakdownRow:
    return ComponentBreakdownRow(
        run_id=str(row[0]),
        component=str(row[1]),
        amount=_float_value(row[2]),
        currency=str(row[3]),
        node_count=_int_value(row[4]),
        measure_count=_int_value(row[5]),
    )


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


def _date_from_storage(value: object) -> date:
    return date.fromisoformat(str(value))
