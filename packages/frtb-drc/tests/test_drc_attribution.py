from __future__ import annotations

from dataclasses import replace
from datetime import date

import pytest
from frtb_drc import (
    US_NPR_2_0_PROFILE_ID,
    AttributionMethod,
    CreditQuality,
    DefaultDirection,
    DrcCalculationContext,
    DrcCapitalContribution,
    DrcCapitalResult,
    DrcInputError,
    DrcInstrumentType,
    DrcPosition,
    DrcRiskClass,
    DrcSeniority,
    DrcSourceLineage,
    build_drc_nonsec_batch_from_positions,
    calculate_drc_attribution,
    calculate_drc_capital,
    calculate_drc_capital_from_batch,
    validate_attribution_reconciliation,
)


def test_nonsec_long_only_attribution_is_analytical_and_reconciles() -> None:
    result = calculate_drc_capital(
        (
            _nonsec_position(
                "long-only",
                DefaultDirection.LONG,
                100.0,
                issuer_id="issuer-long-only",
            ),
        ),
        context=_context(),
    )

    _assert_reconciles(result.attribution_records, result.total_drc)
    assert len(result.attribution_records) == 1
    record = result.attribution_records[0]
    assert record.method is AttributionMethod.ANALYTICAL_EULER
    assert record.source_level == "net_jtd"
    assert record.base_amount == pytest.approx(75.0)
    assert record.contribution == pytest.approx(result.total_drc)
    assert record.residual == 0.0
    validate_attribution_reconciliation(result)


def test_nonsec_hedged_attribution_allocates_long_and_short_net_jtds() -> None:
    result = calculate_drc_capital(
        (
            _nonsec_position("long", DefaultDirection.LONG, 100.0, issuer_id="issuer-a"),
            _nonsec_position("short", DefaultDirection.SHORT, 40.0, issuer_id="issuer-b"),
        ),
        context=_context(),
    )

    analytical = [
        record
        for record in result.attribution_records
        if record.method is AttributionMethod.ANALYTICAL_EULER
    ]
    assert len(analytical) == 2
    assert {record.source_level for record in analytical} == {"net_jtd"}
    assert all(record.bucket_key == "CORPORATE" for record in analytical)
    assert any((record.contribution or 0.0) < 0.0 for record in analytical)
    _assert_reconciles(result.attribution_records, result.total_drc)
    validate_attribution_reconciliation(result)


def test_securitisation_bucket_floor_emits_unsupported_attribution_record() -> None:
    result = calculate_drc_capital(
        (
            _sec_position(
                "small-long",
                DefaultDirection.LONG,
                market_value=10.0,
                issuer_id="rmbs-2026-1",
                tranche_id="a",
                bucket_key="SEC_RMBS_EUROPE",
            ),
            _sec_position(
                "large-short",
                DefaultDirection.SHORT,
                market_value=100.0,
                issuer_id="rmbs-2026-2",
                tranche_id="a",
                bucket_key="SEC_RMBS_EUROPE",
            ),
        ),
        context=_context(
            securitisation_non_ctp_risk_weights={
                "small-long": 0.1,
                "large-short": 1.0,
            },
        ),
    )

    assert result.categories[0].bucket_results[0].floor_applied is True
    unsupported = [
        record
        for record in result.attribution_records
        if record.method is AttributionMethod.UNSUPPORTED
    ]
    assert len(unsupported) == 1
    assert unsupported[0].source_level == "bucket"
    assert unsupported[0].bucket_key == "SEC_RMBS_EUROPE"
    assert "bucket floor" in unsupported[0].reason
    _assert_reconciles(result.attribution_records, result.total_drc)
    validate_attribution_reconciliation(result)


def test_securitisation_non_ctp_attribution_is_analytical_when_branch_is_stable() -> None:
    result = calculate_drc_capital(
        (
            _sec_position(
                "sec-long",
                DefaultDirection.LONG,
                market_value=100.0,
                issuer_id="clo-2026-1",
                tranche_id="mezz",
                bucket_key="SEC_CLO_NORTH_AMERICA",
            ),
        ),
        context=_context(securitisation_non_ctp_risk_weights={"sec-long": 0.2}),
    )

    assert result.categories[0].risk_class is DrcRiskClass.SECURITISATION_NON_CTP
    assert {record.method for record in result.attribution_records} == {
        AttributionMethod.ANALYTICAL_EULER
    }
    assert result.attribution_records[0].contribution == pytest.approx(20.0)
    _assert_reconciles(result.attribution_records, result.total_drc)


def test_ctp_attribution_respects_positive_and_negative_bucket_recognition() -> None:
    result = calculate_drc_capital(
        (
            _ctp_position(
                "ctp-long",
                DefaultDirection.LONG,
                market_value=100.0,
                bucket_key="CDX_NA_IG",
                index_series_id="cdx-na-ig-43",
            ),
            _ctp_position(
                "ctp-short",
                DefaultDirection.SHORT,
                market_value=100.0,
                bucket_key="CDX_EU_IG",
                index_series_id="itraxx-eu-43",
            ),
        ),
        context=_context(
            ctp_risk_weights={"ctp-long": 0.2, "ctp-short": 0.2},
        ),
    )

    assert result.total_drc == pytest.approx(15.0)
    records = result.attribution_records
    assert {record.method for record in records} == {AttributionMethod.ANALYTICAL_EULER}
    assert sorted(record.contribution for record in records if record.contribution is not None) == [
        pytest.approx(-2.5),
        pytest.approx(17.5),
    ]
    _assert_reconciles(records, result.total_drc)


def test_missing_net_risk_weight_lineage_returns_unsupported_record() -> None:
    result = calculate_drc_capital(
        (
            _nonsec_position(
                "missing-lineage",
                DefaultDirection.LONG,
                100.0,
                issuer_id="issuer-missing-lineage",
            ),
        ),
        context=_context(),
    )

    records = calculate_drc_attribution(result, risk_weights_by_position={})

    assert len(records) == 1
    assert records[0].method is AttributionMethod.UNSUPPORTED
    assert records[0].source_level == "bucket"
    assert records[0].residual == pytest.approx(result.total_drc)
    assert "risk weight lineage" in records[0].reason
    _assert_reconciles(records, result.total_drc)


def test_batch_result_exposes_api_compatible_attribution_records() -> None:
    positions = (
        _nonsec_position("batch-long", DefaultDirection.LONG, 100.0, issuer_id="issuer-a"),
        _nonsec_position("batch-short", DefaultDirection.SHORT, 40.0, issuer_id="issuer-b"),
    )
    calculation = calculate_drc_capital_from_batch(
        build_drc_nonsec_batch_from_positions(positions),
        context=_context(),
    )

    assert calculation.result.attribution_records
    assert {record.method for record in calculation.result.attribution_records} == {
        AttributionMethod.ANALYTICAL_EULER
    }
    _assert_reconciles(calculation.result.attribution_records, calculation.result.total_drc)
    validate_attribution_reconciliation(calculation.result)


def test_attribution_reconciliation_rejects_tampered_contribution() -> None:
    result = calculate_drc_capital(
        (
            _nonsec_position(
                "tamper",
                DefaultDirection.LONG,
                100.0,
                issuer_id="issuer-tamper",
            ),
        ),
        context=_context(),
    )
    record = result.attribution_records[0]
    tampered = (
        replace(
            record,
            contribution=(record.contribution or 0.0) + 1.0,
        ),
    )

    with pytest.raises(DrcInputError, match="attribution records do not reconcile"):
        validate_attribution_reconciliation(result, tampered)


def test_attribution_reconciliation_uses_compensated_float_summation() -> None:
    records = (
        _contribution("large-positive", contribution=1e16),
        _contribution("unit", contribution=1.0),
        _contribution("large-negative", contribution=-1e16),
    )
    result = DrcCapitalResult(
        result_id="drc-fsum",
        run_id="run-attribution-fsum",
        calculation_date=date(2026, 5, 29),
        base_currency="USD",
        profile_id=US_NPR_2_0_PROFILE_ID,
        profile_hash="profile-hash",
        input_hash="input-hash",
        categories=(),
        total_drc=1.0,
        citations=(),
        attribution_records=records,
    )

    validate_attribution_reconciliation(result)


def _assert_reconciles(
    records: tuple[DrcCapitalContribution, ...],
    total_drc: float,
) -> None:
    total = sum((record.contribution or 0.0) + record.residual for record in records)
    assert total == pytest.approx(total_drc)


def _contribution(source_id: str, *, contribution: float) -> DrcCapitalContribution:
    return DrcCapitalContribution(
        contribution_id=f"attr-{source_id}",
        source_id=source_id,
        source_level="net_jtd",
        bucket_key="CORPORATE",
        category=DrcRiskClass.NON_SECURITISATION,
        base_amount=0.0,
        marginal_multiplier=0.0,
        contribution=contribution,
        method=AttributionMethod.ANALYTICAL_EULER,
    )


def _context(
    *,
    securitisation_non_ctp_risk_weights: dict[str, float] | None = None,
    ctp_risk_weights: dict[str, float] | None = None,
) -> DrcCalculationContext:
    return DrcCalculationContext(
        run_id="run-attribution",
        calculation_date=date(2026, 5, 29),
        base_currency="USD",
        profile_id=US_NPR_2_0_PROFILE_ID,
        securitisation_non_ctp_risk_weights={}
        if securitisation_non_ctp_risk_weights is None
        else securitisation_non_ctp_risk_weights,
        ctp_risk_weights={} if ctp_risk_weights is None else ctp_risk_weights,
    )


def _nonsec_position(
    position_id: str,
    direction: DefaultDirection,
    notional: float,
    *,
    issuer_id: str,
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
        bucket_key="CORPORATE",
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


def _sec_position(
    position_id: str,
    direction: DefaultDirection,
    *,
    market_value: float,
    bucket_key: str,
    issuer_id: str,
    tranche_id: str,
) -> DrcPosition:
    return DrcPosition(
        position_id=position_id,
        source_row_id=f"row-{position_id}",
        desk_id="sec-desk",
        legal_entity="bank-na",
        risk_class=DrcRiskClass.SECURITISATION_NON_CTP,
        instrument_type=DrcInstrumentType.SECURITISATION_TRANCHE,
        default_direction=direction,
        issuer_id=issuer_id,
        tranche_id=tranche_id,
        index_series_id=None,
        bucket_key=bucket_key,
        seniority=None,
        credit_quality=None,
        notional=abs(market_value),
        market_value=market_value,
        cumulative_pnl=None,
        maturity_years=1.0,
        currency="USD",
        lineage=_lineage(position_id, source_file="securitisation.csv"),
        citation_ids=("US_NPR_210_C_1",),
    )


def _ctp_position(
    position_id: str,
    direction: DefaultDirection,
    *,
    market_value: float,
    bucket_key: str,
    index_series_id: str,
) -> DrcPosition:
    return DrcPosition(
        position_id=position_id,
        source_row_id=f"row-{position_id}",
        desk_id="ctp-desk",
        legal_entity="bank-na",
        risk_class=DrcRiskClass.CORRELATION_TRADING_PORTFOLIO,
        instrument_type=DrcInstrumentType.INDEX_TRANCHE,
        default_direction=direction,
        issuer_id=None,
        tranche_id=None,
        index_series_id=index_series_id,
        bucket_key=bucket_key,
        seniority=None,
        credit_quality=None,
        notional=abs(market_value),
        market_value=market_value,
        cumulative_pnl=None,
        maturity_years=1.0,
        currency="USD",
        lineage=_lineage(position_id, source_file="ctp.csv"),
        citation_ids=("US_NPR_210_D_1",),
    )


def _lineage(position_id: str, *, source_file: str) -> DrcSourceLineage:
    return DrcSourceLineage(
        source_system="synthetic",
        source_file=source_file,
        source_row_id=f"row-{position_id}",
        source_column_map={"position_id": "position_id"},
    )
