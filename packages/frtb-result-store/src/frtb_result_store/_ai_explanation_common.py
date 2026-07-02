"""Shared helpers for governed AI explanation snapshots."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import fields, is_dataclass
from datetime import datetime
from enum import Enum
from typing import cast

from frtb_common.hashing import stable_json_hash

from frtb_result_store.model import ArtifactRef, ResultStoreContractError

_PROMPT_TEMPLATE_ID = "capital-navigator-ai-explanation-snapshot"
_PROMPT_TEMPLATE_VERSION = "1.0.0"
_SNAPSHOT_BUILDER_VERSION = "1.0.0"
_REDACTION_POLICY_VERSION = "navigator-display-redaction-v1"
_MAX_SECTION_ROWS = 25
_MAX_SOURCE_SAMPLE_ROWS = 25
_TARGET_TYPES = frozenset({"view", "panel", "row", "desk", "risk_factor", "source_rows"})


def _availability(
    evidence: Mapping[str, object], limitations: Sequence[Mapping[str, object]]
) -> dict[str, object]:
    bounded = cast(Mapping[str, object], evidence["bounded_payload"])
    evidence_refs = cast(Sequence[object], evidence["evidence_refs"])
    limitation_codes = {str(item.get("code")) for item in limitations}
    if "target_no_data" in limitation_codes or "risk_factor_no_data" in limitation_codes:
        return {"state": "NO_DATA", "message": "No bounded evidence matched the selected target."}
    if not evidence_refs:
        return {"state": "NO_DATA", "message": "No bounded evidence matched the selected target."}
    if any(item.get("code") == "prompt_injection_risk" for item in limitations):
        return {
            "state": "PARTIAL",
            "message": "Snapshot includes quoted source text with prompt-injection risk markers.",
        }
    if limitations:
        return {"state": "PARTIAL", "message": "Snapshot built with explicit limitations."}
    if bounded.get("source_row_samples"):
        return {"state": "AVAILABLE", "message": "Snapshot includes bounded source-row samples."}
    return {"state": "AVAILABLE", "message": "Snapshot built from committed result-store evidence."}


def _no_data_snapshot(
    run_id: str,
    request: Mapping[str, object],
    code: str,
    message: str,
) -> dict[str, object]:
    state = _json_mapping({"run_id": run_id, "navigator_state": request.get("navigator_state", {})})
    target = {
        "target_type": "view",
        "target_id": run_id,
        "target_label": run_id,
        "selected_drilldown_target": None,
    }
    availability = {"state": "NO_DATA", "message": message}
    limitation = _limitation(code, message)
    core: dict[str, object] = {
        "prompt_template_id": _PROMPT_TEMPLATE_ID,
        "prompt_template_version": _PROMPT_TEMPLATE_VERSION,
        "redaction_policy_version": _REDACTION_POLICY_VERSION,
        "entitlement_context_hash": stable_json_hash({}),
        "run_context": {"run_id": run_id},
        "navigator_state_hash": stable_json_hash(state),
        "navigator_state": state,
        "target": target,
        "style": "risk_manager",
        "depth": "standard",
        "user_question": None,
        "evidence_refs": [],
        "bounded_payload": {
            "aggregate_rows": [],
            "measure_rows": [],
            "movement_rows": [],
            "attribution_rows": [],
            "diagnostics": [],
            "lineage": [],
            "source_row_samples": [],
            "artifact_page_refs": [],
            "model_evidence": [],
        },
        "redaction_report": {
            "redacted_fields": [],
            "omitted_evidence_refs": [],
            "reason_codes": [],
            "limitations": [],
        },
        "availability": availability,
        "limitations": [limitation],
    }
    digest = stable_json_hash(core)
    return {
        "snapshot_id": f"ai-snapshot-{digest[:16]}",
        "input_snapshot_hash": digest,
        "snapshot_builder_version": _SNAPSHOT_BUILDER_VERSION,
        **core,
    }


def _run_context(run: object) -> dict[str, object]:
    return {
        "run_id": getattr(run, "run_id"),
        "run_group_id": getattr(run, "run_group_id", None),
        "lifecycle_status": "committed",
        "profile_id": getattr(run, "calculation_policy_id", ""),
        "currency": getattr(run, "base_currency", ""),
        "generated_at": getattr(run, "created_at", None),
    }


def _entitlement_context(request: Mapping[str, object]) -> dict[str, object]:
    raw = request.get("entitlement_context")
    if not isinstance(raw, Mapping):
        return {"policy": "placeholder", "source_rows": "display-safe"}
    return _json_mapping(raw)


def _artifact_ref_payload(ref: ArtifactRef) -> dict[str, object]:
    return {
        "run_id": ref.run_id,
        "artifact_id": ref.artifact_id,
        "component": str(ref.component),
        "artifact_type": str(ref.artifact_type),
        "format": ref.format,
        "row_count": ref.row_count,
        "schema_fingerprint": ref.schema_fingerprint,
        "partition_keys": ref.partition_keys,
        "metadata": ref.metadata,
    }


def _limitation(code: str, message: str) -> dict[str, object]:
    return {"code": code, "message": message, "evidence_refs": []}


def _dataclass_payload(value: object) -> dict[str, object]:
    if is_dataclass(value):
        return {field.name: _json_value(getattr(value, field.name)) for field in fields(value)}
    if isinstance(value, Mapping):
        return _json_mapping(value)
    raise ResultStoreContractError("evidence row must be a dataclass or mapping")


def _json_mapping(value: Mapping[str, object]) -> dict[str, object]:
    return {str(key): _json_value(item) for key, item in value.items()}


def _json_value(value: object) -> object:
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, datetime):
        return value.isoformat()
    if is_dataclass(value):
        return _dataclass_payload(value)
    if isinstance(value, Mapping):
        return {str(key): _json_value(item) for key, item in value.items()}
    if isinstance(value, tuple | list):
        return [_json_value(item) for item in value]
    return value


def _text_list(value: object) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [item for item in (part.strip() for part in value.split(",")) if item]
    if isinstance(value, Sequence):
        return [str(item) for item in value if str(item)]
    return [str(value)]


def _optional_text(value: object) -> str | None:
    if value is None:
        return None
    text = str(value)
    return text or None


def _nested_value(row: Mapping[str, object], outer: str, inner: str) -> object | None:
    value = row.get(outer)
    if isinstance(value, Mapping):
        return value.get(inner)
    return None


def _quote_identifier(value: str) -> str:
    return '"' + value.replace('"', '""') + '"'


def _sql_literal(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def _source_page_window(source_page: Mapping[str, object]) -> tuple[int, int]:
    limit = source_page.get("limit")
    offset = source_page.get("offset", 0)
    if not isinstance(limit, int) or isinstance(limit, bool):
        raise ResultStoreContractError(
            "source_page.limit must be an integer", field="source_page.limit"
        )
    if limit < 1 or limit > _MAX_SOURCE_SAMPLE_ROWS:
        raise ResultStoreContractError(
            f"source_page.limit must be between 1 and {_MAX_SOURCE_SAMPLE_ROWS}",
            field="source_page.limit",
        )
    if not isinstance(offset, int) or isinstance(offset, bool) or offset < 0:
        raise ResultStoreContractError(
            "source_page.offset must be a non-negative integer",
            field="source_page.offset",
        )
    return limit, offset
