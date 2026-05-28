"""
Post-run audit records, NDJSON serialisation, and Markdown report rendering.

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

from frtb_ima.regimes import DeskEligibilityStatus


def _empty_mapping() -> Mapping[str, object]:
    return MappingProxyType({})


@dataclass(frozen=True)
class DeskAuditRecord:
    """Serialisable audit record for one desk in one capital run."""

    run_id: str
    desk_id: str
    regime: str
    desk_eligibility: str = field(default="IMA_ELIGIBLE", kw_only=True)
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
        try:
            desk_eligibility = DeskEligibilityStatus(self.desk_eligibility).value
        except ValueError as exc:
            raise ValueError("desk_eligibility must be a DeskEligibilityStatus value") from exc
        if self.elapsed_seconds < 0.0:
            raise ValueError("elapsed_seconds must be non-negative")
        object.__setattr__(self, "desk_eligibility", desk_eligibility)
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
            "desk_eligibility": self.desk_eligibility,
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


def render_capital_run_audit_report(
    log: CapitalRunAuditLog,
    *,
    title: str = "FRTB IMA Capital Run Audit Report",
) -> str:
    """
    Render a deterministic Markdown audit report for a capital run.

    This is an orchestration-layer report view over already-computed audit
    records. It does not recalculate capital and does not attempt to be a final
    regulatory disclosure template.
    """
    lines: list[str] = [
        f"# {title}",
        "",
        "> Prototype report only. Not for regulatory reporting.",
        "> NPR 2.0 values are proposed-rule working assumptions.",
        "",
        "## Run summary",
        "",
    ]
    lines.extend(
        _markdown_table(
            ("Field", "Value"),
            (
                ("Run ID", log.run_id),
                ("Regime", log.regime),
                (
                    "As of date",
                    log.as_of_date.isoformat() if log.as_of_date is not None else "",
                ),
                ("Desk count", log.desk_count),
            ),
        )
    )

    if log.metadata:
        lines.extend(_json_section("Run metadata", log.metadata, heading_level=3))

    lines.extend(["", "## Desk summary", ""])
    lines.extend(
        _markdown_table(
            (
                "Desk",
                "As of date",
                "IMCC",
                "Total SES",
                "Models-based capital",
                "PLA zone",
                "Backtesting eligible",
                "Elapsed seconds",
            ),
            (
                (
                    record.desk_id,
                    record.as_of_date.isoformat() if record.as_of_date is not None else "",
                    _format_report_value(_mapping_value(record.imcc, "imcc")),
                    _format_report_value(_mapping_value(record.ses, "total_ses", "ses")),
                    _format_report_value(_mapping_value(record.capital, "models_based_capital")),
                    _format_report_value(_mapping_value(record.pla, "zone", "pla_zone")),
                    _format_report_value(_mapping_value(record.backtesting, "model_eligible")),
                    _format_report_value(record.elapsed_seconds),
                )
                for record in log.desk_records
            ),
        )
    )

    for record in log.desk_records:
        lines.extend(["", f"## Desk: {record.desk_id}", ""])
        lines.extend(
            _markdown_table(
                ("Field", "Value"),
                (
                    ("Run ID", record.run_id),
                    ("Regime", record.regime),
                    (
                        "As of date",
                        record.as_of_date.isoformat() if record.as_of_date is not None else "",
                    ),
                    ("Elapsed seconds", _format_report_value(record.elapsed_seconds)),
                ),
            )
        )
        if record.notes:
            lines.extend(["", "### Notes", ""])
            lines.extend(f"- {_escape_table_cell(note)}" for note in record.notes)
        lines.extend(_json_section("IMCC", record.imcc, heading_level=3))
        lines.extend(_json_section("SES", record.ses, heading_level=3))
        lines.extend(_json_section("PLA", record.pla, heading_level=3))
        lines.extend(_json_section("Backtesting", record.backtesting, heading_level=3))
        lines.extend(_json_section("Capital", record.capital, heading_level=3))
        if record.nmrf_valuation:
            lines.extend(
                _json_section(
                    "NMRF valuation",
                    record.nmrf_valuation,
                    heading_level=3,
                )
            )
        if record.metadata:
            lines.extend(_json_section("Desk metadata", record.metadata, heading_level=3))

    return "\n".join(lines).rstrip() + "\n"


def write_capital_run_audit_report(
    log: CapitalRunAuditLog,
    path: str | Path,
    *,
    title: str = "FRTB IMA Capital Run Audit Report",
) -> None:
    """Write a deterministic Markdown audit report for a capital run."""
    report_path = Path(path)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        render_capital_run_audit_report(log, title=title),
        encoding="utf-8",
    )


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


def _json_section(
    title: str,
    value: object,
    *,
    heading_level: int,
) -> list[str]:
    heading = "#" * heading_level
    return [
        "",
        f"{heading} {title}",
        "",
        "```json",
        json.dumps(_jsonable(value), indent=2, sort_keys=True),
        "```",
    ]


def _markdown_table(
    headers: tuple[str, ...],
    rows: Iterable[tuple[object, ...]],
) -> list[str]:
    header = "| " + " | ".join(_escape_table_cell(item) for item in headers) + " |"
    separator = "| " + " | ".join("---" for _ in headers) + " |"
    body = ["| " + " | ".join(_escape_table_cell(item) for item in row) + " |" for row in rows]
    return [header, separator, *body]


def _mapping_value(mapping: Mapping[str, object], *keys: str) -> object:
    for key in keys:
        if key in mapping:
            return mapping[key]
    return ""


def _format_report_value(value: object) -> str:
    if isinstance(value, bool):
        return str(value)
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        return f"{value:.6g}"
    if value is None:
        return ""
    return str(value)


def _escape_table_cell(value: object) -> str:
    text = _format_report_value(value)
    return text.replace("|", "\\|").replace("\n", "<br>")


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
