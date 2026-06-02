from __future__ import annotations

import json
from dataclasses import replace
from datetime import date
from pathlib import Path
from typing import Any

import pytest
from frtb_drc import (
    US_NPR_2_0_PROFILE_ID,
    DefaultDirection,
    DrcCalculationContext,
    DrcInputError,
    DrcInstrumentType,
    DrcPosition,
    DrcRiskClass,
    DrcSourceLineage,
    calculate_drc_capital,
    get_rule_profile,
    validate_reconciliation,
)


def test_securitisation_non_ctp_unhedged_book_uses_market_value_and_context_weight() -> None:
    position = _sec_position(
        "long-clo",
        DefaultDirection.LONG,
        market_value=125.0,
        bucket_key="SEC_CLO_NORTH_AMERICA",
        issuer_id="clo-2026-1",
        tranche_id="mezz",
    )

    result = calculate_drc_capital(
        (position,),
        context=_context(
            securitisation_non_ctp_risk_weights={position.position_id: 0.16},
        ),
    )

    assert result.total_drc == pytest.approx(20.0)
    assert result.categories[0].risk_class is DrcRiskClass.SECURITISATION_NON_CTP
    assert result.gross_jtds[0].gross_jtd == pytest.approx(125.0)
    assert "LGD is embedded" in result.gross_jtds[0].lgd_source
    assert result.categories[0].bucket_results[0].hbr.ratio == pytest.approx(1.0)
    assert "US_NPR_210_C_1" in result.citations
    assert "US_NPR_210_C_3_III" in result.citations
    validate_reconciliation(result)


def test_securitisation_non_ctp_fixture_matches_hand_checked_expected() -> None:
    fixture = _load_securitisation_fixture()

    result = calculate_drc_capital(fixture["positions"], context=fixture["context"])
    expected = fixture["expected"]
    buckets = {bucket.bucket_key: bucket for bucket in result.categories[0].bucket_results}

    assert result.input_count == expected["input_count"]
    assert result.total_drc == pytest.approx(expected["total_drc"])
    assert result.categories[0].capital == pytest.approx(expected["category_capital"])
    assert buckets["SEC_CLO_NORTH_AMERICA"].capital == pytest.approx(
        expected["buckets"]["SEC_CLO_NORTH_AMERICA"]
    )
    assert buckets["SEC_RMBS_EUROPE"].capital == pytest.approx(
        expected["buckets"]["SEC_RMBS_EUROPE"]
    )
    assert buckets["SEC_CLO_NORTH_AMERICA"].hbr.ratio == pytest.approx(1.0)
    assert buckets["SEC_RMBS_EUROPE"].hbr.ratio == pytest.approx(expected["rmbs_hbr"])
    rejected = tuple(
        rejected for net_jtd in result.net_jtds for rejected in net_jtd.rejected_offsets
    )
    assert {item.reason_code for item in rejected} == {
        "SEC_NON_CTP_OFFSET_REQUIRES_SAME_POOL_TRANCHE_OR_REPLICATION"
    }
    validate_reconciliation(result)


def test_securitisation_non_ctp_exact_pool_and_tranche_offsets_across_maturity() -> None:
    long_position = _sec_position(
        "long-mezz",
        DefaultDirection.LONG,
        market_value=100.0,
        issuer_id="clo-2026-1",
        tranche_id="mezz",
    )
    short_position = _sec_position(
        "short-mezz",
        DefaultDirection.SHORT,
        market_value=40.0,
        issuer_id="clo-2026-1",
        tranche_id="mezz",
        maturity_years=0.5,
    )

    result = calculate_drc_capital(
        (long_position, short_position),
        context=_context(
            securitisation_non_ctp_risk_weights={
                "long-mezz": 0.2,
                "short-mezz": 0.2,
            },
        ),
    )

    assert len(result.net_jtds) == 1
    assert result.net_jtds[0].net_direction is DefaultDirection.LONG
    assert result.net_jtds[0].net_amount == pytest.approx(80.0)
    assert result.total_drc == pytest.approx(16.0)


def test_securitisation_non_ctp_different_tranche_offset_is_audited() -> None:
    long_position = _sec_position(
        "long-senior",
        DefaultDirection.LONG,
        market_value=100.0,
        issuer_id="clo-2026-1",
        tranche_id="senior",
    )
    short_position = _sec_position(
        "short-mezz",
        DefaultDirection.SHORT,
        market_value=40.0,
        issuer_id="clo-2026-1",
        tranche_id="mezz",
    )

    result = calculate_drc_capital(
        (long_position, short_position),
        context=_context(
            securitisation_non_ctp_risk_weights={
                "long-senior": 0.1,
                "short-mezz": 0.1,
            },
        ),
    )

    assert len(result.net_jtds) == 2
    rejected = tuple(
        rejected for net_jtd in result.net_jtds for rejected in net_jtd.rejected_offsets
    )
    assert rejected
    assert {item.reason_code for item in rejected} == {
        "SEC_NON_CTP_OFFSET_REQUIRES_SAME_POOL_TRANCHE_OR_REPLICATION"
    }
    assert result.total_drc == pytest.approx(7.142857142857142)


def test_securitisation_non_ctp_explicit_replication_group_can_offset() -> None:
    long_position = _sec_position(
        "long-rep",
        DefaultDirection.LONG,
        market_value=100.0,
        issuer_id="clo-2026-1",
        tranche_id="0-15",
    )
    short_position = _sec_position(
        "short-rep",
        DefaultDirection.SHORT,
        market_value=40.0,
        issuer_id="clo-2026-1",
        tranche_id="0-3",
    )

    result = calculate_drc_capital(
        (long_position, short_position),
        context=_context(
            securitisation_non_ctp_risk_weights={
                "long-rep": 0.2,
                "short-rep": 0.2,
            },
            securitisation_non_ctp_offset_groups={
                "long-rep": "replicated-clo-2026-1-0-15",
                "short-rep": "replicated-clo-2026-1-0-15",
            },
        ),
    )

    assert len(result.net_jtds) == 1
    assert result.net_jtds[0].net_amount == pytest.approx(60.0)
    assert result.total_drc == pytest.approx(12.0)


def test_securitisation_non_ctp_bucket_floor_applies() -> None:
    long_position = _sec_position(
        "small-long",
        DefaultDirection.LONG,
        market_value=10.0,
        issuer_id="rmbs-2026-1",
        tranche_id="a",
        bucket_key="SEC_RMBS_EUROPE",
    )
    short_position = _sec_position(
        "large-short",
        DefaultDirection.SHORT,
        market_value=100.0,
        issuer_id="rmbs-2026-2",
        tranche_id="a",
        bucket_key="SEC_RMBS_EUROPE",
    )

    result = calculate_drc_capital(
        (long_position, short_position),
        context=_context(
            securitisation_non_ctp_risk_weights={
                "small-long": 0.1,
                "large-short": 1.0,
            },
        ),
    )

    bucket = result.categories[0].bucket_results[0]
    assert bucket.capital == 0.0
    assert bucket.floor_applied is True
    assert any(branch.branch_type.value == "FLOOR" for branch in bucket.branch_metadata)
    validate_reconciliation(result)


def test_securitisation_non_ctp_missing_market_value_fails_closed() -> None:
    position = replace(
        _sec_position("missing-mv", DefaultDirection.LONG, market_value=100.0),
        market_value=None,
    )

    with pytest.raises(DrcInputError, match="requires market_value"):
        calculate_drc_capital(
            (position,),
            context=_context(
                securitisation_non_ctp_risk_weights={"missing-mv": 0.2},
            ),
        )


def test_securitisation_non_ctp_missing_risk_weight_fails_closed() -> None:
    position = _sec_position("missing-weight", DefaultDirection.LONG, market_value=100.0)

    with pytest.raises(DrcInputError, match=r"context\.securitisation_non_ctp_risk_weights"):
        calculate_drc_capital((position,), context=_context())


def test_securitisation_non_ctp_mixed_risk_weights_in_net_group_fail_closed() -> None:
    long_position = _sec_position("long-mixed", DefaultDirection.LONG, market_value=100.0)
    short_position = _sec_position("short-mixed", DefaultDirection.SHORT, market_value=40.0)

    with pytest.raises(DrcInputError, match="exactly one risk weight"):
        calculate_drc_capital(
            (long_position, short_position),
            context=_context(
                securitisation_non_ctp_risk_weights={
                    "long-mixed": 0.2,
                    "short-mixed": 0.25,
                },
                securitisation_non_ctp_offset_groups={
                    "long-mixed": "same-replication",
                    "short-mixed": "same-replication",
                },
            ),
        )


def test_securitisation_non_ctp_invalid_bucket_fails_closed() -> None:
    position = _sec_position(
        "bad-bucket",
        DefaultDirection.LONG,
        market_value=100.0,
        bucket_key="SEC_UNKNOWN",
    )

    with pytest.raises(DrcInputError, match="US_NPR_210_C_3_I_II"):
        calculate_drc_capital(
            (position,),
            context=_context(
                securitisation_non_ctp_risk_weights={"bad-bucket": 0.2},
            ),
        )


def test_profile_supports_securitisation_non_ctp() -> None:
    profile = get_rule_profile(US_NPR_2_0_PROFILE_ID)

    assert DrcRiskClass.SECURITISATION_NON_CTP in profile.supported_risk_classes


def _context(
    *,
    securitisation_non_ctp_risk_weights: dict[str, float] | None = None,
    securitisation_non_ctp_offset_groups: dict[str, str] | None = None,
) -> DrcCalculationContext:
    return DrcCalculationContext(
        run_id="run-sec-non-ctp",
        calculation_date=date(2026, 5, 29),
        base_currency="USD",
        profile_id=US_NPR_2_0_PROFILE_ID,
        securitisation_non_ctp_risk_weights={}
        if securitisation_non_ctp_risk_weights is None
        else securitisation_non_ctp_risk_weights,
        securitisation_non_ctp_offset_groups={}
        if securitisation_non_ctp_offset_groups is None
        else securitisation_non_ctp_offset_groups,
    )


def _sec_position(
    position_id: str,
    direction: DefaultDirection,
    *,
    market_value: float,
    bucket_key: str = "SEC_CLO_NORTH_AMERICA",
    issuer_id: str | None = "clo-2026-1",
    tranche_id: str | None = "mezz",
    maturity_years: float = 1.0,
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
        maturity_years=maturity_years,
        currency="USD",
        lineage=DrcSourceLineage(
            source_system="synthetic",
            source_file="securitisation.csv",
            source_row_id=f"row-{position_id}",
            source_column_map={"position_id": "position_id"},
        ),
        citation_ids=("US_NPR_210_C_1",),
    )


def _load_securitisation_fixture() -> dict[str, Any]:
    fixture_dir = Path(__file__).resolve().parent / "fixtures" / "drc_sec_nonctp_v1"
    payload = json.loads((fixture_dir / "positions.json").read_text(encoding="utf-8"))
    expected = json.loads((fixture_dir / "expected_outputs.json").read_text(encoding="utf-8"))
    context_raw = payload["context"]
    positions = tuple(_position_from_dict(raw) for raw in payload["positions"])
    context = DrcCalculationContext(
        run_id=context_raw["run_id"],
        calculation_date=date.fromisoformat(context_raw["calculation_date"]),
        base_currency=context_raw["base_currency"],
        profile_id=context_raw["profile_id"],
        securitisation_non_ctp_risk_weights=context_raw["securitisation_non_ctp_risk_weights"],
    )
    return {"positions": positions, "context": context, "expected": expected}


def _position_from_dict(raw: dict[str, Any]) -> DrcPosition:
    lineage = raw["lineage"]
    return DrcPosition(
        position_id=raw["position_id"],
        source_row_id=raw["source_row_id"],
        desk_id=raw["desk_id"],
        legal_entity=raw["legal_entity"],
        risk_class=raw["risk_class"],
        instrument_type=raw["instrument_type"],
        default_direction=raw["default_direction"],
        issuer_id=raw.get("issuer_id"),
        tranche_id=raw.get("tranche_id"),
        index_series_id=raw.get("index_series_id"),
        bucket_key=raw["bucket_key"],
        seniority=raw.get("seniority"),
        credit_quality=raw.get("credit_quality"),
        notional=float(raw["notional"]),
        market_value=None if raw.get("market_value") is None else float(raw["market_value"]),
        cumulative_pnl=raw.get("cumulative_pnl"),
        maturity_years=float(raw["maturity_years"]),
        currency=raw["currency"],
        lineage=DrcSourceLineage(
            source_system=lineage["source_system"],
            source_file=lineage["source_file"],
            source_row_id=lineage["source_row_id"],
            source_column_map=dict(lineage.get("source_column_map") or {}),
        ),
        citation_ids=tuple(raw["citation_ids"]),
    )
