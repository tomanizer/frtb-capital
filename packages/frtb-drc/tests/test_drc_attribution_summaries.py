from __future__ import annotations

from datetime import date

import pytest
from frtb_drc import (
    US_NPR_2_0_PROFILE_ID,
    AttributionMethod,
    CapitalContribution,
    DefaultDirection,
    DrcAttributionGrain,
    DrcCapitalResult,
    DrcRiskClass,
    NetJtd,
    ReconciliationStatus,
    summarize_drc_attribution,
    summarize_drc_attribution_by_bucket,
    summarize_drc_attribution_by_category,
    summarize_drc_attribution_by_issuer,
    summarize_drc_attribution_by_risk_class,
    top_drc_attribution_summaries,
)


def test_issuer_summaries_preserve_net_jtd_and_issuer_lineage() -> None:
    result = _result()

    summaries = summarize_drc_attribution_by_issuer(result)
    by_key = {summary.key: summary for summary in summaries}

    assert [summary.key for summary in summaries] == [
        "clo-2026-1|mezz",
        "issuer-a",
        "UNALLOCATED",
        "cdx-na-ig-43",
    ]
    issuer = by_key["issuer-a"]
    assert issuer.grain is DrcAttributionGrain.ISSUER
    assert issuer.risk_class == str(DrcRiskClass.NON_SECURITISATION)
    assert issuer.bucket_key == "CORPORATE"
    assert issuer.contribution == pytest.approx(5.0)
    assert issuer.residual == 0.0
    assert issuer.total == pytest.approx(5.0)
    assert issuer.record_count == 2
    assert issuer.net_jtd_ids == ("net-nonsec-long", "net-nonsec-short")
    assert issuer.source_ids == ("net-nonsec-long", "net-nonsec-short")
    assert issuer.methods == (str(AttributionMethod.ANALYTICAL_EULER),)
    assert issuer.reconciliation_status is ReconciliationStatus.RECONCILED

    unallocated = by_key["UNALLOCATED"]
    assert unallocated.record_count == 2
    assert unallocated.net_jtd_ids == ()
    assert unallocated.residual == pytest.approx(4.0)
    assert unallocated.total == pytest.approx(4.0)
    assert set(unallocated.methods) == {
        str(AttributionMethod.RESIDUAL),
        str(AttributionMethod.UNSUPPORTED),
    }
    assert unallocated.reconciliation_status is ReconciliationStatus.PARTIAL_RESIDUAL


def test_bucket_category_and_risk_class_summaries_reconcile_to_source_records() -> None:
    result = _result()

    for summaries in (
        summarize_drc_attribution_by_bucket(result),
        summarize_drc_attribution_by_category(result),
        summarize_drc_attribution_by_risk_class(result),
    ):
        assert sum(summary.total for summary in summaries) == pytest.approx(result.total_drc)
        assert sum(summary.record_count for summary in summaries) == len(result.attribution_records)

    bucket = {summary.key: summary for summary in summarize_drc_attribution_by_bucket(result)}
    assert bucket["SEC_CLO_NORTH_AMERICA"].contribution == pytest.approx(20.0)
    assert bucket["SEC_CLO_NORTH_AMERICA"].residual == pytest.approx(3.0)
    assert bucket["SEC_CLO_NORTH_AMERICA"].total == pytest.approx(23.0)
    assert (
        bucket["SEC_CLO_NORTH_AMERICA"].reconciliation_status
        is ReconciliationStatus.PARTIAL_RESIDUAL
    )

    categories = {
        summary.key: summary for summary in summarize_drc_attribution_by_category(result)
    }
    assert categories[str(DrcRiskClass.SECURITISATION_NON_CTP)].total == pytest.approx(
        23.0,
    )
    assert categories[
        str(DrcRiskClass.CORRELATION_TRADING_PORTFOLIO)
    ].total == pytest.approx(
        -1.5,
    )

    risk_classes = {
        summary.key: summary for summary in summarize_drc_attribution_by_risk_class(result)
    }
    assert risk_classes[str(DrcRiskClass.NON_SECURITISATION)].total == pytest.approx(5.0)
    assert risk_classes[str(DrcRiskClass.SECURITISATION_NON_CTP)].source_ids == (
        "bucket-sec-floor",
        "net-sec",
    )


def test_generic_and_top_summary_helpers_are_stable_and_validate_limit() -> None:
    result = _result()

    generic = summarize_drc_attribution(result, grain="issuer")
    top = top_drc_attribution_summaries(result, grain="issuer", limit=2)

    assert top == generic[:2]
    assert [summary.key for summary in top] == ["clo-2026-1|mezz", "issuer-a"]
    assert top[0].summary_id == "drc-attr-issuer-clo-2026-1-mezz"
    assert top[0].as_dict()["key"] == "clo-2026-1|mezz"
    assert top_drc_attribution_summaries(result, grain="issuer", limit=0) == ()
    with pytest.raises(ValueError, match="limit must be non-negative"):
        top_drc_attribution_summaries(result, grain="issuer", limit=-1)


def _result() -> DrcCapitalResult:
    records = _records()
    return DrcCapitalResult(
        result_id="drc-summary",
        run_id="run-drc-summary",
        calculation_date=date(2026, 6, 10),
        base_currency="USD",
        profile_id=US_NPR_2_0_PROFILE_ID,
        profile_hash="profile-hash",
        input_hash="input-hash",
        categories=(),
        total_drc=sum(
            (record.contribution or 0.0) + record.residual for record in records
        ),
        citations=("US_NPR_210_SCOPE",),
        net_jtds=_net_jtds(),
        attribution_records=records,
    )


def _records() -> tuple[CapitalContribution, ...]:
    return (
        _analytical(
            "net-nonsec-long",
            bucket_key="CORPORATE",
            category=DrcRiskClass.NON_SECURITISATION,
            contribution=7.5,
            citations=("US_NPR_210_SCOPE",),
        ),
        _analytical(
            "net-nonsec-short",
            bucket_key="CORPORATE",
            category=DrcRiskClass.NON_SECURITISATION,
            contribution=-2.5,
            citations=("US_NPR_210_SCOPE",),
        ),
        _analytical(
            "net-sec",
            bucket_key="SEC_CLO_NORTH_AMERICA",
            category=DrcRiskClass.SECURITISATION_NON_CTP,
            contribution=20.0,
            citations=("US_NPR_210_C_1",),
        ),
        _analytical(
            "net-ctp",
            bucket_key="CDX_NA_IG",
            category=DrcRiskClass.CORRELATION_TRADING_PORTFOLIO,
            contribution=-2.5,
            citations=("US_NPR_210_D_1",),
        ),
        CapitalContribution(
            contribution_id="attr-unsupported-bucket-sec-floor",
            source_id="bucket-sec-floor",
            source_level="bucket",
            bucket_key="SEC_CLO_NORTH_AMERICA",
            category=str(DrcRiskClass.SECURITISATION_NON_CTP),
            base_amount=0.0,
            marginal_multiplier=None,
            contribution=None,
            method=AttributionMethod.UNSUPPORTED,
            residual=3.0,
            reason="bucket floor makes exact Euler attribution unsupported",
            citations=("US_NPR_210_C_1",),
            reconciliation_status=ReconciliationStatus.PARTIAL_RESIDUAL,
        ),
        CapitalContribution(
            contribution_id="attr-residual-ctp-category",
            source_id="category-ctp",
            source_level="category",
            bucket_key=None,
            category=str(DrcRiskClass.CORRELATION_TRADING_PORTFOLIO),
            base_amount=0.0,
            marginal_multiplier=None,
            contribution=None,
            method=AttributionMethod.RESIDUAL,
            residual=1.0,
            reason="category residual reconciles analytical contribution records to capital",
            citations=("US_NPR_210_D_1",),
            reconciliation_status=ReconciliationStatus.PARTIAL_RESIDUAL,
        ),
    )


def _analytical(
    source_id: str,
    *,
    bucket_key: str,
    category: DrcRiskClass,
    contribution: float,
    citations: tuple[str, ...],
) -> CapitalContribution:
    return CapitalContribution(
        contribution_id=f"attr-{source_id}",
        source_id=source_id,
        source_level="net_jtd",
        bucket_key=bucket_key,
        category=str(category),
        base_amount=abs(contribution),
        marginal_multiplier=1.0,
        contribution=contribution,
        method=AttributionMethod.ANALYTICAL_EULER,
        reason="analytical Euler over stable DRC bucket/category branch",
        citations=citations,
        reconciliation_status=ReconciliationStatus.RECONCILED,
    )


def _net_jtds() -> tuple[NetJtd, ...]:
    return (
        _net_jtd(
            "net-nonsec-long",
            DrcRiskClass.NON_SECURITISATION,
            "CORPORATE",
            "issuer-a",
            DefaultDirection.LONG,
        ),
        _net_jtd(
            "net-nonsec-short",
            DrcRiskClass.NON_SECURITISATION,
            "CORPORATE",
            "issuer-a",
            DefaultDirection.SHORT,
        ),
        _net_jtd(
            "net-sec",
            DrcRiskClass.SECURITISATION_NON_CTP,
            "SEC_CLO_NORTH_AMERICA",
            "clo-2026-1|mezz",
            DefaultDirection.LONG,
        ),
        _net_jtd(
            "net-ctp",
            DrcRiskClass.CORRELATION_TRADING_PORTFOLIO,
            "CDX_NA_IG",
            "cdx-na-ig-43",
            DefaultDirection.SHORT,
        ),
    )


def _net_jtd(
    net_jtd_id: str,
    risk_class: DrcRiskClass,
    bucket_key: str,
    obligor_or_tranche_key: str,
    direction: DefaultDirection,
) -> NetJtd:
    return NetJtd(
        net_jtd_id=net_jtd_id,
        netting_group_id=f"group-{net_jtd_id}",
        risk_class=risk_class,
        bucket_key=bucket_key,
        obligor_or_tranche_key=obligor_or_tranche_key,
        seniority_layer="SENIOR_DEBT",
        gross_long=10.0 if direction is DefaultDirection.LONG else 0.0,
        gross_short=10.0 if direction is DefaultDirection.SHORT else 0.0,
        scaled_long=10.0 if direction is DefaultDirection.LONG else 0.0,
        scaled_short=10.0 if direction is DefaultDirection.SHORT else 0.0,
        net_amount=10.0,
        net_direction=direction,
        position_ids=(f"position-{net_jtd_id}",),
        scaled_jtd_ids=(f"scaled-{net_jtd_id}",),
    )
