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
    DrcFairValueCapEvidence,
    DrcInputError,
    DrcInstrumentType,
    DrcPosition,
    DrcRiskClass,
    DrcRiskWeightEvidence,
    DrcSourceLineage,
    calculate_drc_capital,
    fair_value_cap_evidence_by_position,
    get_rule_profile,
    risk_weight_evidence_by_position,
    validate_reconciliation,
)

from tests.drc_fixture_helpers import (
    drc_fair_value_cap_evidence_from_dict,
    drc_position_from_dict,
    drc_risk_weight_evidence_from_dict,
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
    assert result.gross_jtds[0].branch_metadata[0].branch_type.value == "NORMAL"
    assert "no fair-value cap evidence" in result.gross_jtds[0].branch_metadata[0].reason
    assert "LGD is embedded" in result.gross_jtds[0].lgd_source
    assert result.categories[0].bucket_results[0].hbr.ratio == pytest.approx(1.0)
    assert "US_NPR_210_C_1" in result.citations
    assert "US_NPR_210_C_3_III" in result.citations
    validate_reconciliation(result)


def test_securitisation_non_ctp_applies_eligible_fair_value_cap() -> None:
    position = _sec_position("capped-sec", DefaultDirection.LONG, market_value=125.0)
    cap_evidence = _fair_value_cap_evidence(position, fair_value_cap_amount=80.0)

    result = calculate_drc_capital(
        (position,),
        context=_context(
            securitisation_non_ctp_risk_weights={position.position_id: 0.2},
            securitisation_non_ctp_fair_value_cap_evidence=fair_value_cap_evidence_by_position(
                (cap_evidence,)
            ),
        ),
    )

    assert result.gross_jtds[0].gross_jtd == pytest.approx(80.0)
    assert result.maturity_scaled_jtds[0].scaled_jtd == pytest.approx(80.0)
    assert result.total_drc == pytest.approx(16.0)
    assert result.fair_value_cap_evidence == (cap_evidence,)
    branch = result.gross_jtds[0].branch_metadata[0]
    assert branch.branch_type.value == "CAP"
    assert "cap_amount=80.0" in branch.reason
    assert "BASEL_MAR22_34" in result.citations
    validate_reconciliation(result)


def test_securitisation_non_ctp_eligible_fair_value_cap_can_be_non_binding() -> None:
    position = _sec_position("not-binding-cap", DefaultDirection.LONG, market_value=75.0)
    cap_evidence = _fair_value_cap_evidence(position, fair_value_cap_amount=80.0)

    result = calculate_drc_capital(
        (position,),
        context=_context(
            securitisation_non_ctp_risk_weights={position.position_id: 0.2},
            securitisation_non_ctp_fair_value_cap_evidence=fair_value_cap_evidence_by_position(
                (cap_evidence,)
            ),
        ),
    )

    assert result.gross_jtds[0].gross_jtd == pytest.approx(75.0)
    assert result.total_drc == pytest.approx(15.0)
    assert result.gross_jtds[0].branch_metadata[0].branch_type.value == "NORMAL"
    assert "not binding" in result.gross_jtds[0].branch_metadata[0].reason


def test_securitisation_non_ctp_ineligible_fair_value_cap_does_not_apply() -> None:
    position = _sec_position("ineligible-cap", DefaultDirection.LONG, market_value=125.0)
    cap_evidence = _fair_value_cap_evidence(
        position,
        fair_value_cap_amount=None,
        eligible=False,
        eligibility_reason="synthetic non-cash securitisation test case",
    )

    result = calculate_drc_capital(
        (position,),
        context=_context(
            securitisation_non_ctp_risk_weights={position.position_id: 0.2},
            securitisation_non_ctp_fair_value_cap_evidence=fair_value_cap_evidence_by_position(
                (cap_evidence,)
            ),
        ),
    )

    assert result.gross_jtds[0].gross_jtd == pytest.approx(125.0)
    assert result.total_drc == pytest.approx(25.0)
    assert result.fair_value_cap_evidence == (cap_evidence,)
    assert "ineligible" in result.gross_jtds[0].branch_metadata[0].reason


def test_securitisation_non_ctp_missing_cap_amount_fails_closed() -> None:
    position = _sec_position("missing-cap-amount", DefaultDirection.LONG, market_value=100.0)
    cap_evidence = _fair_value_cap_evidence(position, fair_value_cap_amount=None)

    with pytest.raises(DrcInputError, match="fair_value_cap_amount is required"):
        calculate_drc_capital(
            (position,),
            context=_context(
                securitisation_non_ctp_risk_weights={position.position_id: 0.2},
                securitisation_non_ctp_fair_value_cap_evidence=fair_value_cap_evidence_by_position(
                    (cap_evidence,)
                ),
            ),
        )


def test_securitisation_non_ctp_stale_cap_evidence_fails_closed() -> None:
    position = _sec_position("stale-cap", DefaultDirection.LONG, market_value=100.0)
    cap_evidence = _fair_value_cap_evidence(position, fair_value_cap_amount=80.0, is_stale=True)

    with pytest.raises(DrcInputError, match="is stale"):
        calculate_drc_capital(
            (position,),
            context=_context(
                securitisation_non_ctp_risk_weights={position.position_id: 0.2},
                securitisation_non_ctp_fair_value_cap_evidence=fair_value_cap_evidence_by_position(
                    (cap_evidence,)
                ),
            ),
        )


@pytest.mark.parametrize(
    ("field_name", "replacement", "message"),
    [
        ("as_of_date", None, "as_of_date is required"),
        ("eligible", None, "eligible is required"),
    ],
)
def test_securitisation_non_ctp_none_cap_evidence_fields_fail_closed(
    field_name: str,
    replacement: object,
    message: str,
) -> None:
    position = _sec_position("none-cap-field", DefaultDirection.LONG, market_value=100.0)
    cap_evidence = replace(
        _fair_value_cap_evidence(position, fair_value_cap_amount=80.0),
        **{field_name: replacement},
    )

    with pytest.raises(DrcInputError, match=message):
        calculate_drc_capital(
            (position,),
            context=_context(
                securitisation_non_ctp_risk_weights={position.position_id: 0.2},
                securitisation_non_ctp_fair_value_cap_evidence=fair_value_cap_evidence_by_position(
                    (cap_evidence,)
                ),
            ),
        )


def test_securitisation_non_ctp_unused_cap_evidence_fails_closed() -> None:
    position = _sec_position("used-cap-position", DefaultDirection.LONG, market_value=100.0)
    unused = _sec_position("unused-cap-position", DefaultDirection.LONG, market_value=100.0)

    with pytest.raises(DrcInputError, match="fair_value_cap_evidence contains unused"):
        calculate_drc_capital(
            (position,),
            context=_context(
                securitisation_non_ctp_risk_weights={position.position_id: 0.2},
                securitisation_non_ctp_fair_value_cap_evidence=fair_value_cap_evidence_by_position(
                    (_fair_value_cap_evidence(unused, fair_value_cap_amount=80.0),)
                ),
            ),
        )


def test_securitisation_non_ctp_consumes_cited_risk_weight_evidence() -> None:
    position = _sec_position("long-evidence", DefaultDirection.LONG, market_value=125.0)
    evidence = _risk_weight_evidence(position, risk_weight=0.16)

    result = calculate_drc_capital(
        (position,),
        context=_context(
            securitisation_non_ctp_risk_weight_evidence=risk_weight_evidence_by_position(
                (evidence,)
            ),
        ),
    )

    assert result.total_drc == pytest.approx(20.0)
    assert result.risk_weight_evidence == (evidence,)
    assert result.risk_weight_evidence[0].source_table == "US_NPR_SECURITISATION_RW"
    assert "US_NPR_210_C_3_III" in result.citations


def test_securitisation_non_ctp_evidence_changes_input_hash() -> None:
    position = _sec_position("hash-evidence", DefaultDirection.LONG, market_value=125.0)
    first = _risk_weight_evidence(position, risk_weight=0.16, source_id="rw-source-a")
    second = _risk_weight_evidence(position, risk_weight=0.16, source_id="rw-source-b")

    first_result = calculate_drc_capital(
        (position,),
        context=_context(
            securitisation_non_ctp_risk_weight_evidence=risk_weight_evidence_by_position((first,)),
        ),
    )
    second_result = calculate_drc_capital(
        (position,),
        context=_context(
            securitisation_non_ctp_risk_weight_evidence=risk_weight_evidence_by_position((second,)),
        ),
    )

    assert first_result.input_hash != second_result.input_hash


def test_securitisation_non_ctp_duplicate_evidence_fails_closed() -> None:
    position = _sec_position("duplicate-evidence", DefaultDirection.LONG, market_value=100.0)

    with pytest.raises(DrcInputError, match="duplicate risk-weight evidence"):
        risk_weight_evidence_by_position(
            (
                _risk_weight_evidence(position, risk_weight=0.2, source_id="rw-a"),
                _risk_weight_evidence(position, risk_weight=0.2, source_id="rw-b"),
            )
        )


def test_securitisation_non_ctp_stale_evidence_fails_closed() -> None:
    position = _sec_position("stale-evidence", DefaultDirection.LONG, market_value=100.0)
    evidence = _risk_weight_evidence(position, risk_weight=0.2, is_stale=True)

    with pytest.raises(DrcInputError, match="is stale"):
        calculate_drc_capital(
            (position,),
            context=_context(
                securitisation_non_ctp_risk_weight_evidence=risk_weight_evidence_by_position(
                    (evidence,)
                ),
            ),
        )


def test_securitisation_non_ctp_uncited_evidence_fails_closed() -> None:
    position = _sec_position("uncited-evidence", DefaultDirection.LONG, market_value=100.0)
    evidence = _risk_weight_evidence(position, risk_weight=0.2, citation_ids=())

    with pytest.raises(DrcInputError, match="citation_ids must be non-empty"):
        calculate_drc_capital(
            (position,),
            context=_context(
                securitisation_non_ctp_risk_weight_evidence=risk_weight_evidence_by_position(
                    (evidence,)
                ),
            ),
        )


def test_securitisation_non_ctp_fixture_matches_hand_checked_expected() -> None:
    fixture = _load_securitisation_fixture("drc_sec_nonctp_v1")

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


def test_basel_securitisation_non_ctp_fixture_matches_hand_checked_expected() -> None:
    fixture = _load_securitisation_fixture("drc_basel_sec_nonctp_v1")

    result = calculate_drc_capital(fixture["positions"], context=fixture["context"])
    expected = fixture["expected"]
    buckets = {bucket.bucket_key: bucket for bucket in result.categories[0].bucket_results}

    assert result.profile_id == BASEL_MAR22_PROFILE_ID
    assert result.input_count == expected["input_count"]
    assert result.total_drc == pytest.approx(expected["total_drc"])
    assert result.categories[0].risk_class is DrcRiskClass.SECURITISATION_NON_CTP
    assert result.categories[0].capital == pytest.approx(expected["category_capital"])
    assert buckets["SEC_CLO_NORTH_AMERICA"].capital == pytest.approx(
        expected["buckets"]["SEC_CLO_NORTH_AMERICA"]
    )
    assert buckets["SEC_RMBS_EUROPE"].capital == pytest.approx(
        expected["buckets"]["SEC_RMBS_EUROPE"]
    )
    assert buckets["SEC_RMBS_EUROPE"].hbr.ratio == pytest.approx(expected["rmbs_hbr"])
    gross_by_position = {record.position_id: record.gross_jtd for record in result.gross_jtds}
    assert gross_by_position["long-rmbs-a"] == pytest.approx(
        expected["fair_value_capped_gross_jtd"]
    )
    assert len(result.risk_weight_evidence) == 4
    assert len(result.fair_value_cap_evidence) == 1
    assert "BASEL_MAR22_34" in result.citations
    assert "BASEL_MAR22_35" in result.citations
    assert not any(citation.startswith("US_NPR") for citation in result.citations)
    validate_reconciliation(result)


def test_basel_securitisation_non_ctp_rejects_legacy_raw_weight_map() -> None:
    position = _sec_position("basel-legacy-raw", DefaultDirection.LONG, market_value=100.0)

    with pytest.raises(DrcInputError, match="legacy float maps"):
        calculate_drc_capital(
            (position,),
            context=_context(
                profile_id=BASEL_MAR22_PROFILE_ID,
                securitisation_non_ctp_risk_weights={position.position_id: 0.2},
            ),
        )


def test_basel_securitisation_non_ctp_rejects_us_profile_evidence() -> None:
    position = _sec_position("basel-us-evidence", DefaultDirection.LONG, market_value=100.0)
    evidence = _risk_weight_evidence(position, risk_weight=0.2)

    with pytest.raises(DrcInputError, match="does not match context profile_id"):
        calculate_drc_capital(
            (position,),
            context=_context(
                profile_id=BASEL_MAR22_PROFILE_ID,
                securitisation_non_ctp_risk_weight_evidence=risk_weight_evidence_by_position(
                    (evidence,)
                ),
            ),
        )


def test_basel_securitisation_non_ctp_rejects_wrong_profile_citation() -> None:
    position = _sec_position("basel-us-citation", DefaultDirection.LONG, market_value=100.0)
    evidence = _risk_weight_evidence(
        position,
        risk_weight=0.2,
        source_profile_id=BASEL_MAR22_PROFILE_ID,
        citation_ids=("US_NPR_210_C_3_III",),
    )

    with pytest.raises(DrcInputError, match="outside profile BASEL_MAR22"):
        calculate_drc_capital(
            (position,),
            context=_context(
                profile_id=BASEL_MAR22_PROFILE_ID,
                securitisation_non_ctp_risk_weight_evidence=risk_weight_evidence_by_position(
                    (evidence,)
                ),
            ),
        )


def test_basel_securitisation_non_ctp_future_dated_evidence_fails_closed() -> None:
    position = _sec_position("basel-future-evidence", DefaultDirection.LONG, market_value=100.0)
    evidence = _risk_weight_evidence(
        position,
        risk_weight=0.2,
        source_profile_id=BASEL_MAR22_PROFILE_ID,
        as_of_date=date(2026, 5, 30),
        citation_ids=("BASEL_MAR22_34",),
    )

    with pytest.raises(DrcInputError, match="must not be after calculation_date"):
        calculate_drc_capital(
            (position,),
            context=_context(
                profile_id=BASEL_MAR22_PROFILE_ID,
                securitisation_non_ctp_risk_weight_evidence=risk_weight_evidence_by_position(
                    (evidence,)
                ),
            ),
        )


def test_basel_securitisation_non_ctp_wrong_risk_class_evidence_fails_closed() -> None:
    position = _sec_position("basel-wrong-risk-class", DefaultDirection.LONG, market_value=100.0)
    evidence = _risk_weight_evidence(
        position,
        risk_weight=0.2,
        risk_class=DrcRiskClass.CORRELATION_TRADING_PORTFOLIO,
        source_profile_id=BASEL_MAR22_PROFILE_ID,
        citation_ids=("BASEL_MAR22_34",),
    )

    with pytest.raises(DrcInputError, match="wrong risk_class"):
        calculate_drc_capital(
            (position,),
            context=_context(
                profile_id=BASEL_MAR22_PROFILE_ID,
                securitisation_non_ctp_risk_weight_evidence=risk_weight_evidence_by_position(
                    (evidence,)
                ),
            ),
        )


@pytest.mark.parametrize(
    ("risk_weight", "message"),
    [
        (float("inf"), "finite"),
        (-0.01, "non-negative"),
    ],
)
def test_basel_securitisation_non_ctp_non_finite_or_negative_evidence_fails_closed(
    risk_weight: float,
    message: str,
) -> None:
    position = _sec_position("basel-bad-weight", DefaultDirection.LONG, market_value=100.0)
    evidence = _risk_weight_evidence(
        position,
        risk_weight=risk_weight,
        source_profile_id=BASEL_MAR22_PROFILE_ID,
        citation_ids=("BASEL_MAR22_34",),
    )

    with pytest.raises(DrcInputError, match=message):
        calculate_drc_capital(
            (position,),
            context=_context(
                profile_id=BASEL_MAR22_PROFILE_ID,
                securitisation_non_ctp_risk_weight_evidence=risk_weight_evidence_by_position(
                    (evidence,)
                ),
            ),
        )


@pytest.mark.parametrize(
    ("is_stale", "citation_ids", "message"),
    [
        (True, ("BASEL_MAR22_34",), "is stale"),
        (False, (), "citation_ids must be non-empty"),
    ],
)
def test_basel_securitisation_non_ctp_stale_or_uncited_evidence_fails_closed(
    is_stale: bool,
    citation_ids: tuple[str, ...],
    message: str,
) -> None:
    position = _sec_position("basel-stale-uncited", DefaultDirection.LONG, market_value=100.0)
    evidence = _risk_weight_evidence(
        position,
        risk_weight=0.2,
        source_profile_id=BASEL_MAR22_PROFILE_ID,
        citation_ids=citation_ids,
        is_stale=is_stale,
    )

    with pytest.raises(DrcInputError, match=message):
        calculate_drc_capital(
            (position,),
            context=_context(
                profile_id=BASEL_MAR22_PROFILE_ID,
                securitisation_non_ctp_risk_weight_evidence=risk_weight_evidence_by_position(
                    (evidence,)
                ),
            ),
        )


def test_basel_securitisation_non_ctp_unused_evidence_fails_closed() -> None:
    position = _sec_position("basel-used-evidence", DefaultDirection.LONG, market_value=100.0)
    unused = _sec_position("basel-unused-evidence", DefaultDirection.LONG, market_value=100.0)
    used_evidence = _risk_weight_evidence(
        position,
        risk_weight=0.2,
        source_profile_id=BASEL_MAR22_PROFILE_ID,
        citation_ids=("BASEL_MAR22_34",),
    )
    unused_evidence = _risk_weight_evidence(
        unused,
        risk_weight=0.2,
        source_profile_id=BASEL_MAR22_PROFILE_ID,
        citation_ids=("BASEL_MAR22_34",),
    )

    with pytest.raises(DrcInputError, match="contains unused"):
        calculate_drc_capital(
            (position,),
            context=_context(
                profile_id=BASEL_MAR22_PROFILE_ID,
                securitisation_non_ctp_risk_weight_evidence=risk_weight_evidence_by_position(
                    (used_evidence, unused_evidence)
                ),
            ),
        )


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
    profile_id: str = US_NPR_2_0_PROFILE_ID,
    securitisation_non_ctp_risk_weights: dict[str, float] | None = None,
    securitisation_non_ctp_risk_weight_evidence: (dict[str, DrcRiskWeightEvidence] | None) = None,
    securitisation_non_ctp_fair_value_cap_evidence: (
        dict[str, DrcFairValueCapEvidence] | None
    ) = None,
    securitisation_non_ctp_offset_groups: dict[str, str] | None = None,
) -> DrcCalculationContext:
    return DrcCalculationContext(
        run_id="run-sec-non-ctp",
        calculation_date=date(2026, 5, 29),
        base_currency="USD",
        profile_id=profile_id,
        securitisation_non_ctp_risk_weights={}
        if securitisation_non_ctp_risk_weights is None
        else securitisation_non_ctp_risk_weights,
        securitisation_non_ctp_risk_weight_evidence={}
        if securitisation_non_ctp_risk_weight_evidence is None
        else securitisation_non_ctp_risk_weight_evidence,
        securitisation_non_ctp_fair_value_cap_evidence={}
        if securitisation_non_ctp_fair_value_cap_evidence is None
        else securitisation_non_ctp_fair_value_cap_evidence,
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


def _risk_weight_evidence(
    position: DrcPosition,
    *,
    risk_weight: float,
    risk_class: DrcRiskClass = DrcRiskClass.SECURITISATION_NON_CTP,
    source_profile_id: str = US_NPR_2_0_PROFILE_ID,
    source_id: str = "rw-source",
    as_of_date: date = date(2026, 5, 29),
    is_stale: bool = False,
    citation_ids: tuple[str, ...] = ("US_NPR_210_C_3_III",),
) -> DrcRiskWeightEvidence:
    return DrcRiskWeightEvidence(
        position_id=position.position_id,
        risk_class=risk_class,
        source_profile_id=source_profile_id,
        source_table=(
            "BASEL_MAR22_BANKING_BOOK_SECURITISATION_RW"
            if source_profile_id == BASEL_MAR22_PROFILE_ID
            else "US_NPR_SECURITISATION_RW"
        ),
        source_method="upstream-banking-book-securitisation",
        effective_risk_weight=risk_weight,
        as_of_date=as_of_date,
        source_id=source_id,
        lineage=DrcSourceLineage(
            source_system="synthetic-risk-weight-engine",
            source_file="securitisation-risk-weights.csv",
            source_row_id=f"rw-{position.position_id}",
            source_column_map={"effective_risk_weight": "risk_weight"},
        ),
        citation_ids=citation_ids,
        is_stale=is_stale,
    )


def _fair_value_cap_evidence(
    position: DrcPosition,
    *,
    fair_value_cap_amount: float | None,
    source_profile_id: str = US_NPR_2_0_PROFILE_ID,
    eligible: bool = True,
    eligibility_reason: str = "synthetic cash securitisation cap eligible",
    source_id: str = "fair-value-cap-source",
    is_stale: bool = False,
    citation_ids: tuple[str, ...] = ("US_NPR_210_C_3_III", "BASEL_MAR22_34"),
) -> DrcFairValueCapEvidence:
    return DrcFairValueCapEvidence(
        position_id=position.position_id,
        source_profile_id=source_profile_id,
        eligible=eligible,
        fair_value_cap_amount=fair_value_cap_amount,
        eligibility_reason=eligibility_reason,
        as_of_date=date(2026, 5, 29),
        source_id=source_id,
        lineage=DrcSourceLineage(
            source_system="synthetic-risk-weight-engine",
            source_file="securitisation-fair-value-cap.csv",
            source_row_id=f"cap-{position.position_id}",
            source_column_map={"fair_value_cap_amount": "fair_value_cap_amount"},
        ),
        citation_ids=citation_ids,
        is_stale=is_stale,
    )


def _load_securitisation_fixture(fixture_name: str) -> dict[str, Any]:
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
        securitisation_non_ctp_risk_weights=context_raw.get(
            "securitisation_non_ctp_risk_weights",
            {},
        ),
        securitisation_non_ctp_risk_weight_evidence=risk_weight_evidence_by_position(
            drc_risk_weight_evidence_from_dict(raw)
            for raw in context_raw.get("securitisation_non_ctp_risk_weight_evidence", ())
        ),
        securitisation_non_ctp_fair_value_cap_evidence=fair_value_cap_evidence_by_position(
            drc_fair_value_cap_evidence_from_dict(raw)
            for raw in context_raw.get("securitisation_non_ctp_fair_value_cap_evidence", ())
        ),
    )
    return {"positions": positions, "context": context, "expected": expected}
