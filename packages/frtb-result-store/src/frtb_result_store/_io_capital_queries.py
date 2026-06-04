"""Capital graph, artifact, attribution, lineage, and movement queries."""

from __future__ import annotations

from typing import Any

from frtb_result_store.model import (
    ArtifactRef,
    ArtifactType,
    CapitalAttributionRecord,
    CapitalEdge,
    CapitalMeasure,
    CapitalNode,
    LineageRef,
    MovementResult,
)
from frtb_result_store.store_row_io import (
    _artifact_from_row,
    _attribution_from_row,
    _edge_from_row,
    _lineage_from_row,
    _measure_from_row,
    _movement_from_row,
    _node_from_row,
)


class StoreCapitalQueryMixin:
    def child_nodes(self: Any, run_id: str, parent_node_id: str) -> tuple[CapitalNode, ...]:
        """Return direct child nodes in graph order.
        Parameters
        ----------
        run_id : str
            Run id.
        parent_node_id : str
            Parent node id.

        Returns
        -------
        tuple[CapitalNode, ...]
            Result of the operation.
        """

        if not self.run_exists(run_id):
            return ()
        self._ensure_run_compatible(run_id)
        if not self._has_table_files("capital_nodes") or not self._has_table_files("capital_edges"):
            return ()
        rows = self._fetch_custom(
            """
            SELECT n.run_id, n.node_id, n.node_type, n.component, n.label, n.desk_id,
                   n.portfolio_id, n.book_id, n.risk_class, n.bucket, n.issuer_id,
                   n.counterparty_id, n.calculation_branch, n.regulatory_rule_id,
                   n.sort_key, n.metadata_json
            FROM {nodes} n
            JOIN {edges} e
              ON e.run_id = n.run_id
             AND e.child_node_id = n.node_id
            WHERE e.run_id = ? AND e.parent_node_id = ?
            ORDER BY e.sort_key, n.sort_key, n.node_id
            """.format(
                nodes=self._parquet_relation("capital_nodes"),
                edges=self._parquet_relation("capital_edges"),
            ),
            (run_id, parent_node_id),
        )
        return tuple(_node_from_row(row) for row in rows)

    def edges(self: Any, run_id: str) -> tuple[CapitalEdge, ...]:
        """Return graph edges for one run.
        Parameters
        ----------
        run_id : str
            Run id.

        Returns
        -------
        tuple[CapitalEdge, ...]
            Result of the operation.
        """

        if not self.run_exists(run_id):
            return ()
        rows = self._fetchall(
            "capital_edges",
            """
            SELECT run_id, parent_node_id, child_node_id, edge_type,
                   aggregation_weight, sort_key
            FROM {table}
            WHERE run_id = ?
            ORDER BY sort_key, parent_node_id, child_node_id
            """,
            (run_id,),
        )
        return tuple(_edge_from_row(row) for row in rows)

    def measures_for_node(self: Any, run_id: str, node_id: str) -> tuple[CapitalMeasure, ...]:
        """Return scalar measures attached to one node.
        Parameters
        ----------
        run_id : str
            Run id.
        node_id : str
            Node id.

        Returns
        -------
        tuple[CapitalMeasure, ...]
            Result of the operation.
        """

        if not self.run_exists(run_id):
            return ()
        rows = self._fetchall(
            "capital_measures",
            """
            SELECT run_id, node_id, measure_name, amount, currency, unit, scenario,
                   methodology, regulatory_rule_id, citations_json, metadata_json
            FROM {table}
            WHERE run_id = ? AND node_id = ?
            ORDER BY measure_name, scenario NULLS FIRST
            """,
            (run_id, node_id),
        )
        return tuple(_measure_from_row(row) for row in rows)

    def artifact_refs(
        self: Any,
        run_id: str,
        *,
        artifact_type: ArtifactType | str | None = None,
    ) -> tuple[ArtifactRef, ...]:
        """Return large-artifact references for a run.
        Parameters
        ----------
        run_id : str
            Run id.
        artifact_type : ArtifactType | str | None, optional
            Artifact type.

        Returns
        -------
        tuple[ArtifactRef, ...]
            Result of the operation.
        """

        if not self.run_exists(run_id):
            return ()
        if artifact_type is None:
            rows = self._fetchall(
                "artifact_refs",
                """
                SELECT run_id, artifact_id, component, artifact_type, uri, format,
                       row_count, schema_fingerprint, partition_keys_json, metadata_json
                FROM {table}
                WHERE run_id = ?
                ORDER BY artifact_type, artifact_id
                """,
                (run_id,),
            )
        else:
            coerced = ArtifactType(artifact_type).value
            rows = self._fetchall(
                "artifact_refs",
                """
                SELECT run_id, artifact_id, component, artifact_type, uri, format,
                       row_count, schema_fingerprint, partition_keys_json, metadata_json
                FROM {table}
                WHERE run_id = ? AND artifact_type = ?
                ORDER BY artifact_id
                """,
                (run_id, coerced),
            )
        return tuple(_artifact_from_row(row) for row in rows)

    def attributions_for_node(
        self: Any,
        run_id: str,
        node_id: str,
    ) -> tuple[CapitalAttributionRecord, ...]:
        """Return attribution rows attached to one capital node.
        Parameters
        ----------
        run_id : str
            Run id.
        node_id : str
            Node id.

        Returns
        -------
        tuple[CapitalAttributionRecord, ...]
            Result of the operation.
        """

        if not self.run_exists(run_id):
            return ()
        rows = self._fetchall(
            "capital_attributions",
            """
            SELECT run_id, node_id, attribution_id, target_type, target_id, source_id,
                   source_level, method, category, bucket_key, base_amount,
                   marginal_multiplier, contribution, residual, unsupported_reason,
                   artifact_id, metadata_json
            FROM {table}
            WHERE run_id = ? AND node_id = ?
            ORDER BY attribution_id
            """,
            (run_id, node_id),
        )
        return tuple(_attribution_from_row(row) for row in rows)

    def movement_results(
        self: Any,
        run_id: str,
        *,
        baseline_run_id: str | None = None,
        node_id: str | None = None,
    ) -> tuple[MovementResult, ...]:
        """Return official movement result rows attached to one current run.
        Parameters
        ----------
        run_id : str
            Run id.
        baseline_run_id : str | None, optional
            Baseline run id.
        node_id : str | None, optional
            Node id.

        Returns
        -------
        tuple[MovementResult, ...]
            Result of the operation.
        """

        if not self.run_exists(run_id):
            return ()
        filters = ["run_id = ?"]
        parameters: list[object] = [run_id]
        if baseline_run_id is not None:
            filters.append("baseline_run_id = ?")
            parameters.append(baseline_run_id)
        if node_id is not None:
            filters.append("node_id = ?")
            parameters.append(node_id)
        rows = self._fetchall(
            "movement_results",
            f"""
            SELECT run_id, baseline_run_id, movement_id, node_id, movement_type,
                   from_amount, to_amount, delta_amount, base_currency, driver_type,
                   driver_id, explanation, attribution_method, artifact_id, metadata_json
            FROM {{table}}
            WHERE {" AND ".join(filters)}
            ORDER BY node_id, movement_type, driver_type, driver_id, movement_id
            """,
            tuple(parameters),
        )
        return tuple(_movement_from_row(row) for row in rows)

    def lineage_for_result(self: Any, run_id: str, result_id: str) -> tuple[LineageRef, ...]:
        """Return lineage references for a stored result object.
        Parameters
        ----------
        run_id : str
            Run id.
        result_id : str
            Result id.

        Returns
        -------
        tuple[LineageRef, ...]
            Result of the operation.
        """

        if not self.run_exists(run_id):
            return ()
        rows = self._fetchall(
            "lineage_refs",
            """
            SELECT run_id, result_id, source_type, source_id, relationship, source_hash,
                   metadata_json
            FROM {table}
            WHERE run_id = ? AND result_id = ?
            ORDER BY source_type, source_id, relationship
            """,
            (run_id, result_id),
        )
        return tuple(_lineage_from_row(row) for row in rows)
