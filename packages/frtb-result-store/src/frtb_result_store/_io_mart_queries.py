"""Persisted mart queries for dashboard and comparison views."""

from __future__ import annotations

from typing import Any

from frtb_result_store.marts import (
    capital_summary_from_row,
    capital_tree_mart_from_row,
    component_breakdown_from_row,
    movement_summary_from_row,
)
from frtb_result_store.model import (
    CapitalNode,
    CapitalSummaryRow,
    CapitalTreeMartRow,
    ComponentBreakdownRow,
    MovementSummaryRow,
)
from frtb_result_store.store_paths import _mart_columns
from frtb_result_store.store_schemas import _dict_rows


class StoreMartQueryMixin:
    def capital_tree(self: Any, run_id: str) -> tuple[CapitalNode, ...]:
        """Return all capital graph nodes for one run from the persisted mart."""

        return tuple(row.to_node() for row in self.capital_tree_mart(run_id))

    def capital_summary(self: Any, run_id: str) -> tuple[CapitalSummaryRow, ...]:
        """Return persisted dashboard summary rows for one run."""

        if not self.run_exists(run_id):
            return ()
        rows = self._fetch_mart(
            "capital_summary",
            """
            SELECT run_id, as_of_date, regime_id, base_currency, lifecycle_status,
                   suggested_status, total_capital, currency, node_count, measure_count,
                   component_count
            FROM {mart}
            WHERE run_id = ?
            ORDER BY run_id
            """,
            (run_id,),
        )
        return tuple(capital_summary_from_row(row) for row in rows)

    def capital_tree_mart(self: Any, run_id: str) -> tuple[CapitalTreeMartRow, ...]:
        """Return persisted flattened capital tree rows for one run."""

        if not self.run_exists(run_id):
            return ()
        rows = self._fetch_mart(
            "capital_tree",
            """
            SELECT run_id, node_id, parent_node_id, depth, node_type, component, label,
                   desk_id, portfolio_id, book_id, risk_class, bucket, issuer_id,
                   counterparty_id, calculation_branch, regulatory_rule_id, sort_key,
                   metadata_json
            FROM {mart}
            WHERE run_id = ?
            ORDER BY depth, sort_key, node_id
            """,
            (run_id,),
        )
        return tuple(capital_tree_mart_from_row(row) for row in rows)

    def component_breakdown(self: Any, run_id: str) -> tuple[ComponentBreakdownRow, ...]:
        """Return persisted component-level dashboard totals for one run."""

        if not self.run_exists(run_id):
            return ()
        rows = self._fetch_mart(
            "component_breakdown",
            """
            SELECT run_id, component, amount, currency, node_count, measure_count
            FROM {mart}
            WHERE run_id = ?
            ORDER BY component
            """,
            (run_id,),
        )
        return tuple(component_breakdown_from_row(row) for row in rows)

    def movement_summary(
        self: Any,
        run_id: str,
        *,
        node_id: str | None = None,
    ) -> tuple[MovementSummaryRow, ...]:
        """Return persisted movement summary rows for one run, optionally by node."""

        if not self.run_exists(run_id):
            return ()
        where_clause = "WHERE run_id = ?"
        parameters: tuple[object, ...] = (run_id,)
        if node_id is not None:
            where_clause += " AND node_id = ?"
            parameters = (run_id, node_id)
        rows = self._fetch_mart(
            "movement_summary",
            f"""
            SELECT run_id, baseline_run_id, movement_id, node_id, movement_type,
                   from_amount, to_amount, delta_amount, base_currency, driver_type,
                   driver_id, attribution_method, artifact_id
            FROM {{mart}}
            {where_clause}
            ORDER BY node_id, movement_type, driver_type, driver_id, movement_id
            """,
            parameters,
        )
        return tuple(movement_summary_from_row(row) for row in rows)

    def top_contributors(
        self: Any, run_id: str, *, limit: int = 10
    ) -> tuple[dict[str, object], ...]:
        """Return top attribution contributors from the persisted mart."""

        if not self.run_exists(run_id):
            return ()
        limit = max(1, limit)
        columns = _mart_columns("top_contributors")
        rows = self._fetch_mart(
            "top_contributors",
            f"""
            SELECT {", ".join(columns)}
            FROM {{mart}}
            WHERE run_id = ?
            ORDER BY rank
            LIMIT ?
            """,
            (run_id, limit),
        )
        return _dict_rows(columns, rows)

    def mart_rows(self: Any, run_id: str, mart_name: str) -> tuple[dict[str, object], ...]:
        """Return rows from one persisted mart for a committed run."""

        if not self.run_exists(run_id):
            return ()
        columns = _mart_columns(mart_name)
        rows = self._fetch_mart(
            mart_name,
            f"""
            SELECT {", ".join(columns)}
            FROM {{mart}}
            WHERE run_id = ?
            ORDER BY {", ".join(columns[: min(3, len(columns))])}
            """,
            (run_id,),
        )
        return _dict_rows(columns, rows)

    def regime_comparison(self: Any, run_group_id: str) -> tuple[dict[str, object], ...]:
        """Return persisted comparison rows for one run group."""

        columns = _mart_columns("regime_comparison")
        if not self._has_mart_files("regime_comparison"):
            return ()
        rows = self._fetch_custom(
            f"""
            SELECT {", ".join(columns)}
            FROM {self._mart_relation("regime_comparison")}
            WHERE run_group_id = ?
            ORDER BY as_of_date, regime_id, run_id
            """,
            (run_group_id,),
        )
        return _dict_rows(columns, rows)
