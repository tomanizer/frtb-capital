"""FastAPI route registration for governed AI explanation snapshots."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, Protocol

from frtb_result_store.io import DuckDbParquetResultStore
from frtb_result_store.model import ResultStoreContractError

__all__ = ["register_ai_explanation_routes"]

_Endpoint = Callable[..., Any]


class _RouteRegistrar(Protocol):
    def get(
        self,
        path: str,
        *,
        tags: list[str] | None = None,
        summary: str | None = None,
        **kwargs: Any,
    ) -> Callable[[_Endpoint], _Endpoint]: ...


def register_ai_explanation_routes(
    app: _RouteRegistrar,
    result_store: DuckDbParquetResultStore,
    http_exception_type: type[Exception],
    *,
    require_run: Callable[[DuckDbParquetResultStore, str, type[Exception]], object],
) -> None:
    """Register read-only snapshot-builder routes for Navigator AI explanations.

    Parameters
    ----------
    app : _RouteRegistrar
        FastAPI-compatible route registrar.
    result_store : DuckDbParquetResultStore
        Committed result-store backend queried by the route.
    http_exception_type : type[Exception]
        HTTP exception class supplied by the API factory.
    require_run : Callable[[DuckDbParquetResultStore, str, type[Exception]], object]
        Shared run existence validator used by other result-store routes.
    """

    @app.get(
        "/runs/{run_id:path}/ai-explanation-snapshot",
        tags=["AI Explanations"],
        summary="Build a bounded governed AI explanation input snapshot",
    )
    def ai_explanation_snapshot(
        run_id: str,
        target_type: str = "row",
        target_id: str | None = None,
        target_label: str | None = None,
        hierarchy_node_id: str = "total",
        analysis_mode: str = "capital",
        capital_view: str = "binding",
        framework: str | None = None,
        scenario: str = "Binding",
        grid_mode: str = "capital_stack",
        row_id: str | None = None,
        desk_id: str | None = None,
        risk_factor_id: str | None = None,
        artifact_id: str | None = None,
        visible_row_ids: list[str] | None = None,
        visible_diagnostic_ids: list[str] | None = None,
        style: str = "risk_manager",
        depth: str = "standard",
        user_question: str | None = None,
        source_page_artifact_id: str | None = None,
        source_page_limit: int | None = None,
        source_page_offset: int = 0,
    ) -> dict[str, object]:
        require_run(result_store, run_id, http_exception_type)
        request = _request_from_query(
            run_id=run_id,
            target_type=target_type,
            target_id=target_id,
            target_label=target_label,
            hierarchy_node_id=hierarchy_node_id,
            analysis_mode=analysis_mode,
            capital_view=capital_view,
            framework=framework,
            scenario=scenario,
            grid_mode=grid_mode,
            row_id=row_id,
            desk_id=desk_id,
            risk_factor_id=risk_factor_id,
            artifact_id=artifact_id,
            visible_row_ids=visible_row_ids or [],
            visible_diagnostic_ids=visible_diagnostic_ids or [],
            style=style,
            depth=depth,
            user_question=user_question,
            source_page_artifact_id=source_page_artifact_id,
            source_page_limit=source_page_limit,
            source_page_offset=source_page_offset,
        )
        try:
            return result_store.ai_explanation_snapshot(run_id, request)
        except ResultStoreContractError as exc:
            raise http_exception_type(  # type: ignore[call-arg]
                status_code=400,
                detail=f"Invalid AI explanation snapshot request: {exc!s}",
            ) from exc


def _request_from_query(
    *,
    run_id: str,
    target_type: str,
    target_id: str | None,
    target_label: str | None,
    hierarchy_node_id: str,
    analysis_mode: str,
    capital_view: str,
    framework: str | None,
    scenario: str,
    grid_mode: str,
    row_id: str | None,
    desk_id: str | None,
    risk_factor_id: str | None,
    artifact_id: str | None,
    visible_row_ids: list[str],
    visible_diagnostic_ids: list[str],
    style: str,
    depth: str,
    user_question: str | None,
    source_page_artifact_id: str | None,
    source_page_limit: int | None,
    source_page_offset: int,
) -> dict[str, object]:
    source_page = None
    if source_page_artifact_id is not None or source_page_limit is not None:
        source_page = {
            "artifact_id": source_page_artifact_id or artifact_id,
            "limit": source_page_limit,
            "offset": source_page_offset,
        }
    return {
        "run_id": run_id,
        "navigator_state": {
            "run_id": run_id,
            "hierarchy_node_id": hierarchy_node_id,
            "analysis_mode": analysis_mode,
            "capital_view": capital_view,
            "framework": framework,
            "scenario": scenario,
            "grid_mode": grid_mode,
            "row_id": row_id,
            "desk_id": desk_id,
            "risk_factor_id": risk_factor_id,
            "artifact_id": artifact_id or source_page_artifact_id,
            "visible_row_ids": visible_row_ids,
            "visible_diagnostic_ids": visible_diagnostic_ids,
            "source_page": source_page,
        },
        "target": {
            "target_type": target_type,
            "target_id": target_id,
            "target_label": target_label
            or target_id
            or row_id
            or desk_id
            or risk_factor_id
            or run_id,
        },
        "style": style,
        "depth": depth,
        "user_question": user_question,
    }
