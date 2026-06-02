from __future__ import annotations

from datetime import date
from importlib.metadata import version as package_version

import pytest
from frtb_drc import (
    US_NPR_2_0_PROFILE_ID,
    CreditQuality,
    DefaultDirection,
    DrcCalculationContext,
    DrcFxConversion,
    DrcFxRate,
    DrcInputError,
    DrcInstrumentType,
    DrcPosition,
    DrcRiskClass,
    DrcSeniority,
    DrcSourceLineage,
    calculate_drc_capital,
    validate_reconciliation,
)


def test_calculate_drc_capital_wires_nonsec_chain_and_audit_lineage() -> None:
    result = calculate_drc_capital(
        (
            _position("long", DefaultDirection.LONG, 100.0, issuer="issuer-a"),
            _position("short", DefaultDirection.SHORT, 40.0, issuer="issuer-b"),
        ),
        context=_context(),
    )

    assert result.package_name == "frtb-drc"
    assert result.package_version
    assert result.package_version == package_version("frtb-drc")
    assert result.package_version not in {"0.0.0+unknown", "0.1.0"}
    assert result.input_count == 2
    assert result.rejected_input_count == 0
    assert len(result.input_hash) == 64
    assert len(result.profile_hash) == 64
    assert len(result.input_positions) == 2
    assert result.input_positions[0].lineage is not None
    assert result.input_positions[0].lineage.source_row_id == "row-long"
    assert len(result.gross_jtds) == 2
    assert len(result.maturity_scaled_jtds) == 2
    assert [(net.net_direction, net.net_amount) for net in result.net_jtds] == [
        (DefaultDirection.LONG, 75.0),
        (DefaultDirection.SHORT, 30.0),
    ]
    assert result.total_drc == pytest.approx(2.1964285714285716)
    assert result.categories[0].capital == result.total_drc
    assert "US_NPR_210_B_2" in result.citations
    assert "US_NPR_210_A_2_IV_A" in result.citations
    assert "US_NPR_210_B_3_II" in result.citations
    validate_reconciliation(result)


def test_public_api_wires_securitisation_non_ctp_category() -> None:
    result = calculate_drc_capital(
        (
            _position(
                "sec",
                DefaultDirection.LONG,
                100.0,
                risk_class=DrcRiskClass.SECURITISATION_NON_CTP,
                instrument_type=DrcInstrumentType.SECURITISATION_TRANCHE,
                issuer="clo-2026-1",
                tranche="tranche-a",
                bucket_key="SEC_CLO_NORTH_AMERICA",
                seniority=None,
                credit_quality=None,
                citation_ids=("US_NPR_210_C_1",),
            ),
        ),
        context=_context(securitisation_non_ctp_risk_weights={"sec": 0.2}),
    )

    assert result.total_drc == pytest.approx(20.0)
    assert result.categories[0].risk_class is DrcRiskClass.SECURITISATION_NON_CTP
    assert "US_NPR_210_C_1" in result.citations
    assert "US_NPR_210_C_3_IV" in result.citations
    validate_reconciliation(result)


def test_public_api_rejects_ambiguous_net_credit_quality() -> None:
    with pytest.raises(DrcInputError, match="one credit quality"):
        calculate_drc_capital(
            (
                _position(
                    "long",
                    DefaultDirection.LONG,
                    100.0,
                    issuer="issuer-a",
                    credit_quality=CreditQuality.INVESTMENT_GRADE,
                ),
                _position(
                    "short",
                    DefaultDirection.SHORT,
                    40.0,
                    issuer="issuer-a",
                    credit_quality=CreditQuality.SPECULATIVE_GRADE,
                ),
            ),
            context=_context(),
        )


def test_public_api_rejects_unrated_before_risk_weight_lookup() -> None:
    with pytest.raises(
        DrcInputError,
        match=r"UNRATED.*map it to one of.*US_NPR_210_B_3_II",
    ):
        calculate_drc_capital(
            (
                _position(
                    "unrated",
                    DefaultDirection.LONG,
                    100.0,
                    credit_quality=CreditQuality.UNRATED,
                ),
            ),
            context=_context(),
        )


def test_public_api_rejects_position_outside_context_desk_scope() -> None:
    with pytest.raises(DrcInputError, match="desk_id"):
        calculate_drc_capital(
            (_position("desk-b", DefaultDirection.LONG, 100.0, desk_id="desk-b"),),
            context=_context(desk_id="desk-a"),
        )


def test_public_api_rejects_position_outside_context_legal_entity_scope() -> None:
    with pytest.raises(DrcInputError, match="legal_entity"):
        calculate_drc_capital(
            (_position("le-b", DefaultDirection.LONG, 100.0, legal_entity="bank-eu"),),
            context=_context(legal_entity="bank-na"),
        )


def test_public_api_accepts_populated_position_scope_when_context_is_unscoped() -> None:
    result = calculate_drc_capital(
        (
            _position(
                "desk-b",
                DefaultDirection.LONG,
                100.0,
                desk_id="desk-b",
                legal_entity="bank-eu",
            ),
        ),
        context=_context(),
    )

    assert result.input_count == 1


def test_public_api_translates_multi_currency_book_before_gross_jtd() -> None:
    result = calculate_drc_capital(
        (
            _position("usd", DefaultDirection.LONG, 100.0, issuer="issuer-usd"),
            _position(
                "eur",
                DefaultDirection.LONG,
                100.0,
                issuer="issuer-eur",
                currency="EUR",
            ),
        ),
        context=_context(fx_rates={"EUR": _fx_rate("EUR", 1.2)}),
    )

    gross_by_position = {record.position_id: record for record in result.gross_jtds}
    input_currency_by_position = {
        position.position_id: position.currency for position in result.input_positions
    }
    assert input_currency_by_position["eur"] == "EUR"
    assert gross_by_position["usd"].gross_jtd == pytest.approx(75.0)
    assert gross_by_position["eur"].notional == pytest.approx(120.0)
    assert gross_by_position["eur"].gross_jtd == pytest.approx(90.0)
    assert result.total_drc == pytest.approx((75.0 + 90.0) * 0.041)
    assert result.fx_conversions == (
        DrcFxConversion(
            source_currency="EUR",
            target_currency="USD",
            rate=1.2,
            as_of_date=date(2026, 5, 29),
            source_id="unit-fx-source",
            position_count=1,
            lineage=_fx_lineage(),
            citation_ids=("US_NPR_207_A_8", "US_NPR_208_H_1_II"),
        ),
    )
    assert "US_NPR_207_A_8" in result.citations
    assert "US_NPR_208_H_1_II" in result.citations
    assert result.branch_metadata[-1].source_id == "unit-fx-source"


def test_public_api_missing_fx_rate_fails_closed() -> None:
    with pytest.raises(DrcInputError, match=r"missing FX rate EUR->USD.*position eur"):
        calculate_drc_capital(
            (_position("eur", DefaultDirection.LONG, 100.0, currency="EUR"),),
            context=_context(),
        )


def test_public_api_rejects_non_finite_fx_rate_at_context_boundary() -> None:
    with pytest.raises(DrcInputError, match=r"FX rate EUR->USD must be finite and positive"):
        calculate_drc_capital(
            (_position("usd", DefaultDirection.LONG, 100.0),),
            context=_context(fx_rates={"EUR": _fx_rate("EUR", float("inf"))}),
        )


def test_public_api_rejects_none_fx_rate_text_fields() -> None:
    bad_rate = DrcFxRate(
        source_currency="EUR",
        target_currency="USD",
        rate=1.2,
        as_of_date=date(2026, 5, 29),
        source_id=None,  # type: ignore[arg-type]
        lineage=_fx_lineage(),
    )

    with pytest.raises(DrcInputError, match=r"fx_rate\.source_id must be non-empty"):
        calculate_drc_capital(
            (_position("usd", DefaultDirection.LONG, 100.0),),
            context=_context(fx_rates={"EUR": bad_rate}),
        )


def test_public_api_rejects_fx_rate_for_wrong_as_of_date() -> None:
    with pytest.raises(DrcInputError, match=r"as_of_date 2026-05-28.*calculation_date 2026-05-29"):
        calculate_drc_capital(
            (_position("eur", DefaultDirection.LONG, 100.0, currency="EUR"),),
            context=_context(fx_rates={"EUR": _fx_rate("EUR", 1.2, as_of_date=date(2026, 5, 28))}),
        )


def test_public_api_single_currency_output_is_unchanged_without_fx() -> None:
    positions = (_position("usd", DefaultDirection.LONG, 100.0),)

    first = calculate_drc_capital(positions, context=_context())
    second = calculate_drc_capital(positions, context=_context(fx_rates={}))

    assert second.fx_conversions == ()
    assert second.input_hash == first.input_hash
    assert second.total_drc == first.total_drc


def test_public_api_rejects_uncited_position_under_strict_policy() -> None:
    with pytest.raises(DrcInputError, match="citation_ids"):
        calculate_drc_capital(
            (_position("uncited", DefaultDirection.LONG, 100.0, citation_ids=()),),
            context=_context(),
        )


def test_public_api_preserves_zero_lgd_audit_records_with_zero_capital() -> None:
    result = calculate_drc_capital(
        (
            _position(
                "zero",
                DefaultDirection.LONG,
                100.0,
                seniority=DrcSeniority.NOT_RECOVERY_LINKED,
            ),
        ),
        context=_context(),
    )

    assert result.total_drc == 0.0
    assert result.gross_jtds[0].gross_jtd == 0.0
    assert result.maturity_scaled_jtds[0].scaled_jtd == 0.0
    assert result.net_jtds == ()
    assert result.categories[0].bucket_results == ()


def _context(
    *,
    run_id: str = "run-public-api",
    calculation_date: date = date(2026, 5, 29),
    base_currency: str = "USD",
    profile_id: str = US_NPR_2_0_PROFILE_ID,
    desk_id: str = "",
    legal_entity: str = "",
    citation_policy: str = "strict",
    fx_rates: dict[str, DrcFxRate] | None = None,
    securitisation_non_ctp_risk_weights: dict[str, float] | None = None,
    securitisation_non_ctp_offset_groups: dict[str, str] | None = None,
) -> DrcCalculationContext:
    return DrcCalculationContext(
        run_id=run_id,
        calculation_date=calculation_date,
        base_currency=base_currency,
        profile_id=profile_id,
        desk_id=desk_id,
        legal_entity=legal_entity,
        citation_policy=citation_policy,
        fx_rates={} if fx_rates is None else fx_rates,
        securitisation_non_ctp_risk_weights={}
        if securitisation_non_ctp_risk_weights is None
        else securitisation_non_ctp_risk_weights,
        securitisation_non_ctp_offset_groups={}
        if securitisation_non_ctp_offset_groups is None
        else securitisation_non_ctp_offset_groups,
    )


def _position(
    position_id: str,
    direction: DefaultDirection,
    notional: float,
    *,
    issuer: str | None = "issuer-a",
    tranche: str | None = None,
    risk_class: DrcRiskClass = DrcRiskClass.NON_SECURITISATION,
    instrument_type: DrcInstrumentType = DrcInstrumentType.BOND,
    seniority: DrcSeniority | None = DrcSeniority.SENIOR_DEBT,
    credit_quality: CreditQuality | None = CreditQuality.INVESTMENT_GRADE,
    bucket_key: str = "CORPORATE",
    desk_id: str = "desk-a",
    legal_entity: str = "bank-na",
    currency: str = "USD",
    citation_ids: tuple[str, ...] = ("US_NPR_210_SCOPE",),
) -> DrcPosition:
    return DrcPosition(
        position_id=position_id,
        source_row_id=f"row-{position_id}",
        desk_id=desk_id,
        legal_entity=legal_entity,
        risk_class=risk_class,
        instrument_type=instrument_type,
        default_direction=direction,
        issuer_id=issuer,
        tranche_id=tranche,
        index_series_id=None,
        bucket_key=bucket_key,
        seniority=seniority,
        credit_quality=credit_quality,
        notional=notional,
        market_value=notional,
        cumulative_pnl=0.0,
        maturity_years=1.0,
        currency=currency,
        lineage=DrcSourceLineage(
            source_system="synthetic",
            source_file="public-api.csv",
            source_row_id=f"row-{position_id}",
            source_column_map={"position_id": "position_id", "issuer_id": "issuer_id"},
        ),
        citation_ids=citation_ids,
    )


def _fx_rate(
    source_currency: str,
    rate: float,
    *,
    as_of_date: date = date(2026, 5, 29),
) -> DrcFxRate:
    return DrcFxRate(
        source_currency=source_currency,
        target_currency="USD",
        rate=rate,
        as_of_date=as_of_date,
        source_id="unit-fx-source",
        lineage=_fx_lineage(),
    )


def _fx_lineage() -> DrcSourceLineage:
    return DrcSourceLineage(
        source_system="unit-test",
        source_file="fx-rates.csv",
        source_row_id="EUR-USD-2026-05-29",
        source_column_map={"rate": "rate"},
    )
