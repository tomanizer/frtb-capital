"""Component-specific reporting mart row builders for result-store bundles."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from frtb_result_store.model import (
    ArtifactRef,
    ArtifactType,
    CapitalMeasure,
    CapitalNode,
    FrtbComponent,
    ResultBundle,
)


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


def _drc_issuer_contributor_rows(bundle: ResultBundle) -> list[dict[str, object]]:
    return _component_identifier_rows(
        bundle,
        component=FrtbComponent.DRC,
        identifier_field="issuer_id",
        artifact_type=ArtifactType.DRC_JTD_TABLE,
    )


def _cva_counterparty_contributor_rows(bundle: ResultBundle) -> list[dict[str, object]]:
    return _component_identifier_rows(
        bundle,
        component=FrtbComponent.CVA,
        identifier_field="counterparty_id",
        artifact_type=ArtifactType.CVA_EXPOSURE_TABLE,
    )


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
        if not node.calculation_branch:
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
