"""Baseline-vs-candidate impact analysis for DRC capital results."""

from __future__ import annotations

from frtb_common.attribution import ReconciliationStatus
from frtb_common.impact import CapitalImpact, ImpactMethod

from frtb_drc._impact_models import (
    _TOLERANCE,
    DrcImpactAnalysis,
    DrcImpactMethod,
    DrcImpactRecord,
)
from frtb_drc._impact_record_builder import impact_records
from frtb_drc._impact_record_factories import (
    reconciled_delta,
    record_delta_sum,
    residual_record,
)
from frtb_drc.data_models import DrcCapitalResult
from frtb_drc.validation import DrcInputError


def calculate_drc_impact(
    baseline: DrcCapitalResult,
    candidate: DrcCapitalResult,
    *,
    tolerance: float = _TOLERANCE,
) -> DrcImpactAnalysis:
    """Compare two DRC capital results without changing either capital number.

    Parameters
    ----------
    baseline : DrcCapitalResult
        Completed baseline DRC result graph.
    candidate : DrcCapitalResult
        Completed candidate DRC result graph.
    tolerance : float, optional
        Absolute reconciliation tolerance for record sums versus total delta.

    Returns
    -------
    DrcImpactAnalysis
        Total impact record and deterministic DRC branch records.

    Raises
    ------
    DrcInputError
        If the result pair is incompatible or generated records do not reconcile.
    """

    _validate_result_pair(baseline, candidate)
    total_impact = CapitalImpact(
        baseline_run_id=baseline.run_id,
        candidate_run_id=candidate.run_id,
        component="frtb_drc",
        baseline_total=baseline.total_drc,
        candidate_total=candidate.total_drc,
        delta=candidate.total_drc - baseline.total_drc,
        method=ImpactMethod.FINITE_DIFFERENCE,
        baseline_input_hash=baseline.input_hash,
        candidate_input_hash=candidate.input_hash,
        baseline_profile_hash=baseline.profile_hash,
        candidate_profile_hash=candidate.profile_hash,
        notes=_total_notes(baseline, candidate),
    )
    records = impact_records(baseline, candidate)
    residual = total_impact.delta - reconciled_delta(records)
    if abs(residual) > tolerance:
        records = (
            *records,
            residual_record(
                baseline,
                candidate,
                residual=residual,
                reason="residual reconciles explained DRC impact records to total capital delta",
            ),
        )
    analysis = DrcImpactAnalysis(
        total_impact=total_impact,
        records=records,
        residual=total_impact.delta - record_delta_sum(records),
        reconciliation_status=_reconciliation_status(total_impact.delta, records, tolerance),
        tolerance=tolerance,
    )
    validate_drc_impact_reconciliation(analysis)
    return analysis


def validate_drc_impact_reconciliation(
    analysis: DrcImpactAnalysis,
    *,
    tolerance: float | None = None,
) -> None:
    """Validate that DRC impact records reconcile or explicitly state residual impact.

    Parameters
    ----------
    analysis : DrcImpactAnalysis
        Impact analysis to validate.
    tolerance : float | None, optional
        Override reconciliation tolerance. When omitted, ``analysis.tolerance``
        is used.

    Raises
    ------
    DrcInputError
        If records do not reconcile to the total delta or the analysis is marked
        unreconciled.
    """

    limit = analysis.tolerance if tolerance is None else tolerance
    if abs(analysis.delta - record_delta_sum(analysis.records)) > limit:
        raise DrcInputError("DRC impact records do not reconcile to total capital delta")
    if analysis.reconciliation_status is ReconciliationStatus.UNRECONCILED:
        raise DrcInputError("DRC impact analysis is marked unreconciled")


def _reconciliation_status(
    total_delta: float,
    records: tuple[DrcImpactRecord, ...],
    tolerance: float,
) -> ReconciliationStatus:
    if abs(total_delta - record_delta_sum(records)) <= tolerance:
        return ReconciliationStatus.RECONCILED
    return ReconciliationStatus.UNRECONCILED


def _total_notes(baseline: DrcCapitalResult, candidate: DrcCapitalResult) -> tuple[str, ...]:
    notes: list[str] = []
    if baseline.profile_id != candidate.profile_id:
        notes.append("profile_id changed")
    if baseline.profile_hash != candidate.profile_hash:
        notes.append("profile_hash changed")
    if baseline.input_hash != candidate.input_hash:
        notes.append("input_hash changed")
    return tuple(notes)


def _validate_result_pair(baseline: DrcCapitalResult, candidate: DrcCapitalResult) -> None:
    if baseline.package_name != candidate.package_name:
        raise DrcInputError("baseline and candidate DRC results must be from the same package")
    if baseline.base_currency != candidate.base_currency:
        raise DrcInputError("baseline and candidate DRC results must use the same base currency")
    if baseline.calculation_date != candidate.calculation_date:
        raise DrcInputError("baseline and candidate DRC results must use the same calculation date")


__all__ = [
    "DrcImpactAnalysis",
    "DrcImpactMethod",
    "DrcImpactRecord",
    "calculate_drc_impact",
    "validate_drc_impact_reconciliation",
]
