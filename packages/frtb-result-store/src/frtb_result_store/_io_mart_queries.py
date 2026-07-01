"""Persisted mart queries for dashboard and comparison views."""

from __future__ import annotations

from typing import Any, cast

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
    ResultStoreContractError,
)
from frtb_result_store.store_paths import _mart_columns
from frtb_result_store.store_schemas import _dict_rows
from collections.abc import Sequence


DIMENSION_COLUMNS = [
    "component",
    "desk_id",
    "portfolio_id",
    "book_id",
    "risk_class",
    "bucket",
    "issuer_id",
    "counterparty_id",
    "calculation_branch",
    "regulatory_rule_id",
]


class StoreMartQueryMixin:

    def capital_tree(self: Any, run_id: str) -> tuple[CapitalNode, ...]:
        """Return all capital graph nodes for one run from the persisted mart.
        Parameters
        ----------
        run_id : str
            Run id.

        Returns
        -------
        tuple[CapitalNode, ...]
            Result of the operation.
        """

        return tuple(row.to_node() for row in self.capital_tree_mart(run_id))

    def capital_summary(self: Any, run_id: str) -> tuple[CapitalSummaryRow, ...]:
        """Return persisted dashboard summary rows for one run.
        Parameters
        ----------
        run_id : str
            Run id.

        Returns
        -------
        tuple[CapitalSummaryRow, ...]
            Result of the operation.
        """

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
        """Return persisted flattened capital tree rows for one run.
        Parameters
        ----------
        run_id : str
            Run id.

        Returns
        -------
        tuple[CapitalTreeMartRow, ...]
            Result of the operation.
        """

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
        """Return persisted component-level dashboard totals for one run.
        Parameters
        ----------
        run_id : str
            Run id.

        Returns
        -------
        tuple[ComponentBreakdownRow, ...]
            Result of the operation.
        """

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
        """Return persisted movement summary rows for one run, optionally by node.
        Parameters
        ----------
        run_id : str
            Run id.
        node_id : str | None, optional
            Node id.

        Returns
        -------
        tuple[MovementSummaryRow, ...]
            Result of the operation.
        """

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
        """Return top attribution contributors from the persisted mart.
        Parameters
        ----------
        run_id : str
            Run id.
        limit : int, optional
            Limit.

        Returns
        -------
        tuple[dict[str, object], ...]
            Result of the operation.
        """

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

    def residual_attribution_records(
        self: Any,
        run_id: str,
        *,
        node_id: str | None = None,
    ) -> tuple[dict[str, object], ...]:
        """Return persisted residual attribution projection rows for one run.
        Parameters
        ----------
        run_id : str
            Run id.
        node_id : str | None, optional
            Node id.

        Returns
        -------
        tuple[dict[str, object], ...]
            Result of the operation.
        """

        return cast(
            tuple[dict[str, object], ...],
            self._attribution_projection_rows(
                "residual_attribution",
                run_id,
                node_id=node_id,
            ),
        )

    def unsupported_attribution_records(
        self: Any,
        run_id: str,
        *,
        node_id: str | None = None,
    ) -> tuple[dict[str, object], ...]:
        """Return persisted unsupported attribution projection rows for one run.
        Parameters
        ----------
        run_id : str
            Run id.
        node_id : str | None, optional
            Node id.

        Returns
        -------
        tuple[dict[str, object], ...]
            Result of the operation.
        """

        return cast(
            tuple[dict[str, object], ...],
            self._attribution_projection_rows(
                "unsupported_attribution",
                run_id,
                node_id=node_id,
            ),
        )

    def _attribution_projection_rows(
        self: Any,
        mart_name: str,
        run_id: str,
        *,
        node_id: str | None = None,
    ) -> tuple[dict[str, object], ...]:
        if not self.run_exists(run_id):
            return ()
        where_clause = "WHERE run_id = ?"
        parameters: tuple[object, ...] = (run_id,)
        if node_id is not None:
            where_clause += " AND node_id = ?"
            parameters = (run_id, node_id)
        columns = _mart_columns(mart_name)
        rows = self._fetch_mart(
            mart_name,
            f"""
            SELECT {", ".join(columns)}
            FROM {{mart}}
            {where_clause}
            ORDER BY rank
            """,
            parameters,
        )
        return _dict_rows(columns, rows)

    def mart_rows(self: Any, run_id: str, mart_name: str) -> tuple[dict[str, object], ...]:
        """Return rows from one persisted mart for a committed run.
        Parameters
        ----------
        run_id : str
            Run id.
        mart_name : str
            Mart name.

        Returns
        -------
        tuple[dict[str, object], ...]
            Result of the operation.
        """

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
        """Return persisted comparison rows for one run group.
        Parameters
        ----------
        run_group_id : str
            Run group id.

        Returns
        -------
        tuple[dict[str, object], ...]
            Result of the operation.
        """

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

    def pivot_query(
        self: Any,
        run_id: str,
        *,
        rows: Sequence[str],
        cols: Sequence[str] = (),
        measures: Sequence[str] = ("capital",),
        filters: Sequence[str] = (),
        limit: int = 100,
        offset: int = 0,
    ) -> dict[str, object]:
        """Perform a server-side pivot aggregate query over capital nodes and measures.

        Parameters
        ----------
        run_id : str
            Run id.
        rows : Sequence[str]
            Row dimensions to group/pivot by.
        cols : Sequence[str]
            Column dimensions to pivot by.
        measures : Sequence[str]
            Measures to aggregate.
        filters : Sequence[str]
            Query filters.
        limit : int
            Page limit.
        offset : int
            Page offset.

        Returns
        -------
        dict[str, object]
            Pivoted data and metadata.
        """
        if not self.run_exists(run_id):
            return {
                "pivot_rows": [],
                "total_count": 0,
                "limit": limit,
                "offset": offset,
            }

        rows, cols, measures, filters = self._parse_pivot_params(rows, cols, measures, filters)
        official_nodes_map = self._get_official_nodes_map(run_id)
        group_cols = list(rows) + list(cols)

        rows_data = self._execute_pivot_sql(run_id, group_cols, measures, filters)
        grouped_results = self._pivot_results(rows_data, rows, cols, group_cols)

        pivot_rows = []
        for row_vals, res in grouped_results.items():
            dimensions = res["dimensions"]
            populated = {
                dim: val
                for dim, val in dimensions.items()
                if val is not None and val != "" and dim in DIMENSION_COLUMNS
            }
            key = (frozenset(populated.keys()), tuple(sorted(populated.items())))
            node_id = official_nodes_map.get(key)
            subtotal_type = "additive_official" if node_id is not None else "display_group"

            pivot_rows.append({
                "dimensions": dimensions,
                "measures": res["measures"],
                "subtotal_type": subtotal_type,
                "node_id": node_id,
            })

        total_count = len(pivot_rows)
        return {
            "pivot_rows": pivot_rows[offset : offset + limit],
            "total_count": total_count,
            "limit": limit,
            "offset": offset,
        }

    def _parse_pivot_params(
        self: Any,
        rows: Sequence[str],
        cols: Sequence[str],
        measures: Sequence[str],
        filters: Sequence[str],
    ) -> tuple[list[str], list[str], list[str], list[str]]:
        parsed_rows = []
        for r in rows:
            parsed_rows.extend(x.strip() for x in r.split(",") if x.strip())
        parsed_cols = []
        for c in cols:
            parsed_cols.extend(x.strip() for x in c.split(",") if x.strip())
        parsed_measures = []
        for m in measures:
            parsed_measures.extend(x.strip() for x in m.split(",") if x.strip())
        parsed_filters = []
        for f in filters:
            parsed_filters.extend(x.strip() for x in f.split(",") if x.strip())

        if not parsed_measures:
            raise ResultStoreContractError("At least one measure must be specified", field="measures")

        valid_dimensions = set(DIMENSION_COLUMNS + ["node_type"])
        for dim in parsed_rows:
            if dim not in valid_dimensions:
                raise ResultStoreContractError(f"Invalid row dimension: {dim}", field="rows")
        for dim in parsed_cols:
            if dim not in valid_dimensions:
                raise ResultStoreContractError(f"Invalid column dimension: {dim}", field="cols")
        return parsed_rows, parsed_cols, parsed_measures, parsed_filters

    def _get_official_nodes_map(
        self: Any,
        run_id: str,
    ) -> dict[tuple[frozenset[str], tuple[tuple[str, object], ...]], str]:
        official_nodes_map = {}
        for node in self.capital_tree(run_id):
            populated = {}
            for dim in DIMENSION_COLUMNS:
                val = getattr(node, dim, None)
                if val is not None and val != "":
                    from enum import Enum
                    if isinstance(val, Enum):
                        val = val.value
                    populated[dim] = val
            key = (frozenset(populated.keys()), tuple(sorted(populated.items())))
            if key not in official_nodes_map:
                official_nodes_map[key] = node.node_id
        return official_nodes_map

    def _execute_pivot_sql(
        self: Any,
        run_id: str,
        group_cols: list[str],
        measures: list[str],
        filters: list[str],
    ) -> tuple[tuple[object, ...], ...]:
        where_parts = ["n.run_id = ?"]
        params = [run_id]
        valid_dimensions = set(DIMENSION_COLUMNS + ["node_type"])

        for f in filters:
            if ":" in f:
                parts = f.split(":", 2)
                if len(parts) == 3 and parts[1] == "eq":
                    key, _, val = parts
                else:
                    key, val = parts[0], parts[-1]
            elif "=" in f:
                key, val = f.split("=", 1)
            else:
                raise ResultStoreContractError(f"Invalid filter format: {f!r}", field="filters")

            key = key.strip()
            val = val.strip()

            if key == "scenario":
                where_parts.append("m.scenario = ?")
                params.append(val)
            elif key == "measure_name":
                where_parts.append("m.measure_name = ?")
                params.append(val)
            elif key in valid_dimensions:
                where_parts.append(f"n.{key} = ?")
                params.append(val)
            else:
                raise ResultStoreContractError(f"Invalid filter column: {key}", field="filters")

        if not group_cols:
            raise ResultStoreContractError("At least one dimension must be specified", field="rows")

        select_cols = [f"n.{col}" for col in group_cols]
        select_clause = ", ".join(select_cols)
        group_clause = ", ".join(select_cols)

        measure_placeholders = ", ".join("?" for _ in measures)
        where_parts.append(f"m.measure_name IN ({measure_placeholders})")
        params.extend(measures)

        sql = f"""
            SELECT 
                {select_clause},
                m.measure_name,
                SUM(m.amount) AS amount
            FROM {self._parquet_relation("capital_nodes")} n
            JOIN {self._parquet_relation("capital_measures")} m
              ON n.run_id = m.run_id
             AND n.node_id = m.node_id
            WHERE {" AND ".join(where_parts)}
            GROUP BY {group_clause}, m.measure_name
            ORDER BY {group_clause}
        """
        return self._fetch_custom(sql, params)

    def _pivot_results(
        self: Any,
        rows_data: tuple[tuple[object, ...], ...],
        rows: list[str],
        cols: list[str],
        group_cols: list[str],
    ) -> dict[tuple[object, ...], dict[str, Any]]:
        num_group_cols = len(group_cols)
        num_row_cols = len(rows)

        grouped_results = {}
        for r_data in rows_data:
            row_vals = tuple(r_data[:num_row_cols])
            col_vals = tuple(r_data[num_row_cols:num_group_cols])
            measure_name = r_data[num_group_cols]
            amount = r_data[num_group_cols + 1]

            if row_vals not in grouped_results:
                grouped_results[row_vals] = {
                    "dimensions": dict(zip(rows, row_vals)),
                    "measures": {},
                }

            if cols:
                col_suffix = "_".join(str(cv) if cv is not None else "" for cv in col_vals)
                measure_key = f"{measure_name}_{col_suffix}" if col_suffix else measure_name
            else:
                measure_key = measure_name

            grouped_results[row_vals]["measures"][measure_key] = amount
        return grouped_results

