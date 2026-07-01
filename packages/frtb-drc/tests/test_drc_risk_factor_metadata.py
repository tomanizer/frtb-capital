"""Tests for DRC risk-factor-adjacent metadata drilldown rows."""

from __future__ import annotations

from datetime import date

from frtb_drc.data_models import (
    DefaultDirection,
    DrcCapitalResult,
    DrcInstrumentType,
    DrcPosition,
    DrcRiskClass,
    DrcSourceLineage,
    GrossJtd,
    MaturityScaledJtd,
    NetJtd,
)
from frtb_drc.risk_factor_metadata import build_drc_risk_factor_metadata_rows


def test_drc_risk_factor_metadata_rows_preserve_issuer_source_and_lineage_ids() -> None:
    position = DrcPosition(
        position_id="pos-1",
        source_row_id="src-1",
        desk_id="credit",
        legal_entity="bank",
        risk_class=DrcRiskClass.NON_SECURITISATION,
        instrument_type=DrcInstrumentType.BOND,
        default_direction=DefaultDirection.LONG,
        issuer_id="issuer-1",
        tranche_id=None,
        index_series_id=None,
        bucket_key="corporate",
        seniority="SENIOR_DEBT",
        credit_quality="BBB",
        notional=100.0,
        market_value=98.0,
        cumulative_pnl=1.0,
        maturity_years=2.5,
        currency="USD",
        lineage=DrcSourceLineage("risk-engine", "drc.csv", "src-1"),
    )
    gross = GrossJtd(
        gross_jtd_id="gross-1",
        position_id="pos-1",
        risk_class=DrcRiskClass.NON_SECURITISATION,
        issuer_or_tranche_key="issuer-1",
        bucket_key="corporate",
        default_direction=DefaultDirection.LONG,
        lgd_rate=0.75,
        lgd_source="seniority",
        notional=100.0,
        pnl_component=1.0,
        gross_jtd=74.0,
        citations=(),
    )
    scaled = MaturityScaledJtd(
        scaled_jtd_id="scaled-1",
        gross_jtd_id="gross-1",
        position_id="pos-1",
        gross_jtd=74.0,
        maturity_years=2.5,
        maturity_weight=1.0,
        scaled_jtd=74.0,
        floor_applied=False,
        citations=(),
    )
    net = NetJtd(
        net_jtd_id="net-1",
        netting_group_id="netting-issuer-1-senior",
        risk_class=DrcRiskClass.NON_SECURITISATION,
        bucket_key="corporate",
        obligor_or_tranche_key="issuer-1",
        seniority_layer="SENIOR_DEBT",
        gross_long=74.0,
        gross_short=0.0,
        scaled_long=74.0,
        scaled_short=0.0,
        net_amount=74.0,
        net_direction=DefaultDirection.LONG,
        position_ids=("pos-1",),
        scaled_jtd_ids=("scaled-1",),
    )
    result = DrcCapitalResult(
        result_id="drc-result",
        run_id="run-1",
        calculation_date=date(2025, 1, 2),
        base_currency="USD",
        profile_id="US_NPR_2_0",
        profile_hash="profile",
        input_hash="input",
        categories=(),
        total_drc=0.0,
        citations=(),
        input_positions=(position,),
        gross_jtds=(gross,),
        maturity_scaled_jtds=(scaled,),
        net_jtds=(net,),
    )

    rows = build_drc_risk_factor_metadata_rows(result)

    assert rows[0].issuer_id == "issuer-1"
    assert rows[0].obligor_id == "issuer-1"
    assert rows[0].source_row_id == "src-1"
    assert rows[0].netting_group_ids == ("netting-issuer-1-senior",)
    assert rows[0].gross_jtd_ids == ("gross-1",)
    assert rows[0].scaled_jtd_ids == ("scaled-1",)
    assert rows[0].lgd_source == "seniority"


def test_drc_risk_factor_metadata_rows_tolerate_nullable_result_collections() -> None:
    result = DrcCapitalResult(
        result_id="drc-result",
        run_id="run-1",
        calculation_date=date(2025, 1, 2),
        base_currency="USD",
        profile_id="US_NPR_2_0",
        profile_hash="profile",
        input_hash="input",
        categories=(),
        total_drc=0.0,
        citations=(),
        input_positions=(),
        gross_jtds=(),
        maturity_scaled_jtds=(),
        net_jtds=(),
    )

    object.__setattr__(result, "input_positions", None)
    object.__setattr__(result, "gross_jtds", None)
    object.__setattr__(result, "maturity_scaled_jtds", None)
    object.__setattr__(result, "net_jtds", None)
    assert build_drc_risk_factor_metadata_rows(result) == ()
