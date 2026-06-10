"""Capital summary mart row builders for persisted result-store projections."""

from __future__ import annotations

from collections.abc import Sequence

from frtb_result_store._row_codecs import (
    stored_value as _stored_value,
)
from frtb_result_store.model import (
    CapitalMeasure,
    CapitalNode,
    CapitalSummaryRow,
    FrtbComponent,
    ResultBundle,
    ResultEvent,
    ResultEventSeverity,
    RunStatus,
)


def _capital_summary_row(
    bundle: ResultBundle,
    *,
    lifecycle_status: RunStatus,
) -> dict[str, object]:
    """Return the persisted dashboard summary row for one result bundle."""

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


def _regime_comparison_row(
    bundle: ResultBundle,
    *,
    lifecycle_status: RunStatus,
) -> dict[str, object]:
    """Return the persisted regime-comparison summary row for one result bundle."""

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


def _components(nodes: Sequence[CapitalNode]) -> tuple[FrtbComponent, ...]:
    """Return non-top-level FRTB components represented in a node collection."""

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
