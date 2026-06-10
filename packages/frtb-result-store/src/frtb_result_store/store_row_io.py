"""Row serialization and deserialization for result-store tables."""

from __future__ import annotations

import time
from collections.abc import Sequence
from datetime import date, datetime
from typing import cast

from frtb_common import AttributionMethod
from frtb_common.hashing import stable_json_dumps

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
    json_text_tuple as _json_text_tuple,
)
from frtb_result_store._row_codecs import (
    metadata_json as _metadata_json,
)
from frtb_result_store._row_codecs import (
    optional_float as _optional_float,
)
from frtb_result_store._row_codecs import (
    optional_text as _optional_text,
)
from frtb_result_store._row_codecs import (
    stored_value as _stored_value,
)
from frtb_result_store.artifacts import RequiredArtifactExpectation
from frtb_result_store.model import (
    ArtifactRef,
    ArtifactType,
    CalculationRun,
    CapitalAttributionRecord,
    CapitalEdge,
    CapitalMeasure,
    CapitalNode,
    EdgeType,
    FrtbComponent,
    LineageRef,
    MovementResult,
    NodeType,
    ResultBundle,
    RunStatus,
    RunStatusEvent,
)
from frtb_result_store.run_metadata_io import (
    input_manifest_row as _input_manifest_row,
)
from frtb_result_store.run_metadata_io import (
    result_event_row as _result_event_row,
)
from frtb_result_store.run_metadata_io import (
    telemetry_row as _telemetry_row,
)
from frtb_result_store.store_hierarchy_rows import (
    _hierarchy_definition_from_row as _hierarchy_definition_from_row,
    _hierarchy_definition_row as _hierarchy_definition_row,
    _hierarchy_level_from_mapping as _hierarchy_level_from_mapping,
    _hierarchy_node_from_row as _hierarchy_node_from_row,
    _hierarchy_node_row as _hierarchy_node_row,
    _hierarchy_path_item_from_mapping as _hierarchy_path_item_from_mapping,
    _json_object_list as _json_object_list,
)


def _rows_for_bundle(
    bundle: ResultBundle,
    *,
    artifact_refs: Sequence[ArtifactRef] = (),
    artifact_expectations: Sequence[RequiredArtifactExpectation] = (),
) -> dict[str, list[dict[str, object]]]:
    artifacts = tuple(bundle.artifacts) + tuple(artifact_refs)
    return {
        "runs": [_run_row(bundle.run)],
        "hierarchy_definitions": (
            []
            if bundle.hierarchy_definition is None
            else [_hierarchy_definition_row(bundle.run.run_id, bundle.hierarchy_definition)]
        ),
        "hierarchy_nodes": [
            _hierarchy_node_row(bundle.run.run_id, node) for node in bundle.hierarchy_nodes
        ],
        "capital_nodes": [_node_row(node) for node in bundle.nodes],
        "capital_edges": [_edge_row(edge) for edge in bundle.edges],
        "capital_measures": [_measure_row(measure) for measure in bundle.measures],
        "artifact_refs": [_artifact_row(artifact) for artifact in artifacts],
        "artifact_expectations": [
            _artifact_expectation_row(bundle.run.run_id, expectation)
            for expectation in artifact_expectations
        ],
        "input_snapshot_manifests": [
            _input_manifest_row(manifest) for manifest in bundle.input_manifests
        ],
        "lineage_refs": [_lineage_row(lineage) for lineage in bundle.lineage],
        "capital_attributions": [
            _attribution_row(attribution) for attribution in bundle.attributions
        ],
        "movement_results": [_movement_row(movement) for movement in bundle.movement_results],
        "result_events": [_result_event_row(event) for event in bundle.events],
        "run_telemetry": [_telemetry_row(telemetry) for telemetry in bundle.telemetry],
    }


def _run_row(run: CalculationRun) -> dict[str, object]:
    return {
        "run_id": run.run_id,
        "run_group_id": run.run_group_id,
        "as_of_date": run.as_of_date.isoformat(),
        "regime_id": run.regime_id,
        "base_currency": run.base_currency,
        "input_snapshot_id": run.input_snapshot_id,
        "calculation_scope": run.calculation_scope,
        "engine_version": run.engine_version,
        "code_version": run.code_version,
        "calculation_policy_id": run.calculation_policy_id,
        "created_at": run.created_at.isoformat(),
        "identity_payload_json": _metadata_json(run.identity_payload),
        "run_group_identity_payload_json": _metadata_json(run.run_group_identity_payload),
        "metadata_json": _metadata_json(run.metadata),
    }


def _node_row(node: CapitalNode) -> dict[str, object]:
    return {
        "run_id": node.run_id,
        "node_id": node.node_id,
        "node_type": _stored_value(node.node_type),
        "component": _stored_value(node.component),
        "label": node.label,
        "desk_id": node.desk_id,
        "portfolio_id": node.portfolio_id,
        "book_id": node.book_id,
        "risk_class": node.risk_class,
        "bucket": node.bucket,
        "issuer_id": node.issuer_id,
        "counterparty_id": node.counterparty_id,
        "calculation_branch": node.calculation_branch,
        "regulatory_rule_id": node.regulatory_rule_id,
        "sort_key": node.sort_key,
        "metadata_json": _metadata_json(node.metadata),
    }


def _edge_row(edge: CapitalEdge) -> dict[str, object]:
    return {
        "run_id": edge.run_id,
        "parent_node_id": edge.parent_node_id,
        "child_node_id": edge.child_node_id,
        "edge_type": _stored_value(edge.edge_type),
        "aggregation_weight": edge.aggregation_weight,
        "sort_key": edge.sort_key,
    }


def _measure_row(measure: CapitalMeasure) -> dict[str, object]:
    return {
        "run_id": measure.run_id,
        "node_id": measure.node_id,
        "measure_name": measure.measure_name,
        "amount": measure.amount,
        "currency": measure.currency,
        "unit": measure.unit,
        "scenario": measure.scenario,
        "methodology": measure.methodology,
        "regulatory_rule_id": measure.regulatory_rule_id,
        "citations_json": stable_json_dumps(measure.citations),
        "metadata_json": _metadata_json(measure.metadata),
    }


def _artifact_row(artifact: ArtifactRef) -> dict[str, object]:
    return {
        "run_id": artifact.run_id,
        "artifact_id": artifact.artifact_id,
        "component": _stored_value(artifact.component),
        "artifact_type": _stored_value(artifact.artifact_type),
        "uri": artifact.uri,
        "format": artifact.format,
        "row_count": artifact.row_count,
        "schema_fingerprint": artifact.schema_fingerprint,
        "partition_keys_json": stable_json_dumps(artifact.partition_keys),
        "metadata_json": _metadata_json(artifact.metadata),
    }


def _artifact_expectation_row(
    run_id: str,
    expectation: RequiredArtifactExpectation,
) -> dict[str, object]:
    return {
        "run_id": run_id,
        "component": _stored_value(expectation.component),
        "artifact_type": _stored_value(expectation.artifact_type),
        "trigger_name": expectation.trigger_name,
        "required": expectation.required,
        "reason": expectation.reason,
    }


def _lineage_row(lineage: LineageRef) -> dict[str, object]:
    return {
        "run_id": lineage.run_id,
        "result_id": lineage.result_id,
        "source_type": lineage.source_type,
        "source_id": lineage.source_id,
        "relationship": lineage.relationship,
        "source_hash": lineage.source_hash,
        "metadata_json": _metadata_json(lineage.metadata),
    }


def _attribution_row(attribution: CapitalAttributionRecord) -> dict[str, object]:
    return {
        "run_id": attribution.run_id,
        "node_id": attribution.node_id,
        "attribution_id": attribution.attribution_id,
        "target_type": attribution.target_type,
        "target_id": attribution.target_id,
        "source_id": attribution.source_id,
        "source_level": attribution.source_level,
        "method": _stored_value(attribution.method),
        "category": attribution.category,
        "bucket_key": attribution.bucket_key,
        "base_amount": attribution.base_amount,
        "marginal_multiplier": attribution.marginal_multiplier,
        "contribution": attribution.contribution,
        "residual": attribution.residual,
        "unsupported_reason": attribution.unsupported_reason,
        "artifact_id": attribution.artifact_id,
        "metadata_json": _metadata_json(attribution.metadata),
    }


def _movement_row(movement: MovementResult) -> dict[str, object]:
    return {
        "run_id": movement.run_id,
        "baseline_run_id": movement.baseline_run_id,
        "movement_id": movement.movement_id,
        "node_id": movement.node_id,
        "movement_type": movement.movement_type,
        "from_amount": movement.from_amount,
        "to_amount": movement.to_amount,
        "delta_amount": movement.delta_amount,
        "base_currency": movement.base_currency,
        "driver_type": movement.driver_type,
        "driver_id": movement.driver_id,
        "explanation": movement.explanation,
        "attribution_method": None
        if movement.attribution_method is None
        else _stored_value(movement.attribution_method),
        "artifact_id": movement.artifact_id,
        "metadata_json": _metadata_json(movement.metadata),
    }


def _elapsed_ms(started_at: float) -> float:
    return (time.perf_counter() - started_at) * 1000.0


def _initial_status_event(run: CalculationRun) -> RunStatusEvent:
    return RunStatusEvent.transition(
        run_id=run.run_id,
        from_status=None,
        to_status=RunStatus.CANDIDATE,
        event_time=run.created_at,
        actor="result-store",
        reason_code="RUN_COMMITTED",
        reason_text="Run committed to result store",
    )


def _status_event_row(event: RunStatusEvent) -> dict[str, object]:
    from_status = None if event.from_status is None else cast(RunStatus, event.from_status)
    to_status = cast(RunStatus, event.to_status)
    return {
        "event_id": event.event_id,
        "run_id": event.run_id,
        "from_status": None if from_status is None else from_status.value,
        "to_status": to_status.value,
        "event_time": event.event_time.isoformat(),
        "actor": event.actor,
        "reason_code": event.reason_code,
        "reason_text": event.reason_text,
        "external_evidence_ref": event.external_evidence_ref,
    }


def _run_from_row(row: Sequence[object]) -> CalculationRun:
    return CalculationRun(
        run_id=str(row[0]),
        run_group_id=_optional_text(row[1]),
        as_of_date=date.fromisoformat(str(row[2])),
        regime_id=str(row[3]),
        base_currency=str(row[4]),
        input_snapshot_id=str(row[5]),
        calculation_scope=str(row[6]),
        engine_version=str(row[7]),
        code_version=str(row[8]),
        calculation_policy_id=str(row[9]),
        created_at=datetime.fromisoformat(str(row[10])),
        identity_payload=_json_mapping(row[11]),
        run_group_identity_payload=_json_mapping(row[12]),
        metadata=_json_mapping(row[13]),
    )


def _node_from_row(row: Sequence[object]) -> CapitalNode:
    return CapitalNode(
        run_id=str(row[0]),
        node_id=str(row[1]),
        node_type=NodeType(str(row[2])),
        component=FrtbComponent(str(row[3])),
        label=str(row[4]),
        desk_id=_optional_text(row[5]),
        portfolio_id=_optional_text(row[6]),
        book_id=_optional_text(row[7]),
        risk_class=_optional_text(row[8]),
        bucket=_optional_text(row[9]),
        issuer_id=_optional_text(row[10]),
        counterparty_id=_optional_text(row[11]),
        calculation_branch=_optional_text(row[12]),
        regulatory_rule_id=_optional_text(row[13]),
        sort_key=_int_value(row[14]),
        metadata=_json_mapping(row[15]),
    )


def _edge_from_row(row: Sequence[object]) -> CapitalEdge:
    return CapitalEdge(
        run_id=str(row[0]),
        parent_node_id=str(row[1]),
        child_node_id=str(row[2]),
        edge_type=EdgeType(str(row[3])),
        aggregation_weight=_float_value(row[4]),
        sort_key=_int_value(row[5]),
    )


def _measure_from_row(row: Sequence[object]) -> CapitalMeasure:
    return CapitalMeasure(
        run_id=str(row[0]),
        node_id=str(row[1]),
        measure_name=str(row[2]),
        amount=_float_value(row[3]),
        currency=str(row[4]),
        unit=str(row[5]),
        scenario=_optional_text(row[6]),
        methodology=_optional_text(row[7]),
        regulatory_rule_id=_optional_text(row[8]),
        citations=_json_text_tuple(row[9]),
        metadata=_json_mapping(row[10]),
    )


def _artifact_from_row(row: Sequence[object]) -> ArtifactRef:
    return ArtifactRef(
        run_id=str(row[0]),
        artifact_id=str(row[1]),
        component=FrtbComponent(str(row[2])),
        artifact_type=ArtifactType(str(row[3])),
        uri=str(row[4]),
        format=str(row[5]),
        row_count=_int_value(row[6]),
        schema_fingerprint=_optional_text(row[7]),
        partition_keys=_json_text_tuple(row[8]),
        metadata=_json_mapping(row[9]),
    )


def _lineage_from_row(row: Sequence[object]) -> LineageRef:
    return LineageRef(
        run_id=str(row[0]),
        result_id=str(row[1]),
        source_type=str(row[2]),
        source_id=str(row[3]),
        relationship=str(row[4]),
        source_hash=_optional_text(row[5]),
        metadata=_json_mapping(row[6]),
    )


def _attribution_from_row(row: Sequence[object]) -> CapitalAttributionRecord:
    return CapitalAttributionRecord(
        run_id=str(row[0]),
        node_id=str(row[1]),
        contribution_id=str(row[2]),
        source_id=str(row[5]),
        source_level=str(row[6]),
        method=AttributionMethod(str(row[7])),
        category=str(row[8]),
        bucket_key=_optional_text(row[9]),
        base_amount=_float_value(row[10]),
        marginal_multiplier=_optional_float(row[11]),
        contribution=_optional_float(row[12]),
        residual=_float_value(row[13]),
        reason=str(row[14]),
        target_type=str(row[3]),
        target_id=str(row[4]),
        unsupported_reason=str(row[14]),
        artifact_id=_optional_text(row[15]),
        metadata=_json_mapping(row[16]),
    )


def _movement_from_row(row: Sequence[object]) -> MovementResult:
    return MovementResult(
        run_id=str(row[0]),
        baseline_run_id=str(row[1]),
        movement_id=str(row[2]),
        node_id=str(row[3]),
        movement_type=str(row[4]),
        from_amount=_float_value(row[5]),
        to_amount=_float_value(row[6]),
        delta_amount=_float_value(row[7]),
        base_currency=str(row[8]),
        driver_type=str(row[9]),
        driver_id=str(row[10]),
        explanation=str(row[11]),
        attribution_method=_optional_text(row[12]),
        artifact_id=_optional_text(row[13]),
        metadata=_json_mapping(row[14]),
    )


def _status_event_from_row(row: Sequence[object]) -> RunStatusEvent:
    from_status_text = _optional_text(row[2])
    return RunStatusEvent(
        event_id=str(row[0]),
        run_id=str(row[1]),
        from_status=None if not from_status_text else RunStatus(from_status_text),
        to_status=RunStatus(str(row[3])),
        event_time=datetime.fromisoformat(str(row[4])),
        actor=str(row[5]),
        reason_code=str(row[6]),
        reason_text=str(row[7]),
        external_evidence_ref=_optional_text(row[8]),
    )
