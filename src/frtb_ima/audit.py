"""
Post-run audit records and NDJSON serialisation.

These dataclasses sit at the orchestration boundary. They collect decomposed
calculation results into serialisable records without adding storage or
analytics dependencies to the calculation layer.

Regulatory traceability:
    Supports auditability and run traceability for Basel MAR31-MAR33, U.S. NPR
    2.0 model-risk governance working assumptions, and EU CRR internal-model
    governance. See docs/REGULATORY_TRACEABILITY.md.
"""

from __future__ import annotations

import json
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from datetime import date, datetime
from enum import Enum
from pathlib import Path
from types import MappingProxyType, TracebackType
from typing import Any


def _empty_mapping() -> Mapping[str, object]:
    return MappingProxyType({})


@dataclass(frozen=True)
class DeskAuditRecord:
    """Serialisable audit record for one desk in one capital run."""

    run_id: str
    desk_id: str
    regime: str
    imcc: Mapping[str, object]
    ses: Mapping[str, object]
    pla: Mapping[str, object]
    backtesting: Mapping[str, object]
    capital: Mapping[str, object]
    elapsed_seconds: float
    nmrf_valuation: Mapping[str, object] = field(default_factory=_empty_mapping)
    as_of_date: date | None = None
    notes: tuple[str, ...] = ()
    metadata: Mapping[str, object] = field(default_factory=_empty_mapping)

    def __post_init__(self) -> None:
        if not self.run_id:
            raise ValueError("run_id must be non-empty")
        if not self.desk_id:
            raise ValueError("desk_id must be non-empty")
        if not self.regime:
            raise ValueError("regime must be non-empty")
        if self.elapsed_seconds < 0.0:
            raise ValueError("elapsed_seconds must be non-negative")
        object.__setattr__(self, "imcc", _freeze_mapping(self.imcc))
        object.__setattr__(self, "ses", _freeze_mapping(self.ses))
        object.__setattr__(self, "pla", _freeze_mapping(self.pla))
        object.__setattr__(self, "backtesting", _freeze_mapping(self.backtesting))
        object.__setattr__(self, "capital", _freeze_mapping(self.capital))
        object.__setattr__(
            self,
            "nmrf_valuation",
            _freeze_mapping(self.nmrf_valuation),
        )
        object.__setattr__(self, "notes", tuple(self.notes))
        object.__setattr__(self, "metadata", _freeze_mapping(self.metadata))

    def as_dict(self) -> dict[str, object]:
        """Return a JSON-serialisable dictionary."""
        return {
            "run_id": self.run_id,
            "desk_id": self.desk_id,
            "regime": self.regime,
            "as_of_date": self.as_of_date.isoformat() if self.as_of_date is not None else None,
            "imcc": _jsonable(self.imcc),
            "ses": _jsonable(self.ses),
            "pla": _jsonable(self.pla),
            "backtesting": _jsonable(self.backtesting),
            "capital": _jsonable(self.capital),
            "nmrf_valuation": _jsonable(self.nmrf_valuation),
            "elapsed_seconds": self.elapsed_seconds,
            "notes": list(self.notes),
            "metadata": _jsonable(self.metadata),
        }

    def to_json_line(self) -> str:
        """Return this desk audit record as one NDJSON line."""
        return json.dumps(self.as_dict(), sort_keys=True, separators=(",", ":"))


@dataclass(frozen=True)
class CapitalRunAuditLog:
    """Collection of desk audit records for one capital run."""

    run_id: str
    regime: str
    desk_records: tuple[DeskAuditRecord, ...]
    as_of_date: date | None = None
    metadata: Mapping[str, object] = field(default_factory=_empty_mapping)

    def __post_init__(self) -> None:
        if not self.run_id:
            raise ValueError("run_id must be non-empty")
        if not self.regime:
            raise ValueError("regime must be non-empty")
        desk_records = tuple(self.desk_records)
        desk_ids = [record.desk_id for record in desk_records]
        if len(desk_ids) != len(set(desk_ids)):
            raise ValueError("desk_records contains duplicate desk_id values")
        for record in desk_records:
            if record.run_id != self.run_id:
                raise ValueError("all desk_records must have the same run_id")
            if record.regime != self.regime:
                raise ValueError("all desk_records must have the same regime")
        object.__setattr__(self, "desk_records", desk_records)
        object.__setattr__(self, "metadata", _freeze_mapping(self.metadata))

    @property
    def desk_count(self) -> int:
        """Number of desks in the audit log."""
        return len(self.desk_records)

    def as_dict(self) -> dict[str, object]:
        """Return a JSON-serialisable dictionary."""
        return {
            "run_id": self.run_id,
            "regime": self.regime,
            "as_of_date": self.as_of_date.isoformat() if self.as_of_date is not None else None,
            "desk_count": self.desk_count,
            "desk_records": [record.as_dict() for record in self.desk_records],
            "metadata": _jsonable(self.metadata),
        }

    def to_ndjson(self) -> str:
        """Return desk records as newline-delimited JSON."""
        return audit_records_to_ndjson(self.desk_records)


def audit_records_to_ndjson(records: Iterable[DeskAuditRecord]) -> str:
    """Serialise desk audit records to newline-delimited JSON."""
    lines = [record.to_json_line() for record in records]
    if not lines:
        return ""
    return "\n".join(lines) + "\n"


def write_audit_records_ndjson(
    records: Iterable[DeskAuditRecord],
    path: str | Path,
    *,
    append: bool = False,
) -> None:
    """Write desk audit records to an NDJSON file."""
    mode = "a" if append else "w"
    with Path(path).open(mode, encoding="utf-8") as handle:
        handle.write(audit_records_to_ndjson(records))


def _freeze_mapping(values: Mapping[str, object]) -> Mapping[str, object]:
    return MappingProxyType(dict(values))


def _jsonable(value: Any) -> object:
    if hasattr(value, "as_dict") and callable(value.as_dict):
        return _jsonable(value.as_dict())
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, datetime | date):
        return value.isoformat()
    if isinstance(value, Mapping):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, tuple | list):
        return [_jsonable(item) for item in value]
    if isinstance(value, BaseException):
        return repr(value)
    if isinstance(value, TracebackType):
        return repr(value)
    try:
        json.dumps(value)
    except TypeError:
        return str(value)
    return value
