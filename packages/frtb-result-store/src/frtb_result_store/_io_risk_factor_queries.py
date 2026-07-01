"""Risk-factor metadata snapshot query helpers."""

from __future__ import annotations

from typing import Any, cast

from frtb_result_store._io_risk_factor_query_utils import (
    _framework_value,
    _numeric_or_zero,
    _page,
    _record_search_text,
    _risk_factor_attribution_rows,
    _validate_page_window,
)
from frtb_result_store.model import (
    FrtbComponent,
    ResultStoreContractError,
    RiskFactorMetadataRecord,
    RiskFactorMetadataSnapshot,
    RiskFactorSourceMapping,
)
from frtb_result_store.risk_factor_metadata_rows import (
    _risk_factor_metadata_from_row,
    _risk_factor_snapshot_from_row,
    _risk_factor_source_mapping_from_row,
)


class StoreRiskFactorQueryMixin:
    """Read committed risk-factor metadata snapshots and source mappings."""

    def list_risk_factors(
        self: Any,
        run_id: str,
        *,
        search: str | None = None,
        risk_class: str | None = None,
        bucket_id: str | None = None,
        snapshot_id: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> dict[str, object]:
        """Return a bounded, searchable risk-factor metadata page.

        Parameters
        ----------
        run_id : str
            Run id.
        search : str | None, optional
            Case-insensitive search over risk-factor ids, labels, taxonomy
            fields, source ids, and populated domain attributes.
        risk_class : str | None, optional
            Optional risk-class filter.
        bucket_id : str | None, optional
            Optional regulatory bucket filter.
        snapshot_id : str | None, optional
            Optional snapshot id filter.
        limit : int, optional
            Maximum page size, capped at 1000.
        offset : int, optional
            Zero-based page offset.

        Returns
        -------
        dict[str, object]
            Page payload with state, records, count, limit, offset, and
            next-offset metadata.

        The contract is intentionally read-model shaped for Navigator and
        future OLAP adapters: callers get stable metadata records, page
        metadata, and an explicit no-data state without client-side regulatory
        classification.
        """

        limit, offset = _validate_page_window(limit, offset)
        snapshot_id = _default_risk_factor_snapshot_id(self, run_id, snapshot_id)
        records = self.risk_factor_metadata_by_classification(
            run_id,
            risk_class=risk_class,
            bucket_id=bucket_id,
            snapshot_id=snapshot_id,
        )
        if search is not None:
            needle = search.casefold().strip()
            if needle:
                records = tuple(
                    record for record in records if needle in _record_search_text(record)
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

    def get_risk_factor(
        self: Any,
        run_id: str,
        risk_factor_id: str,
        *,
        snapshot_id: str | None = None,
    ) -> dict[str, object]:
        """Return canonical metadata details for one stable risk-factor id.

        Parameters
        ----------
        run_id : str
            Run id.
        risk_factor_id : str
            Stable risk-factor id.
        snapshot_id : str | None, optional
            Optional snapshot id filter.

        Returns
        -------
        dict[str, object]
            Detail payload with metadata and lineage count, or an explicit
            no-data state when the id is not present.
        """

        record = self.get_risk_factor_metadata(
            run_id,
            risk_factor_id,
            snapshot_id=snapshot_id,
        )
        if record is None:
            return {
                "state": "no_data",
                "risk_factor_id": risk_factor_id,
                "metadata": None,
                "lineage_count": 0,
            }
        mappings = self.risk_factor_source_mappings(
            run_id,
            snapshot_id=record.snapshot_id,
            risk_factor_id=risk_factor_id,
        )
        return {
            "state": "available",
            "risk_factor_id": risk_factor_id,
            "metadata": record,
            "lineage_count": len(mappings),
        }

    def risk_factor_lineage(
        self: Any,
        run_id: str,
        risk_factor_id: str,
        *,
        snapshot_id: str | None = None,
    ) -> dict[str, object]:
        """Return source-system and mapping-version lineage for a risk factor.

        Parameters
        ----------
        run_id : str
            Run id.
        risk_factor_id : str
            Stable risk-factor id.
        snapshot_id : str | None, optional
            Optional snapshot id filter.

        Returns
        -------
        dict[str, object]
            Lineage payload with source mappings and lineage count, or an
            explicit no-data state.
        """

        snapshot_id = _default_risk_factor_snapshot_id(self, run_id, snapshot_id)
        mappings = self.risk_factor_source_mappings(
            run_id,
            snapshot_id=snapshot_id,
            risk_factor_id=risk_factor_id,
        )
        return {
            "state": "available" if mappings else "no_data",
            "risk_factor_id": risk_factor_id,
            "lineage": mappings,
            "lineage_count": len(mappings),
        }

    def risk_factor_capital(
        self: Any,
        run_id: str,
        risk_factor_id: str,
        *,
        framework: FrtbComponent | str | None = None,
    ) -> dict[str, object]:
        """Return stored risk-factor capital contribution aggregates.

        Parameters
        ----------
        run_id : str
            Run id.
        risk_factor_id : str
            Stable risk-factor id.
        framework : FrtbComponent | str | None, optional
            Optional framework/component filter.

        Returns
        -------
        dict[str, object]
            Aggregate payload with contribution totals, persisted row count,
            unsupported row count, and explicit no-data state when unavailable.

        Only persisted attribution rows whose source or target is the selected
        risk factor are aggregated. Missing contribution rows return ``no_data``
        rather than inferred or recomputed capital.
        """

        rows = _risk_factor_attribution_rows(
            self,
            run_id,
            risk_factor_id,
            framework=framework,
        )
        contribution = sum(_numeric_or_zero(row["contribution"]) for row in rows)
        base_amount = sum(_numeric_or_zero(row["base_amount"]) for row in rows)
        residual = sum(_numeric_or_zero(row["residual"]) for row in rows)
        return {
            "state": "available" if rows else "no_data",
            "risk_factor_id": risk_factor_id,
            "framework": _framework_value(framework),
            "attribution_count": len(rows),
            "contribution": contribution if rows else None,
            "base_amount": base_amount if rows else None,
            "residual": residual if rows else None,
            "unsupported_count": sum(1 for row in rows if row["unsupported_reason"]),
        }

    def risk_factor_source_rows(
        self: Any,
        run_id: str,
        risk_factor_id: str,
        *,
        snapshot_id: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> dict[str, object]:
        """Return a bounded page of source mappings for risk-factor drilldown.

        Parameters
        ----------
        run_id : str
            Run id.
        risk_factor_id : str
            Stable risk-factor id.
        snapshot_id : str | None, optional
            Optional snapshot id filter.
        limit : int, optional
            Maximum page size, capped at 1000.
        offset : int, optional
            Zero-based page offset.

        Returns
        -------
        dict[str, object]
            Source-row page with state, rows, count, limit, offset, and
            next-offset metadata.
        """

        limit, offset = _validate_page_window(limit, offset)
        snapshot_id = _default_risk_factor_snapshot_id(self, run_id, snapshot_id)
        mappings = self.risk_factor_source_mappings(
            run_id,
            snapshot_id=snapshot_id,
            risk_factor_id=risk_factor_id,
        )
        rows, next_offset = _page(mappings, limit=limit, offset=offset)
        return {
            "state": "available" if mappings else "no_data",
            "risk_factor_id": risk_factor_id,
            "rows": rows,
            "total_count": len(mappings),
            "limit": limit,
            "offset": offset,
            "next_offset": next_offset,
        }

    def risk_factor_snapshots(self: Any, run_id: str) -> tuple[RiskFactorMetadataSnapshot, ...]:
        """Return risk-factor metadata snapshots for one committed run.

        Parameters
        ----------
        run_id : str
            Run id.

        Returns
        -------
        tuple[RiskFactorMetadataSnapshot, ...]
            Deterministically ordered snapshot rows.
        """

        if not self.run_exists(run_id):
            return ()
        rows = self._fetchall(
            "risk_factor_metadata_snapshots",
            """
            SELECT run_id, snapshot_id, mapping_version, effective_date, source_system,
                   created_at, metadata_json
            FROM {table}
            WHERE run_id = ?
            ORDER BY effective_date, snapshot_id
            """,
            (run_id,),
        )
        return tuple(_risk_factor_snapshot_from_row(row) for row in rows)

    def risk_factor_metadata(
        self: Any,
        run_id: str,
        *,
        snapshot_id: str | None = None,
    ) -> tuple[RiskFactorMetadataRecord, ...]:
        """Return canonical risk-factor metadata records for a run.

        Parameters
        ----------
        run_id : str
            Run id.
        snapshot_id : str | None, optional
            Optional snapshot id filter.

        Returns
        -------
        tuple[RiskFactorMetadataRecord, ...]
            Deterministically ordered metadata records.
        """

        if not self.run_exists(run_id):
            return ()
        where = "WHERE run_id = ?"
        params: tuple[object, ...] = (run_id,)
        if snapshot_id is not None:
            where += " AND snapshot_id = ?"
            params = (run_id, snapshot_id)
        rows = self._fetchall(
            "risk_factor_metadata",
            f"""
            SELECT run_id, snapshot_id, risk_factor_id, display_name, risk_class,
                   risk_factor_type, mapping_version, bucket_id, bucket_label,
                   sensitivity_type, currency, curve_id, tenor, issuer_id, obligor_id,
                   counterparty_id, commodity_id, equity_id, status, rfet_evidence_state,
                   rfet_evidence_id, modellability_state, liquidity_horizon_days,
                   nmrf_state, stress_period_id, source_system, source_row_id,
                   metadata_json
            FROM {{table}}
            {where}
            ORDER BY snapshot_id, risk_class, bucket_id, risk_factor_id
            """,
            params,
        )
        return tuple(_risk_factor_metadata_from_row(row) for row in rows)

    def get_risk_factor_metadata(
        self: Any,
        run_id: str,
        risk_factor_id: str,
        *,
        snapshot_id: str | None = None,
    ) -> RiskFactorMetadataRecord | None:
        """Return one canonical risk-factor metadata record by stable id.

        Parameters
        ----------
        run_id : str
            Run id.
        risk_factor_id : str
            Stable risk-factor id.
        snapshot_id : str | None, optional
            Optional snapshot id filter.

        Returns
        -------
        RiskFactorMetadataRecord | None
            Matching record, or ``None`` when absent.
        """

        snapshot_id = _default_risk_factor_snapshot_id(self, run_id, snapshot_id)
        records = tuple(
            record
            for record in self.risk_factor_metadata(run_id, snapshot_id=snapshot_id)
            if str(record.risk_factor_id) == risk_factor_id
        )
        if len(records) > 1:
            raise ResultStoreContractError(
                f"risk_factor_id {risk_factor_id!r} is ambiguous across snapshots",
                field="risk_factor_id",
            )
        return None if not records else records[0]

    def risk_factor_metadata_by_classification(
        self: Any,
        run_id: str,
        *,
        risk_class: str | None = None,
        bucket_id: str | None = None,
        snapshot_id: str | None = None,
    ) -> tuple[RiskFactorMetadataRecord, ...]:
        """Return risk-factor metadata filtered by classification or bucket.

        Parameters
        ----------
        run_id : str
            Run id.
        risk_class : str | None, optional
            Optional risk-class filter.
        bucket_id : str | None, optional
            Optional bucket-id filter.
        snapshot_id : str | None, optional
            Optional snapshot id filter.

        Returns
        -------
        tuple[RiskFactorMetadataRecord, ...]
            Deterministically ordered matching records.
        """

        records = cast(
            tuple[RiskFactorMetadataRecord, ...],
            self.risk_factor_metadata(run_id, snapshot_id=snapshot_id),
        )
        if risk_class is not None:
            risk_class = risk_class.upper()
            records = tuple(record for record in records if str(record.risk_class) == risk_class)
        if bucket_id is not None:
            records = tuple(
                record
                for record in records
                if record.bucket_id is not None and str(record.bucket_id) == bucket_id
            )
        return records

    def risk_factor_source_mappings(
        self: Any,
        run_id: str,
        *,
        snapshot_id: str | None = None,
        risk_factor_id: str | None = None,
    ) -> tuple[RiskFactorSourceMapping, ...]:
        """Return source mappings for canonical risk-factor metadata.

        Parameters
        ----------
        run_id : str
            Run id.
        snapshot_id : str | None, optional
            Optional snapshot id filter.
        risk_factor_id : str | None, optional
            Optional stable risk-factor id filter.

        Returns
        -------
        tuple[RiskFactorSourceMapping, ...]
            Deterministically ordered source mappings.
        """

        if not self.run_exists(run_id):
            return ()
        where = ["run_id = ?"]
        params: list[object] = [run_id]
        if snapshot_id is not None:
            where.append("snapshot_id = ?")
            params.append(snapshot_id)
        if risk_factor_id is not None:
            where.append("risk_factor_id = ?")
            params.append(risk_factor_id)
        rows = self._fetchall(
            "risk_factor_source_mappings",
            f"""
            SELECT run_id, snapshot_id, risk_factor_id, source_system, source_row_id,
                   mapping_version, relationship, source_hash, metadata_json
            FROM {{table}}
            WHERE {" AND ".join(where)}
            ORDER BY snapshot_id, risk_factor_id, source_system, source_row_id, relationship
            """,
            tuple(params),
        )
        return tuple(_risk_factor_source_mapping_from_row(row) for row in rows)


def _default_risk_factor_snapshot_id(
    store: Any,
    run_id: str,
    snapshot_id: str | None,
) -> str | None:
    if snapshot_id is not None:
        return snapshot_id
    snapshots = cast(
        tuple[RiskFactorMetadataSnapshot, ...],
        store.risk_factor_snapshots(run_id),
    )
    if not snapshots:
        return None
    return snapshots[-1].snapshot_id
