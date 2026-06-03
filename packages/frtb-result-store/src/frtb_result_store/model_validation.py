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


def _freeze_metadata(instance: object, metadata: Mapping[str, object]) -> None:
    if not isinstance(metadata, Mapping):
        raise ResultStoreContractError("metadata must be a mapping", field="metadata")
    object.__setattr__(instance, "metadata", MappingProxyType(dict(metadata)))


def _freeze_mapping(instance: object, field_name: str, value: Mapping[str, object]) -> None:
    if not isinstance(value, Mapping):
        raise ResultStoreContractError(f"{field_name} must be a mapping", field=field_name)
    object.__setattr__(instance, field_name, MappingProxyType(dict(value)))
