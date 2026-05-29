from __future__ import annotations

import pytest
from frtb_common import UnsupportedRegulatoryFeatureError

from frtb_rrao import (
    RraoClassification,
    RraoEvidenceType,
    RraoInputError,
    RraoPosition,
    RraoRegulatoryProfile,
    RraoSourceLineage,
    classify_rrao_position,
    classify_rrao_positions,
)


def sample_lineage() -> RraoSourceLineage:
    return RraoSourceLineage(
        source_system="synthetic-risk",
        source_file="rrao.csv",
        source_row_id="row-001",
        source_column_map=(
            ("RiskType", "evidence_type"),
            ("AmountUSD", "gross_effective_notional"),
        ),
    )


def sample_position(**overrides: object) -> RraoPosition:
    fields = {
        "position_id": "pos-001",
        "source_row_id": "row-001",
        "desk_id": "rates-exotics",
        "legal_entity": "LE-001",
        "gross_effective_notional": 1_000_000.0,
        "currency": "USD",
        "evidence_type": RraoEvidenceType.EXOTIC_UNDERLYING,
        "evidence_label": "weather derivative",
        "classification_hint": RraoClassification.EXOTIC,
        "lineage": sample_lineage(),
        "citations": ("source-row-map-001",),
    }
    fields.update(overrides)
    return RraoPosition(**fields)  # type: ignore[arg-type]


def test_exotic_example_classifies_to_one_percent_treatment() -> None:
    decision = classify_rrao_position(sample_position(), profile=RraoRegulatoryProfile.US_NPR_2_0)

    assert decision.classification is RraoClassification.EXOTIC
    assert decision.risk_weight_key == "EXOTIC_1_PERCENT"
    assert decision.reason_code == "US_NPR_EXOTIC_EXPOSURE"
    assert decision.citations == ("us_npr_211_a_1", "source-row-map-001")


@pytest.mark.parametrize(
    "evidence_type",
    [
        RraoEvidenceType.GAP_RISK,
        RraoEvidenceType.CORRELATION_RISK,
        RraoEvidenceType.BEHAVIOURAL_RISK,
        RraoEvidenceType.CTP_THREE_OR_MORE_UNDERLYINGS,
        RraoEvidenceType.NON_REPLICABLE_OPTIONALITY,
        RraoEvidenceType.NO_MATURITY_OPTIONALITY,
        RraoEvidenceType.NO_STRIKE_OR_BARRIER_OPTIONALITY,
        RraoEvidenceType.MULTIPLE_STRIKE_OR_BARRIER_OPTIONALITY,
    ],
)
def test_other_residual_examples_classify_to_point_one_percent_treatment(
    evidence_type: RraoEvidenceType,
) -> None:
    decision = classify_rrao_position(
        sample_position(
            evidence_type=evidence_type,
            evidence_label=evidence_type.value.lower(),
            classification_hint=RraoClassification.OTHER_RESIDUAL_RISK,
        ),
        profile=RraoRegulatoryProfile.US_NPR_2_0,
    )

    assert decision.classification is RraoClassification.OTHER_RESIDUAL_RISK
    assert decision.risk_weight_key == "OTHER_0_1_PERCENT"
    assert decision.citations[0] == "us_npr_211_a_2"


def test_classify_rrao_positions_preserves_input_order() -> None:
    decisions = classify_rrao_positions(
        (
            sample_position(position_id="pos-001", source_row_id="row-001"),
            sample_position(
                position_id="pos-002",
                source_row_id="row-002",
                evidence_type=RraoEvidenceType.GAP_RISK,
                evidence_label="gap risk",
                classification_hint=RraoClassification.OTHER_RESIDUAL_RISK,
            ),
        ),
        profile=RraoRegulatoryProfile.BASEL_MAR23,
    )

    assert [decision.position_id for decision in decisions] == ["pos-001", "pos-002"]
    assert decisions[0].risk_weight_key == "EXOTIC_1_PERCENT"
    assert decisions[1].risk_weight_key == "OTHER_0_1_PERCENT"


def test_supervisor_directed_position_requires_and_preserves_directive_id() -> None:
    with pytest.raises(RraoInputError, match="supervisor_directive_id"):
        classify_rrao_position(
            sample_position(
                evidence_type=RraoEvidenceType.SUPERVISOR_DIRECTIVE,
                evidence_label="agency directive",
                classification_hint=RraoClassification.SUPERVISOR_DIRECTED,
            )
        )

    decision = classify_rrao_position(
        sample_position(
            evidence_type=RraoEvidenceType.SUPERVISOR_DIRECTIVE,
            evidence_label="agency directive",
            classification_hint=RraoClassification.SUPERVISOR_DIRECTED,
            supervisor_directive_id="agency-letter-001",
        )
    )

    assert decision.classification is RraoClassification.SUPERVISOR_DIRECTED
    assert decision.risk_weight_key == "SUPERVISOR_DIRECTED_0_1_PERCENT"
    assert decision.supervisor_directive_id == "agency-letter-001"
    assert decision.citations[0] == "us_npr_211_a_4"


def test_classification_hint_conflict_fails() -> None:
    with pytest.raises(RraoInputError, match="classification hint conflicts"):
        classify_rrao_position(
            sample_position(
                evidence_type=RraoEvidenceType.GAP_RISK,
                evidence_label="gap risk",
                classification_hint=RraoClassification.EXOTIC,
            )
        )


def test_unsupported_profiles_fail_before_classification() -> None:
    with pytest.raises(UnsupportedRegulatoryFeatureError, match="unsupported"):
        classify_rrao_position(sample_position(), profile=RraoRegulatoryProfile.PRA_UK_CRR)
