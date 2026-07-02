"""Helpers for PLA/backtesting desk eligibility API payloads."""

from __future__ import annotations

from typing import cast

from frtb_result_store._model_desk_eligibility import DeskEligibilityRow
from frtb_result_store.io import DuckDbParquetResultStore


def desk_eligibility_payload(
    result_store: DuckDbParquetResultStore,
    run_id: str,
    *,
    hierarchy_node_id: str | None = None,
    desk_id: str | None = None,
    eligibility_state: str | None = None,
    pla_state: str | None = None,
    backtesting_state: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> dict[str, object]:
    """Build a JSON-ready PLA/backtesting desk eligibility page.

    Parameters
    ----------
    result_store : DuckDbParquetResultStore
        Store queried for committed desk eligibility evidence.
    run_id : str
        Committed run identifier.
    hierarchy_node_id : str | None, optional
        Optional hierarchy or desk node filter.
    desk_id : str | None, optional
        Optional stable desk identifier filter.
    eligibility_state : str | None, optional
        Optional upstream eligibility state filter.
    pla_state : str | None, optional
        Optional PLA state filter.
    backtesting_state : str | None, optional
        Optional backtesting state filter.
    limit : int, optional
        Maximum page size.
    offset : int, optional
        Zero-based page offset.

    Returns
    -------
    dict[str, object]
        JSON-ready page payload with filters and paging metadata.
    """
    page = result_store.list_desk_eligibility(
        run_id,
        hierarchy_node_id=hierarchy_node_id,
        desk_id=desk_id,
        eligibility_state=eligibility_state,
        pla_state=pla_state,
        backtesting_state=backtesting_state,
        limit=limit,
        offset=offset,
    )
    items = cast(tuple[DeskEligibilityRow, ...], page["items"])
    return {
        "state": page["state"],
        "items": [_desk_eligibility_row_to_jsonable(row) for row in items],
        "total_count": page["total_count"],
        "limit": page["limit"],
        "offset": page["offset"],
        "next_offset": page["next_offset"],
        "filters": {
            "hierarchy_node_id": hierarchy_node_id,
            "desk_id": desk_id,
            "eligibility_state": eligibility_state,
            "pla_state": pla_state,
            "backtesting_state": backtesting_state,
        },
    }


def desk_eligibility_detail_payload(
    result_store: DuckDbParquetResultStore,
    run_id: str,
    desk_id: str,
) -> dict[str, object]:
    """Build a JSON-ready PLA/backtesting eligibility detail payload.

    Parameters
    ----------
    result_store : DuckDbParquetResultStore
        Store queried for committed desk eligibility evidence.
    run_id : str
        Committed run identifier.
    desk_id : str
        Stable desk identifier.

    Returns
    -------
    dict[str, object]
        JSON-ready detail payload for one desk or an explicit no-data state.
    """
    detail = result_store.get_desk_eligibility(run_id, desk_id)
    if detail["state"] == "no_data":
        return {"state": "no_data", "desk_id": desk_id, "eligibility": None}
    return {
        "state": "available",
        "desk_id": desk_id,
        "eligibility": _desk_eligibility_row_to_jsonable(
            cast(DeskEligibilityRow, detail["eligibility"])
        ),
    }


def _desk_eligibility_row_to_jsonable(row: DeskEligibilityRow) -> dict[str, object]:
    return {
        "run_id": row.run_id,
        "desk_id": row.desk_id,
        "desk_node_id": row.desk_node_id,
        "label": row.label,
        "legal_entity_id": row.legal_entity_id,
        "division_id": row.division_id,
        "business_line_id": row.business_line_id,
        "volcker_desk_id": row.volcker_desk_id,
        "book_ids": list(row.book_ids),
        "eligibility_state": str(row.eligibility_state),
        "pla_state": str(row.pla_state),
        "pla_threshold_profile_id": row.pla_threshold_profile_id,
        "pla_metric_summary": dict(row.pla_metric_summary),
        "backtesting_state": str(row.backtesting_state),
        "backtesting_zone": row.backtesting_zone,
        "backtesting_exception_count": row.backtesting_exception_count,
        "backtesting_window": row.backtesting_window,
        "latest_exception_date": (
            None if row.latest_exception_date is None else row.latest_exception_date.isoformat()
        ),
        "rfet_modellable_count": row.rfet_modellable_count,
        "nmrf_count": row.nmrf_count,
        "ses_amount": row.ses_amount,
        "capital_consequence_amount": row.capital_consequence_amount,
        "capital_consequence_currency": row.capital_consequence_currency,
        "capital_node_id": row.capital_node_id,
        "pnl_artifact_id": row.pnl_artifact_id,
        "rfet_artifact_id": row.rfet_artifact_id,
        "source_artifact_id": row.source_artifact_id,
        "model_run_id": row.model_run_id,
        "profile_hash": row.profile_hash,
        "source_hashes": list(row.source_hashes),
        "calculation_timestamp": (
            None if row.calculation_timestamp is None else row.calculation_timestamp.isoformat()
        ),
        "metadata": dict(row.metadata),
    }
