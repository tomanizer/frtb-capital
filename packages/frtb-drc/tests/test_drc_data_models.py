from __future__ import annotations

import json
from dataclasses import FrozenInstanceError
from datetime import date
from typing import Any, cast

import pytest
from frtb_drc import (
    BranchMetadata,
    BranchType,
    BucketDrc,
    CategoryDrc,
    CreditQuality,
    DefaultDirection,
    DrcCalculationContext,
    DrcCapitalResult,
    DrcCitation,
    DrcFxRate,
    DrcInstrumentType,
    DrcPosition,
    DrcRiskClass,
    DrcSeniority,
    DrcSourceLineage,
    GrossJtd,
    HedgeBenefitRatio,
    MaturityScaledJtd,
    NetJtd,
)


def test_drc_position_normalises_enums_and_is_frozen() -> None:
    position = _valid_position()

    assert position.risk_class is DrcRiskClass.NON_SECURITISATION
    assert position.instrument_type is DrcInstrumentType.BOND
    assert position.default_direction is DefaultDirection.LONG
    assert position.seniority is DrcSeniority.SENIOR_DEBT
    assert position.credit_quality is CreditQuality.INVESTMENT_GRADE

    with pytest.raises(FrozenInstanceError):
        position.position_id = "changed"  # type: ignore[misc]


def test_invalid_enum_value_fails_deterministically() -> None:
    with pytest.raises(ValueError, match="risk_class must be one of"):
        _valid_position(risk_class="UNKNOWN")


def test_source_lineage_freezes_column_map() -> None:
    lineage = DrcSourceLineage(
        source_system="test",
        source_file="positions.csv",
        source_row_id="row-1",
        source_column_map={"Qualifier": "issuer_id"},
    )

    with pytest.raises(TypeError):
        cast(Any, lineage.source_column_map)["Qualifier"] = "changed"


def test_context_freezes_fx_rate_mapping() -> None:
    rate = DrcFxRate(
        source_currency="EUR",
        target_currency="USD",
        rate=1.2,
        as_of_date=date(2026, 5, 29),
        source_id="unit-fx-source",
        lineage=DrcSourceLineage(
            source_system="test",
            source_file="fx.csv",
            source_row_id="EUR-USD",
        ),
    )
    context = DrcCalculationContext(
        run_id="run-1",
        calculation_date=date(2026, 5, 29),
        base_currency="USD",
        profile_id="us-npr-2.0",
        fx_rates={"EUR": rate},
        ctp_risk_weights={"ctp-1": 0.2},
        ctp_offset_groups={"ctp-1": "replication-group"},
    )

    with pytest.raises(TypeError):
        cast(Any, context.fx_rates)["GBP"] = rate
    with pytest.raises(TypeError):
        cast(Any, context.ctp_risk_weights)["ctp-2"] = 0.3
    with pytest.raises(TypeError):
        cast(Any, context.ctp_offset_groups)["ctp-2"] = "other-group"


def test_result_records_are_json_serialisable() -> None:
    branch = BranchMetadata(
        branch_id="branch-hbr-normal",
        branch_type=BranchType.NORMAL,
        source_id="bucket-corporate",
        selected=True,
        reason="normal denominator",
        citations=("US_NPR_210_A_2_IV_A",),
    )
    hbr = HedgeBenefitRatio(
        hbr_id="hbr-corporate",
        bucket_key="CORPORATE",
        aggregate_net_long=100.0,
        aggregate_net_short=25.0,
        denominator=125.0,
        ratio=0.8,
        citations=("US_NPR_210_A_2_IV_A",),
        branch_metadata=(branch,),
    )
    bucket = BucketDrc(
        bucket_id="bucket-corporate",
        bucket_key="CORPORATE",
        risk_class=DrcRiskClass.NON_SECURITISATION,
        hbr=hbr,
        weighted_long=2.1,
        weighted_short=0.5,
        capital=1.7,
        floor_applied=False,
        net_jtd_ids=("net-issuer-a-senior",),
        citations=("US_NPR_210_A_2_IV_B",),
        branch_metadata=(branch,),
    )
    category = CategoryDrc(
        category_id="category-nonsec",
        risk_class=DrcRiskClass.NON_SECURITISATION,
        bucket_results=(bucket,),
        capital=1.7,
    )
    result = DrcCapitalResult(
        result_id="drc-result-1",
        run_id="run-1",
        calculation_date=date(2026, 5, 29),
        base_currency="USD",
        profile_id="us-npr-2.0",
        profile_hash="profile-hash",
        input_hash="input-hash",
        categories=(category,),
        total_drc=1.7,
        citations=("US_NPR_210_A_4",),
        branch_metadata=(branch,),
    )

    as_dict = result.as_dict()
    categories = cast(list[dict[str, object]], as_dict["categories"])
    first_category = categories[0]
    buckets = cast(list[dict[str, object]], first_category["bucket_results"])
    hbr_record = cast(dict[str, object], buckets[0]["hbr"])
    branch_metadata = cast(list[dict[str, object]], as_dict["branch_metadata"])

    assert as_dict["calculation_date"] == "2026-05-29"
    assert hbr_record["ratio"] == 0.8
    assert branch_metadata[0]["branch_type"] == "NORMAL"
    json.dumps(as_dict, sort_keys=True)


def test_intermediate_records_preserve_attribution_ready_ids() -> None:
    gross = GrossJtd(
        gross_jtd_id="gross-pos-1",
        position_id="pos-1",
        risk_class=DrcRiskClass.NON_SECURITISATION,
        issuer_or_tranche_key="issuer-a",
        bucket_key="CORPORATE",
        default_direction=DefaultDirection.LONG,
        lgd_rate=0.75,
        lgd_source="profile",
        notional=100.0,
        pnl_component=0.0,
        gross_jtd=75.0,
        citations=("US_NPR_210_B_1_IV",),
    )
    scaled = MaturityScaledJtd(
        scaled_jtd_id="scaled-pos-1",
        gross_jtd_id=gross.gross_jtd_id,
        position_id=gross.position_id,
        gross_jtd=gross.gross_jtd,
        maturity_years=1.0,
        maturity_weight=1.0,
        scaled_jtd=75.0,
        floor_applied=False,
        citations=("US_NPR_210_A_2_III",),
    )
    net = NetJtd(
        net_jtd_id="net-issuer-a-senior",
        netting_group_id="ng-corporate-issuer-a-senior",
        risk_class=DrcRiskClass.NON_SECURITISATION,
        bucket_key="CORPORATE",
        obligor_or_tranche_key="issuer-a",
        seniority_layer="SENIOR_DEBT",
        gross_long=75.0,
        gross_short=0.0,
        scaled_long=75.0,
        scaled_short=0.0,
        net_amount=75.0,
        net_direction=DefaultDirection.LONG,
        position_ids=(gross.position_id,),
        scaled_jtd_ids=(scaled.scaled_jtd_id,),
    )

    assert scaled.gross_jtd_id == gross.gross_jtd_id
    assert net.position_ids == ("pos-1",)
    assert net.scaled_jtd_ids == ("scaled-pos-1",)


def test_citation_record_is_json_ready() -> None:
    citation = DrcCitation(
        citation_id="US_NPR_210_B_1_IV",
        source_id="US_NPR_2_0_91_FR_14952",
        paragraph="proposed section __.210(b)(1)(iv)",
        url="https://www.govinfo.gov/app/details/FR-2026-03-27/2026-05959",
    )

    assert citation.as_dict()["citation_id"] == "US_NPR_210_B_1_IV"


def _valid_position(**overrides: object) -> DrcPosition:
    values: dict[str, object] = {
        "position_id": "pos-1",
        "source_row_id": "row-1",
        "desk_id": "desk-a",
        "legal_entity": "bank-na",
        "risk_class": "NON_SECURITISATION",
        "instrument_type": "BOND",
        "default_direction": "LONG",
        "issuer_id": "issuer-a",
        "tranche_id": None,
        "index_series_id": None,
        "bucket_key": "CORPORATE",
        "seniority": "SENIOR_DEBT",
        "credit_quality": "INVESTMENT_GRADE",
        "notional": 100.0,
        "market_value": 99.0,
        "cumulative_pnl": 0.0,
        "maturity_years": 1.0,
        "currency": "USD",
        "lineage": DrcSourceLineage(
            source_system="test",
            source_file="positions.csv",
            source_row_id="row-1",
            source_column_map={"Qualifier": "issuer_id"},
        ),
    }
    values.update(overrides)
    return DrcPosition(**values)  # type: ignore[arg-type]
