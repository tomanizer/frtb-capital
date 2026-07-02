"""Evidence collection helpers for governed AI explanation snapshots."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from frtb_result_store._ai_explanation_artifacts import (
    _artifact_refs_for_evidence,
    _source_samples,
)
from frtb_result_store._ai_explanation_common import (
    _MAX_SECTION_ROWS,
    _artifact_ref_payload,
    _dataclass_payload,
    _json_mapping,
    _limitation,
    _optional_text,
    _text_list,
)
from frtb_result_store._ai_explanation_refs import _evidence_refs
from frtb_result_store._io_risk_factor_query_utils import _risk_factor_attribution_rows
from frtb_result_store.model import ResultStoreContractError


def _collect_evidence(
    store: Any,
    run_id: str,
    target: Mapping[str, object],
    state: Mapping[str, object],
    request: Mapping[str, object],
) -> dict[str, object]:
    nodes = tuple(store.capital_tree(run_id))
    target_type = str(target["target_type"])
    target_id = str(target["target_id"])
    selected_nodes = _selected_nodes(nodes, target_type, target_id, state)
    aggregate_rows = [_dataclass_payload(node) for node in selected_nodes[:_MAX_SECTION_ROWS]]
    measures = _measures_for_nodes(store, run_id, selected_nodes)
    attributions = _attributions_for_target(store, run_id, target_type, target_id, selected_nodes)
    movements = _movements_for_nodes(store, run_id, selected_nodes, state)
    lineage = _lineage_for_nodes(store, run_id, selected_nodes)
    diagnostics = _diagnostics(store, run_id, state)
    risk_factor_payload = _risk_factor_payload(store, run_id, target_type, target_id, state)
    source_samples, artifact_sample_refs, source_limitations = _source_samples(
        store,
        run_id,
        target_type,
        state,
    )
    artifact_refs = _artifact_refs_for_evidence(
        store,
        run_id,
        attributions,
        lineage,
        artifact_sample_refs,
        state,
    )
    bounded_payload = {
        "aggregate_rows": aggregate_rows,
        "measure_rows": measures,
        "movement_rows": movements,
        "attribution_rows": attributions,
        "diagnostics": diagnostics,
        "lineage": lineage,
        "source_row_samples": source_samples,
        "artifact_page_refs": [_artifact_ref_payload(ref) for ref in artifact_refs],
        "model_evidence": risk_factor_payload,
    }
    limitations = [*source_limitations]
    if not aggregate_rows and target_type in {"row", "desk", "panel"}:
        limitations.append(
            _limitation(
                "target_no_data",
                "No persisted capital node matched the selected explanation target.",
            )
        )
    if target_type == "risk_factor" and not risk_factor_payload:
        limitations.append(
            _limitation(
                "risk_factor_no_data",
                "No persisted risk-factor metadata or attribution evidence matched the target.",
            )
        )
    if not artifact_refs:
        limitations.append(
            _limitation(
                "artifact_refs_no_data",
                "No artifact page references were available for the selected evidence.",
            )
        )
    return {
        "bounded_payload": bounded_payload,
        "evidence_refs": _evidence_refs(run_id, target, bounded_payload),
        "limitations": limitations,
    }


def _selected_nodes(
    nodes: Sequence[object],
    target_type: str,
    target_id: str,
    state: Mapping[str, object],
) -> tuple[object, ...]:
    if target_type in {"row", "panel", "source_rows"}:
        row_id = _optional_text(state.get("row_id")) or target_id
        return tuple(node for node in nodes if getattr(node, "node_id", None) == row_id)
    if target_type == "desk":
        return tuple(node for node in nodes if getattr(node, "desk_id", None) == target_id)
    if target_type == "view":
        hierarchy_node_id = _optional_text(state.get("hierarchy_node_id")) or target_id
        selected = tuple(
            node for node in nodes if getattr(node, "node_id", None) == hierarchy_node_id
        )
        return selected or tuple(nodes[:_MAX_SECTION_ROWS])
    return ()


def _measures_for_nodes(
    store: Any, run_id: str, nodes: Sequence[object]
) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for node in nodes[:_MAX_SECTION_ROWS]:
        rows.extend(
            _dataclass_payload(measure)
            for measure in store.measures_for_node(run_id, str(getattr(node, "node_id")))
        )
    return rows[:_MAX_SECTION_ROWS]


def _attributions_for_target(
    store: Any,
    run_id: str,
    target_type: str,
    target_id: str,
    nodes: Sequence[object],
) -> list[dict[str, object]]:
    if target_type == "risk_factor":
        return [
            dict(row)
            for row in _risk_factor_attribution_rows(
                store, run_id, target_id, limit=_MAX_SECTION_ROWS
            )
        ]
    rows: list[dict[str, object]] = []
    for node in nodes[:_MAX_SECTION_ROWS]:
        rows.extend(
            _dataclass_payload(row)
            for row in store.attributions_for_node(run_id, str(getattr(node, "node_id")))
        )
    return rows[:_MAX_SECTION_ROWS]


def _movements_for_nodes(
    store: Any,
    run_id: str,
    nodes: Sequence[object],
    state: Mapping[str, object],
) -> list[dict[str, object]]:
    baseline_run_id = _optional_text(state.get("baseline_run_id"))
    rows: list[dict[str, object]] = []
    for node in nodes[:_MAX_SECTION_ROWS]:
        rows.extend(
            _dataclass_payload(row)
            for row in store.movement_results(
                run_id,
                baseline_run_id=baseline_run_id,
                node_id=str(getattr(node, "node_id")),
            )
        )
    if not rows and nodes:
        rows.extend(
            _dataclass_payload(row)
            for row in store.movement_results(run_id, baseline_run_id=baseline_run_id)
        )
    return rows[:_MAX_SECTION_ROWS]


def _lineage_for_nodes(store: Any, run_id: str, nodes: Sequence[object]) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for node in nodes[:_MAX_SECTION_ROWS]:
        rows.extend(
            _dataclass_payload(row)
            for row in store.lineage_for_result(run_id, str(getattr(node, "node_id")))
        )
    return rows[:_MAX_SECTION_ROWS]


def _diagnostics(store: Any, run_id: str, state: Mapping[str, object]) -> list[dict[str, object]]:
    visible = set(_text_list(state.get("visible_diagnostic_ids")))
    rows = [_dataclass_payload(row) for row in store.result_events(run_id)]
    if visible:
        rows = [row for row in rows if str(row.get("event_id")) in visible]
    return rows[:_MAX_SECTION_ROWS]


def _risk_factor_payload(
    store: Any,
    run_id: str,
    target_type: str,
    target_id: str,
    state: Mapping[str, object],
) -> list[dict[str, object]]:
    risk_factor_id = (
        target_id if target_type == "risk_factor" else _optional_text(state.get("risk_factor_id"))
    )
    if risk_factor_id is None:
        return []
    payloads: list[dict[str, object]] = []
    try:
        metadata = store.get_risk_factor(run_id, risk_factor_id)
        if metadata.get("state") == "available":
            payloads.append({"kind": "risk_factor_metadata", **_json_mapping(metadata)})
        lineage = store.risk_factor_lineage(run_id, risk_factor_id)
        if lineage.get("state") == "available":
            payloads.append({"kind": "risk_factor_lineage", **_json_mapping(lineage)})
        capital = store.risk_factor_capital(run_id, risk_factor_id)
        if capital.get("state") == "available":
            payloads.append({"kind": "risk_factor_capital", **_json_mapping(capital)})
        source_rows = store.risk_factor_source_rows(run_id, risk_factor_id, limit=5)
        if source_rows.get("state") == "available":
            payloads.append({"kind": "risk_factor_source_rows", **_json_mapping(source_rows)})
    except ResultStoreContractError:
        raise
    return payloads[:_MAX_SECTION_ROWS]
