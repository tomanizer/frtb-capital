"""Analyst-facing summaries over suite attribution contribution records."""

from __future__ import annotations

import math
from collections.abc import Iterable
from dataclasses import dataclass

from frtb_common.attribution import AttributionMethod, CapitalContribution, ReconciliationStatus

from frtb_orchestration._validation import (
    OrchestrationInputError,
)
from frtb_orchestration._validation import (
    require_non_negative_int as _require_non_negative_int,
)
from frtb_orchestration.suite import SuiteAttributionReport


@dataclass(frozen=True)
class SuiteAttributionRecordSummary:
    """Drillthrough-ready projection of one suite attribution contribution record."""

    component: str
    contribution_id: str
    source_id: str
    source_level: str
    bucket_key: str | None
    category: str
    method: AttributionMethod
    contribution: float | None
    residual: float
    amount: float
    absolute_amount: float
    reconciliation_status: ReconciliationStatus
    reason: str

    @classmethod
    def from_record(
        cls,
        *,
        component: str,
        record: CapitalContribution,
    ) -> SuiteAttributionRecordSummary:
        """Project a component-labelled contribution record without changing it."""

        if not isinstance(record, CapitalContribution):
            raise OrchestrationInputError("record must be a CapitalContribution", field="record")
        amount = _record_amount(record)
        return cls(
            component=component,
            contribution_id=record.contribution_id,
            source_id=record.source_id,
            source_level=record.source_level,
            bucket_key=record.bucket_key,
            category=record.category,
            method=AttributionMethod(record.method),
            contribution=record.contribution,
            residual=record.residual,
            amount=amount,
            absolute_amount=abs(amount),
            reconciliation_status=ReconciliationStatus(record.reconciliation_status),
            reason=record.reason,
        )

    def as_dict(self) -> dict[str, object]:
        """Return a JSON-serialisable row projection."""

        return {
            "component": self.component,
            "contribution_id": self.contribution_id,
            "source_id": self.source_id,
            "source_level": self.source_level,
            "bucket_key": self.bucket_key,
            "category": self.category,
            "method": self.method.value,
            "contribution": self.contribution,
            "residual": self.residual,
            "amount": self.amount,
            "absolute_amount": self.absolute_amount,
            "reconciliation_status": self.reconciliation_status.value,
            "reason": self.reason,
        }


@dataclass(frozen=True)
class SuiteAttributionGroupSummary:
    """Stable grouped contribution summary for a component or source level."""

    group_key: str
    record_count: int
    contribution: float
    residual: float
    amount: float
    absolute_amount: float
    contribution_ids: tuple[str, ...]
    source_ids: tuple[str, ...]

    def as_dict(self) -> dict[str, object]:
        """Return a JSON-serialisable group projection."""

        return {
            "group_key": self.group_key,
            "record_count": self.record_count,
            "contribution": self.contribution,
            "residual": self.residual,
            "amount": self.amount,
            "absolute_amount": self.absolute_amount,
            "contribution_ids": list(self.contribution_ids),
            "source_ids": list(self.source_ids),
        }


@dataclass(frozen=True)
class SuiteAttributionSummary:
    """Top-contributor, residual, and unsupported summaries for a suite report."""

    run_id: str
    suite_total_capital: float
    component_set: tuple[str, ...]
    top_contributors: tuple[SuiteAttributionRecordSummary, ...]
    contributors_by_component: tuple[SuiteAttributionGroupSummary, ...]
    contributors_by_source_level: tuple[SuiteAttributionGroupSummary, ...]
    residual_records: tuple[SuiteAttributionRecordSummary, ...]
    unsupported_records: tuple[SuiteAttributionRecordSummary, ...]

    def as_dict(self) -> dict[str, object]:
        """Return a deterministic JSON-serialisable summary payload."""

        return {
            "run_id": self.run_id,
            "suite_total_capital": self.suite_total_capital,
            "component_set": list(self.component_set),
            "top_contributors": [row.as_dict() for row in self.top_contributors],
            "contributors_by_component": [row.as_dict() for row in self.contributors_by_component],
            "contributors_by_source_level": [
                row.as_dict() for row in self.contributors_by_source_level
            ],
            "residual_records": [row.as_dict() for row in self.residual_records],
            "unsupported_records": [row.as_dict() for row in self.unsupported_records],
        }


def summarise_suite_attribution(
    report: SuiteAttributionReport,
    *,
    top_n: int = 10,
) -> SuiteAttributionSummary:
    """Build derived top-contributor, residual, and unsupported summaries.

    The helper consumes only ``SuiteAttributionReport`` contribution records.
    It does not re-run capital or attribution formulas.
    """

    if not isinstance(report, SuiteAttributionReport):
        raise OrchestrationInputError(
            "report must be a SuiteAttributionReport",
            field="report",
        )
    _require_non_negative_int(top_n, "top_n")
    rows = _record_summaries(report)
    return SuiteAttributionSummary(
        run_id=report.run_id,
        suite_total_capital=report.suite_total_capital,
        component_set=report.component_set,
        top_contributors=top_suite_attribution_contributors(report, top_n=top_n),
        contributors_by_component=_group_records(rows, key_name="component"),
        contributors_by_source_level=_group_records(rows, key_name="source_level"),
        residual_records=suite_attribution_residual_records(report),
        unsupported_records=suite_attribution_unsupported_records(report),
    )


def top_suite_attribution_contributors(
    report: SuiteAttributionReport,
    *,
    top_n: int = 10,
) -> tuple[SuiteAttributionRecordSummary, ...]:
    """Return contribution records ranked by absolute contribution plus residual."""

    if not isinstance(report, SuiteAttributionReport):
        raise OrchestrationInputError(
            "report must be a SuiteAttributionReport",
            field="report",
        )
    _require_non_negative_int(top_n, "top_n")
    rows = _stable_record_sort(_record_summaries(report))
    return rows[:top_n]


def suite_attribution_residual_records(
    report: SuiteAttributionReport,
) -> tuple[SuiteAttributionRecordSummary, ...]:
    """Return residual-method rows and rows carrying explicit non-zero residuals."""

    if not isinstance(report, SuiteAttributionReport):
        raise OrchestrationInputError(
            "report must be a SuiteAttributionReport",
            field="report",
        )
    rows = (
        row
        for row in _record_summaries(report)
        if row.method == AttributionMethod.RESIDUAL or row.residual != 0.0
    )
    return _stable_record_sort(rows)


def suite_attribution_unsupported_records(
    report: SuiteAttributionReport,
) -> tuple[SuiteAttributionRecordSummary, ...]:
    """Return rows whose producer marked attribution as unsupported."""

    if not isinstance(report, SuiteAttributionReport):
        raise OrchestrationInputError(
            "report must be a SuiteAttributionReport",
            field="report",
        )
    rows = (row for row in _record_summaries(report) if row.method == AttributionMethod.UNSUPPORTED)
    return _stable_record_sort(rows)


def _record_summaries(
    report: SuiteAttributionReport,
) -> tuple[SuiteAttributionRecordSummary, ...]:
    rows = [
        SuiteAttributionRecordSummary.from_record(
            component=component.component,
            record=record,
        )
        for component in report.components
        for record in component.contributions
    ]
    rows.append(
        SuiteAttributionRecordSummary.from_record(component="suite", record=report.suite_residual)
    )
    return tuple(rows)


def _group_records(
    rows: tuple[SuiteAttributionRecordSummary, ...],
    *,
    key_name: str,
) -> tuple[SuiteAttributionGroupSummary, ...]:
    if key_name not in {"component", "source_level"}:
        raise OrchestrationInputError(
            "key_name must be component or source_level",
            field="key_name",
        )
    by_key: dict[str, list[SuiteAttributionRecordSummary]] = {}
    for row in rows:
        key = row.component if key_name == "component" else row.source_level
        by_key.setdefault(key, []).append(row)

    groups = tuple(_build_group_summary(key, tuple(value)) for key, value in by_key.items())
    return tuple(
        sorted(
            groups,
            key=lambda row: (
                -row.absolute_amount,
                row.group_key,
            ),
        )
    )


def _build_group_summary(
    key: str,
    rows: tuple[SuiteAttributionRecordSummary, ...],
) -> SuiteAttributionGroupSummary:
    contribution = math.fsum(row.contribution or 0.0 for row in rows)
    residual = math.fsum(row.residual for row in rows)
    amount = contribution + residual
    return SuiteAttributionGroupSummary(
        group_key=key,
        record_count=len(rows),
        contribution=contribution,
        residual=residual,
        amount=amount,
        absolute_amount=abs(amount),
        contribution_ids=_unique_ordered(row.contribution_id for row in _stable_record_sort(rows)),
        source_ids=_unique_ordered(row.source_id for row in _stable_record_sort(rows)),
    )


def _stable_record_sort(
    rows: Iterable[SuiteAttributionRecordSummary],
) -> tuple[SuiteAttributionRecordSummary, ...]:
    return tuple(
        sorted(
            rows,
            key=lambda row: (
                -row.absolute_amount,
                row.component,
                row.source_level,
                row.source_id,
                row.contribution_id,
            ),
        )
    )


def _record_amount(record: CapitalContribution) -> float:
    return math.fsum([record.contribution or 0.0, record.residual])


def _unique_ordered(values: Iterable[str]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(values))


__all__ = [
    "SuiteAttributionGroupSummary",
    "SuiteAttributionRecordSummary",
    "SuiteAttributionSummary",
    "suite_attribution_residual_records",
    "suite_attribution_unsupported_records",
    "summarise_suite_attribution",
    "top_suite_attribution_contributors",
]
