from __future__ import annotations

import pytest
from frtb_rrao import (
    RraoClassification,
    RraoEvidenceType,
    RraoExclusionReason,
    RraoInputError,
    RraoPosition,
    RraoRegulatoryProfile,
    RraoSourceLineage,
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


def test_exact_back_to_back_exclusion_preserves_cited_reason() -> None:
    decision = classify_rrao_position(
        sample_excluded_position(
            evidence_label="exact third-party back-to-back",
            exclusion_reason=RraoExclusionReason.EXACT_THIRD_PARTY_BACK_TO_BACK,
            exclusion_evidence_id="match-group-001",
        ),
        profile=RraoRegulatoryProfile.US_NPR_2_0,
    )

    assert decision.classification is RraoClassification.EXCLUDED
    assert decision.reason_code == "US_NPR_EXCLUSION_EXACT_BACK_TO_BACK"
    assert decision.exclusion_evidence_id == "match-group-001"
    assert decision.citations == ("us_npr_211_b_2_i",)


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
