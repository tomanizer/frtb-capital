from __future__ import annotations

from datetime import date

import numpy as np
import pytest
from frtb_sbm import (
    SbmCalculationContext,
    SbmInputError,
    SbmPairwiseEvidenceMode,
    SbmRegulatoryProfile,
    SbmRiskClass,
    SbmRiskMeasure,
    SbmRunControls,
    SbmSensitivity,
    SbmSignConvention,
    SbmSourceLineage,
    WeightedSensitivity,
    build_girr_curvature_batch_from_sensitivities,
    calculate_sbm_capital,
    calculate_sbm_capital_from_batch,
)
from frtb_sbm.aggregation import aggregate_intra_bucket


def _weighted(sensitivity_id: str, scaled_amount: float = 100.0) -> WeightedSensitivity:
    return WeightedSensitivity(
        sensitivity_id=sensitivity_id,
        risk_class=SbmRiskClass.GIRR,
        risk_measure=SbmRiskMeasure.DELTA,
        bucket="1",
        raw_amount=scaled_amount,
        risk_weight=1.0,
        scaled_amount=scaled_amount,
        citation_ids=("basel_mar21_45_49",),
    )


def _context(
    *,
    run_controls: SbmRunControls | None = None,
) -> SbmCalculationContext:
    return SbmCalculationContext(
        run_id="run-pairwise-evidence",
        calculation_date=date(2026, 5, 30),
        base_currency="USD",
        reporting_currency="USD",
        profile_id=SbmRegulatoryProfile.BASEL_MAR21.value,
        run_controls=run_controls,
    )


def _girr_sensitivities(size: int) -> tuple[SbmSensitivity, ...]:
    return tuple(
        SbmSensitivity(
            sensitivity_id=f"girr-{index:05d}",
            source_row_id=f"row-{index:05d}",
            desk_id="rates-desk",
            legal_entity="LE-001",
            risk_class=SbmRiskClass.GIRR,
            risk_measure=SbmRiskMeasure.DELTA,
            bucket="1",
            risk_factor=f"CURVE-{index:05d}",
            amount=10_000.0 + index,
            amount_currency="USD",
            tenor="5y",
            sign_convention=SbmSignConvention.RECEIVE,
            lineage=SbmSourceLineage(
                source_system="synthetic",
                source_file="pairwise-evidence.csv",
                source_row_id=f"row-{index:05d}",
            ),
        )
        for index in range(size)
    )


def _girr_curvature_sensitivities(size: int) -> tuple[SbmSensitivity, ...]:
    currencies = ("USD", "EUR", "GBP", "JPY", "AUD")
    return tuple(
        SbmSensitivity(
            sensitivity_id=f"girr-curv-{index:05d}",
            source_row_id=f"row-curv-{index:05d}",
            desk_id="rates-desk",
            legal_entity="LE-001",
            risk_class=SbmRiskClass.GIRR,
            risk_measure=SbmRiskMeasure.CURVATURE,
            bucket="1",
            risk_factor=currencies[index % len(currencies)],
            amount=0.0,
            amount_currency="USD",
            tenor="5y",
            sign_convention=SbmSignConvention.RECEIVE,
            lineage=SbmSourceLineage(
                source_system="synthetic",
                source_file="curvature-pairwise-evidence.csv",
                source_row_id=f"row-curv-{index:05d}",
            ),
            up_shock_amount=100.0 + index,
            down_shock_amount=40.0 + index,
        )
        for index in range(size)
    )


def test_default_auto_pairwise_evidence_keeps_small_fixture_detail() -> None:
    result = aggregate_intra_bucket(
        "1",
        (_weighted("a"), _weighted("b")),
        correlation_matrix=np.array(
            [[1.0, 0.4], [0.4, 1.0]],
            dtype=float,
        ),
        risk_class=SbmRiskClass.GIRR,
        risk_measure=SbmRiskMeasure.DELTA,
    )

    assert len(result.pairwise_correlations) == 3
    assert result.pairwise_correlation_summary.evidence_mode is SbmPairwiseEvidenceMode.AUTO
    assert result.pairwise_correlation_summary.total_count == 3
    assert result.pairwise_correlation_summary.materialized_count == 3
    assert result.pairwise_correlation_summary.omitted_count == 0
    assert result.pairwise_correlation_summary.factor_ids == ("a", "b")


def test_summary_pairwise_evidence_mode_omits_materialized_records() -> None:
    result = aggregate_intra_bucket(
        "1",
        (_weighted("a"), _weighted("b")),
        correlation_matrix=np.array(
            [[1.0, 0.4], [0.4, 1.0]],
            dtype=float,
        ),
        risk_class=SbmRiskClass.GIRR,
        risk_measure=SbmRiskMeasure.DELTA,
        pairwise_evidence_mode=SbmPairwiseEvidenceMode.SUMMARY,
    )

    assert result.pairwise_correlations == ()
    assert result.pairwise_correlation_summary.total_count == 3
    assert result.pairwise_correlation_summary.materialized_count == 0
    assert result.pairwise_correlation_summary.omitted_count == 3
    assert result.pairwise_correlation_summary.factor_ids == ("a", "b")


@pytest.mark.parametrize("limit", ["100", True])
def test_pairwise_evidence_limit_rejects_non_integer_direct_aggregation(limit: object) -> None:
    with pytest.raises(SbmInputError, match="pairwise_evidence_limit") as exc_info:
        aggregate_intra_bucket(
            "1",
            (_weighted("a"), _weighted("b")),
            correlation_matrix=np.array(
                [[1.0, 0.4], [0.4, 1.0]],
                dtype=float,
            ),
            risk_class=SbmRiskClass.GIRR,
            risk_measure=SbmRiskMeasure.DELTA,
            pairwise_evidence_limit=limit,  # type: ignore[arg-type]
        )

    assert exc_info.value.field == "pairwise_evidence_limit"


def test_auto_pairwise_evidence_omits_large_buckets_without_changing_capital() -> None:
    sensitivities = _girr_sensitivities(80)
    auto_result = calculate_sbm_capital(sensitivities, context=_context())
    full_result = calculate_sbm_capital(
        sensitivities,
        context=_context(
            run_controls=SbmRunControls(pairwise_evidence_mode=SbmPairwiseEvidenceMode.FULL)
        ),
    )

    assert auto_result.total_capital == pytest.approx(full_result.total_capital)
    auto_bucket = auto_result.risk_classes[0].scenario_details[0].intra_buckets[0]
    full_bucket = full_result.risk_classes[0].scenario_details[0].intra_buckets[0]
    assert auto_bucket.pairwise_correlations == ()
    assert auto_bucket.pairwise_correlation_summary is not None
    assert auto_bucket.pairwise_correlation_summary.total_count == 3240
    assert auto_bucket.pairwise_correlation_summary.omitted_count == 3240
    assert len(full_bucket.pairwise_correlations) == 3240


def test_curvature_batch_summary_pairwise_evidence_mode_omits_materialized_records() -> None:
    sensitivities = tuple(
        SbmSensitivity(
            sensitivity_id=f"girr-curv-{index:02d}",
            source_row_id=f"row-curv-{index:02d}",
            desk_id="rates-desk",
            legal_entity="LE-001",
            risk_class=SbmRiskClass.GIRR,
            risk_measure=SbmRiskMeasure.CURVATURE,
            bucket="1",
            risk_factor=f"CURVE-{index}",
            amount=0.0,
            amount_currency="USD",
            tenor="5y",
            sign_convention=SbmSignConvention.RECEIVE,
            lineage=SbmSourceLineage(
                source_system="synthetic",
                source_file="pairwise-evidence.csv",
                source_row_id=f"row-curv-{index:02d}",
            ),
            up_shock_amount=-10_000.0 - index,
            down_shock_amount=-12_000.0 - index,
        )
        for index in range(4)
    )
    batch = build_girr_curvature_batch_from_sensitivities(sensitivities)
    result = calculate_sbm_capital_from_batch(
        batch,
        context=_context(
            run_controls=SbmRunControls(pairwise_evidence_mode=SbmPairwiseEvidenceMode.SUMMARY)
        ),
    )

    bucket = result.risk_classes[0].scenario_details[0].intra_buckets[0]
    assert bucket.pairwise_correlations == ()
    assert bucket.pairwise_correlation_summary is not None
    assert bucket.pairwise_correlation_summary.materialized_count == 0
    assert bucket.pairwise_correlation_summary.total_count == 10


def test_serialized_summary_preserves_reconstruction_metadata() -> None:
    result = calculate_sbm_capital(
        _girr_sensitivities(3),
        context=_context(
            run_controls=SbmRunControls(pairwise_evidence_mode=SbmPairwiseEvidenceMode.SUMMARY)
        ),
    )

    risk_class = result.as_dict()["risk_classes"][0]
    detail = risk_class["scenario_details"][0]
    bucket = detail["intra_buckets"][0]
    summary = bucket["pairwise_correlation_summary"]

    assert detail["scenario"] in {"LOW", "MEDIUM", "HIGH"}
    assert bucket["bucket_id"] == "1"
    assert "basel_mar21_45_49" in bucket["citation_ids"]
    assert bucket["pairwise_correlations"] == []
    assert summary == {
        "evidence_mode": "SUMMARY",
        "total_count": 6,
        "materialized_count": 0,
        "omitted_count": 6,
        "factor_ids": ["girr-00000", "girr-00001", "girr-00002"],
    }


def test_curvature_summary_pairwise_evidence_mode_omits_materialized_records() -> None:
    result = calculate_sbm_capital(
        _girr_curvature_sensitivities(3),
        context=_context(
            run_controls=SbmRunControls(pairwise_evidence_mode=SbmPairwiseEvidenceMode.SUMMARY)
        ),
    )

    bucket = result.risk_classes[0].scenario_details[0].intra_buckets[0]

    assert bucket.pairwise_correlations == ()
    assert bucket.pairwise_correlation_summary is not None
    assert bucket.pairwise_correlation_summary.evidence_mode is SbmPairwiseEvidenceMode.SUMMARY
    assert bucket.pairwise_correlation_summary.total_count == 6
    assert bucket.pairwise_correlation_summary.materialized_count == 0
    assert bucket.pairwise_correlation_summary.omitted_count == 6


def test_curvature_full_pairwise_evidence_mode_preserves_materialized_records() -> None:
    result = calculate_sbm_capital(
        _girr_curvature_sensitivities(3),
        context=_context(
            run_controls=SbmRunControls(pairwise_evidence_mode=SbmPairwiseEvidenceMode.FULL)
        ),
    )

    bucket = result.risk_classes[0].scenario_details[0].intra_buckets[0]

    assert len(bucket.pairwise_correlations) == 6
    assert bucket.pairwise_correlation_summary is not None
    assert bucket.pairwise_correlation_summary.evidence_mode is SbmPairwiseEvidenceMode.FULL
    assert bucket.pairwise_correlation_summary.materialized_count == 6
