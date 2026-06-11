"""Attribution projection reporting mart row builders for result-store bundles."""

from __future__ import annotations

from collections.abc import Callable

from frtb_common import AttributionMethod

from frtb_result_store._row_codecs import (
    stored_value as _stored_value,
)
from frtb_result_store.model import CapitalAttributionRecord, FrtbComponent, ResultBundle


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


__all__ = [
    "_attribution_amount",
    "_attribution_projection_rows",
    "_residual_attribution_rows",
    "_top_contributor_rows",
    "_unsupported_attribution_rows",
]
