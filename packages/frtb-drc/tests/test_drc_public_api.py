from __future__ import annotations

from datetime import date
from importlib.metadata import version as package_version

import pytest
from frtb_common import UnsupportedRegulatoryFeatureError
from frtb_drc import (
    US_NPR_2_0_PROFILE_ID,
    CreditQuality,
    DefaultDirection,
    DrcCalculationContext,
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
    assert result.total_drc == pytest.approx(1.125)
    assert result.categories[0].capital == result.total_drc
    assert "US_NPR_210_B_2" in result.citations
    assert "US_NPR_210_A_2_IV_A" in result.citations
    assert "US_NPR_210_B_3_II" in result.citations
    validate_reconciliation(result)


def test_public_api_rejects_unsupported_securitisation_path() -> None:
    with pytest.raises(UnsupportedRegulatoryFeatureError, match="securitisation non-CTP"):
        calculate_drc_capital(
            (
                _position(
                    "sec",
                    DefaultDirection.LONG,
                    100.0,
                    risk_class=DrcRiskClass.SECURITISATION_NON_CTP,
                    instrument_type=DrcInstrumentType.SECURITISATION_TRANCHE,
                    issuer=None,
                    tranche="tranche-a",
                ),
            ),
            context=_context(),
        )


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
) -> DrcCalculationContext:
    return DrcCalculationContext(
        run_id=run_id,
        calculation_date=calculation_date,
        base_currency=base_currency,
        profile_id=profile_id,
        desk_id=desk_id,
        legal_entity=legal_entity,
        citation_policy=citation_policy,
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
    seniority: DrcSeniority = DrcSeniority.SENIOR_DEBT,
    credit_quality: CreditQuality = CreditQuality.INVESTMENT_GRADE,
    desk_id: str = "desk-a",
    legal_entity: str = "bank-na",
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
        bucket_key="CORPORATE",
        seniority=seniority,
        credit_quality=credit_quality,
        notional=notional,
        market_value=notional,
        cumulative_pnl=0.0,
        maturity_years=1.0,
        currency="USD",
        lineage=DrcSourceLineage(
            source_system="synthetic",
            source_file="public-api.csv",
            source_row_id=f"row-{position_id}",
            source_column_map={"position_id": "position_id", "issuer_id": "issuer_id"},
        ),
        citation_ids=citation_ids,
    )
