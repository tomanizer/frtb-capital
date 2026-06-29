"""Source profiling helpers for v1 IMA client-data mapping."""

from __future__ import annotations

import csv
import json
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any

from frtb_ima.adapters._mapping_hash import stable_mapping_hash

_INTEGER_RE = re.compile(r"^[+-]?\d+$")
_FLOAT_RE = re.compile(r"^[+-]?(?:(?:\d+\.\d*)|(?:\d*\.\d+)|(?:\d+))(?:[eE][+-]?\d+)?$")
_TRUE_VALUES = frozenset({"true", "t", "yes", "y"})
_FALSE_VALUES = frozenset({"false", "f", "no", "n"})


@dataclass(frozen=True)
class SourceColumnProfile:
    """Profile for one source column in a client export.

    Parameters
    ----------
    name : str
        Source column name.
    row_count : int
        Total number of profiled rows.
    null_count : int
        Number of rows where this column is missing or blank.
    null_rate : float
        Null count divided by row count, or ``0.0`` for an empty input.
    inferred_type : str
        Best-effort type label for non-null values.
    distinct_count : int
        Exact count of distinct non-null string values.
    examples : tuple[str, ...]
        First distinct non-null examples, capped by the profiler.
    min_value : object | None
        Minimum typed value for numeric, date, or timestamp columns.
    max_value : object | None
        Maximum typed value for numeric, date, or timestamp columns.
    """

    name: str
    row_count: int
    null_count: int
    null_rate: float
    inferred_type: str
    distinct_count: int
    examples: tuple[str, ...]
    min_value: object | None = None
    max_value: object | None = None

    def as_dict(self) -> dict[str, object]:
        """Return a JSON-serializable column profile.

        Returns
        -------
        dict[str, object]
            Column profile suitable for inclusion in ``profile.json``.
        """

        return {
            "name": self.name,
            "row_count": self.row_count,
            "null_count": self.null_count,
            "null_rate": self.null_rate,
            "inferred_type": self.inferred_type,
            "distinct_count": self.distinct_count,
            "examples": list(self.examples),
            "min_value": _json_value(self.min_value),
            "max_value": _json_value(self.max_value),
        }


@dataclass(frozen=True)
class SourceProfile:
    """Profile report for one client source export.

    Parameters
    ----------
    source_name : str
        Logical source name or file path.
    row_count : int
        Number of profiled rows.
    column_count : int
        Number of discovered source columns.
    source_hash : str
        Stable hash of normalized source rows.
    columns : tuple[SourceColumnProfile, ...]
        Per-column profile records in discovered column order.
    """

    source_name: str
    row_count: int
    column_count: int
    source_hash: str
    columns: tuple[SourceColumnProfile, ...]

    def column(self, name: str) -> SourceColumnProfile:
        """Return the profile for ``name``.

        Parameters
        ----------
        name : str
            Source column name.

        Returns
        -------
        SourceColumnProfile
            Matching column profile.
        """

        for column in self.columns:
            if column.name == name:
                return column
        raise KeyError(name)

    def as_dict(self) -> dict[str, object]:
        """Return a JSON-serializable source profile payload.

        Returns
        -------
        dict[str, object]
            Payload suitable for writing as v1 ``profile.json``.
        """

        return {
            "profile_schema": "ima-source-profile-v1",
            "source_name": self.source_name,
            "row_count": self.row_count,
            "column_count": self.column_count,
            "source_hash": self.source_hash,
            "columns": [column.as_dict() for column in self.columns],
        }

    def to_json(self) -> str:
        """Serialize the profile using stable JSON formatting.

        Returns
        -------
        str
            Stable, indented JSON representation of this profile.
        """

        return json.dumps(self.as_dict(), indent=2, sort_keys=True) + "\n"


def profile_csv_source(path: str | Path, *, max_examples: int = 3) -> SourceProfile:
    """Profile a CSV client export without requiring a mapping spec.

    Parameters
    ----------
    path : str | Path
        CSV file path.
    max_examples : int, optional
        Maximum distinct non-null examples retained per column.

    Returns
    -------
    SourceProfile
        Source profile containing row, column, null, type, and range metadata.
    """

    source_path = Path(path)
    source_text = source_path.read_text(encoding="utf-8")
    rows = tuple(csv.DictReader(source_text.splitlines()))
    profile = profile_source_rows(
        rows,
        source_name=str(source_path),
        max_examples=max_examples,
    )
    return SourceProfile(
        source_name=profile.source_name,
        row_count=profile.row_count,
        column_count=profile.column_count,
        source_hash=stable_mapping_hash({"source_text": source_text}),
        columns=profile.columns,
    )


def profile_source_rows(
    rows: Sequence[Mapping[str, object]],
    *,
    source_name: str = "<rows>",
    max_examples: int = 3,
) -> SourceProfile:
    """Profile already-loaded client source rows.

    Parameters
    ----------
    rows : Sequence[Mapping[str, object]]
        Source rows keyed by client column names.
    source_name : str, optional
        Logical source name recorded in the profile.
    max_examples : int, optional
        Maximum distinct non-null examples retained per column.

    Returns
    -------
    SourceProfile
        Source profile containing discovered columns and per-column metadata.
    """

    if max_examples < 0:
        raise ValueError("max_examples must be non-negative")
    columns = _discovered_columns(rows)
    normalized_rows = tuple(
        {column: _cell_text(row.get(column)) for column in columns} for row in rows
    )
    return SourceProfile(
        source_name=source_name,
        row_count=len(rows),
        column_count=len(columns),
        source_hash=stable_mapping_hash({"rows": list(normalized_rows)}),
        columns=tuple(
            _profile_column(column, normalized_rows, max_examples=max_examples)
            for column in columns
        ),
    )


def _discovered_columns(rows: Sequence[Mapping[str, object]]) -> tuple[str, ...]:
    columns: list[str] = []
    seen: set[str] = set()
    for row in rows:
        for column in row:
            if column not in seen:
                seen.add(column)
                columns.append(str(column))
    return tuple(columns)


def _profile_column(
    column: str,
    rows: Sequence[Mapping[str, str]],
    *,
    max_examples: int,
) -> SourceColumnProfile:
    row_count = len(rows)
    values = tuple(row.get(column, "") for row in rows)
    non_null = tuple(value for value in values if value != "")
    null_count = row_count - len(non_null)
    distinct_values = tuple(dict.fromkeys(non_null))
    inferred_type = _infer_type(non_null)
    min_value, max_value = _range_for_values(non_null, inferred_type)
    return SourceColumnProfile(
        name=column,
        row_count=row_count,
        null_count=null_count,
        null_rate=0.0 if row_count == 0 else null_count / row_count,
        inferred_type=inferred_type,
        distinct_count=len(set(non_null)),
        examples=distinct_values[:max_examples],
        min_value=min_value,
        max_value=max_value,
    )


def _infer_type(values: Sequence[str]) -> str:
    if not values:
        return "empty"
    if all(_parse_bool(value) is not None for value in values):
        return "boolean"
    if all(_parse_integer(value) is not None for value in values):
        return "integer"
    if all(_parse_float(value) is not None for value in values):
        return "float"
    if all(_parse_date(value) is not None for value in values):
        return "date"
    if all(_parse_datetime(value) is not None for value in values):
        return "timestamp"
    return "string"


def _range_for_values(
    values: Sequence[str], inferred_type: str
) -> tuple[object | None, object | None]:
    parsed: tuple[Any, ...]
    if inferred_type == "integer":
        parsed = tuple(_parse_integer(value) for value in values)
    elif inferred_type == "float":
        parsed = tuple(_parse_float(value) for value in values)
    elif inferred_type == "date":
        parsed = tuple(_parse_date(value) for value in values)
    elif inferred_type == "timestamp":
        parsed = tuple(_parse_datetime(value) for value in values)
    else:
        return None, None
    return min(parsed), max(parsed)


def _cell_text(value: object) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _parse_bool(value: str) -> bool | None:
    lowered = value.lower()
    if lowered in _TRUE_VALUES:
        return True
    if lowered in _FALSE_VALUES:
        return False
    return None


def _parse_integer(value: str) -> int | None:
    normalized = value.replace(",", "")
    if _INTEGER_RE.fullmatch(normalized) is None:
        return None
    return int(normalized)


def _parse_float(value: str) -> float | None:
    normalized = value.replace(",", "")
    if _FLOAT_RE.fullmatch(normalized) is None:
        return None
    return float(normalized)


def _parse_date(value: str) -> date | None:
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def _parse_datetime(value: str) -> datetime | None:
    try:
        return datetime.fromisoformat(value.removesuffix("Z") + "+00:00")
    except ValueError:
        try:
            return datetime.fromisoformat(value)
        except ValueError:
            return None


def _json_value(value: object | None) -> object | None:
    if isinstance(value, date | datetime):
        return value.isoformat()
    return value
