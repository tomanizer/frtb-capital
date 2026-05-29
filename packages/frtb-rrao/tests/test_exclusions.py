from __future__ import annotations

from datetime import date

import pytest

from frtb_rrao import (
    RraoBackToBackMatch,
    RraoCalculationContext,
    RraoClassification,
    RraoEvidenceType,
    RraoExclusionReason,
    RraoInputError,
    RraoPosition,
    RraoRegulatoryProfile,
    RraoSourceLineage,
    calculate_rrao_capital,
    classify_rrao_position,
)


def sample_lineage() -> RraoSourceLineage:
    return RraoSourceLineage(
        source_system="synthetic-risk",
        source_file="rrao.csv",
        source_row_id="row-001",
        source_column_map=(("Exclusion", "exclusion_reason"),),
    )


def sample_excluded_position(**overrides: object) -> RraoPosition:
    fields = {
        "position_id": "pos-excluded-001",
        "source_row_id": "row-001",
        "desk_id": "rates-exotics",
        "legal_entity": "LE-001",
        "gross_effective_notional": 1_000_000.0,
        "currency": "USD",
        "evidence_type": RraoEvidenceType.EXPLICIT_EXCLUSION,
        "evidence_label": "listed option",
        "classification_hint": RraoClassification.EXCLUDED,
        "exclusion_reason": RraoExclusionReason.LISTED,
        "exclusion_evidence_id": "exchange-listing-001",
        "lineage": sample_lineage(),
    }
    fields.update(overrides)
    return RraoPosition(**fields)  # type: ignore[arg-type]


def sample_context(
    profile: RraoRegulatoryProfile = RraoRegulatoryProfile.US_NPR_2_0,
) -> RraoCalculationContext:
    return RraoCalculationContext(
        run_id="rrao-exclusion-test",
        calculation_date=date(2026, 3, 31),
        base_currency="USD" if profile is not RraoRegulatoryProfile.EU_CRR3 else "EUR",
        profile=profile,
    )


def test_us_exclusion_produces_zero_capital_decision_with_evidence_id() -> None:
    decision = classify_rrao_position(
        sample_excluded_position(),
        profile=RraoRegulatoryProfile.US_NPR_2_0,
    )

    assert decision.classification is RraoClassification.EXCLUDED
    assert decision.risk_weight_key == "EXCLUDED_0_PERCENT"
    assert decision.exclusion_reason is RraoExclusionReason.LISTED
    assert decision.exclusion_evidence_id == "exchange-listing-001"
    assert decision.reason_code == "US_NPR_EXCLUSION_LISTED"
    assert decision.citations == ("us_npr_211_b_1",)


@pytest.mark.parametrize(
    ("profile", "expected_reason_code", "expected_citation"),
    [
        (
            RraoRegulatoryProfile.BASEL_MAR23,
            "BASEL_EXCLUSION_EXACT_THIRD_PARTY_BACK_TO_BACK",
            "basel_mar23_4_7",
        ),
        (
            RraoRegulatoryProfile.US_NPR_2_0,
            "US_NPR_EXCLUSION_EXACT_BACK_TO_BACK",
            "us_npr_211_b_2_i",
        ),
    ],
)
def test_valid_exact_back_to_back_pair_excludes_both_transactions(
    profile: RraoRegulatoryProfile,
    expected_reason_code: str,
    expected_citation: str,
) -> None:
    positions = (
        sample_excluded_position(
            position_id="b2b-left",
            source_row_id="row-left",
            gross_effective_notional=2_500_000.0,
            evidence_label="exact third-party back-to-back left",
            exclusion_reason=RraoExclusionReason.EXACT_THIRD_PARTY_BACK_TO_BACK,
            exclusion_evidence_id="match-group-001",
            back_to_back_match=RraoBackToBackMatch(
                match_group_id="match-group-001",
                matched_position_id="b2b-right",
            ),
        ),
        sample_excluded_position(
            position_id="b2b-right",
            source_row_id="row-right",
            gross_effective_notional=2_500_000.0,
            evidence_label="exact third-party back-to-back right",
            exclusion_reason=RraoExclusionReason.EXACT_THIRD_PARTY_BACK_TO_BACK,
            exclusion_evidence_id="match-group-001",
            back_to_back_match=RraoBackToBackMatch(
                match_group_id="match-group-001",
                matched_position_id="b2b-left",
            ),
        ),
    )

    result = calculate_rrao_capital(positions, context=sample_context(profile))

    assert result.lines == ()
    assert [line.position_id for line in result.excluded_lines] == ["b2b-left", "b2b-right"]
    assert {line.reason_code for line in result.excluded_lines} == {expected_reason_code}
    assert all(line.exclusion_evidence_id == "match-group-001" for line in result.excluded_lines)
    assert all(expected_citation in line.citations for line in result.excluded_lines)
    assert result.total_rrao == 0.0


def test_exact_back_to_back_pair_rejects_missing_partner() -> None:
    with pytest.raises(RraoInputError, match="matched position is missing") as exc_info:
        calculate_rrao_capital(
            (
                sample_excluded_position(
                    exclusion_reason=RraoExclusionReason.EXACT_THIRD_PARTY_BACK_TO_BACK,
                    exclusion_evidence_id="match-group-001",
                    back_to_back_match=RraoBackToBackMatch(
                        match_group_id="match-group-001",
                        matched_position_id="missing-position",
                    ),
                ),
            ),
            context=sample_context(),
        )
    assert exc_info.value.field == "back_to_back_match.matched_position_id"
    assert exc_info.value.position_id == "pos-excluded-001"


def test_exact_back_to_back_validation_checks_later_match_groups() -> None:
    with pytest.raises(RraoInputError, match="matched position is missing") as exc_info:
        calculate_rrao_capital(
            (
                sample_excluded_position(
                    position_id="ordinary-listed",
                    source_row_id="row-listed",
                ),
                sample_excluded_position(
                    position_id="b2b-left",
                    source_row_id="row-left",
                    exclusion_reason=RraoExclusionReason.EXACT_THIRD_PARTY_BACK_TO_BACK,
                    exclusion_evidence_id="match-group-001",
                    back_to_back_match=RraoBackToBackMatch(
                        match_group_id="match-group-001",
                        matched_position_id="missing-position",
                    ),
                ),
            ),
            context=sample_context(),
        )
    assert exc_info.value.field == "back_to_back_match.matched_position_id"
    assert exc_info.value.position_id == "b2b-left"


def test_exact_back_to_back_pair_rejects_missing_match_evidence() -> None:
    with pytest.raises(RraoInputError, match="match evidence") as exc_info:
        calculate_rrao_capital(
            (
                sample_excluded_position(
                    exclusion_reason=RraoExclusionReason.EXACT_THIRD_PARTY_BACK_TO_BACK,
                    exclusion_evidence_id="match-group-001",
                ),
            ),
            context=sample_context(),
        )
    assert exc_info.value.field == "back_to_back_match"
    assert exc_info.value.position_id == "pos-excluded-001"


def test_exact_back_to_back_pair_rejects_mismatched_notional() -> None:
    with pytest.raises(RraoInputError, match="matching gross effective notional") as exc_info:
        calculate_rrao_capital(
            (
                sample_excluded_position(
                    position_id="b2b-left",
                    source_row_id="row-left",
                    gross_effective_notional=2_500_000.0,
                    exclusion_reason=RraoExclusionReason.EXACT_THIRD_PARTY_BACK_TO_BACK,
                    exclusion_evidence_id="match-group-001",
                    back_to_back_match=RraoBackToBackMatch(
                        match_group_id="match-group-001",
                        matched_position_id="b2b-right",
                    ),
                ),
                sample_excluded_position(
                    position_id="b2b-right",
                    source_row_id="row-right",
                    gross_effective_notional=2_400_000.0,
                    exclusion_reason=RraoExclusionReason.EXACT_THIRD_PARTY_BACK_TO_BACK,
                    exclusion_evidence_id="match-group-001",
                    back_to_back_match=RraoBackToBackMatch(
                        match_group_id="match-group-001",
                        matched_position_id="b2b-left",
                    ),
                ),
            ),
            context=sample_context(),
        )
    assert exc_info.value.field == "gross_effective_notional"
    assert exc_info.value.position_id == "b2b-right"


def test_exact_back_to_back_pair_rejects_mismatched_currency() -> None:
    with pytest.raises(RraoInputError, match="matching currency") as exc_info:
        calculate_rrao_capital(
            (
                sample_excluded_position(
                    position_id="b2b-left",
                    source_row_id="row-left",
                    currency="USD",
                    exclusion_reason=RraoExclusionReason.EXACT_THIRD_PARTY_BACK_TO_BACK,
                    exclusion_evidence_id="match-group-001",
                    back_to_back_match=RraoBackToBackMatch(
                        match_group_id="match-group-001",
                        matched_position_id="b2b-right",
                    ),
                ),
                sample_excluded_position(
                    position_id="b2b-right",
                    source_row_id="row-right",
                    currency="EUR",
                    exclusion_reason=RraoExclusionReason.EXACT_THIRD_PARTY_BACK_TO_BACK,
                    exclusion_evidence_id="match-group-001",
                    back_to_back_match=RraoBackToBackMatch(
                        match_group_id="match-group-001",
                        matched_position_id="b2b-left",
                    ),
                ),
            ),
            context=sample_context(),
        )
    assert exc_info.value.field == "currency"
    assert exc_info.value.position_id == "b2b-right"


def test_exact_back_to_back_pair_rejects_one_sided_exclusion() -> None:
    with pytest.raises(RraoInputError, match="must contain exactly two") as exc_info:
        calculate_rrao_capital(
            (
                sample_excluded_position(
                    position_id="b2b-left",
                    source_row_id="row-left",
                    exclusion_reason=RraoExclusionReason.EXACT_THIRD_PARTY_BACK_TO_BACK,
                    exclusion_evidence_id="match-group-001",
                    back_to_back_match=RraoBackToBackMatch(
                        match_group_id="match-group-001",
                        matched_position_id="b2b-right",
                    ),
                ),
                sample_excluded_position(
                    position_id="b2b-right",
                    source_row_id="row-right",
                    exclusion_reason=RraoExclusionReason.LISTED,
                    exclusion_evidence_id="exchange-listing-001",
                ),
            ),
            context=sample_context(),
        )
    assert exc_info.value.field == "back_to_back_match.match_group_id"


def test_exact_back_to_back_pair_rejects_duplicate_reused_match_group() -> None:
    with pytest.raises(RraoInputError, match="exactly two") as exc_info:
        calculate_rrao_capital(
            (
                sample_excluded_position(
                    position_id="b2b-left",
                    source_row_id="row-left",
                    exclusion_reason=RraoExclusionReason.EXACT_THIRD_PARTY_BACK_TO_BACK,
                    exclusion_evidence_id="match-group-001",
                    back_to_back_match=RraoBackToBackMatch(
                        match_group_id="match-group-001",
                        matched_position_id="b2b-right",
                    ),
                ),
                sample_excluded_position(
                    position_id="b2b-right",
                    source_row_id="row-right",
                    exclusion_reason=RraoExclusionReason.EXACT_THIRD_PARTY_BACK_TO_BACK,
                    exclusion_evidence_id="match-group-001",
                    back_to_back_match=RraoBackToBackMatch(
                        match_group_id="match-group-001",
                        matched_position_id="b2b-left",
                    ),
                ),
                sample_excluded_position(
                    position_id="b2b-extra",
                    source_row_id="row-extra",
                    exclusion_reason=RraoExclusionReason.EXACT_THIRD_PARTY_BACK_TO_BACK,
                    exclusion_evidence_id="match-group-001",
                    back_to_back_match=RraoBackToBackMatch(
                        match_group_id="match-group-001",
                        matched_position_id="b2b-left",
                    ),
                ),
            ),
            context=sample_context(),
        )
    assert exc_info.value.field == "back_to_back_match.match_group_id"


def test_basel_exclusion_subset_is_supported() -> None:
    decision = classify_rrao_position(
        sample_excluded_position(
            exclusion_reason=RraoExclusionReason.CCP_OR_QCCP_CLEARABLE,
            exclusion_evidence_id="clearing-evidence-001",
        ),
        profile=RraoRegulatoryProfile.BASEL_MAR23,
    )

    assert decision.classification is RraoClassification.EXCLUDED
    assert decision.reason_code == "BASEL_EXCLUSION_CCP_OR_QCCP_CLEARABLE"
    assert decision.citations == ("basel_mar23_4_7",)


def test_us_specific_exclusion_fails_for_basel_profile() -> None:
    with pytest.raises(RraoInputError, match="no RRAO exclusion rule"):
        classify_rrao_position(
            sample_excluded_position(
                exclusion_reason=RraoExclusionReason.GOVERNMENT_OR_GSE_DEBT,
                exclusion_evidence_id="government-security-001",
            ),
            profile=RraoRegulatoryProfile.BASEL_MAR23,
        )


def test_exclusion_requires_reason_and_evidence_id() -> None:
    with pytest.raises(RraoInputError, match="exclusion reason"):
        classify_rrao_position(
            sample_excluded_position(
                exclusion_reason=None,
                exclusion_evidence_id=None,
            )
        )
    with pytest.raises(RraoInputError, match="exclusion_evidence_id"):
        classify_rrao_position(sample_excluded_position(exclusion_evidence_id=None))
