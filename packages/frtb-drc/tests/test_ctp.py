from __future__ import annotations

import json
from dataclasses import replace
from datetime import date
from pathlib import Path
from typing import Any

import pytest
from frtb_common import UnsupportedRegulatoryFeatureError
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


def test_ctp_unhedged_book_uses_market_value_and_context_risk_weight() -> None:
    position = _ctp_position(
        "long-index-tranche",
        DefaultDirection.LONG,
        market_value=125.0,
        bucket_key="CDX_NA_IG",
        index_series_id="CDX.NA.IG.S18",
        tranche_id="10-15",
    )

    result = calculate_drc_capital(
        (position,),
        context=_context(ctp_risk_weights={position.position_id: 0.2}),
    )

    assert result.total_drc == pytest.approx(25.0)
    assert result.categories[0].risk_class is DrcRiskClass.CORRELATION_TRADING_PORTFOLIO
    assert result.gross_jtds[0].gross_jtd == pytest.approx(125.0)
    assert result.gross_jtds[0].lgd_source.startswith("CTP gross default exposure")
    assert result.categories[0].bucket_results[0].hbr.ratio == pytest.approx(1.0)
    assert "US_NPR_210_D_1" in result.citations
    assert "US_NPR_210_D_3_IV_D" in result.citations
    validate_reconciliation(result)


def test_ctp_fixture_cross_tranche_replication_matches_hand_checked_expected() -> None:
    fixture = _load_ctp_fixture()

    result = calculate_drc_capital(fixture["positions"], context=fixture["context"])
    expected = fixture["expected"]
    buckets = {bucket.bucket_key: bucket for bucket in result.categories[0].bucket_results}

    assert result.input_count == expected["input_count"]
    assert result.total_drc == pytest.approx(expected["total_drc"])
    assert result.categories[0].capital == pytest.approx(expected["category_capital"])
    assert buckets["CDX_NA_IG"].capital == pytest.approx(expected["buckets"]["CDX_NA_IG"])
    assert buckets["CDX_HY"].capital == pytest.approx(expected["buckets"]["CDX_HY"])
    assert buckets["CDX_HY"].capital < 0.0
    assert buckets["CDX_NA_IG"].hbr.ratio == pytest.approx(expected["ctp_hbr"])
    assert any(
        branch.branch_id == "category-ctp-cross-index-aggregation"
        for branch in result.categories[0].branch_metadata
    )
    validate_reconciliation(result)


def test_ctp_disallowed_cross_tranche_offset_is_audited() -> None:
    long_position = _ctp_position(
        "long-10-15",
        DefaultDirection.LONG,
        market_value=100.0,
        bucket_key="CDX_NA_IG",
        index_series_id="CDX.NA.IG.S18",
        tranche_id="10-15",
    )
    short_position = _ctp_position(
        "short-10-12",
        DefaultDirection.SHORT,
        market_value=40.0,
        bucket_key="CDX_NA_IG",
        index_series_id="CDX.NA.IG.S18",
        tranche_id="10-12",
    )

    result = calculate_drc_capital(
        (long_position, short_position),
        context=_context(
            ctp_risk_weights={
                "long-10-15": 0.2,
                "short-10-12": 0.2,
            }
        ),
    )

    assert len(result.net_jtds) == 2
    rejected = tuple(
        rejected for net_jtd in result.net_jtds for rejected in net_jtd.rejected_offsets
    )
    assert rejected
    assert {item.reason_code for item in rejected} == {
        "CTP_OFFSET_REQUIRES_EXACT_MATCH_OR_EXPLICIT_REPLICATION"
    }
    assert result.total_drc == pytest.approx(14.285714285714285)


def test_ctp_category_floor_applies_after_negative_bucket_recognition() -> None:
    long_position = _ctp_position(
        "small-long",
        DefaultDirection.LONG,
        market_value=10.0,
        bucket_key="CDX_NA_IG",
        index_series_id="CDX.NA.IG.S18",
    )
    short_position = _ctp_position(
        "large-short",
        DefaultDirection.SHORT,
        market_value=100.0,
        bucket_key="CDX_HY",
        index_series_id="CDX.HY.S40",
    )

    result = calculate_drc_capital(
        (long_position, short_position),
        context=_context(
            ctp_risk_weights={
                "small-long": 0.1,
                "large-short": 1.0,
            }
        ),
    )

    assert result.total_drc == 0.0
    assert any(bucket.capital < 0.0 for bucket in result.categories[0].bucket_results)
    assert any(
        branch.branch_type.value == "FLOOR" for branch in result.categories[0].branch_metadata
    )
    validate_reconciliation(result)


def test_ctp_missing_market_value_fails_closed() -> None:
    position = _ctp_position(
        "missing-mv",
        DefaultDirection.LONG,
        market_value=0.0,
        bucket_key="CDX_NA_IG",
        index_series_id="CDX.NA.IG.S18",
    )
    position = replace(position, market_value=None)

    with pytest.raises(DrcInputError, match="requires market_value"):
        calculate_drc_capital(
            (position,),
            context=_context(ctp_risk_weights={"missing-mv": 0.2}),
        )


def test_ctp_missing_risk_weight_fails_closed() -> None:
    position = _ctp_position(
        "missing-weight",
        DefaultDirection.LONG,
        market_value=100.0,
        bucket_key="CDX_NA_IG",
        index_series_id="CDX.NA.IG.S18",
    )

    with pytest.raises(DrcInputError, match=r"context\.ctp_risk_weights is required"):
        calculate_drc_capital((position,), context=_context())


def test_ctp_net_group_rejects_mixed_risk_weights() -> None:
    long_position = _ctp_position(
        "long-rep",
        DefaultDirection.LONG,
        market_value=100.0,
        bucket_key="CDX_NA_IG",
        index_series_id="CDX.NA.IG.S18",
        tranche_id="10-15",
    )
    short_position = _ctp_position(
        "short-rep",
        DefaultDirection.SHORT,
        market_value=40.0,
        bucket_key="CDX_NA_IG",
        index_series_id="CDX.NA.IG.S18",
        tranche_id="10-12",
    )

    with pytest.raises(DrcInputError, match="exactly one risk weight"):
        calculate_drc_capital(
            (long_position, short_position),
            context=_context(
                ctp_risk_weights={"long-rep": 0.2, "short-rep": 0.25},
                ctp_offset_groups={
                    "long-rep": "replicated-10-15",
                    "short-rep": "replicated-10-15",
                },
            ),
        )


def test_securitisation_non_ctp_remains_unsupported() -> None:
    profile = get_rule_profile(US_NPR_2_0_PROFILE_ID)

    assert DrcRiskClass.SECURITISATION_NON_CTP not in profile.supported_risk_classes
    with pytest.raises(UnsupportedRegulatoryFeatureError, match="securitisation non-CTP"):
        calculate_drc_capital(
            (
                _ctp_position(
                    "sec-non-ctp",
                    DefaultDirection.LONG,
                    market_value=100.0,
                    bucket_key="CLO_NA",
                    risk_class=DrcRiskClass.SECURITISATION_NON_CTP,
                    index_series_id=None,
                    tranche_id="0-3",
                ),
            ),
            context=_context(),
        )


def _context(
    *,
    ctp_risk_weights: dict[str, float] | None = None,
    ctp_offset_groups: dict[str, str] | None = None,
) -> DrcCalculationContext:
    return DrcCalculationContext(
        run_id="run-ctp",
        calculation_date=date(2026, 5, 29),
        base_currency="USD",
        profile_id=US_NPR_2_0_PROFILE_ID,
        ctp_risk_weights={} if ctp_risk_weights is None else ctp_risk_weights,
        ctp_offset_groups={} if ctp_offset_groups is None else ctp_offset_groups,
    )


def _ctp_position(
    position_id: str,
    direction: DefaultDirection,
    *,
    market_value: float,
    bucket_key: str,
    risk_class: DrcRiskClass = DrcRiskClass.CORRELATION_TRADING_PORTFOLIO,
    instrument_type: DrcInstrumentType = DrcInstrumentType.INDEX_TRANCHE,
    issuer_id: str | None = None,
    index_series_id: str | None = None,
    tranche_id: str | None = None,
    maturity_years: float = 1.0,
) -> DrcPosition:
    return DrcPosition(
        position_id=position_id,
        source_row_id=f"row-{position_id}",
        desk_id="ctp-desk",
        legal_entity="bank-na",
        risk_class=risk_class,
        instrument_type=instrument_type,
        default_direction=direction,
        issuer_id=issuer_id,
        tranche_id=tranche_id,
        index_series_id=index_series_id,
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
            source_file="ctp.csv",
            source_row_id=f"row-{position_id}",
            source_column_map={"position_id": "position_id"},
        ),
        citation_ids=("US_NPR_210_D_1",),
    )


def _load_ctp_fixture() -> dict[str, Any]:
    fixture_dir = Path(__file__).resolve().parent / "fixtures" / "drc_ctp_v1"
    payload = json.loads((fixture_dir / "positions.json").read_text(encoding="utf-8"))
    expected = json.loads((fixture_dir / "expected_outputs.json").read_text(encoding="utf-8"))
    context_raw = payload["context"]
    positions = tuple(_position_from_dict(raw) for raw in payload["positions"])
    context = DrcCalculationContext(
        run_id=context_raw["run_id"],
        calculation_date=date.fromisoformat(context_raw["calculation_date"]),
        base_currency=context_raw["base_currency"],
        profile_id=context_raw["profile_id"],
        ctp_risk_weights=context_raw["ctp_risk_weights"],
        ctp_offset_groups=context_raw["ctp_offset_groups"],
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
