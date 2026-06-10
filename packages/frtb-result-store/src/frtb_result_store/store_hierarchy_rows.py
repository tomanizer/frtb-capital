"""Hierarchy row serialization helpers for result-store tables."""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from datetime import datetime

from frtb_common.hashing import stable_json_dumps

from frtb_result_store._row_codecs import (
    int_value as _int_value,
)
from frtb_result_store._row_codecs import (
    json_mapping as _json_mapping,
)
from frtb_result_store._row_codecs import (
    metadata_json as _metadata_json,
)
from frtb_result_store._row_codecs import (
    optional_text as _optional_text,
)
from frtb_result_store.model import (
    HierarchyDefinition,
    HierarchyLevel,
    HierarchyNode,
    ResultStoreContractError,
)


def _hierarchy_definition_row(
    run_id: str,
    definition: HierarchyDefinition,
) -> dict[str, object]:
    return {
        "run_id": run_id,
        "hierarchy_id": definition.hierarchy_id,
        "hierarchy_version": definition.hierarchy_version,
        "hierarchy_name": definition.hierarchy_name,
        "leaf_level": definition.leaf_level,
        "levels_json": stable_json_dumps(
            [
                {
                    "level_name": level.level_name,
                    "dimension": level.dimension,
                    "level_order": level.level_order,
                }
                for level in definition.levels
            ]
        ),
        "created_at": definition.created_at.isoformat(),
        "metadata_json": _metadata_json(definition.metadata),
    }


def _hierarchy_node_row(run_id: str, node: HierarchyNode) -> dict[str, object]:
    return {
        "run_id": run_id,
        "hierarchy_id": node.hierarchy_id,
        "hierarchy_version": node.hierarchy_version,
        "hierarchy_node_id": node.hierarchy_node_id,
        "parent_hierarchy_node_id": node.parent_hierarchy_node_id,
        "level_name": node.level_name,
        "level_order": node.level_order,
        "business_key": node.business_key,
        "label": node.label,
        "path_json": stable_json_dumps(
            [
                {"level_name": level_name, "business_key": business_key}
                for level_name, business_key in node.path
            ]
        ),
        "metadata_json": _metadata_json(node.metadata),
    }


def _hierarchy_definition_from_row(row: Sequence[object]) -> HierarchyDefinition:
    return HierarchyDefinition(
        hierarchy_id=str(row[1]),
        hierarchy_version=str(row[2]),
        hierarchy_name=str(row[3]),
        leaf_level=str(row[4]),
        levels=tuple(_hierarchy_level_from_mapping(item) for item in _json_object_list(row[5])),
        created_at=datetime.fromisoformat(str(row[6])),
        metadata=_json_mapping(row[7]),
    )


def _hierarchy_node_from_row(row: Sequence[object]) -> HierarchyNode:
    path = tuple(_hierarchy_path_item_from_mapping(item) for item in _json_object_list(row[9]))
    return HierarchyNode(
        hierarchy_id=str(row[1]),
        hierarchy_version=str(row[2]),
        hierarchy_node_id=str(row[3]),
        parent_hierarchy_node_id=_optional_text(row[4]),
        level_name=str(row[5]),
        level_order=_int_value(row[6]),
        business_key=str(row[7]),
        label=str(row[8]),
        path=path,
        metadata=_json_mapping(row[10]),
    )


def _hierarchy_level_from_mapping(value: Mapping[str, object]) -> HierarchyLevel:
    level_name = _required_mapping_value(value, "level_name", "hierarchy level")
    dimension = _required_mapping_value(value, "dimension", "hierarchy level")
    level_order = _required_mapping_value(value, "level_order", "hierarchy level")
    return HierarchyLevel(
        level_name=str(level_name),
        dimension=str(dimension),
        level_order=_int_value(level_order),
    )


def _hierarchy_path_item_from_mapping(value: Mapping[str, object]) -> tuple[str, str]:
    level_name = _required_mapping_value(value, "level_name", "hierarchy node path")
    business_key = _required_mapping_value(value, "business_key", "hierarchy node path")
    return str(level_name), str(business_key)


def _required_mapping_value(
    value: Mapping[str, object],
    key: str,
    context: str,
) -> object:
    if key not in value:
        raise ResultStoreContractError(f"missing key in {context}: {key}")
    return value[key]


def _json_object_list(value: object) -> tuple[Mapping[str, object], ...]:
    try:
        parsed = json.loads(str(value))
    except json.JSONDecodeError as exc:
        raise ResultStoreContractError(f"malformed JSON object list: {exc}") from exc
    if not isinstance(parsed, list) or not all(isinstance(item, dict) for item in parsed):
        raise ResultStoreContractError("JSON field must decode to a list of objects")
    return tuple(parsed)
