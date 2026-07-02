"""PLA/backtesting desk eligibility mart query helpers."""

from __future__ import annotations

from typing import Any, cast

from frtb_result_store._io_risk_factor_query_utils import _page, _validate_page_window
from frtb_result_store._model_desk_eligibility import DeskEligibilityRow
from frtb_result_store.desk_eligibility_rows import _desk_eligibility_mart_from_row
from frtb_result_store.model import ResultStoreContractError


class StoreDeskEligibilityQueryMixin:
    """Read committed PLA/backtesting desk eligibility mart rows."""

    def list_desk_eligibility(
        self: Any,
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
        """Return a bounded, filterable desk eligibility page.

        Parameters
        ----------
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
            Maximum page size, capped by the shared page-window validator.
        offset : int, optional
            Zero-based page offset.

        Returns
        -------
        dict[str, object]
            Page payload with state, records, count, limit, offset, and
            next-offset metadata.
        """
        limit, offset = _validate_page_window(limit, offset)
        records = self._desk_eligibility_by_filters(
            run_id,
            hierarchy_node_id=hierarchy_node_id,
            desk_id=desk_id,
            eligibility_state=eligibility_state,
            pla_state=pla_state,
            backtesting_state=backtesting_state,
        )
        items, next_offset = _page(records, limit=limit, offset=offset)
        return {
            "state": "available" if records else "no_data",
            "items": items,
            "total_count": len(records),
            "limit": limit,
            "offset": offset,
            "next_offset": next_offset,
        }

    def get_desk_eligibility(
        self: Any,
        run_id: str,
        desk_id: str,
    ) -> dict[str, object]:
        """Return PLA/backtesting eligibility evidence for one stable desk id.

        Parameters
        ----------
        run_id : str
            Committed run identifier.
        desk_id : str
            Stable desk identifier.

        Returns
        -------
        dict[str, object]
            Detail payload containing one eligibility row or an explicit
            no-data state.
        """
        record = self._get_desk_eligibility_record(run_id, desk_id)
        if record is None:
            return {"state": "no_data", "desk_id": desk_id, "eligibility": None}
        return {"state": "available", "desk_id": desk_id, "eligibility": record}

    def _desk_eligibility_by_filters(
        self: Any,
        run_id: str,
        *,
        hierarchy_node_id: str | None = None,
        desk_id: str | None = None,
        eligibility_state: str | None = None,
        pla_state: str | None = None,
        backtesting_state: str | None = None,
    ) -> tuple[DeskEligibilityRow, ...]:
        if not self.run_exists(run_id):
            return ()
        where = ["run_id = ?"]
        params: list[object] = [run_id]

        if hierarchy_node_id is not None:
            where.append(
                "("
                "desk_node_id = ? OR legal_entity_id = ? "
                "OR division_id = ? OR business_line_id = ?"
                ")"
            )
            params.extend([hierarchy_node_id] * 4)
        if desk_id is not None:
            where.append("desk_id = ?")
            params.append(desk_id)
        if eligibility_state is not None:
            where.append("eligibility_state = ?")
            params.append(eligibility_state)
        if pla_state is not None:
            where.append("pla_state = ?")
            params.append(pla_state)
        if backtesting_state is not None:
            where.append("backtesting_state = ?")
            params.append(backtesting_state)

        rows = self._fetch_mart(
            "desk_eligibility",
            f"""
            SELECT run_id, desk_id, desk_node_id, label, legal_entity_id,
                   division_id, business_line_id, volcker_desk_id,
                   book_ids_json, eligibility_state, pla_state,
                   pla_threshold_profile_id, pla_metric_summary_json,
                   backtesting_state, backtesting_zone,
                   backtesting_exception_count, backtesting_window,
                   latest_exception_date, rfet_modellable_count, nmrf_count,
                   ses_amount, capital_consequence_amount,
                   capital_consequence_currency, capital_node_id,
                   pnl_artifact_id, rfet_artifact_id, source_artifact_id,
                   model_run_id, profile_hash, source_hashes_json,
                   calculation_timestamp, metadata_json
            FROM {{mart}}
            WHERE {" AND ".join(where)}
            ORDER BY desk_id
            """,
            tuple(params),
        )
        return tuple(_desk_eligibility_mart_from_row(row) for row in rows)

    def _get_desk_eligibility_record(
        self: Any,
        run_id: str,
        desk_id: str,
    ) -> DeskEligibilityRow | None:
        records = cast(
            tuple[DeskEligibilityRow, ...],
            self._desk_eligibility_by_filters(run_id, desk_id=desk_id),
        )
        if not records:
            return None
        if len(records) > 1:
            raise ResultStoreContractError(
                f"desk_id {desk_id!r} has multiple eligibility rows",
                field="desk_id",
            )
        return records[0]
