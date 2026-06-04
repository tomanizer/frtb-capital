"""RRAO contribution projection helpers.

These helpers consume completed RRAO results or allocation reports and project
them to the shared ``frtb_common.CapitalContribution`` contract. They do not
recalculate or alter RRAO capital.
"""

from __future__ import annotations

from collections.abc import Iterable

from frtb_common.attribution import AttributionMethod, CapitalContribution, ReconciliationStatus
from frtb_common.contribution_bundle import ComponentContributionBundle

from frtb_rrao.allocation import (
    build_rrao_allocation_report,
    validate_rrao_allocation_report,
)
from frtb_rrao.audit import validate_rrao_result_reconciliation
from frtb_rrao.data_models import (
    RraoAllocationBucket,
    RraoAllocationDimension,
    RraoAllocationReport,
    RraoCapitalLine,
    RraoCapitalResult,
)
from frtb_rrao.numeric import is_reconciled
from frtb_rrao.validation import RraoInputError

_COMPONENT_NAME = "frtb_rrao"
_STANDALONE_REASON = (
    "RRAO additive line add-on projected as standalone contribution; not analytical Euler."
)


def calculate_rrao_attribution(
    result: RraoCapitalResult,
    dimension: RraoAllocationDimension | str = RraoAllocationDimension.LINE,
) -> tuple[CapitalContribution, ...]:
    """Project a completed RRAO result to shared contribution records.

    ``dimension`` follows the same supported values and aliases as
    ``build_rrao_allocation_report``. The default line view is the canonical
    bundle view because it preserves the result's line-level source ids.
    """

    if not isinstance(result, RraoCapitalResult):
        raise RraoInputError("result must be RraoCapitalResult", field="result")

    validate_rrao_result_reconciliation(result)
    report = build_rrao_allocation_report(result, dimension)
    line_lookup = _line_lookup(result.lines + result.excluded_lines)
    return rrao_allocation_report_to_contributions(
        report,
        profile_hash=result.profile_hash,
        citations=result.citations,
        line_lookup=line_lookup,
    )


def rrao_allocation_report_to_contributions(
    report: RraoAllocationReport,
    *,
    profile_hash: str = "",
    citations: Iterable[str] = (),
    line_lookup: dict[str, RraoCapitalLine] | None = None,
) -> tuple[CapitalContribution, ...]:
    """Project an RRAO allocation report to shared contribution records.

    ``line_lookup`` is optional so serialized reports can be projected directly.
    When supplied, line-level citations and classifications are preserved on the
    emitted records.
    """

    validate_rrao_allocation_report(report)
    contribution_citations = tuple(citations)
    records = tuple(
        _bucket_to_contribution(
            report=report,
            bucket=bucket,
            profile_hash=profile_hash,
            citations=contribution_citations,
            line_lookup=line_lookup,
        )
        for bucket in report.buckets
    )
    _validate_contribution_total(records, report.total_rrao)
    return records


def build_rrao_contribution_bundle(result: RraoCapitalResult) -> ComponentContributionBundle:
    """Return the canonical RRAO component contribution bundle."""

    if not isinstance(result, RraoCapitalResult):
        raise RraoInputError("result must be RraoCapitalResult", field="result")

    contributions = calculate_rrao_attribution(result, RraoAllocationDimension.LINE)
    _validate_contribution_total(contributions, result.total_rrao)
    try:
        return ComponentContributionBundle(
            component=_COMPONENT_NAME,
            contributions=contributions,
            component_total=result.total_rrao,
            component_input_hash=result.input_hash,
            component_profile_hash=result.profile_hash,
        )
    except ValueError as exc:
        raise RraoInputError(str(exc), field="component_total") from exc


def _bucket_to_contribution(
    *,
    report: RraoAllocationReport,
    bucket: RraoAllocationBucket,
    profile_hash: str,
    citations: tuple[str, ...],
    line_lookup: dict[str, RraoCapitalLine] | None,
) -> CapitalContribution:
    bucket_lines = _bucket_lines(bucket, line_lookup)
    line_citations = tuple(citation for line in bucket_lines for citation in line.citations)
    record_citations = _dedupe(citations + line_citations)
    category = _category_for_bucket(report.dimension, bucket, bucket_lines)

    return CapitalContribution(
        contribution_id=f"rrao:{report.run_id}:{report.dimension.value}:{bucket.bucket_key}",
        source_id=_source_id_for_bucket(report.dimension, bucket),
        source_level=_source_level(report.dimension),
        bucket_key=None if report.dimension is RraoAllocationDimension.LINE else bucket.bucket_key,
        category=category,
        base_amount=bucket.gross_effective_notional,
        marginal_multiplier=None,
        contribution=bucket.add_on,
        method=AttributionMethod.STANDALONE,
        residual=0.0,
        reason=_STANDALONE_REASON,
        citations=record_citations,
        input_hash=report.input_hash,
        profile_hash=profile_hash,
        reconciliation_status=ReconciliationStatus.RECONCILED,
    )


def _validate_contribution_total(
    records: tuple[CapitalContribution, ...],
    total_rrao: float,
) -> None:
    contribution_total = sum((record.contribution or 0.0) + record.residual for record in records)
    if not is_reconciled(contribution_total, total_rrao):
        raise RraoInputError(
            "RRAO contribution records do not reconcile to total RRAO",
            field="total_rrao",
        )


def _line_lookup(lines: tuple[RraoCapitalLine, ...]) -> dict[str, RraoCapitalLine]:
    return {line.position_id: line for line in lines}


def _bucket_lines(
    bucket: RraoAllocationBucket,
    line_lookup: dict[str, RraoCapitalLine] | None,
) -> tuple[RraoCapitalLine, ...]:
    if line_lookup is None:
        return ()

    lines: list[RraoCapitalLine] = []
    for position_id in bucket.position_ids:
        line = line_lookup.get(position_id)
        if line is None:
            raise RraoInputError(
                f"position id {position_id!r} from bucket {bucket.bucket_key!r} "
                "was not found in result lines",
                field="position_ids",
            )
        lines.append(line)
    return tuple(lines)


def _source_id_for_bucket(
    dimension: RraoAllocationDimension,
    bucket: RraoAllocationBucket,
) -> str:
    if dimension is RraoAllocationDimension.LINE:
        if not bucket.position_ids:
            raise RraoInputError(
                f"line-level allocation bucket {bucket.bucket_key!r} has no position ids",
                field="position_ids",
            )
        return bucket.position_ids[0]
    return bucket.bucket_key


def _source_level(dimension: RraoAllocationDimension) -> str:
    if dimension is RraoAllocationDimension.DESK:
        return "desk"
    return dimension.value


def _category_for_bucket(
    dimension: RraoAllocationDimension,
    bucket: RraoAllocationBucket,
    lines: tuple[RraoCapitalLine, ...],
) -> str:
    if dimension is RraoAllocationDimension.LINE and len(lines) == 1:
        return lines[0].classification.value
    if dimension is RraoAllocationDimension.EVIDENCE_TYPE:
        return bucket.bucket_key
    return "RRAO"


def _dedupe(values: tuple[str, ...]) -> tuple[str, ...]:
    seen: set[str] = set()
    deduped: list[str] = []
    for value in values:
        if value and value not in seen:
            seen.add(value)
            deduped.append(value)
    return tuple(deduped)


__all__ = [
    "build_rrao_contribution_bundle",
    "calculate_rrao_attribution",
    "rrao_allocation_report_to_contributions",
]
