from __future__ import annotations

import pytest
from frtb_common.attribution import AttributionMethod, CapitalContribution, ReconciliationStatus
from frtb_sbm.attribution import (
    SbmAttributionGrain,
    SbmAttributionSummary,
    summarize_sbm_attribution,
    summarize_sbm_attribution_by_bucket,
    summarize_sbm_attribution_by_risk_class,
    summarize_sbm_attribution_by_sensitivity,
    top_sbm_attribution_summaries,
)


def test_sensitivity_summaries_keep_positive_negative_zero_residual_and_unsupported() -> None:
    records = _records()

    summaries = summarize_sbm_attribution_by_sensitivity(records)
    by_key = _by_key(summaries)

    assert _keys(summaries) == [
        "s-positive",
        "FX:CURVATURE",
        "s-negative",
        "GIRR:DELTA",
        "s-zero",
    ]
    positive = by_key["s-positive"]
    assert positive.grain is SbmAttributionGrain.SENSITIVITY
    assert positive.risk_class == "GIRR"
    assert positive.bucket_key == "1"
    assert positive.contribution == pytest.approx(12.0)
    assert positive.residual == 0.0
    assert positive.total == pytest.approx(12.0)
    assert positive.sensitivity_ids == ("s-positive",)
    assert positive.source_ids == ("s-positive",)
    assert positive.methods == (str(AttributionMethod.ANALYTICAL_EULER),)
    assert positive.reconciliation_status is ReconciliationStatus.RECONCILED

    unsupported = by_key["FX:CURVATURE"]
    assert unsupported.contribution == 0.0
    assert unsupported.residual == pytest.approx(7.0)
    assert unsupported.total == pytest.approx(7.0)
    assert unsupported.sensitivity_ids == ()
    assert unsupported.reasons == ("curvature attribution unsupported",)
    assert unsupported.reconciliation_status is ReconciliationStatus.PARTIAL_RESIDUAL

    zero = by_key["s-zero"]
    assert zero.total == 0.0
    assert zero.record_count == 1


def test_bucket_and_risk_class_summaries_reconcile_to_source_records() -> None:
    records = _records()

    bucket_summaries = summarize_sbm_attribution_by_bucket(records)
    risk_class_summaries = summarize_sbm_attribution_by_risk_class(records)

    assert _total(bucket_summaries) == pytest.approx(_record_total(records))
    assert _record_count(bucket_summaries) == len(records)
    assert _total(risk_class_summaries) == pytest.approx(_record_total(records))
    assert _record_count(risk_class_summaries) == len(records)

    buckets = _by_key(bucket_summaries)
    assert _keys(bucket_summaries) == ["UNALLOCATED", "1", "2"]
    assert buckets["UNALLOCATED"].residual == pytest.approx(9.0)
    assert buckets["UNALLOCATED"].source_ids == ("FX:CURVATURE", "GIRR:DELTA")
    assert buckets["1"].contribution == pytest.approx(8.0)
    assert buckets["2"].contribution == 0.0

    risk_classes = _by_key(risk_class_summaries)
    assert _keys(risk_class_summaries) == ["GIRR", "FX"]
    assert risk_classes["GIRR"].contribution == pytest.approx(8.0)
    assert risk_classes["GIRR"].residual == pytest.approx(2.0)
    assert risk_classes["GIRR"].total == pytest.approx(10.0)
    assert risk_classes["GIRR"].bucket_key is None
    assert risk_classes["FX"].total == pytest.approx(7.0)
    assert risk_classes["FX"].reconciliation_status is ReconciliationStatus.PARTIAL_RESIDUAL


def test_generic_and_top_summary_helpers_are_stable_and_validate_limit() -> None:
    records = _records()

    generic = summarize_sbm_attribution(records, grain="risk_class")
    top = top_sbm_attribution_summaries(records, grain="risk_class", limit=1)

    assert top == generic[:1]
    assert top[0].key == "GIRR"
    assert top[0].summary_id == "sbm-attr-risk_class-girr"
    assert top[0].as_dict()["key"] == "GIRR"
    assert top_sbm_attribution_summaries(records, grain="bucket", limit=0) == ()
    with pytest.raises(ValueError, match="limit must be non-negative"):
        top_sbm_attribution_summaries(records, grain="bucket", limit=-1)


def _records() -> tuple[CapitalContribution, ...]:
    return (
        _analytical("s-positive", bucket_key="1", category="GIRR", contribution=12.0),
        _analytical("s-negative", bucket_key="1", category="GIRR", contribution=-4.0),
        _analytical("s-zero", bucket_key="2", category="GIRR", contribution=0.0),
        CapitalContribution(
            contribution_id="sbm-girr-residual",
            source_id="GIRR:DELTA",
            source_level="risk_class",
            bucket_key=None,
            category="GIRR",
            base_amount=0.0,
            marginal_multiplier=None,
            contribution=None,
            method=AttributionMethod.RESIDUAL,
            residual=2.0,
            reason="rounding residual",
            citations=("basel_mar21_4_inter_bucket",),
            reconciliation_status=ReconciliationStatus.PARTIAL_RESIDUAL,
        ),
        CapitalContribution(
            contribution_id="sbm-fx-curvature-unsupported",
            source_id="FX:CURVATURE",
            source_level="risk_class",
            bucket_key=None,
            category="FX",
            base_amount=0.0,
            marginal_multiplier=None,
            contribution=None,
            method=AttributionMethod.UNSUPPORTED,
            residual=7.0,
            reason="curvature attribution unsupported",
            citations=("basel_mar21_5_curvature",),
            reconciliation_status=ReconciliationStatus.PARTIAL_RESIDUAL,
        ),
    )


def _analytical(
    source_id: str,
    *,
    bucket_key: str,
    category: str,
    contribution: float,
) -> CapitalContribution:
    return CapitalContribution(
        contribution_id=f"sbm-{source_id}",
        source_id=source_id,
        source_level="sensitivity",
        bucket_key=bucket_key,
        category=category,
        base_amount=abs(contribution),
        marginal_multiplier=1.0,
        contribution=contribution,
        method=AttributionMethod.ANALYTICAL_EULER,
        citations=("basel_mar21_4_intra_bucket",),
        reconciliation_status=ReconciliationStatus.RECONCILED,
    )


def _by_key(
    summaries: tuple[SbmAttributionSummary, ...],
) -> dict[str, SbmAttributionSummary]:
    by_key: dict[str, SbmAttributionSummary] = {}
    for summary in summaries:
        by_key[summary.key] = summary
    return by_key


def _keys(summaries: tuple[SbmAttributionSummary, ...]) -> list[str]:
    keys: list[str] = []
    for summary in summaries:
        keys.append(summary.key)
    return keys


def _total(summaries: tuple[SbmAttributionSummary, ...]) -> float:
    total = 0.0
    for summary in summaries:
        total += summary.total
    return total


def _record_total(records: tuple[CapitalContribution, ...]) -> float:
    total = 0.0
    for record in records:
        total += (record.contribution or 0.0) + record.residual
    return total


def _record_count(summaries: tuple[SbmAttributionSummary, ...]) -> int:
    count = 0
    for summary in summaries:
        count += summary.record_count
    return count
