"""Movement-summary reporting mart row builders for result-store bundles."""

from __future__ import annotations

from frtb_result_store._row_codecs import (
    stored_value as _stored_value,
)
from frtb_result_store.model import MovementResult, MovementSummaryRow, ResultBundle


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


__all__ = ["_movement_summary_row", "_movement_summary_rows"]
