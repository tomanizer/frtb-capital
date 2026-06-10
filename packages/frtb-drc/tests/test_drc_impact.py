from __future__ import annotations

from dataclasses import replace
from datetime import date

import pytest
from frtb_common.attribution import ReconciliationStatus
from frtb_drc.data_models import (
    BranchMetadata,
    BranchType,
    BucketDrc,
    CategoryDrc,
    DrcCapitalResult,
    DrcRiskClass,
    HedgeBenefitRatio,
)
from frtb_drc.impact import (
    DrcImpactMethod,
    calculate_drc_impact,
    validate_drc_impact_reconciliation,
)
from frtb_drc.regimes import US_NPR_2_0_PROFILE_ID
from frtb_drc.validation import DrcInputError


def test_stable_bucket_impact_reconciles_to_run_delta() -> None:
    baseline = _result(run_id="baseline", bucket_capital=10.0, total_drc=10.0)
    candidate = _result(run_id="candidate", bucket_capital=14.0, total_drc=14.0)

    analysis = calculate_drc_impact(baseline, candidate)

    assert analysis.run_impact.delta == pytest.approx(4.0)
    assert analysis.residual == pytest.approx(0.0)
    assert analysis.reconciliation_status is ReconciliationStatus.RECONCILED
    assert len(analysis.records) == 1
    record = analysis.records[0]
    assert record.method is DrcImpactMethod.FINITE_DIFFERENCE
    assert record.source_level == "bucket"
    assert record.bucket_key == "CORPORATE"
    assert record.baseline_amount == pytest.approx(10.0)
    assert record.candidate_amount == pytest.approx(14.0)
    assert record.delta == pytest.approx(4.0)
    assert record.baseline_input_hash == baseline.input_hash
    assert record.candidate_input_hash == candidate.input_hash
    validate_drc_impact_reconciliation(analysis)


def test_profile_change_reports_unsupported_result_impact() -> None:
    baseline = _result(run_id="baseline", bucket_capital=10.0, total_drc=10.0)
    candidate = replace(
        _result(run_id="candidate", bucket_capital=14.0, total_drc=14.0),
        profile_id="BASEL_MAR22",
        profile_hash="candidate-profile-hash",
    )

    analysis = calculate_drc_impact(baseline, candidate)

    assert len(analysis.records) == 1
    record = analysis.records[0]
    assert record.method is DrcImpactMethod.UNSUPPORTED
    assert record.source_level == "result"
    assert record.delta == pytest.approx(4.0)
    assert "profile changed" in record.reason
    assert analysis.reconciliation_status is ReconciliationStatus.PARTIAL_RESIDUAL
    validate_drc_impact_reconciliation(analysis)


def test_floor_branch_reports_unsupported_bucket_impact() -> None:
    baseline = _result(run_id="baseline", bucket_capital=10.0, total_drc=10.0)
    candidate_bucket = replace(
        _bucket(capital=14.0),
        floor_applied=True,
        branch_metadata=(
            BranchMetadata(
                branch_id="branch-floor",
                branch_type=BranchType.FLOOR,
                source_id="bucket-corporate",
                selected=True,
                reason="floor selected",
                citations=("US_NPR_210_2",),
            ),
        ),
    )
    candidate = _result(
        run_id="candidate",
        bucket_capital=14.0,
        total_drc=14.0,
        category=_category(candidate_bucket, capital=14.0),
    )

    analysis = calculate_drc_impact(baseline, candidate)

    assert len(analysis.records) == 1
    record = analysis.records[0]
    assert record.method is DrcImpactMethod.UNSUPPORTED
    assert record.delta == pytest.approx(4.0)
    assert "floor or unsupported branch" in record.reason
    assert "US_NPR_210_2" in record.citations
    assert record.reconciliation_status is ReconciliationStatus.PARTIAL_RESIDUAL


def test_bucket_move_reports_unsupported_impact_records() -> None:
    baseline = _result(run_id="baseline", bucket_capital=10.0, total_drc=10.0)
    moved_bucket = replace(_bucket(bucket_key="SOVEREIGN", capital=14.0), bucket_id="bucket-corporate")
    candidate = _result(
        run_id="candidate",
        bucket_capital=14.0,
        total_drc=14.0,
        category=_category(moved_bucket, capital=14.0),
    )

    analysis = calculate_drc_impact(baseline, candidate)

    assert [record.method for record in analysis.records] == [
        DrcImpactMethod.UNSUPPORTED,
        DrcImpactMethod.UNSUPPORTED,
    ]
    assert sum(record.delta for record in analysis.records) == pytest.approx(4.0)
    assert all("bucket/category move" in record.reason for record in analysis.records)
    validate_drc_impact_reconciliation(analysis)


def test_category_residual_record_reconciles_total_delta() -> None:
    baseline = _result(run_id="baseline", bucket_capital=10.0, total_drc=10.0)
    candidate = _result(run_id="candidate", bucket_capital=14.0, total_drc=20.0)

    analysis = calculate_drc_impact(baseline, candidate)

    assert [record.method for record in analysis.records] == [
        DrcImpactMethod.FINITE_DIFFERENCE,
        DrcImpactMethod.RESIDUAL,
    ]
    assert analysis.records[0].delta == pytest.approx(4.0)
    assert analysis.records[1].delta == pytest.approx(6.0)
    assert analysis.records[1].source_level == "result"
    assert analysis.reconciliation_status is ReconciliationStatus.PARTIAL_RESIDUAL
    validate_drc_impact_reconciliation(analysis)


def test_validation_rejects_tampered_impact_records() -> None:
    baseline = _result(run_id="baseline", bucket_capital=10.0, total_drc=10.0)
    candidate = _result(run_id="candidate", bucket_capital=14.0, total_drc=14.0)
    analysis = calculate_drc_impact(baseline, candidate)
    tampered = replace(
        analysis,
        records=(replace(analysis.records[0], candidate_amount=15.0, delta=5.0),),
    )

    with pytest.raises(DrcInputError, match="impact records do not reconcile"):
        validate_drc_impact_reconciliation(tampered)


def _result(
    *,
    run_id: str,
    bucket_capital: float,
    total_drc: float,
    category: CategoryDrc | None = None,
) -> DrcCapitalResult:
    if category is None:
        category = _category(_bucket(capital=bucket_capital), capital=total_drc)
    return DrcCapitalResult(
        result_id=f"result-{run_id}",
        run_id=run_id,
        calculation_date=date(2026, 5, 29),
        base_currency="USD",
        profile_id=US_NPR_2_0_PROFILE_ID,
        profile_hash=f"profile-hash-{run_id}",
        input_hash=f"input-hash-{run_id}",
        categories=(category,),
        total_drc=total_drc,
        citations=("US_NPR_210_SCOPE",),
    )


def _category(bucket: BucketDrc, *, capital: float) -> CategoryDrc:
    return CategoryDrc(
        category_id="category-nonsec",
        risk_class=DrcRiskClass.NON_SECURITISATION,
        bucket_results=(bucket,),
        capital=capital,
    )


def _bucket(
    *,
    bucket_key: str = "CORPORATE",
    capital: float,
) -> BucketDrc:
    return BucketDrc(
        bucket_id="bucket-corporate",
        bucket_key=bucket_key,
        risk_class=DrcRiskClass.NON_SECURITISATION,
        hbr=HedgeBenefitRatio(
            hbr_id=f"hbr-{bucket_key.lower()}",
            bucket_key=bucket_key,
            aggregate_net_long=capital,
            aggregate_net_short=0.0,
            denominator=capital,
            ratio=1.0,
            citations=("US_NPR_210_2",),
        ),
        weighted_long=capital,
        weighted_short=0.0,
        capital=capital,
        floor_applied=False,
        net_jtd_ids=(),
        citations=("US_NPR_210_2",),
    )
