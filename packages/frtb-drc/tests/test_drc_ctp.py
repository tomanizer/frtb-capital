from __future__ import annotations

import json
from dataclasses import replace
from datetime import date
from pathlib import Path
from typing import Any

import pytest
from frtb_drc import (
    BASEL_MAR22_PROFILE_ID,
    US_NPR_2_0_PROFILE_ID,
    DefaultDirection,
    DrcCalculationContext,
    DrcInputError,
    DrcInstrumentType,
    DrcPosition,
    DrcRiskClass,
    DrcRiskWeightEvidence,
    DrcSourceLineage,
    calculate_drc_capital,
    risk_weight_evidence_by_position,
    validate_reconciliation,
)

from tests.drc_fixture_helpers import (
    drc_position_from_dict,
    drc_risk_weight_evidence_from_dict,
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


def test_ctp_consumes_cited_risk_weight_evidence() -> None:
    position = _ctp_position(
        "long-evidence",
        DefaultDirection.LONG,
        market_value=125.0,
        bucket_key="CDX_NA_IG",
        index_series_id="CDX.NA.IG.S18",
        tranche_id="10-15",
    )
    evidence = _risk_weight_evidence(position, risk_weight=0.2)

    result = calculate_drc_capital(
        (position,),
        context=_context(
            ctp_risk_weight_evidence=risk_weight_evidence_by_position((evidence,)),
        ),
    )

    assert result.total_drc == pytest.approx(25.0)
    assert result.risk_weight_evidence == (evidence,)
    assert result.risk_weight_evidence[0].source_method == "upstream-ctp-securitisation"


def test_basel_ctp_consumes_cited_risk_weight_evidence_without_us_citations() -> None:
    position = replace(
        _ctp_position(
            "basel-long-evidence",
            DefaultDirection.LONG,
            market_value=125.0,
            bucket_key="CDX_NA_IG",
            index_series_id="CDX.NA.IG.S18",
            tranche_id="10-15",
        ),
        citation_ids=("BASEL_MAR22_36", "BASEL_MAR22_42"),
    )
    evidence = _risk_weight_evidence(
        position,
        risk_weight=0.2,
        source_profile_id=BASEL_MAR22_PROFILE_ID,
        source_table="BASEL_MAR22_CTP_BANKING_BOOK_SECURITISATION_RW",
        source_method="upstream-basel-ctp-decomposition",
        citation_ids=("BASEL_MAR22_42",),
    )

    result = calculate_drc_capital(
        (position,),
        context=_context(
            profile_id=BASEL_MAR22_PROFILE_ID,
            ctp_risk_weight_evidence=risk_weight_evidence_by_position((evidence,)),
        ),
    )

    assert result.total_drc == pytest.approx(25.0)
    assert result.risk_weight_evidence == (evidence,)
    assert "BASEL_MAR22_42" in result.citations
    assert "BASEL_MAR22_45" in result.citations
    assert not any(citation.startswith("US_NPR") for citation in result.citations)


def test_basel_ctp_rejects_legacy_float_risk_weight_map() -> None:
    position = replace(
        _ctp_position(
            "basel-legacy-weight",
            DefaultDirection.LONG,
            market_value=125.0,
            bucket_key="CDX_NA_IG",
            index_series_id="CDX.NA.IG.S18",
            tranche_id="10-15",
        ),
        citation_ids=("BASEL_MAR22_36", "BASEL_MAR22_42"),
    )

    with pytest.raises(DrcInputError, match="legacy float maps are only supported"):
        calculate_drc_capital(
            (position,),
            context=_context(
                profile_id=BASEL_MAR22_PROFILE_ID,
                ctp_risk_weights={position.position_id: 0.2},
            ),
        )


def test_ctp_stale_evidence_fails_closed() -> None:
    position = _ctp_position(
        "stale-evidence",
        DefaultDirection.LONG,
        market_value=125.0,
        bucket_key="CDX_NA_IG",
        index_series_id="CDX.NA.IG.S18",
    )
    evidence = _risk_weight_evidence(position, risk_weight=0.2, is_stale=True)

    with pytest.raises(DrcInputError, match="is stale"):
        calculate_drc_capital(
            (position,),
            context=_context(
                ctp_risk_weight_evidence=risk_weight_evidence_by_position((evidence,)),
            ),
        )


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


def test_basel_ctp_fixture_cross_tranche_replication_matches_hand_checked_expected() -> None:
    fixture = _load_basel_ctp_fixture()

    result = calculate_drc_capital(fixture["positions"], context=fixture["context"])
    expected = fixture["expected"]
    buckets = {bucket.bucket_key: bucket for bucket in result.categories[0].bucket_results}

    assert result.input_count == expected["input_count"]
    assert result.total_drc == pytest.approx(expected["total_drc"])
    assert result.categories[0].capital == pytest.approx(expected["category_capital"])
    assert buckets["CDX_NA_IG"].capital == pytest.approx(expected["buckets"]["CDX_NA_IG"])
    assert buckets["CDX_HY"].capital == pytest.approx(expected["buckets"]["CDX_HY"])
    assert len(result.risk_weight_evidence) == result.input_count
    assert "BASEL_MAR22_42" in result.citations
    assert not any(citation.startswith("US_NPR") for citation in result.citations)
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


def test_ctp_short_maturity_is_not_nonsec_scaled() -> None:
    position = _ctp_position(
        "short-maturity-ctp",
        DefaultDirection.LONG,
        market_value=100.0,
        bucket_key="CDX_NA_IG",
        index_series_id="CDX.NA.IG.S18",
        maturity_years=0.5,
    )

    result = calculate_drc_capital(
        (position,),
        context=_context(ctp_risk_weights={position.position_id: 0.2}),
    )

    assert result.maturity_scaled_jtds[0].maturity_weight == 1.0
    assert result.maturity_scaled_jtds[0].scaled_jtd == pytest.approx(100.0)
    assert result.total_drc == pytest.approx(20.0)
    assert "US_NPR_210_D_1" in result.maturity_scaled_jtds[0].citations
    validate_reconciliation(result)


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


def _context(
    *,
    profile_id: str = US_NPR_2_0_PROFILE_ID,
    ctp_risk_weights: dict[str, float] | None = None,
    ctp_risk_weight_evidence: dict[str, DrcRiskWeightEvidence] | None = None,
    ctp_offset_groups: dict[str, str] | None = None,
) -> DrcCalculationContext:
    return DrcCalculationContext(
        run_id="run-ctp",
        calculation_date=date(2026, 5, 29),
        base_currency="USD",
        profile_id=profile_id,
        ctp_risk_weights={} if ctp_risk_weights is None else ctp_risk_weights,
        ctp_risk_weight_evidence={}
        if ctp_risk_weight_evidence is None
        else ctp_risk_weight_evidence,
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


def _risk_weight_evidence(
    position: DrcPosition,
    *,
    risk_weight: float,
    source_profile_id: str = US_NPR_2_0_PROFILE_ID,
    source_table: str = "US_NPR_CTP_RW",
    source_method: str = "upstream-ctp-securitisation",
    citation_ids: tuple[str, ...] = ("US_NPR_210_D_3_IV_D",),
    is_stale: bool = False,
) -> DrcRiskWeightEvidence:
    return DrcRiskWeightEvidence(
        position_id=position.position_id,
        risk_class=DrcRiskClass.CORRELATION_TRADING_PORTFOLIO,
        source_profile_id=source_profile_id,
        source_table=source_table,
        source_method=source_method,
        effective_risk_weight=risk_weight,
        as_of_date=date(2026, 5, 29),
        source_id="ctp-rw-source",
        lineage=DrcSourceLineage(
            source_system="synthetic-risk-weight-engine",
            source_file="ctp-risk-weights.csv",
            source_row_id=f"rw-{position.position_id}",
            source_column_map={"effective_risk_weight": "risk_weight"},
        ),
        citation_ids=citation_ids,
        is_stale=is_stale,
    )


def _load_ctp_fixture() -> dict[str, Any]:
    return _load_ctp_fixture_named("drc_ctp_v1")


def _load_basel_ctp_fixture() -> dict[str, Any]:
    return _load_ctp_fixture_named("drc_basel_ctp_v1")


def _load_ctp_fixture_named(fixture_name: str) -> dict[str, Any]:
    fixture_dir = Path(__file__).resolve().parent / "fixtures" / fixture_name
    payload = json.loads((fixture_dir / "positions.json").read_text(encoding="utf-8"))
    expected = json.loads((fixture_dir / "expected_outputs.json").read_text(encoding="utf-8"))
    context_raw = payload["context"]
    positions = tuple(drc_position_from_dict(raw) for raw in payload["positions"])
    context = DrcCalculationContext(
        run_id=context_raw["run_id"],
        calculation_date=date.fromisoformat(context_raw["calculation_date"]),
        base_currency=context_raw["base_currency"],
        profile_id=context_raw["profile_id"],
        ctp_risk_weights=context_raw.get("ctp_risk_weights", {}),
        ctp_risk_weight_evidence=risk_weight_evidence_by_position(
            drc_risk_weight_evidence_from_dict(raw)
            for raw in context_raw.get("ctp_risk_weight_evidence", ())
        ),
        ctp_offset_groups=context_raw.get("ctp_offset_groups", {}),
    )
    return {"positions": positions, "context": context, "expected": expected}
