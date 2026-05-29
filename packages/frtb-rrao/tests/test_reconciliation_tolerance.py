from __future__ import annotations

import math
from dataclasses import replace
from datetime import date

import pytest
from frtb_rrao import (
    RraoAllocationDimension,
    RraoCapitalLine,
    RraoCapitalResult,
    RraoClassification,
    RraoEvidenceType,
    RraoExclusionReason,
    RraoInputError,
    build_rrao_allocation_report,
    validate_rrao_allocation_report,
    validate_rrao_result_reconciliation,
)
from frtb_rrao.capital import build_rrao_subtotals
from frtb_rrao.numeric import (
    RRAO_RECONCILIATION_ABS_TOLERANCE,
    RRAO_RECONCILIATION_REL_TOLERANCE,
)

VALID_HASH = "0" * 64


def included_line(index: int, add_on: float) -> RraoCapitalLine:
    return RraoCapitalLine(
        position_id=f"pos-{index:05d}",
        classification=RraoClassification.OTHER_RESIDUAL_RISK,
        evidence_type=RraoEvidenceType.GAP_RISK,
        gross_effective_notional=1.0,
        risk_weight=1.0 / 3.0,
        add_on=add_on,
        currency="USD",
        is_excluded=False,
        reason_code="SIMULATED_NON_EXACT_WEIGHT",
        citations=("simulated_tolerance_regression",),
        desk_id="desk-a",
        legal_entity="LE-001",
        source_row_id=f"row-{index:05d}",
    )


def excluded_line(add_on: float) -> RraoCapitalLine:
    return RraoCapitalLine(
        position_id="excluded-001",
        classification=RraoClassification.EXCLUDED,
        evidence_type=RraoEvidenceType.EXPLICIT_EXCLUSION,
        gross_effective_notional=1.0,
        risk_weight=0.0,
        add_on=add_on,
        currency="USD",
        is_excluded=True,
        reason_code="SIMULATED_EXCLUSION",
        citations=("simulated_tolerance_regression",),
        desk_id="desk-a",
        legal_entity="LE-001",
        source_row_id="row-excluded-001",
        exclusion_reason=RraoExclusionReason.LISTED,
        exclusion_evidence_id="exchange-listing-001",
    )


def result_for_lines(
    lines: tuple[RraoCapitalLine, ...],
    *,
    total_rrao: float,
) -> RraoCapitalResult:
    return RraoCapitalResult(
        run_id="tolerance-regression",
        calculation_date=date(2026, 3, 31),
        base_currency="USD",
        profile_id="SIMULATED",
        profile_hash=VALID_HASH,
        input_hash=VALID_HASH,
        lines=tuple(line for line in lines if not line.is_excluded),
        excluded_lines=tuple(line for line in lines if line.is_excluded),
        subtotals=build_rrao_subtotals(lines),
        total_rrao=total_rrao,
        citations=("simulated_tolerance_regression",),
    )


def test_reconciliation_uses_relative_tolerance_for_accumulated_float_error() -> None:
    add_ons = [1.0 / 3.0] * 20_000
    lines = tuple(included_line(index, add_on) for index, add_on in enumerate(add_ons))
    base_total = sum(add_ons)
    relative_only_delta = RRAO_RECONCILIATION_ABS_TOLERANCE * 5

    assert relative_only_delta > RRAO_RECONCILIATION_ABS_TOLERANCE
    assert relative_only_delta < RRAO_RECONCILIATION_REL_TOLERANCE * base_total

    validate_rrao_result_reconciliation(
        result_for_lines(lines, total_rrao=base_total + relative_only_delta)
    )


def test_reconciliation_rejects_difference_outside_documented_budget() -> None:
    lines = (included_line(1, 1.0 / 3.0),)

    with pytest.raises(RraoInputError, match="total RRAO does not reconcile"):
        validate_rrao_result_reconciliation(result_for_lines(lines, total_rrao=1.0))


def test_excluded_line_zero_invariant_uses_documented_tolerance() -> None:
    validate_rrao_result_reconciliation(result_for_lines((excluded_line(5e-13),), total_rrao=0.0))

    with pytest.raises(RraoInputError, match="excluded line add-on must be zero"):
        validate_rrao_result_reconciliation(
            result_for_lines((excluded_line(5e-11),), total_rrao=0.0)
        )


def test_allocation_reconciliation_uses_shared_tolerance_budget() -> None:
    add_ons = [1.0 / 3.0] * 20_000
    lines = tuple(included_line(index, add_on) for index, add_on in enumerate(add_ons))
    result = result_for_lines(lines, total_rrao=sum(add_ons))
    report = build_rrao_allocation_report(result, RraoAllocationDimension.LEGAL_ENTITY)
    perturbed = replace(
        report,
        total_rrao=math.fsum(add_ons),
        allocated_rrao=math.fsum(add_ons),
    )

    validate_rrao_allocation_report(perturbed)
