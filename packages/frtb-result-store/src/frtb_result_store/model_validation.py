"""Private validation helpers for result-store contracts."""

from __future__ import annotations

import math
import unicodedata
from collections.abc import Mapping
from datetime import date, datetime
from types import MappingProxyType
from typing import TYPE_CHECKING

from frtb_result_store.model_enums import EnumT, ResultStoreContractError

if TYPE_CHECKING:
    from frtb_result_store.model_entities import (
        CapitalAttributionRecord,
        CapitalEdge,
        CapitalMeasure,
        LineageRef,
        MovementResult,
        ResultBundle,
    )


def _coerce_enum(value: EnumT | str, enum_type: type[EnumT], field_name: str) -> EnumT:
    if isinstance(value, enum_type):
        return value
    try:
        return enum_type(value)
    except ValueError as exc:
        allowed = ", ".join(item.value for item in enum_type)
        raise ResultStoreContractError(
            f"{field_name} must be one of: {allowed}",
            field=field_name,
        ) from exc


def _normalize_identity_text(value: object) -> str:
    if not isinstance(value, str) or not value:
        raise ResultStoreContractError("identity field must be non-empty text")
    return unicodedata.normalize("NFC", value)


def _normalize_identity_value(value: object, field: str) -> object:
    if isinstance(value, str):
        if not value:
            raise ResultStoreContractError(f"{field} must be non-empty text", field=field)
        return unicodedata.normalize("NFC", value)
    if isinstance(value, datetime):
        if value.tzinfo is None:
            raise ResultStoreContractError(
                f"{field} datetime must be timezone-aware",
                field=field,
            )
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, Mapping):
        return {
            _normalize_identity_text(key): _normalize_identity_value(item, field)
            for key, item in value.items()
        }
    if isinstance(value, tuple | list):
        return tuple(_normalize_identity_value(item, field) for item in value)
    if value is None:
        raise ResultStoreContractError(f"{field} must not be null", field=field)
    return value


def _require_non_empty_text(value: object, field: str) -> None:
    if not isinstance(value, str) or not value:
        raise ResultStoreContractError(f"{field} must be non-empty text", field=field)


def _require_registered_value(value: str, registry: frozenset[str], field: str) -> None:
    if value not in registry:
        allowed = ", ".join(sorted(registry))
        raise ResultStoreContractError(f"{field} must be one of: {allowed}", field=field)


def _registered_upper_value(value: str, registry: frozenset[str], field: str) -> str:
    normalized = value.upper()
    _require_registered_value(normalized, registry, field)
    return normalized


def _require_mapping(value: object, field: str) -> None:
    if not isinstance(value, Mapping):
        raise ResultStoreContractError(f"{field} must be a mapping", field=field)


def _validate_optional_text(value: object, field: str) -> None:
    if value is not None and (not isinstance(value, str) or not value):
        raise ResultStoreContractError(f"{field} must be non-empty text when set", field=field)


def _require_plain_date(value: object, field: str) -> None:
    if not isinstance(value, date) or isinstance(value, datetime):
        raise ResultStoreContractError(f"{field} must be a date", field=field)


def _require_finite_number(value: object, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ResultStoreContractError(f"{field} must be numeric", field=field)
    number = float(value)
    if not math.isfinite(number):
        raise ResultStoreContractError(f"{field} must be finite", field=field)
    return number


def _require_non_negative_int(value: object, field: str) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ResultStoreContractError(f"{field} must be a non-negative integer", field=field)


def _require_int(value: object, field: str) -> None:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ResultStoreContractError(f"{field} must be an integer", field=field)


def _require_text_tuple(value: object, field: str) -> tuple[str, ...]:
    if not isinstance(value, tuple) or not all(isinstance(item, str) and item for item in value):
        raise ResultStoreContractError(f"{field} must be a tuple of non-empty text", field=field)
    return value


def _require_non_empty_tuple(value: object, field: str) -> None:
    if not isinstance(value, tuple) or not value:
        raise ResultStoreContractError(f"{field} must be a non-empty tuple", field=field)


def _require_run_id(value: str, expected: str, field: str) -> None:
    if value != expected:
        raise ResultStoreContractError(
            f"{field} run_id {value!r} does not match bundle run_id {expected!r}",
            field=field,
        )


def _tuple_bundle_sequences(bundle: ResultBundle) -> None:
    for field_name in (
        "hierarchy_nodes",
        "edges",
        "measures",
        "artifacts",
        "input_manifests",
        "lineage",
        "attributions",
        "movement_results",
        "risk_factor_snapshots",
        "risk_factor_metadata",
        "risk_factor_source_mappings",
        "events",
        "telemetry",
    ):
        object.__setattr__(bundle, field_name, tuple(getattr(bundle, field_name)))


def _validate_bundle_hierarchy(bundle: ResultBundle) -> None:
    from frtb_result_store.model_entities import HierarchyDefinition

    definition = bundle.hierarchy_definition
    if definition is not None and not isinstance(definition, HierarchyDefinition):
        raise ResultStoreContractError(
            "hierarchy_definition must be a HierarchyDefinition",
            field="hierarchy_definition",
        )
    if bundle.hierarchy_nodes and definition is None:
        raise ResultStoreContractError(
            "hierarchy_nodes require a hierarchy_definition",
            field="hierarchy_nodes",
        )
    if not bundle.hierarchy_nodes or definition is None:
        return
    if not any(node.level_name == definition.leaf_level for node in bundle.hierarchy_nodes):
        raise ResultStoreContractError(
            "hierarchy_nodes must include the configured leaf level",
            field="hierarchy_nodes",
        )


def _duplicate_values(values: list[str]) -> list[str]:
    seen: set[str] = set()
    duplicates: set[str] = set()
    for value in values:
        if value in seen:
            duplicates.add(value)
        else:
            seen.add(value)
    return sorted(duplicates)


def _validate_bundle_edges(
    edges: tuple[CapitalEdge, ...],
    run_id: str,
    known_nodes: set[str],
) -> None:
    for edge in edges:
        _require_run_id(edge.run_id, run_id, "edges")
        if edge.parent_node_id not in known_nodes:
            raise ResultStoreContractError(
                f"edge parent node not found: {edge.parent_node_id}",
                field="edges",
            )
        if edge.child_node_id not in known_nodes:
            raise ResultStoreContractError(
                f"edge child node not found: {edge.child_node_id}",
                field="edges",
            )


def _validate_bundle_measures(
    measures: tuple[CapitalMeasure, ...],
    run_id: str,
    known_nodes: set[str],
) -> None:
    for measure in measures:
        _require_run_id(measure.run_id, run_id, "measures")
        if measure.node_id not in known_nodes:
            raise ResultStoreContractError(
                f"measure node not found: {measure.node_id}",
                field="measures",
            )


def _validate_bundle_attributions(
    attributions: tuple[CapitalAttributionRecord, ...],
    run_id: str,
    known_nodes: set[str],
) -> None:
    for attribution in attributions:
        _require_run_id(attribution.run_id, run_id, "attributions")
        if attribution.node_id not in known_nodes:
            raise ResultStoreContractError(
                f"attribution node not found: {attribution.node_id}",
                field="attributions",
            )


def _validate_bundle_lineage(
    lineage_refs: tuple[LineageRef, ...],
    run_id: str,
    known_results: set[str],
) -> None:
    for lineage in lineage_refs:
        _require_run_id(lineage.run_id, run_id, "lineage")
        if lineage.result_id not in known_results:
            raise ResultStoreContractError(
                f"lineage result not found: {lineage.result_id}",
                field="lineage",
            )


def _validate_bundle_artifact_sources(
    bundle: ResultBundle,
    known_artifacts: set[str],
) -> None:
    known_input_snapshots = (
        {manifest.input_snapshot_id for manifest in bundle.input_manifests}
        | {bundle.run.input_snapshot_id}
    )
    for attribution in bundle.attributions:
        if attribution.artifact_id is not None and attribution.artifact_id not in known_artifacts:
            raise ResultStoreContractError(
                f"attribution artifact not found: {attribution.artifact_id}",
                field="attributions",
            )
    for lineage in bundle.lineage:
        if lineage.source_type == "artifact" and lineage.source_id not in known_artifacts:
            raise ResultStoreContractError(
                f"lineage artifact source not found: {lineage.source_id}",
                field="lineage",
            )
        if (
            lineage.source_type == "input_snapshot"
            and lineage.source_id not in known_input_snapshots
        ):
            raise ResultStoreContractError(
                f"lineage input snapshot source not found: {lineage.source_id}",
                field="lineage",
            )


def _validate_bundle_movements(
    movement_results: tuple[MovementResult, ...],
    run_id: str,
    known_nodes: set[str],
) -> None:
    movement_ids: list[str] = []
    for movement in movement_results:
        _require_run_id(movement.run_id, run_id, "movement_results")
        if movement.node_id not in known_nodes:
            raise ResultStoreContractError(
                f"movement node not found: {movement.node_id}",
                field="movement_results",
            )
        movement_ids.append(movement.movement_id)
    duplicate_movements = _duplicate_values(movement_ids)
    if duplicate_movements:
        raise ResultStoreContractError(
            f"duplicate movement ids: {', '.join(duplicate_movements)}",
            field="movement_results",
        )


def _validate_bundle_risk_factor_metadata(bundle: ResultBundle) -> None:
    run_id = bundle.run.run_id
    snapshot_ids: list[str] = []
    for snapshot in bundle.risk_factor_snapshots:
        _require_run_id(snapshot.run_id, run_id, "risk_factor_snapshots")
        snapshot_ids.append(snapshot.snapshot_id)
    duplicate_snapshots = _duplicate_values(snapshot_ids)
    if duplicate_snapshots:
        raise ResultStoreContractError(
            f"duplicate risk-factor snapshot ids: {', '.join(duplicate_snapshots)}",
            field="risk_factor_snapshots",
        )
    known_snapshots = set(snapshot_ids)
    record_keys: list[str] = []
    known_record_keys: set[tuple[str, str]] = set()
    for record in bundle.risk_factor_metadata:
        _require_run_id(record.run_id, run_id, "risk_factor_metadata")
        if record.snapshot_id not in known_snapshots:
            raise ResultStoreContractError(
                f"risk-factor metadata references unknown snapshot: {record.snapshot_id}",
                field="risk_factor_metadata",
            )
        key = (record.snapshot_id, str(record.risk_factor_id))
        record_keys.append("\x1f".join(key))
        known_record_keys.add(key)
    duplicate_records = _duplicate_values(record_keys)
    if duplicate_records:
        formatted = ", ".join(value.replace("\x1f", "/") for value in duplicate_records)
        raise ResultStoreContractError(
            f"duplicate risk-factor metadata records: {formatted}",
            field="risk_factor_metadata",
        )
    source_keys: list[str] = []
    for mapping in bundle.risk_factor_source_mappings:
        _require_run_id(mapping.run_id, run_id, "risk_factor_source_mappings")
        if mapping.snapshot_id not in known_snapshots:
            raise ResultStoreContractError(
                f"risk-factor source mapping references unknown snapshot: {mapping.snapshot_id}",
                field="risk_factor_source_mappings",
            )
        if (mapping.snapshot_id, str(mapping.risk_factor_id)) not in known_record_keys:
            raise ResultStoreContractError(
                "risk-factor source mapping references unknown risk_factor_id: "
                f"{mapping.risk_factor_id}",
                field="risk_factor_source_mappings",
            )
        source_keys.append(
            "\x1f".join(
                (
                    mapping.snapshot_id,
                    mapping.source_system,
                    mapping.source_row_id,
                    mapping.relationship,
                )
            )
        )
    duplicate_sources = _duplicate_values(source_keys)
    if duplicate_sources:
        formatted = ", ".join(value.replace("\x1f", "/") for value in duplicate_sources)
        raise ResultStoreContractError(
            f"duplicate risk-factor source mappings: {formatted}",
            field="risk_factor_source_mappings",
        )


def _freeze_metadata(instance: object, metadata: Mapping[str, object]) -> None:
    if not isinstance(metadata, Mapping):
        raise ResultStoreContractError("metadata must be a mapping", field="metadata")
    object.__setattr__(instance, "metadata", MappingProxyType(dict(metadata)))


def _freeze_mapping(instance: object, field_name: str, value: Mapping[str, object]) -> None:
    if not isinstance(value, Mapping):
        raise ResultStoreContractError(f"{field_name} must be a mapping", field=field_name)
    object.__setattr__(instance, field_name, MappingProxyType(dict(value)))
