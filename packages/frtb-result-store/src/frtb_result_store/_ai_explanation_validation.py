"""Request validation helpers for governed AI explanation snapshots."""

from __future__ import annotations

from collections.abc import Mapping

from frtb_result_store._ai_explanation_common import (
    _TARGET_TYPES,
    _json_mapping,
    _optional_text,
    _source_page_window,
    _text_list,
)
from frtb_result_store.model import ResultStoreContractError


def _validated_navigator_state(
    run_id: str,
    request: Mapping[str, object],
) -> dict[str, object]:
    raw_state = request.get("navigator_state")
    state = dict(raw_state) if isinstance(raw_state, Mapping) else {}
    request_run_id = _optional_text(request.get("run_id"))
    if request_run_id is not None and request_run_id != run_id:
        raise ResultStoreContractError("request run_id must match route run_id", field="run_id")
    state["run_id"] = run_id
    state.setdefault("baseline_run_id", request.get("baseline_run_id"))
    state.setdefault("hierarchy_node_id", request.get("hierarchy_node_id") or "total")
    state.setdefault("analysis_mode", request.get("analysis_mode") or "capital")
    state.setdefault("capital_view", request.get("capital_view") or "binding")
    state.setdefault("framework", request.get("framework"))
    state.setdefault("scenario", request.get("scenario") or "Binding")
    state.setdefault("time_window", request.get("time_window") or "current")
    state.setdefault("custom_window", request.get("custom_window"))
    state.setdefault("grid_mode", request.get("grid_mode") or "capital_stack")
    state.setdefault("row_id", request.get("row_id"))
    state.setdefault("desk_id", request.get("desk_id"))
    state.setdefault("risk_factor_id", request.get("risk_factor_id"))
    state.setdefault("artifact_id", request.get("artifact_id"))
    state.setdefault("selected_drilldown_target", request.get("selected_drilldown_target"))
    state.setdefault("inspector_tab", request.get("inspector_tab") or "summary")
    state.setdefault(
        "filters", request.get("filters") if isinstance(request.get("filters"), Mapping) else {}
    )
    state.setdefault(
        "sort", request.get("sort") if isinstance(request.get("sort"), Mapping) else {}
    )
    state.setdefault("pivot_rows", _text_list(request.get("pivot_rows")))
    state.setdefault("pivot_columns", _text_list(request.get("pivot_columns")))
    state.setdefault("visible_row_ids", _text_list(request.get("visible_row_ids")))
    state.setdefault("visible_diagnostic_ids", _text_list(request.get("visible_diagnostic_ids")))
    state.setdefault("column_preset", request.get("column_preset") or "capital")
    state.setdefault(
        "source_page",
        request.get("source_page") if isinstance(request.get("source_page"), Mapping) else None,
    )
    return _json_mapping(state)


def _validated_target(
    navigator_state: Mapping[str, object],
    request: Mapping[str, object],
) -> dict[str, object]:
    raw_target = request.get("target")
    target = dict(raw_target) if isinstance(raw_target, Mapping) else {}
    target_type = _optional_text(target.get("target_type") or request.get("target_type")) or "row"
    if target_type not in _TARGET_TYPES:
        raise ResultStoreContractError(
            f"unsupported explanation target: {target_type}", field="target_type"
        )
    target_id = _optional_text(target.get("target_id") or request.get("target_id"))
    if target_id is None:
        target_id = _target_id_from_state(target_type, navigator_state)
    if target_id is None:
        raise ResultStoreContractError("target_id could not be resolved", field="target_id")
    return {
        "target_type": target_type,
        "target_id": target_id,
        "target_label": _optional_text(target.get("target_label") or request.get("target_label"))
        or target_id,
        "selected_drilldown_target": _optional_text(
            target.get("selected_drilldown_target")
            or navigator_state.get("selected_drilldown_target")
        ),
    }


def _target_id_from_state(target_type: str, state: Mapping[str, object]) -> str | None:
    if target_type in {"row", "panel"}:
        return _optional_text(state.get("row_id"))
    if target_type == "desk":
        return _optional_text(state.get("desk_id"))
    if target_type == "risk_factor":
        return _optional_text(state.get("risk_factor_id"))
    if target_type == "source_rows":
        return _optional_text(state.get("artifact_id") or state.get("row_id"))
    return _optional_text(state.get("hierarchy_node_id"))


def _validate_mode_constraints(
    state: Mapping[str, object],
    target: Mapping[str, object],
) -> None:
    target_type = str(target["target_type"])
    if target_type == "row" and _optional_text(state.get("row_id")) is None:
        raise ResultStoreContractError("row explanations require row_id", field="row_id")
    if target_type == "desk" and _optional_text(state.get("desk_id")) is None:
        raise ResultStoreContractError("desk explanations require desk_id", field="desk_id")
    if target_type == "risk_factor" and _optional_text(state.get("risk_factor_id")) is None:
        raise ResultStoreContractError(
            "risk-factor explanations require risk_factor_id",
            field="risk_factor_id",
        )
    if target_type == "source_rows":
        source_page = state.get("source_page")
        if not isinstance(source_page, Mapping):
            raise ResultStoreContractError(
                "source-row explanations require bounded source_page parameters",
                field="source_page",
            )
        _source_page_window(source_page)
    analysis_mode = str(state.get("analysis_mode"))
    framework = _optional_text(state.get("framework"))
    scenario = str(state.get("scenario"))
    if analysis_mode == "pla" and (framework != "IMA" or scenario != "Binding"):
        raise ResultStoreContractError(
            "analysis_mode=pla requires framework=IMA and scenario=Binding",
            field="analysis_mode",
        )
    if analysis_mode == "rfet_nmrf" and framework != "IMA":
        raise ResultStoreContractError(
            "analysis_mode=rfet_nmrf requires framework=IMA",
            field="analysis_mode",
        )
