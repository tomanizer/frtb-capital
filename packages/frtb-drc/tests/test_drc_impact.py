from __future__ import annotations

import json
from dataclasses import replace
from datetime import date

import pytest
from frtb_common.attribution import ReconciliationStatus
from frtb_common.impact import ImpactMethod
from frtb_drc import (
    US_NPR_2_0_PROFILE_ID,
    BranchMetadata,
    BranchType,
    CreditQuality,
    DefaultDirection,
    DrcCalculationContext,
    DrcCapitalResult,
    DrcImpactMethod,
    DrcInputError,
    DrcInstrumentType,
    DrcPosition,
    DrcRiskClass,
    DrcSeniority,
    DrcSourceLineage,
    calculate_drc_capital,
    calculate_drc_impact,
    validate_drc_impact_reconciliation,
)


def test_drc_impact_reconciles_stable_bucket_branch_without_changing_capital() -> None:
    baseline = calculate_drc_capital(
        (_nonsec_position("stable", DefaultDirection.LONG, 100.0, issuer_id="issuer-stable"),),
        context=_context("run-baseline"),
    )
    candidate = calculate_drc_capital(
        (_nonsec_position("stable", DefaultDirection.LONG, 120.0, issuer_id="issuer-stable"),),
        context=_context("run-candidate"),
    )
    baseline_total = baseline.total_drc
    candidate_total = candidate.total_drc

    analysis = calculate_drc_impact(baseline, candidate)

    assert baseline.total_drc == baseline_total
    assert candidate.total_drc == candidate_total
    assert analysis.total_impact.method is ImpactMethod.FINITE_DIFFERENCE
    assert analysis.delta == pytest.approx(candidate.total_drc - baseline.total_drc)
    assert analysis.reconciliation_status is ReconciliationStatus.RECONCILED
    assert analysis.residual == pytest.approx(0.0)
    assert {record.method for record in analysis.records} == {DrcImpactMethod.FINITE_DIFFERENCE}
    assert analysis.records[0].source_level == "bucket"
    assert analysis.records[0].baseline_bucket_key == "CORPORATE"
    validate_drc_impact_reconciliation(analysis)


def test_drc_impact_emits_residual_for_floor_branch() -> None:
    baseline = _with_floor_branch(
        calculate_drc_capital(
            (
                _nonsec_position(
                    "floor-branch",
                    DefaultDirection.LONG,
                    100.0,
                    issuer_id="issuer-floor",
                ),
            ),
            context=_context("run-baseline-floor"),
        )
    )
    candidate = _with_floor_branch(
        calculate_drc_capital(
            (
                _nonsec_position(
                    "floor-branch",
                    DefaultDirection.LONG,
                    120.0,
                    issuer_id="issuer-floor",
                ),
            ),
            context=_context("run-candidate-floor"),
        )
    )

    analysis = calculate_drc_impact(baseline, candidate)

    unsupported = [
        record for record in analysis.records if record.method is DrcImpactMethod.UNSUPPORTED
    ]
    residual = [record for record in analysis.records if record.method is DrcImpactMethod.RESIDUAL]
    assert unsupported
    assert "floor" in unsupported[0].reason
    assert any(branch.branch_type is BranchType.FLOOR for branch in unsupported[0].branch_metadata)
    assert len(residual) == 1
    assert residual[0].delta == pytest.approx(analysis.delta)
    validate_drc_impact_reconciliation(analysis)


def test_drc_impact_reports_profile_and_bucket_moves_as_unsupported_metadata() -> None:
    baseline = calculate_drc_capital(
        (_nonsec_position("mover", DefaultDirection.LONG, 100.0, issuer_id="issuer-mover"),),
        context=_context("run-baseline-move"),
    )
    candidate = replace(
        calculate_drc_capital(
            (_nonsec_position("mover", DefaultDirection.LONG, 100.0, issuer_id="issuer-mover"),),
            context=_context("run-candidate-move"),
        ),
        profile_id="candidate-profile",
        profile_hash="candidate-profile-hash",
        input_positions=(
            _nonsec_position(
                "mover",
                DefaultDirection.LONG,
                100.0,
                issuer_id="issuer-mover",
                bucket_key="SOVEREIGN",
            ),
        ),
    )

    analysis = calculate_drc_impact(baseline, candidate)

    unsupported = [
        record for record in analysis.records if record.method is DrcImpactMethod.UNSUPPORTED
    ]
    assert {record.metadata.get("impact_class") for record in unsupported} >= {
        "profile_change",
        "position_move",
    }
    move = next(
        record for record in unsupported if record.metadata.get("impact_class") == "position_move"
    )
    assert move.baseline_bucket_key == "CORPORATE"
    assert move.candidate_bucket_key == "SOVEREIGN"
    assert "profile_hash changed" in analysis.total_impact.notes
    validate_drc_impact_reconciliation(analysis)


def test_drc_impact_reports_category_move_and_serializes_metadata() -> None:
    branch = BranchMetadata(
        branch_id="branch-category-unsupported",
        branch_type=BranchType.UNSUPPORTED_FEATURE,
        source_id="category-nonsec",
        selected=True,
        reason="unit-test unsupported category move",
    )
    baseline = calculate_drc_capital(
        (_nonsec_position("category-mover", DefaultDirection.LONG, 100.0, issuer_id="issuer-cat"),),
        context=_context("run-baseline-category"),
    )
    candidate = replace(
        baseline,
        run_id="run-candidate-category",
        input_hash="candidate-input-hash",
        categories=(
            replace(
                baseline.categories[0],
                risk_class=DrcRiskClass.CORRELATION_TRADING_PORTFOLIO,
                branch_metadata=(branch,),
            ),
        ),
    )

    analysis = calculate_drc_impact(baseline, candidate)
    payload = analysis.as_dict()

    assert analysis.records[0].method is DrcImpactMethod.UNSUPPORTED
    assert analysis.records[0].baseline_category == "NON_SECURITISATION"
    assert analysis.records[0].candidate_category == "CORRELATION_TRADING_PORTFOLIO"
    assert branch in analysis.records[0].branch_metadata
    json.dumps(payload, sort_keys=True)


def test_drc_impact_rejects_incompatible_result_pairs() -> None:
    baseline = calculate_drc_capital(
        (_nonsec_position("currency", DefaultDirection.LONG, 100.0, issuer_id="issuer-currency"),),
        context=_context("run-baseline-currency"),
    )
    candidate = replace(baseline, run_id="run-candidate-currency", base_currency="EUR")

    with pytest.raises(DrcInputError, match="same base currency"):
        calculate_drc_impact(baseline, candidate)


def _context(
    run_id: str,
) -> DrcCalculationContext:
    return DrcCalculationContext(
        run_id=run_id,
        calculation_date=date(2026, 5, 29),
        base_currency="USD",
        profile_id=US_NPR_2_0_PROFILE_ID,
    )


def _nonsec_position(
    position_id: str,
    direction: DefaultDirection,
    notional: float,
    *,
    issuer_id: str,
    bucket_key: str = "CORPORATE",
) -> DrcPosition:
    return DrcPosition(
        position_id=position_id,
        source_row_id=f"row-{position_id}",
        desk_id="desk-a",
        legal_entity="bank-na",
        risk_class=DrcRiskClass.NON_SECURITISATION,
        instrument_type=DrcInstrumentType.BOND,
        default_direction=direction,
        issuer_id=issuer_id,
        tranche_id=None,
        index_series_id=None,
        bucket_key=bucket_key,
        seniority=DrcSeniority.SENIOR_DEBT,
        credit_quality=CreditQuality.INVESTMENT_GRADE,
        notional=notional,
        market_value=notional,
        cumulative_pnl=0.0,
        maturity_years=1.0,
        currency="USD",
        lineage=_lineage(position_id, source_file="nonsec.csv"),
        citation_ids=("US_NPR_210_SCOPE",),
    )


def _with_floor_branch(result: DrcCapitalResult) -> DrcCapitalResult:
    branch = BranchMetadata(
        branch_id="branch-test-floor",
        branch_type=BranchType.FLOOR,
        source_id="bucket-corporate",
        selected=True,
        reason="unit-test floor branch",
    )
    category = result.categories[0]
    bucket = category.bucket_results[0]
    updated_bucket = replace(
        bucket,
        floor_applied=True,
        branch_metadata=(*bucket.branch_metadata, branch),
    )
    return replace(
        result,
        categories=(replace(category, bucket_results=(updated_bucket,)),),
    )


def _lineage(position_id: str, *, source_file: str) -> DrcSourceLineage:
    return DrcSourceLineage(
        source_system="unit-test",
        source_file=source_file,
        source_row_id=f"row-{position_id}",
    )
