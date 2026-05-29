from __future__ import annotations

import re
from dataclasses import FrozenInstanceError
from datetime import date

import pytest
from frtb_common import UnsupportedRegulatoryFeatureError
from frtb_rrao import (
    RraoCalculationContext,
    RraoCapitalResult,
    RraoClassification,
    RraoEvidenceType,
    RraoExclusionReason,
    RraoInputError,
    RraoPosition,
    RraoRegulatoryProfile,
    RraoSourceLineage,
    calculate_rrao_capital,
)


def sample_lineage(row_id: str) -> RraoSourceLineage:
    return RraoSourceLineage(
        source_system="synthetic-risk",
        source_file="rrao.csv",
        source_row_id=row_id,
        source_column_map=(("AmountUSD", "gross_effective_notional"),),
    )


def sample_position(
    *,
    position_id: str,
    source_row_id: str,
    gross_effective_notional: float,
    evidence_type: RraoEvidenceType,
    classification_hint: RraoClassification,
    evidence_label: str,
    desk_id: str = "desk-a",
    legal_entity: str = "LE-001",
    exclusion_reason: RraoExclusionReason | None = None,
    exclusion_evidence_id: str | None = None,
    supervisor_directive_id: str | None = None,
) -> RraoPosition:
    return RraoPosition(
        position_id=position_id,
        source_row_id=source_row_id,
        desk_id=desk_id,
        legal_entity=legal_entity,
        gross_effective_notional=gross_effective_notional,
        currency="USD",
        evidence_type=evidence_type,
        evidence_label=evidence_label,
        classification_hint=classification_hint,
        exclusion_reason=exclusion_reason,
        exclusion_evidence_id=exclusion_evidence_id,
        supervisor_directive_id=supervisor_directive_id,
        lineage=sample_lineage(source_row_id),
    )


def sample_context(
    profile: RraoRegulatoryProfile = RraoRegulatoryProfile.US_NPR_2_0,
) -> RraoCalculationContext:
    return RraoCalculationContext(
        run_id="rrao-run-001",
        calculation_date=date(2026, 3, 31),
        base_currency="USD",
        profile=profile,
    )


def test_calculate_rrao_capital_returns_public_result_for_supported_inputs() -> None:
    result = calculate_rrao_capital(
        (
            sample_position(
                position_id="exotic-001",
                source_row_id="row-001",
                gross_effective_notional=1_000_000.0,
                evidence_type=RraoEvidenceType.EXOTIC_UNDERLYING,
                evidence_label="weather derivative",
                classification_hint=RraoClassification.EXOTIC,
            ),
            sample_position(
                position_id="gap-001",
                source_row_id="row-002",
                gross_effective_notional=2_000_000.0,
                evidence_type=RraoEvidenceType.GAP_RISK,
                evidence_label="gap risk",
                classification_hint=RraoClassification.OTHER_RESIDUAL_RISK,
            ),
            sample_position(
                position_id="listed-001",
                source_row_id="row-003",
                gross_effective_notional=3_000_000.0,
                evidence_type=RraoEvidenceType.EXPLICIT_EXCLUSION,
                evidence_label="listed option",
                classification_hint=RraoClassification.EXCLUDED,
                exclusion_reason=RraoExclusionReason.LISTED,
                exclusion_evidence_id="exchange-listing-001",
            ),
        ),
        context=sample_context(),
    )

    assert isinstance(result, RraoCapitalResult)
    assert result.run_id == "rrao-run-001"
    assert result.profile_id == "US_NPR_2_0"
    assert re.fullmatch(r"[0-9a-f]{64}", result.profile_hash)
    assert re.fullmatch(r"[0-9a-f]{64}", result.input_hash)
    assert [line.position_id for line in result.lines] == ["exotic-001", "gap-001"]
    assert [line.position_id for line in result.excluded_lines] == ["listed-001"]
    assert result.total_rrao == 12_000.0
    assert "us_npr_211_c_1_i" in result.citations
    assert "us_npr_211_b_1" in result.citations
    assert result.warnings == (
        "US_NPR_2_0 is proposed-rule material; do not present outputs as final regulatory capital.",
    )

    payload = result.as_dict()
    assert payload["total_rrao"] == 12_000.0
    assert payload["calculation_date"] == "2026-03-31"
    assert [line["position_id"] for line in payload["lines"]] == ["exotic-001", "gap-001"]
    with pytest.raises(FrozenInstanceError):
        setattr(result, "total_rrao", 0.0)


def test_calculate_rrao_capital_requires_context() -> None:
    with pytest.raises(RraoInputError, match="calculation context is required"):
        calculate_rrao_capital(())


def test_calculate_rrao_capital_validates_context_shape() -> None:
    position = sample_position(
        position_id="exotic-001",
        source_row_id="row-001",
        gross_effective_notional=1_000_000.0,
        evidence_type=RraoEvidenceType.EXOTIC_UNDERLYING,
        evidence_label="weather derivative",
        classification_hint=RraoClassification.EXOTIC,
    )

    invalid_contexts = (
        (object(), "calculation context must be RraoCalculationContext"),
        (
            RraoCalculationContext(
                run_id="run",
                calculation_date="2026-03-31",
                base_currency="USD",
                profile=RraoRegulatoryProfile.US_NPR_2_0,
            ),
            "calculation date must be a date",
        ),
        (
            RraoCalculationContext(
                run_id="run",
                calculation_date=date(2026, 3, 31),
                base_currency="USD",
                profile="UNKNOWN",
            ),
            "invalid regulatory profile",
        ),
        (
            RraoCalculationContext(
                run_id=" ",
                calculation_date=date(2026, 3, 31),
                base_currency="USD",
                profile=RraoRegulatoryProfile.US_NPR_2_0,
            ),
            "non-empty text is required",
        ),
        (
            RraoCalculationContext(
                run_id="run",
                calculation_date=date(2026, 3, 31),
                base_currency=" ",
                profile=RraoRegulatoryProfile.US_NPR_2_0,
            ),
            "non-empty text is required",
        ),
        (
            RraoCalculationContext(
                run_id="run",
                calculation_date=date(2026, 3, 31),
                base_currency="USD",
                profile=RraoRegulatoryProfile.US_NPR_2_0,
                desk_id=" ",
            ),
            "non-empty text is required",
        ),
        (
            RraoCalculationContext(
                run_id="run",
                calculation_date=date(2026, 3, 31),
                base_currency="USD",
                profile=RraoRegulatoryProfile.US_NPR_2_0,
                legal_entity=" ",
            ),
            "non-empty text is required",
        ),
        (
            RraoCalculationContext(
                run_id="run",
                calculation_date=date(2026, 3, 31),
                base_currency="USD",
                profile=RraoRegulatoryProfile.US_NPR_2_0,
                citation_policy=" ",
            ),
            "non-empty text is required",
        ),
    )
    for context, message in invalid_contexts:
        with pytest.raises(RraoInputError, match=message):
            calculate_rrao_capital((position,), context=context)


def test_calculate_rrao_capital_fails_closed_for_unsupported_profiles() -> None:
    with pytest.raises(UnsupportedRegulatoryFeatureError, match="unsupported"):
        calculate_rrao_capital(
            (
                sample_position(
                    position_id="exotic-001",
                    source_row_id="row-001",
                    gross_effective_notional=1_000_000.0,
                    evidence_type=RraoEvidenceType.EXOTIC_UNDERLYING,
                    evidence_label="weather derivative",
                    classification_hint=RraoClassification.EXOTIC,
                ),
            ),
            context=sample_context(RraoRegulatoryProfile.PRA_UK_CRR),
        )
