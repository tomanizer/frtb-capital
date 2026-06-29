"""Load client datasets into Arrow tables for onboarding preview."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

import pyarrow as pa  # type: ignore[import-untyped]
import pyarrow.csv as pa_csv  # type: ignore[import-untyped]
import pyarrow.ipc as pa_ipc  # type: ignore[import-untyped]
import pyarrow.parquet as pq  # type: ignore[import-untyped]


def load_table_from_path(path: Path) -> pa.Table:
    suffix = path.suffix.lower()
    if suffix in {".parquet", ".pq"}:
        return pq.read_table(path)
    if suffix == ".csv":
        return pa_csv.read_csv(path)
    if suffix in {".arrow", ".ipc", ".feather"}:
        with pa.memory_map(str(path), "r") as source:
            try:
                return pa_ipc.open_file(source).read_all()
            except pa.ArrowInvalid:
                source.seek(0)
                return pa_ipc.open_stream(source).read_all()
    raise ValueError(f"Unsupported input format for {path}; use Parquet, Arrow IPC, or CSV")


def load_table_from_bytes(data: bytes, filename: str) -> pa.Table:
    suffix = Path(filename).suffix.lower()
    if suffix in {".parquet", ".pq"}:
        return pq.read_table(pa.BufferReader(data))
    if suffix == ".csv":
        return pa_csv.read_csv(pa.BufferReader(data))
    if suffix in {".arrow", ".ipc", ".feather"}:
        try:
            return pa_ipc.open_file(pa.BufferReader(data)).read_all()
        except pa.ArrowInvalid:
            return pa_ipc.open_stream(pa.BufferReader(data)).read_all()
    raise ValueError(f"Unsupported upload format {suffix}; use Parquet, Arrow IPC, or CSV")


def load_table_from_duckdb(
    query: str,
    *,
    database_path: str = ":memory:",
    attach_files: Mapping[str, str] | None = None,
) -> pa.Table:
    import duckdb

    connection = duckdb.connect(database_path, read_only=True)
    try:
        if attach_files:
            for alias, file_path in attach_files.items():
                path = Path(file_path)
                suffix = path.suffix.lower()
                if suffix == ".csv":
                    connection.execute(
                        f"CREATE OR REPLACE VIEW {alias} AS SELECT * FROM read_csv_auto(?)",
                        [str(path)],
                    )
                elif suffix in {".parquet", ".pq"}:
                    connection.execute(
                        f"CREATE OR REPLACE VIEW {alias} AS SELECT * FROM read_parquet(?)",
                        [str(path)],
                    )
                else:
                    raise ValueError(f"Unsupported attach format for {path}")
        result = connection.execute(query)
        return result.fetch_arrow_table()
    finally:
        connection.close()


def column_preview(table: pa.Table, column_name: str, *, sample_limit: int = 5) -> dict[str, Any]:
    column = table.column(column_name)
    null_count = int(column.null_count)
    values: list[Any] = []
    for index in range(min(table.num_rows, sample_limit)):
        value = column[index].as_py()
        if value is not None:
            values.append(_json_safe(value))
    distinct_count: int | None = None
    if table.num_rows <= 10_000:
        distinct_count = len({column[index].as_py() for index in range(table.num_rows)})
    return {
        "name": column_name,
        "arrow_type": str(table.schema.field(column_name).type),
        "sample_values": values,
        "null_count": null_count,
        "distinct_count": distinct_count,
    }


def table_preview(table: pa.Table, *, row_limit: int = 50) -> tuple[list[dict[str, Any]], list[str]]:
    sliced = table.slice(0, min(row_limit, table.num_rows))
    columns = list(sliced.column_names)
    rows: list[dict[str, Any]] = []
    for index in range(sliced.num_rows):
        row = {
            column_name: _json_safe(sliced.column(column_name)[index].as_py())
            for column_name in columns
        }
        rows.append(row)
    return rows, columns


def _json_safe(value: Any) -> Any:
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    return str(value)
