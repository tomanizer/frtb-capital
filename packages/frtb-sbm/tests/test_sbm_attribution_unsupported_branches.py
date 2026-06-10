"""Focused tests for unsupported SBM attribution branches."""

from __future__ import annotations

from dataclasses import replace

import pytest
from frtb_common.attribution import (
    AttributionMethod,
    CapitalContribution,
    ReconciliationStatus,
)
from frtb_sbm import (
    BucketCapital,
    IntraBucketScenarioRecord,
    PairwiseCorrelationRecord,
    PairwiseCorrelationSummary,
    RiskClassCapital,
    RiskClassScenarioDetail,
    SbmCapitalResult,
    SbmPairwiseEvidenceMode,
    SbmRiskClass,
    SbmRiskMeasure,
    SbmScenarioLabel,
    WeightedSensitivity,
)
from frtb_sbm.attribution import (
    calculate_sbm_attribution,
    summarize_sbm_attribution_by_bucket,
    summarize_sbm_attribution_by_risk_class,
    summarize_sbm_attribution_by_sensitivity,
)


def test_curvature_branch_reports_unsupported_residual() -> None:
    record = _unsupported_record(
        _risk_class(risk_measure=SbmRiskMeasure.CURVATURE),
    )

    _assert_unsupported(record, reason_contains="Curvature capital")
    assert "MAR21.5" in record.reason


def test_missing_scenario_detail_reports_unsupported_residual() -> None:
    record = _unsupported_record(
        _risk_class(
            selected_scenario=None,
            scenario_details=(),
        ),
    )

    _assert_unsupported(record, reason_contains="No scenario detail retained")


def test_missing_selected_scenario_record_reports_unsupported_residual() -> None:
    record = _unsupported_record(
        _risk_class(
            selected_scenario=SbmScenarioLabel.HIGH,
            scenario_details=(_scenario_detail(),),
        ),
    )

    _assert_unsupported(
        record,
        reason_contains="Scenario detail not found for selected scenario HIGH",
    )


def test_alternative_sb_branch_reports_unsupported_residual() -> None:
    record = _unsupported_record(
        _risk_class(
            scenario_details=(replace(_scenario_detail(), alternative_sb_used=True),),
        ),
    )

    _assert_unsupported(record, reason_contains="Alternative S_b specification")
    assert "MAR21.4(5)(b)" in record.reason


def test_omitted_pairwise_evidence_reports_unsupported_residual() -> None:
    summary = PairwiseCorrelationSummary(
        evidence_mode=SbmPairwiseEvidenceMode.SUMMARY,
        total_count=3,
        materialized_count=1,
        omitted_count=2,
        factor_ids=("s-1", "s-2"),
    )
    record = _unsupported_record(
        _risk_class(
            scenario_details=(
                _scenario_detail(
                    intra_buckets=(
                        replace(
                            _intra_bucket(),
                            pairwise_correlation_summary=summary,
                        ),
                    ),
                ),
            ),
        ),
    )

    _assert_unsupported(record, reason_contains="Pairwise correlations not fully")
    assert "2 of 3 pairs omitted" in record.reason
    assert "pairwise_evidence_limit" in record.reason


def test_active_floor_reports_unsupported_residual() -> None:
    record = _unsupported_record(
        _risk_class(
            buckets=(replace(_bucket(), floor_applied=True),),
        ),
    )

    _assert_unsupported(record, reason_contains="Floor active in bucket '1'")
    assert "Euler derivative undefined" in record.reason


def test_missing_intra_bucket_detail_reports_unsupported_residual() -> None:
    record = _unsupported_record(
        _risk_class(scenario_details=(_scenario_detail(intra_buckets=()),)),
    )

    _assert_unsupported(record, reason_contains="Intra-bucket detail missing")
    assert record.source_id == "GIRR:DELTA:1"


def test_unsupported_records_remain_visible_in_summary_projections() -> None:
    records = calculate_sbm_attribution(
        _result(
            _risk_class(
                buckets=(replace(_bucket(), floor_applied=True),),
            ),
        ),
    )

    sensitivity = summarize_sbm_attribution_by_sensitivity(records)[0]
    bucket = summarize_sbm_attribution_by_bucket(records)[0]
    risk_class = summarize_sbm_attribution_by_risk_class(records)[0]

    assert sensitivity.key == "GIRR:DELTA"
    assert bucket.key == "UNALLOCATED"
    assert risk_class.key == "GIRR"
    for summary in (sensitivity, bucket, risk_class):
        assert summary.methods == (str(AttributionMethod.UNSUPPORTED),)
        assert summary.residual == pytest.approx(_SELECTED_CAPITAL)
        assert summary.total == pytest.approx(_SELECTED_CAPITAL)
        assert summary.reconciliation_status == ReconciliationStatus.PARTIAL_RESIDUAL
        assert "Floor active in bucket '1'" in summary.reasons[0]


_SELECTED_CAPITAL = 123.0
_CITATIONS = ("basel_mar21_4_intra_bucket",)


def _unsupported_record(rc: RiskClassCapital) -> CapitalContribution:
    records = calculate_sbm_attribution(_result(rc))
    assert len(records) == 1
    return records[0]


def _assert_unsupported(
    record: CapitalContribution,
    *,
    reason_contains: str,
) -> None:
    assert record.method == AttributionMethod.UNSUPPORTED
    assert record.contribution is None
    assert record.residual == pytest.approx(_SELECTED_CAPITAL)
    assert record.reconciliation_status == ReconciliationStatus.PARTIAL_RESIDUAL
    assert reason_contains in record.reason


def _result(rc: RiskClassCapital) -> SbmCapitalResult:
    return SbmCapitalResult(
        total_capital=rc.selected_capital,
        risk_classes=(rc,),
        profile_id="BASEL_MAR21",
        profile_hash="profile-hash",
        input_hash="input-hash",
    )


def _risk_class(
    *,
    risk_measure: SbmRiskMeasure = SbmRiskMeasure.DELTA,
    selected_scenario: SbmScenarioLabel | None = SbmScenarioLabel.MEDIUM,
    buckets: tuple[BucketCapital, ...] | None = None,
    scenario_details: tuple[RiskClassScenarioDetail, ...] | None = None,
) -> RiskClassCapital:
    if buckets is None:
        buckets = (_bucket(risk_measure=risk_measure),)
    if scenario_details is None:
        scenario_details = (_scenario_detail(),)
    return RiskClassCapital(
        risk_class=SbmRiskClass.GIRR,
        risk_measure=risk_measure,
        selected_capital=_SELECTED_CAPITAL,
        buckets=buckets,
        citation_ids=_CITATIONS,
        scenario_totals={SbmScenarioLabel.MEDIUM: _SELECTED_CAPITAL},
        selected_scenario=selected_scenario,
        scenario_details=scenario_details,
    )


def _bucket(
    *,
    bucket_id: str = "1",
    risk_measure: SbmRiskMeasure = SbmRiskMeasure.DELTA,
) -> BucketCapital:
    return BucketCapital(
        bucket_id=bucket_id,
        risk_class=SbmRiskClass.GIRR,
        risk_measure=risk_measure,
        kb=100.0,
        weighted_sensitivities=(_weighted_sensitivity(risk_measure=risk_measure),),
        citation_ids=_CITATIONS,
        scenario=SbmScenarioLabel.MEDIUM,
        sb=100.0,
        floor_applied=False,
    )


def _weighted_sensitivity(
    *,
    risk_measure: SbmRiskMeasure = SbmRiskMeasure.DELTA,
) -> WeightedSensitivity:
    return WeightedSensitivity(
        sensitivity_id="s-1",
        risk_class=SbmRiskClass.GIRR,
        risk_measure=risk_measure,
        bucket="1",
        raw_amount=100.0,
        risk_weight=1.0,
        scaled_amount=100.0,
        citation_ids=_CITATIONS,
    )


def _scenario_detail(
    *,
    intra_buckets: tuple[IntraBucketScenarioRecord, ...] | None = None,
) -> RiskClassScenarioDetail:
    if intra_buckets is None:
        intra_buckets = (_intra_bucket(),)
    return RiskClassScenarioDetail(
        scenario=SbmScenarioLabel.MEDIUM,
        capital=_SELECTED_CAPITAL,
        inter_bucket_correlations=(),
        alternative_sb_used=False,
        intra_buckets=intra_buckets,
        citation_ids=_CITATIONS,
    )


def _intra_bucket() -> IntraBucketScenarioRecord:
    return IntraBucketScenarioRecord(
        bucket_id="1",
        kb=100.0,
        sb=100.0,
        floor_applied=False,
        pairwise_correlations=(
            PairwiseCorrelationRecord(
                sensitivity_a="s-1",
                sensitivity_b="s-1",
                correlation=1.0,
            ),
        ),
        citation_ids=_CITATIONS,
    )
