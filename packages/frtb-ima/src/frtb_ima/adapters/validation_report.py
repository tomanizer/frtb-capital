"""Aggregate validation-report helpers for v1 IMA mapping workflows."""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any

from frtb_ima.adapters._mapping_hash import stable_mapping_hash


@dataclass(frozen=True)
class TableValidationSummary:
    """Validation summary for one mapped canonical IMA table."""

    table_name: str
    target_schema: str
    source_system: str
    source_file: str
    mapping_hash: str
    source_hash: str
    row_count_read: int
    row_count_mapped: int
    row_count_rejected: int
    passed: bool
    findings: tuple[Mapping[str, object], ...] = ()

    def as_dict(self) -> dict[str, object]:
        """Return a JSON-serializable table summary.

        Returns
        -------
        dict[str, object]
            Table validation summary suitable for ``validation_report.json``.
        """

        return {
            "table_name": self.table_name,
            "target_schema": self.target_schema,
            "source_system": self.source_system,
            "source_file": self.source_file,
            "mapping_hash": self.mapping_hash,
            "source_hash": self.source_hash,
            "row_count_read": self.row_count_read,
            "row_count_mapped": self.row_count_mapped,
            "row_count_rejected": self.row_count_rejected,
            "passed": self.passed,
            "findings": [dict(finding) for finding in self.findings],
        }


@dataclass(frozen=True)
class ImaMappingValidationReport:
    """Aggregate v1 ``validation_report.json`` payload across mapped IMA tables."""

    target_schema: str
    source_system: str
    mapping_hash: str
    report_hash: str
    tables: tuple[TableValidationSummary, ...]
    source_hashes: Mapping[str, str]
    finding_count: int
    row_count_read: int
    row_count_mapped: int
    row_count_rejected: int

    def __post_init__(self) -> None:
        object.__setattr__(self, "tables", tuple(self.tables))
        object.__setattr__(self, "source_hashes", MappingProxyType(dict(self.source_hashes)))

    @property
    def passed(self) -> bool:
        """Return ``True`` when every table report passed.

        Returns
        -------
        bool
            ``True`` when every table report passed and no aggregate finding exists.
        """

        return all(table.passed for table in self.tables) and self.finding_count == 0

    def as_dict(self) -> dict[str, object]:
        """Return a JSON-serializable aggregate validation report.

        Returns
        -------
        dict[str, object]
            Payload suitable for writing as v1 ``validation_report.json``.
        """

        return {
            "report_schema": "ima-mapping-validation-report-v1",
            "target_schema": self.target_schema,
            "source_system": self.source_system,
            "mapping_hash": self.mapping_hash,
            "report_hash": self.report_hash,
            "passed": self.passed,
            "row_count_read": self.row_count_read,
            "row_count_mapped": self.row_count_mapped,
            "row_count_rejected": self.row_count_rejected,
            "finding_count": self.finding_count,
            "source_hashes": dict(self.source_hashes),
            "tables": [table.as_dict() for table in self.tables],
        }

    def to_json(self) -> str:
        """Serialize this report using stable JSON formatting.

        Returns
        -------
        str
            Stable, indented JSON representation of this validation report.
        """

        return json.dumps(self.as_dict(), indent=2, sort_keys=True) + "\n"


def build_ima_mapping_validation_report(
    table_reports: Mapping[str, object],
) -> ImaMappingValidationReport:
    """Build an aggregate v1 validation report from per-table mapper reports.

    Parameters
    ----------
    table_reports : Mapping[str, object]
        Mapping from canonical table name to a table-specific report object with
        the standard v1 report attributes and ``as_dict()`` method.

    Returns
    -------
    ImaMappingValidationReport
        Aggregate report containing reconciliation totals, hashes, and findings.
    """

    if not table_reports:
        raise ValueError("at least one table report is required")
    tables = tuple(
        _table_summary(table_name, report)
        for table_name, report in sorted(table_reports.items(), key=lambda item: item[0])
    )
    target_schema = _single_value({table.target_schema for table in tables}, "target_schema")
    source_system = _single_value({table.source_system for table in tables}, "source_system")
    mapping_hash = _single_value({table.mapping_hash for table in tables}, "mapping_hash")
    report_payload = {
        "target_schema": target_schema,
        "source_system": source_system,
        "mapping_hash": mapping_hash,
        "tables": [table.as_dict() for table in tables],
    }
    return ImaMappingValidationReport(
        target_schema=target_schema,
        source_system=source_system,
        mapping_hash=mapping_hash,
        report_hash=stable_mapping_hash(report_payload),
        tables=tables,
        source_hashes={table.table_name: table.source_hash for table in tables},
        finding_count=sum(len(table.findings) for table in tables),
        row_count_read=sum(table.row_count_read for table in tables),
        row_count_mapped=sum(table.row_count_mapped for table in tables),
        row_count_rejected=sum(table.row_count_rejected for table in tables),
    )


def _table_summary(table_name: str, report: object) -> TableValidationSummary:
    payload = _report_payload(report)
    findings = tuple(
        {"table_name": table_name, **dict(finding)} for finding in payload.get("findings", [])
    )
    return TableValidationSummary(
        table_name=table_name,
        target_schema=str(payload["target_schema"]),
        source_system=str(payload["source_system"]),
        source_file=str(payload["source_file"]),
        mapping_hash=str(payload["mapping_hash"]),
        source_hash=str(payload["source_hash"]),
        row_count_read=int(payload["row_count_read"]),
        row_count_mapped=int(payload["row_count_mapped"]),
        row_count_rejected=int(payload["row_count_rejected"]),
        passed=bool(payload["passed"]),
        findings=findings,
    )


def _report_payload(report: object) -> Mapping[str, Any]:
    as_dict = getattr(report, "as_dict", None)
    if not callable(as_dict):
        raise TypeError("table reports must provide as_dict()")
    payload = as_dict()
    if not isinstance(payload, Mapping):
        raise TypeError("table report as_dict() must return a mapping")
    return payload


def _single_value(values: set[str], field_name: str) -> str:
    if len(values) != 1:
        raise ValueError(f"table reports must share one {field_name}")
    return next(iter(values))
