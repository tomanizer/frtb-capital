"""Evidence reference helpers for AI explanation snapshots."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import cast

from frtb_result_store._ai_explanation_common import _nested_value, _optional_text


def _evidence_refs(
    run_id: str,
    target: Mapping[str, object],
    bounded_payload: Mapping[str, object],
) -> list[dict[str, object]]:
    refs: list[dict[str, object]] = []
    for row in cast(Sequence[Mapping[str, object]], bounded_payload.get("aggregate_rows", [])):
        refs.append(
            _evidence_ref("node", run_id, target, row.get("node_id"), row.get("label"), row)
        )
    for row in cast(Sequence[Mapping[str, object]], bounded_payload.get("movement_rows", [])):
        refs.append(
            _evidence_ref(
                "movement", run_id, target, row.get("movement_id"), row.get("movement_type"), row
            )
        )
    for row in cast(Sequence[Mapping[str, object]], bounded_payload.get("attribution_rows", [])):
        refs.append(
            _evidence_ref(
                "attribution", run_id, target, row.get("attribution_id"), row.get("category"), row
            )
        )
    for row in cast(Sequence[Mapping[str, object]], bounded_payload.get("lineage", [])):
        refs.append(
            _evidence_ref(
                "lineage", run_id, target, row.get("source_id"), row.get("relationship"), row
            )
        )
    for row in cast(Sequence[Mapping[str, object]], bounded_payload.get("diagnostics", [])):
        refs.append(
            _evidence_ref(
                "diagnostic", run_id, target, row.get("event_id"), row.get("message"), row
            )
        )
    for row in cast(Sequence[Mapping[str, object]], bounded_payload.get("source_row_samples", [])):
        refs.append(
            _evidence_ref(
                "source_row",
                run_id,
                target,
                row.get("source_row_id") or row.get("row_id"),
                "source row sample",
                row,
            )
        )
    for row in cast(Sequence[Mapping[str, object]], bounded_payload.get("artifact_page_refs", [])):
        refs.append(
            _evidence_ref(
                "artifact", run_id, target, row.get("artifact_id"), row.get("artifact_type"), row
            )
        )
    for row in cast(Sequence[Mapping[str, object]], bounded_payload.get("model_evidence", [])):
        risk_factor_id = row.get("risk_factor_id") or _nested_value(
            row, "metadata", "risk_factor_id"
        )
        refs.append(
            _evidence_ref("risk_factor", run_id, target, risk_factor_id, row.get("kind"), row)
        )
    return _dedupe_refs(refs)


def _evidence_ref(
    ref_type: str,
    run_id: str,
    target: Mapping[str, object],
    raw_id: object,
    raw_label: object,
    row: Mapping[str, object],
) -> dict[str, object]:
    ref_id = str(raw_id) if raw_id is not None else f"{ref_type}:{len(str(row))}"
    return {
        "ref_id": f"{ref_type}:{ref_id}",
        "ref_type": ref_type,
        "run_id": run_id,
        "hierarchy_node_id": _optional_text(row.get("node_id") or row.get("hierarchy_node_id")),
        "target_id": str(target["target_id"]),
        "artifact_id": _optional_text(row.get("artifact_id")),
        "source_id": _optional_text(row.get("source_id")),
        "attribution_id": _optional_text(row.get("attribution_id")),
        "risk_factor_id": _optional_text(row.get("risk_factor_id") or row.get("source_id")),
        "desk_id": _optional_text(row.get("desk_id")),
        "label": str(raw_label) if raw_label is not None else ref_id,
        "data_state": str(row.get("data_state", "AVAILABLE")),
        "citation_text": f"{ref_type} {ref_id}",
    }


def _dedupe_refs(refs: Sequence[Mapping[str, object]]) -> list[dict[str, object]]:
    seen: set[str] = set()
    deduped: list[dict[str, object]] = []
    for ref in refs:
        ref_id = str(ref["ref_id"])
        if ref_id not in seen:
            seen.add(ref_id)
            deduped.append(dict(ref))
    return deduped[:100]
