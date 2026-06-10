from __future__ import annotations

from dataclasses import replace
from datetime import date

import pytest
from frtb_drc import (
    US_NPR_2_0_PROFILE_ID,
    AttributionMethod,
    BranchMetadata,
    BranchType,
    BucketDrc,
    CategoryDrc,
    DefaultDirection,
    DrcCapitalResult,
    DrcInputError,
    DrcRiskClass,
    HedgeBenefitRatio,
    NetJtd,
    ReconciliationStatus,
    calculate_drc_attribution,
    validate_attribution_reconciliation,
)


def test_category_floor_emits_category_unsupported_residual() -> None:
    category = CategoryDrc(
        category_id="category-floor",
        risk_class=DrcRiskClass.NON_SECURITISATION,
        bucket_results=(),
        capital=11.0,
        branch_metadata=(_branch(BranchType.FLOOR, "category-floor"),),
    )
    result = _result(categories=(category,), total_drc=11.0)

    records = calculate_drc_attribution(result, risk_weights_by_position={})

    assert len(records) == 1
    record = records[0]
    assert record.method is AttributionMethod.UNSUPPORTED
    assert record.source_level == "category"
    assert record.source_id == "category-floor"
    assert record.residual == pytest.approx(11.0)
    assert "category floor" in record.reason
    assert record.reconciliation_status is ReconciliationStatus.PARTIAL_RESIDUAL
    validate_attribution_reconciliation(result, records)


def test_bucket_floor_emits_bucket_unsupported_residual() -> None:
    bucket = _bucket(
        bucket_id="bucket-floor",
        capital=13.0,
        floor_applied=True,
        branch_metadata=(_branch(BranchType.FLOOR, "bucket-floor"),),
        net_jtd_ids=("net-long",),
    )
    result = _result(
        categories=(_category(bucket, capital=13.0),),
        net_jtds=(_net_jtd("net-long", position_ids=("position-long",)),),
        total_drc=13.0,
    )

    records = calculate_drc_attribution(
        result,
        risk_weights_by_position={"position-long": 0.2},
    )

    assert len(records) == 1
    record = records[0]
    assert record.method is AttributionMethod.UNSUPPORTED
    assert record.source_level == "bucket"
    assert record.source_id == "bucket-floor"
    assert record.residual == pytest.approx(13.0)
    assert "bucket floor" in record.reason
    assert record.reconciliation_status is ReconciliationStatus.PARTIAL_RESIDUAL
    validate_attribution_reconciliation(result, records)


def test_zero_hbr_denominator_emits_bucket_unsupported_residual() -> None:
    bucket = _bucket(
        bucket_id="bucket-zero-denominator",
        capital=17.0,
        hbr=_hbr(denominator=0.0, ratio=0.0),
        net_jtd_ids=("net-long",),
    )
    result = _result(
        categories=(_category(bucket, capital=17.0),),
        net_jtds=(_net_jtd("net-long", position_ids=("position-long",)),),
        total_drc=17.0,
    )

    records = calculate_drc_attribution(
        result,
        risk_weights_by_position={"position-long": 0.2},
    )

    assert len(records) == 1
    record = records[0]
    assert record.method is AttributionMethod.UNSUPPORTED
    assert record.source_level == "bucket"
    assert record.residual == pytest.approx(17.0)
    assert "zero HBR denominator" in record.reason
    assert record.reconciliation_status is ReconciliationStatus.PARTIAL_RESIDUAL
    validate_attribution_reconciliation(result, records)


def test_missing_net_jtd_record_emits_bucket_unsupported_residual() -> None:
    bucket = _bucket(
        bucket_id="bucket-missing-net",
        capital=19.0,
        net_jtd_ids=("missing-net",),
    )
    result = _result(
        categories=(_category(bucket, capital=19.0),),
        total_drc=19.0,
    )

    records = calculate_drc_attribution(
        result,
        risk_weights_by_position={"position-long": 0.2},
    )

    assert len(records) == 1
    record = records[0]
    assert record.method is AttributionMethod.UNSUPPORTED
    assert record.source_level == "bucket"
    assert record.source_id == "bucket-missing-net"
    assert record.residual == pytest.approx(19.0)
    assert "net JTD record is missing" in record.reason
    assert record.reconciliation_status is ReconciliationStatus.PARTIAL_RESIDUAL
    validate_attribution_reconciliation(result, records)


def test_category_residual_reconciles_analytical_records_to_capital() -> None:
    bucket = _bucket(
        bucket_id="bucket-analytical",
        capital=20.0,
        net_jtd_ids=("net-long",),
    )
    result = _result(
        categories=(_category(bucket, capital=23.0),),
        net_jtds=(_net_jtd("net-long", position_ids=("position-long",)),),
        total_drc=23.0,
    )

    records = calculate_drc_attribution(
        result,
        risk_weights_by_position={"position-long": 0.2},
    )

    analytical = [record for record in records if record.method is AttributionMethod.ANALYTICAL_EULER]
    residual = [record for record in records if record.method is AttributionMethod.RESIDUAL]
    assert len(analytical) == 1
    assert len(residual) == 1
    assert analytical[0].source_level == "net_jtd"
    assert analytical[0].contribution == pytest.approx(20.0)
    assert residual[0].source_level == "category"
    assert residual[0].residual == pytest.approx(3.0)
    assert "category residual" in residual[0].reason
    validate_attribution_reconciliation(result, records)


def test_validate_attribution_reconciliation_rejects_tampered_residual() -> None:
    category = CategoryDrc(
        category_id="category-floor",
        risk_class=DrcRiskClass.NON_SECURITISATION,
        bucket_results=(),
        capital=11.0,
        branch_metadata=(_branch(BranchType.FLOOR, "category-floor"),),
    )
    result = _result(categories=(category,), total_drc=11.0)
    records = calculate_drc_attribution(result, risk_weights_by_position={})
    tampered = (replace(records[0], residual=records[0].residual + 1.0),)

    with pytest.raises(DrcInputError, match="attribution records do not reconcile"):
        validate_attribution_reconciliation(result, tampered)


def _result(
    *,
    categories: tuple[CategoryDrc, ...],
    total_drc: float,
    net_jtds: tuple[NetJtd, ...] = (),
) -> DrcCapitalResult:
    return DrcCapitalResult(
        result_id="drc-unsupported-branch",
        run_id="run-drc-unsupported-branch",
        calculation_date=date(2026, 6, 10),
        base_currency="USD",
        profile_id=US_NPR_2_0_PROFILE_ID,
        profile_hash="profile-hash",
        input_hash="input-hash",
        categories=categories,
        total_drc=total_drc,
        citations=("US_NPR_210_SCOPE",),
        net_jtds=net_jtds,
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
    bucket_id: str,
    capital: float,
    hbr: HedgeBenefitRatio | None = None,
    floor_applied: bool = False,
    branch_metadata: tuple[BranchMetadata, ...] = (),
    net_jtd_ids: tuple[str, ...],
) -> BucketDrc:
    return BucketDrc(
        bucket_id=bucket_id,
        bucket_key="CORPORATE",
        risk_class=DrcRiskClass.NON_SECURITISATION,
        hbr=_hbr() if hbr is None else hbr,
        weighted_long=100.0,
        weighted_short=0.0,
        capital=capital,
        floor_applied=floor_applied,
        net_jtd_ids=net_jtd_ids,
        citations=("US_NPR_210_SCOPE",),
        branch_metadata=branch_metadata,
    )


def _hbr(*, denominator: float = 100.0, ratio: float = 0.0) -> HedgeBenefitRatio:
    branch_metadata = ()
    if denominator == 0.0:
        branch_metadata = (_branch(BranchType.ZERO_DENOMINATOR, "hbr-corporate"),)
    return HedgeBenefitRatio(
        hbr_id="hbr-corporate",
        bucket_key="CORPORATE",
        aggregate_net_long=100.0,
        aggregate_net_short=0.0,
        denominator=denominator,
        ratio=ratio,
        citations=("US_NPR_210_SCOPE",),
        branch_metadata=branch_metadata,
    )


def _net_jtd(net_jtd_id: str, *, position_ids: tuple[str, ...]) -> NetJtd:
    return NetJtd(
        net_jtd_id=net_jtd_id,
        netting_group_id=f"group-{net_jtd_id}",
        risk_class=DrcRiskClass.NON_SECURITISATION,
        bucket_key="CORPORATE",
        obligor_or_tranche_key="issuer-a",
        seniority_layer="SENIOR_DEBT",
        gross_long=100.0,
        gross_short=0.0,
        scaled_long=100.0,
        scaled_short=0.0,
        net_amount=100.0,
        net_direction=DefaultDirection.LONG,
        position_ids=position_ids,
        scaled_jtd_ids=(f"scaled-{net_jtd_id}",),
    )


def _branch(branch_type: BranchType, source_id: str) -> BranchMetadata:
    return BranchMetadata(
        branch_id=f"branch-{source_id}-{branch_type.value.lower()}",
        branch_type=branch_type,
        source_id=source_id,
        selected=True,
        reason=branch_type.value.lower(),
        citations=("US_NPR_210_SCOPE",),
    )
