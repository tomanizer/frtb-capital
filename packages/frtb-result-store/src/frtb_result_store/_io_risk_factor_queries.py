"""Risk-factor metadata snapshot query helpers."""

from __future__ import annotations

from typing import Any

from frtb_result_store.model import (
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

        records = tuple(
            record
            for record in self.risk_factor_metadata(run_id, snapshot_id=snapshot_id)
            if record.risk_factor_id.value == risk_factor_id
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

        records = self.risk_factor_metadata(run_id, snapshot_id=snapshot_id)
        if risk_class is not None:
            risk_class = risk_class.upper()
            records = tuple(record for record in records if record.risk_class.value == risk_class)
        if bucket_id is not None:
            records = tuple(
                record
                for record in records
                if record.bucket_id is not None and record.bucket_id.value == bucket_id
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
        rows = self._fetchall(
            "risk_factor_source_mappings",
            """
            SELECT run_id, snapshot_id, risk_factor_id, source_system, source_row_id,
                   mapping_version, relationship, source_hash, metadata_json
            FROM {table}
            WHERE run_id = ?
            ORDER BY snapshot_id, risk_factor_id, source_system, source_row_id, relationship
            """,
            (run_id,),
        )
        mappings = tuple(_risk_factor_source_mapping_from_row(row) for row in rows)
        if snapshot_id is not None:
            mappings = tuple(mapping for mapping in mappings if mapping.snapshot_id == snapshot_id)
        if risk_factor_id is not None:
            mappings = tuple(
                mapping for mapping in mappings if mapping.risk_factor_id.value == risk_factor_id
            )
        return mappings
