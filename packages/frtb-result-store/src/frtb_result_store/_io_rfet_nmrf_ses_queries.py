"""RFET/NMRF/SES risk-factor evidence mart query helpers."""

from __future__ import annotations

from typing import Any

from frtb_result_store._io_risk_factor_query_utils import (
    _page,
    _validate_page_window,
)
from frtb_result_store._model_risk_factor_evidence import (
    NMRFSESBridge,
    RFETObservationEvidence,
    RiskFactorEvidenceRow,
    RiskFactorHierarchyUsage,
)
from frtb_result_store.model import ResultStoreContractError
from frtb_result_store.risk_factor_evidence_rows import (
    _nmrf_ses_bridge_from_row,
    _rfet_observation_evidence_from_row,
    _risk_factor_evidence_mart_from_row,
    _risk_factor_hierarchy_usage_from_row,
)


class StoreRiskFactorEvidenceQueryMixin:
    """Read committed RFET/NMRF/SES risk-factor evidence mart rows."""

    def list_risk_factor_evidence(
        self: Any,
        run_id: str,
        *,
        risk_class: str | None = None,
        desk_id: str | None = None,
        book_id: str | None = None,
        modellability_state: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> dict[str, object]:
        """Return a bounded, filterable RFET/NMRF/SES evidence page.

        Parameters
        ----------
        run_id : str
            Run id.
        risk_class : str | None, optional
            Optional risk-class filter.
        desk_id : str | None, optional
            Optional desk filter.
        book_id : str | None, optional
            Optional book filter.
        modellability_state : str | None, optional
            Optional modellability state filter.
        limit : int, optional
            Maximum page size, capped at 1000.
        offset : int, optional
            Zero-based page offset.

        Returns
        -------
        dict[str, object]
            Page payload with state, records, count, limit, offset, and
            next-offset metadata.
        """

        limit, offset = _validate_page_window(limit, offset)
        records = self._risk_factor_evidence_by_filters(
            run_id,
            risk_class=risk_class,
            desk_id=desk_id,
            book_id=book_id,
            modellability_state=modellability_state,
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

    def get_risk_factor_evidence(
        self: Any,
        run_id: str,
        risk_factor_id: str,
    ) -> dict[str, object]:
        """Return complete RFET/NMRF/SES evidence for one stable risk-factor id.

        Parameters
        ----------
        run_id : str
            Run id.
        risk_factor_id : str
            Stable risk-factor id.

        Returns
        -------
        dict[str, object]
            Detail payload with evidence row, RFET observation summary,
            NMRF/SES bridge, hierarchy usage, and lineage count, or an
            explicit no-data state when the id is not present.
        """

        record = self._get_risk_factor_evidence_record(run_id, risk_factor_id)
        if record is None:
            return {
                "state": "no_data",
                "risk_factor_id": risk_factor_id,
                "evidence": None,
            }
        return {
            "state": "available",
            "risk_factor_id": risk_factor_id,
            "evidence": record,
        }

    def risk_factor_hierarchy_usage(
        self: Any,
        run_id: str,
        risk_factor_id: str,
    ) -> dict[str, object]:
        """Return hierarchy usage mapping for one risk factor.

        Parameters
        ----------
        run_id : str
            Run id.
        risk_factor_id : str
            Stable risk-factor id.

        Returns
        -------
        dict[str, object]
            Hierarchy usage payload with books, desks, and business lines
            using the risk factor, or an explicit no-data state.
        """

        record = self._get_risk_factor_evidence_record(run_id, risk_factor_id)
        if record is None or record.hierarchy_usage is None:
            return {
                "state": "no_data" if record is None else "unavailable",
                "risk_factor_id": risk_factor_id,
                "hierarchy_usage": None,
            }
        return {
            "state": "available",
            "risk_factor_id": risk_factor_id,
            "hierarchy_usage": record.hierarchy_usage,
        }

    def nmrf_ses_capital_by_risk_factor(
        self: Any,
        run_id: str,
        risk_factor_id: str,
    ) -> dict[str, object]:
        """Return NMRF/SES capital bridge for one risk factor.

        Parameters
        ----------
        run_id : str
            Run id.
        risk_factor_id : str
            Stable risk-factor id.

        Returns
        -------
        dict[str, object]
            NMRF/SES bridge payload with SES component, amount, movement,
            stress period, liquidity horizon, and capital node linkage, or an
            explicit no-data/unavailable state.
        """

        record = self._get_risk_factor_evidence_record(run_id, risk_factor_id)
        if record is None or record.nmrf_ses_bridge is None:
            return {
                "state": "no_data" if record is None else "unavailable",
                "risk_factor_id": risk_factor_id,
                "nmrf_ses_bridge": None,
            }
        return {
            "state": "available",
            "risk_factor_id": risk_factor_id,
            "nmrf_ses_bridge": record.nmrf_ses_bridge,
        }

    def _risk_factor_evidence_by_filters(
        self: Any,
        run_id: str,
        *,
        risk_class: str | None = None,
        desk_id: str | None = None,
        book_id: str | None = None,
        modellability_state: str | None = None,
    ) -> tuple[RiskFactorEvidenceRow, ...]:
        """Return risk-factor evidence filtered by classification or hierarchy."""
        if not self.run_exists(run_id):
            return ()
        where = ["run_id = ?"]
        params: list[object] = [run_id]

        if risk_class is not None:
            where.append("risk_class = ?")
            params.append(risk_class.upper())
        if desk_id is not None:
            where.append("desk_id = ?")
            params.append(desk_id)
        if book_id is not None:
            where.append("book_id = ?")
            params.append(book_id)
        if modellability_state is not None:
            where.append("modellability_state = ?")
            params.append(modellability_state)

        rows = self._fetchall(
            "rfet_nmrf_ses_evidence",
            f"""
            SELECT run_id, risk_factor_id, display_name, risk_class, risk_factor_type,
                   modellability_state, observation_count, latest_observation_date,
                   gap_days, stale_state, rejected_observation_count, rfet_artifact_id,
                   ses_component, ses_amount, ses_movement, stress_period_id,
                   liquidity_horizon_days, aggregation_bucket, capital_node_id,
                   book_id, desk_id, volcker_desk_id, business_line_id,
                   legal_entity_id, usage_count, source_artifact_id, metadata_json
            FROM {{table}}
            WHERE {" AND ".join(where)}
            ORDER BY risk_class, risk_factor_id
            """,
            tuple(params),
        )
        return tuple(_risk_factor_evidence_mart_from_row(row) for row in rows)

    def _get_risk_factor_evidence_record(
        self: Any,
        run_id: str,
        risk_factor_id: str,
    ) -> RiskFactorEvidenceRow | None:
        """Return one RFET/NMRF/SES evidence record by stable risk-factor id."""
        if not self.run_exists(run_id):
            return None
        rows = self._fetchall(
            "rfet_nmrf_ses_evidence",
            """
            SELECT run_id, risk_factor_id, display_name, risk_class, risk_factor_type,
                   modellability_state, observation_count, latest_observation_date,
                   gap_days, stale_state, rejected_observation_count, rfet_artifact_id,
                   ses_component, ses_amount, ses_movement, stress_period_id,
                   liquidity_horizon_days, aggregation_bucket, capital_node_id,
                   book_id, desk_id, volcker_desk_id, business_line_id,
                   legal_entity_id, usage_count, source_artifact_id, metadata_json
            FROM {table}
            WHERE run_id = ? AND risk_factor_id = ?
            """,
            (run_id, risk_factor_id),
        )
        if not rows:
            return None
        if len(rows) > 1:
            raise ResultStoreContractError(
                f"risk_factor_id {risk_factor_id!r} has multiple evidence rows",
                field="risk_factor_id",
            )
        return _risk_factor_evidence_mart_from_row(rows[0])

    def _rfet_observation_evidence_records(
        self: Any,
        run_id: str,
        *,
        stale_state: str | None = None,
    ) -> tuple[RFETObservationEvidence, ...]:
        """Return RFET observation evidence summaries for a run."""
        if not self.run_exists(run_id):
            return ()
        where = ["run_id = ?"]
        params: list[object] = [run_id]

        if stale_state is not None:
            where.append("stale_state = ?")
            params.append(stale_state)

        rows = self._fetchall(
            "rfet_nmrf_ses_evidence",
            f"""
            SELECT
                observation_count, latest_observation_date, gap_days,
                stale_state, rejected_observation_count, rfet_artifact_id
            FROM {{table}}
            WHERE {" AND ".join(where)}
            ORDER BY risk_factor_id
            """,
            tuple(params),
        )
        return tuple(_rfet_observation_evidence_from_row(row) for row in rows)

    def _nmrf_ses_bridge_records(
        self: Any,
        run_id: str,
        *,
        ses_component: str | None = None,
    ) -> tuple[NMRFSESBridge, ...]:
        """Return NMRF/SES capital bridges for a run."""
        if not self.run_exists(run_id):
            return ()
        where = ["run_id = ?", "ses_component IS NOT NULL"]
        params: list[object] = [run_id]

        if ses_component is not None:
            where.append("ses_component = ?")
            params.append(ses_component)

        rows = self._fetchall(
            "rfet_nmrf_ses_evidence",
            f"""
            SELECT
                risk_factor_id, ses_component, ses_amount, ses_movement,
                stress_period_id, liquidity_horizon_days, aggregation_bucket,
                capital_node_id
            FROM {{table}}
            WHERE {" AND ".join(where)}
            ORDER BY risk_factor_id
            """,
            tuple(params),
        )
        return tuple(_nmrf_ses_bridge_from_row(row) for row in rows)

    def _risk_factor_hierarchy_usage_records(
        self: Any,
        run_id: str,
    ) -> tuple[RiskFactorHierarchyUsage, ...]:
        """Return risk-factor hierarchy usage mappings for a run."""
        if not self.run_exists(run_id):
            return ()
        rows = self._fetchall(
            "rfet_nmrf_ses_evidence",
            """
            SELECT
                risk_factor_id, book_id, desk_id, volcker_desk_id,
                business_line_id, legal_entity_id, usage_count
            FROM {table}
            WHERE run_id = ? AND book_id IS NOT NULL
            ORDER BY risk_factor_id, desk_id, book_id
            """,
            (run_id,),
        )
        return tuple(_risk_factor_hierarchy_usage_from_row(row) for row in rows)
