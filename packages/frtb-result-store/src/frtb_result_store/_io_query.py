"""Base query helpers for the DuckDB/Parquet result store."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any, cast

from frtb_result_store._io_capital_queries import StoreCapitalQueryMixin
from frtb_result_store._io_mart_queries import StoreMartQueryMixin
from frtb_result_store._io_run_queries import StoreRunQueryMixin
from frtb_result_store.store_paths import _sql_literal


class StoreQueryMixin(StoreRunQueryMixin, StoreMartQueryMixin, StoreCapitalQueryMixin):
    def _fetchall(
        self: Any,
        table_name: str,
        sql_template: str,
        parameters: Sequence[object] = (),
    ) -> tuple[tuple[object, ...], ...]:
        if not self._has_table_files(table_name):
            return ()
        if parameters and isinstance(parameters[0], str) and self.run_exists(parameters[0]):
            self._ensure_run_compatible(parameters[0])
        sql = sql_template.format(table=self._parquet_relation(table_name))
        return cast(tuple[tuple[object, ...], ...], self._fetch_custom(sql, parameters))

    def _fetch_mart(
        self: Any,
        mart_name: str,
        sql_template: str,
        parameters: Sequence[object] = (),
    ) -> tuple[tuple[object, ...], ...]:
        if not self._has_mart_files(mart_name):
            return ()
        relation = self._mart_relation(mart_name)
        if parameters and isinstance(parameters[0], str):
            run_id = parameters[0]
            if self.run_exists(run_id):
                self._ensure_run_compatible(run_id)
                mart_path = self._mart_path(mart_name, run_id)
                if not mart_path.exists():
                    return ()
                relation = f"read_parquet({_sql_literal(str(mart_path))})"
        sql = sql_template.format(mart=relation)
        return cast(tuple[tuple[object, ...], ...], self._fetch_custom(sql, parameters))

    def _fetch_custom(
        self: Any,
        sql: str,
        parameters: Sequence[object] = (),
    ) -> tuple[tuple[object, ...], ...]:
        con = self._connect_query()
        try:
            raw_rows = con.execute(sql, parameters).fetchall()
            return tuple(tuple(row) for row in raw_rows)
        finally:
            con.close()
