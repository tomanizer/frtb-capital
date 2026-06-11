"""Persisted reporting mart generation for the Parquet result store."""

from __future__ import annotations

from collections.abc import Callable, Sequence

from frtb_common import AttributionMethod

from frtb_result_store._row_codecs import (
    stored_value as _stored_value,
)
from frtb_result_store.mart_capital_tree_rows import (
    _capital_tree_rows,
)
from frtb_result_store.mart_component_breakdown_rows import (
    _component_breakdown_rows,
)
from frtb_result_store.mart_component_rows import (
    _cva_counterparty_contributor_rows,
    _drc_issuer_contributor_rows,
    _ima_desk_dashboard_rows,
    _rrao_exposure_summary_rows,
    _sbm_bucket_ladder_rows,
)
from frtb_result_store.mart_movement_rows import (
    _movement_summary_rows,
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
    capital_summary_row,
    regime_comparison_row,
)
from frtb_result_store.model import (
    CapitalAttributionRecord,
    CapitalSummaryRow,
    CapitalTreeMartRow,
    ComponentBreakdownRow,
    FrtbComponent,
    MovementSummaryRow,
    ResultBundle,
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
    """Project one result bundle into every persisted reporting mart.

    Parameters
    ----------
    bundle:
        Validated run result bundle to serialize.
    lifecycle_status:
        Current append-only lifecycle state to stamp into summary-level marts.

    Returns
    -------
    dict[str, list[dict[str, object]]]
        Mapping from mart name to storage-ready row dictionaries.
    """

    return {
        "capital_summary": [capital_summary_row(bundle, lifecycle_status=lifecycle_status)],
        "capital_tree": _capital_tree_rows(bundle),
        "top_contributors": _top_contributor_rows(bundle),
        "residual_attribution": _residual_attribution_rows(bundle),
        "unsupported_attribution": _unsupported_attribution_rows(bundle),
        "movement_summary": _movement_summary_rows(bundle),
        "regime_comparison": [regime_comparison_row(bundle, lifecycle_status=lifecycle_status)],
        "component_breakdown": _component_breakdown_rows(bundle),
        "ima_desk_dashboard": _ima_desk_dashboard_rows(bundle),
        "sbm_bucket_ladder": _sbm_bucket_ladder_rows(bundle),
        "drc_issuer_contributors": _drc_issuer_contributor_rows(bundle),
        "cva_counterparty_contributors": _cva_counterparty_contributor_rows(bundle),
        "rrao_exposure_summary": _rrao_exposure_summary_rows(bundle),
    }


def capital_summary_from_row(row: Sequence[object]) -> CapitalSummaryRow:
    """Deserialize one persisted capital-summary mart row.

    Parameters
    ----------
    row:
        Storage-order field sequence read from the ``capital_summary`` mart.

    Returns
    -------
    CapitalSummaryRow
        Typed capital-summary projection row.
    """

    return _capital_summary_from_row(row)


def capital_tree_mart_from_row(row: Sequence[object]) -> CapitalTreeMartRow:
    """Deserialize one persisted capital-tree mart row.

    Parameters
    ----------
    row:
        Storage-order field sequence read from the ``capital_tree`` mart.

    Returns
    -------
    CapitalTreeMartRow
        Typed flattened capital-tree projection row.
    """

    return _capital_tree_mart_from_row(row)


def component_breakdown_from_row(row: Sequence[object]) -> ComponentBreakdownRow:
    """Deserialize one persisted component-breakdown mart row.

    Parameters
    ----------
    row:
        Storage-order field sequence read from the ``component_breakdown`` mart.

    Returns
    -------
    ComponentBreakdownRow
        Typed component-level capital total projection row.
    """

    return _component_breakdown_from_row(row)


def movement_summary_from_row(row: Sequence[object]) -> MovementSummaryRow:
    """Deserialize one persisted movement-summary mart row.

    Parameters
    ----------
    row:
        Storage-order field sequence read from the ``movement_summary`` mart.

    Returns
    -------
    MovementSummaryRow
        Typed capital movement projection row.
    """

    return _movement_summary_from_row(row)


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


def _attribution_amount(attribution: CapitalAttributionRecord) -> float:
    return (0.0 if attribution.contribution is None else float(attribution.contribution)) + float(
        attribution.residual
    )
