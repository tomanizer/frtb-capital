"""Component-breakdown reporting mart row builders for result-store bundles."""

from __future__ import annotations

from frtb_result_store._row_codecs import (
    stored_value as _stored_value,
)
from frtb_result_store.model import (
    CapitalNode,
    ComponentBreakdownRow,
    FrtbComponent,
    ResultBundle,
)


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


__all__ = ["_component_breakdown_rows"]
