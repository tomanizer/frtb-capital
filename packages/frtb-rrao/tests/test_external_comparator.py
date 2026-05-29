from __future__ import annotations

import math
from datetime import date

from frtb_rrao import (
    RraoBackToBackMatch,
    RraoCalculationContext,
    RraoClassification,
    RraoEvidenceType,
    RraoExclusionReason,
    RraoPosition,
    RraoRegulatoryProfile,
    RraoSourceLineage,
    calculate_rrao_capital,
)

REFERENCE_REL_TOL = 1e-12
REFERENCE_ABS_TOL = 1e-9


def lineage(row_id: str) -> RraoSourceLineage:
    return RraoSourceLineage(
        source_system="external-comparator",
        source_file="hand_calculated_fixture",
        source_row_id=row_id,
        source_column_map=(("notional", "gross_effective_notional"),),
    )


def position(
    *,
    position_id: str,
    row_id: str,
    notional: float,
    evidence_type: RraoEvidenceType,
    classification_hint: RraoClassification,
    evidence_label: str,
    currency: str,
    exclusion_reason: RraoExclusionReason | None = None,
    exclusion_evidence_id: str | None = None,
    back_to_back_match: RraoBackToBackMatch | None = None,
    supervisor_directive_id: str | None = None,
) -> RraoPosition:
    return RraoPosition(
        position_id=position_id,
        source_row_id=row_id,
        desk_id="desk-comparator",
        legal_entity="LE-COMP",
        gross_effective_notional=notional,
        currency=currency,
        evidence_type=evidence_type,
        evidence_label=evidence_label,
        classification_hint=classification_hint,
        exclusion_reason=exclusion_reason,
        exclusion_evidence_id=exclusion_evidence_id,
        back_to_back_match=back_to_back_match,
        supervisor_directive_id=supervisor_directive_id,
        lineage=lineage(row_id),
    )


def test_us_npr_fixture_reconciles_to_independent_hand_calculation() -> None:
    positions = (
        position(
            position_id="cmp-us-exotic",
            row_id="cmp-us-row-001",
            notional=1_000_000.0,
            evidence_type=RraoEvidenceType.EXOTIC_UNDERLYING,
            classification_hint=RraoClassification.EXOTIC,
            evidence_label="weather derivative",
            currency="USD",
        ),
        position(
            position_id="cmp-us-gap",
            row_id="cmp-us-row-002",
            notional=2_000_000.0,
            evidence_type=RraoEvidenceType.GAP_RISK,
            classification_hint=RraoClassification.OTHER_RESIDUAL_RISK,
            evidence_label="gap risk",
            currency="USD",
        ),
        position(
            position_id="cmp-us-supervisor",
            row_id="cmp-us-row-003",
            notional=3_000_000.0,
            evidence_type=RraoEvidenceType.SUPERVISOR_DIRECTIVE,
            classification_hint=RraoClassification.SUPERVISOR_DIRECTED,
            evidence_label="agency-directed inclusion",
            currency="USD",
            supervisor_directive_id="agency-letter-001",
        ),
        position(
            position_id="cmp-us-listed",
            row_id="cmp-us-row-004",
            notional=4_000_000.0,
            evidence_type=RraoEvidenceType.EXPLICIT_EXCLUSION,
            classification_hint=RraoClassification.EXCLUDED,
            evidence_label="listed option",
            currency="USD",
            exclusion_reason=RraoExclusionReason.LISTED,
            exclusion_evidence_id="exchange-listing-001",
        ),
        position(
            position_id="cmp-us-clearable",
            row_id="cmp-us-row-005",
            notional=5_000_000.0,
            evidence_type=RraoEvidenceType.EXPLICIT_EXCLUSION,
            classification_hint=RraoClassification.EXCLUDED,
            evidence_label="QCCP clearable transaction",
            currency="USD",
            exclusion_reason=RraoExclusionReason.CCP_OR_QCCP_CLEARABLE,
            exclusion_evidence_id="qccp-clearable-001",
        ),
        position(
            position_id="cmp-us-b2b-left",
            row_id="cmp-us-row-006",
            notional=6_000_000.0,
            evidence_type=RraoEvidenceType.EXPLICIT_EXCLUSION,
            classification_hint=RraoClassification.EXCLUDED,
            evidence_label="exact third-party back-to-back left",
            currency="USD",
            exclusion_reason=RraoExclusionReason.EXACT_THIRD_PARTY_BACK_TO_BACK,
            exclusion_evidence_id="b2b-match-001",
            back_to_back_match=RraoBackToBackMatch(
                match_group_id="b2b-match-001",
                matched_position_id="cmp-us-b2b-right",
            ),
        ),
        position(
            position_id="cmp-us-b2b-right",
            row_id="cmp-us-row-007",
            notional=6_000_000.0,
            evidence_type=RraoEvidenceType.EXPLICIT_EXCLUSION,
            classification_hint=RraoClassification.EXCLUDED,
            evidence_label="exact third-party back-to-back right",
            currency="USD",
            exclusion_reason=RraoExclusionReason.EXACT_THIRD_PARTY_BACK_TO_BACK,
            exclusion_evidence_id="b2b-match-001",
            back_to_back_match=RraoBackToBackMatch(
                match_group_id="b2b-match-001",
                matched_position_id="cmp-us-b2b-left",
            ),
        ),
    )
    result = calculate_rrao_capital(
        positions,
        context=RraoCalculationContext(
            run_id="external-comparator-us",
            calculation_date=date(2026, 3, 31),
            base_currency="USD",
            profile=RraoRegulatoryProfile.US_NPR_2_0,
        ),
    )

    expected_total = 1_000_000.0 * 0.01 + 2_000_000.0 * 0.001 + 3_000_000.0 * 0.001
    assert math.isclose(
        result.total_rrao,
        expected_total,
        rel_tol=REFERENCE_REL_TOL,
        abs_tol=REFERENCE_ABS_TOL,
    )
    assert [line.position_id for line in result.lines] == [
        "cmp-us-exotic",
        "cmp-us-gap",
        "cmp-us-supervisor",
    ]
    assert [line.position_id for line in result.excluded_lines] == [
        "cmp-us-listed",
        "cmp-us-clearable",
        "cmp-us-b2b-left",
        "cmp-us-b2b-right",
    ]


def test_eu_crr3_fixture_reconciles_to_independent_hand_calculation() -> None:
    positions = (
        position(
            position_id="cmp-eu-exotic",
            row_id="cmp-eu-row-001",
            notional=1_000_000.0,
            evidence_type=RraoEvidenceType.EXOTIC_UNDERLYING,
            classification_hint=RraoClassification.EXOTIC,
            evidence_label="future realised volatility underlying",
            currency="EUR",
        ),
        position(
            position_id="cmp-eu-path-dependent",
            row_id="cmp-eu-row-002",
            notional=2_000_000.0,
            evidence_type=RraoEvidenceType.PATH_DEPENDENT_OPTION,
            classification_hint=RraoClassification.OTHER_RESIDUAL_RISK,
            evidence_label="path-dependent option",
            currency="EUR",
        ),
        position(
            position_id="cmp-eu-article-3",
            row_id="cmp-eu-row-003",
            notional=3_000_000.0,
            evidence_type=RraoEvidenceType.EXPLICIT_EXCLUSION,
            classification_hint=RraoClassification.EXCLUDED,
            evidence_label="Article 3 index option correlation risk only",
            currency="EUR",
            exclusion_reason=RraoExclusionReason.EU_ARTICLE_3_INDEX_OPTION_CORRELATION,
            exclusion_evidence_id="article-3-index-option-correlation-001",
        ),
    )
    result = calculate_rrao_capital(
        positions,
        context=RraoCalculationContext(
            run_id="external-comparator-eu",
            calculation_date=date(2026, 3, 31),
            base_currency="EUR",
            profile=RraoRegulatoryProfile.EU_CRR3,
        ),
    )

    expected_total = 1_000_000.0 * 0.01 + 2_000_000.0 * 0.001
    assert math.isclose(
        result.total_rrao,
        expected_total,
        rel_tol=REFERENCE_REL_TOL,
        abs_tol=REFERENCE_ABS_TOL,
    )
    assert [line.position_id for line in result.lines] == [
        "cmp-eu-exotic",
        "cmp-eu-path-dependent",
    ]
    assert [line.position_id for line in result.excluded_lines] == ["cmp-eu-article-3"]
