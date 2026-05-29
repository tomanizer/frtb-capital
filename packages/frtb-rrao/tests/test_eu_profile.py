from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pytest
from frtb_rrao import (
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

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "rrao_eu"

EU_ARTICLE_2_ANNEX_EVIDENCE = (
    RraoEvidenceType.PATH_DEPENDENT_OPTION,
    RraoEvidenceType.FORWARD_START_UNDETERMINED_STRIKE_OPTION,
    RraoEvidenceType.OPTION_ON_OPTION,
    RraoEvidenceType.DISCONTINUOUS_PAYOFF_OPTION,
    RraoEvidenceType.HOLDER_MODIFIABLE_OPTION,
    RraoEvidenceType.FINITE_EXERCISE_DATES_OPTION,
    RraoEvidenceType.CROSS_CURRENCY_SETTLED_OPTION,
    RraoEvidenceType.MULTI_UNDERLYING_OPTION,
    RraoEvidenceType.BEHAVIOURAL_OPTION,
)

EU_ARTICLE_3_EXCLUSION_REASONS = (
    RraoExclusionReason.EU_ARTICLE_3_DELIVERABLE_RANGE,
    RraoExclusionReason.EU_ARTICLE_3_RELATIVE_IMPLIED_VOLATILITY,
    RraoExclusionReason.EU_ARTICLE_3_INDEX_OPTION_CORRELATION,
    RraoExclusionReason.EU_ARTICLE_3_CIU_INDEX_OPTION_CORRELATION,
    RraoExclusionReason.EU_ARTICLE_3_DIVIDEND_RISK,
)

EU_ARTICLE_325U_4_EXCLUSION_REASONS = (
    RraoExclusionReason.LISTED,
    RraoExclusionReason.CCP_OR_QCCP_CLEARABLE,
    RraoExclusionReason.EXACT_THIRD_PARTY_BACK_TO_BACK,
)


def sample_lineage(row_id: str) -> RraoSourceLineage:
    return RraoSourceLineage(
        source_system="synthetic-eu-rrao-fixture",
        source_file="eu-rrao.csv",
        source_row_id=row_id,
        source_column_map=(
            ("evidence_type", "evidence_type"),
            ("gross_notional", "gross_effective_notional"),
        ),
    )


def eu_position(
    *,
    position_id: str,
    evidence_type: RraoEvidenceType,
    classification_hint: RraoClassification,
    gross_effective_notional: float = 1_000_000.0,
    evidence_label: str = "EU residual-risk fixture",
    source_row_id: str = "row-001",
    exclusion_reason: RraoExclusionReason | None = None,
    exclusion_evidence_id: str | None = None,
) -> RraoPosition:
    return RraoPosition(
        position_id=position_id,
        source_row_id=source_row_id,
        desk_id="eu-trading",
        legal_entity="EU-LE-001",
        gross_effective_notional=gross_effective_notional,
        currency="EUR",
        evidence_type=evidence_type,
        evidence_label=evidence_label,
        classification_hint=classification_hint,
        exclusion_reason=exclusion_reason,
        exclusion_evidence_id=exclusion_evidence_id,
        lineage=sample_lineage(source_row_id),
    )


def eu_context() -> RraoCalculationContext:
    return RraoCalculationContext(
        run_id="eu-rrao-run",
        calculation_date=date(2026, 3, 31),
        base_currency="EUR",
        profile=RraoRegulatoryProfile.EU_CRR3,
    )


def load_eu_fixture() -> dict[str, object]:
    payload = json.loads((FIXTURE_DIR / "positions.json").read_text(encoding="utf-8"))
    assert isinstance(payload, dict)
    return payload


def load_eu_fixture_context() -> RraoCalculationContext:
    payload = load_eu_fixture()["context"]
    assert isinstance(payload, dict)
    return RraoCalculationContext(
        run_id=str(payload["run_id"]),
        calculation_date=date.fromisoformat(str(payload["calculation_date"])),
        base_currency=str(payload["base_currency"]),
        profile=RraoRegulatoryProfile(str(payload["profile"])),
    )


def load_eu_fixture_positions() -> tuple[RraoPosition, ...]:
    positions = load_eu_fixture()["positions"]
    assert isinstance(positions, list)
    return tuple(_position_from_payload(position) for position in positions)


def load_eu_fixture_expected() -> dict[str, object]:
    expected = load_eu_fixture()["expected"]
    assert isinstance(expected, dict)
    return expected


def _position_from_payload(payload: object) -> RraoPosition:
    assert isinstance(payload, dict)
    exclusion_reason = payload.get("exclusion_reason")
    return RraoPosition(
        position_id=str(payload["position_id"]),
        source_row_id=str(payload["source_row_id"]),
        desk_id=str(payload["desk_id"]),
        legal_entity=str(payload["legal_entity"]),
        gross_effective_notional=float(payload["gross_effective_notional"]),
        currency=str(payload["currency"]),
        evidence_type=RraoEvidenceType(str(payload["evidence_type"])),
        evidence_label=str(payload["evidence_label"]),
        classification_hint=RraoClassification(str(payload["classification_hint"])),
        exclusion_reason=(
            RraoExclusionReason(str(exclusion_reason)) if exclusion_reason is not None else None
        ),
        exclusion_evidence_id=_optional_str(payload.get("exclusion_evidence_id")),
        lineage=sample_lineage(str(payload["source_row_id"])),
    )


def _optional_str(value: object) -> str | None:
    if value is None:
        return None
    return str(value)


def test_eu_profile_calculates_article_1_article_2_and_article_3_fixture() -> None:
    expected = load_eu_fixture_expected()
    result = calculate_rrao_capital(
        load_eu_fixture_positions(),
        context=load_eu_fixture_context(),
    )

    assert result.profile_id == "EU_CRR3"
    assert result.total_rrao == expected["total_rrao"]
    assert [line.position_id for line in result.lines] == expected["included_position_ids"]
    assert result.lines[0].risk_weight == 0.01
    assert result.lines[0].reason_code == "EU_CRR3_EXOTIC_UNDERLYING"
    assert "eu_rts_2022_2328_article_1" in result.lines[0].citations
    assert "eu_crr_325u_3_a" in result.lines[0].citations
    assert result.lines[1].risk_weight == 0.001
    assert result.lines[1].reason_code == "EU_CRR3_PATH_DEPENDENT_OPTION"
    assert "eu_rts_2022_2328_article_2_annex" in result.lines[1].citations
    assert "eu_crr_325u_3_b" in result.lines[1].citations
    assert [line.position_id for line in result.excluded_lines] == expected["excluded_position_ids"]
    assert result.excluded_lines[0].add_on == 0.0
    assert result.excluded_lines[0].reason_code == (
        "EU_CRR3_NON_PRESUMPTIVE_EU_ARTICLE_3_INDEX_OPTION_CORRELATION"
    )
    assert "eu_rts_2022_2328_article_3" in result.excluded_lines[0].citations
    assert result.warnings == ()


@pytest.mark.parametrize("evidence_type", EU_ARTICLE_2_ANNEX_EVIDENCE)
def test_eu_article_2_annex_evidence_maps_to_other_residual_risk(
    evidence_type: RraoEvidenceType,
) -> None:
    decision = classify_rrao_position(
        eu_position(
            position_id=f"eu-{evidence_type.value.lower()}",
            evidence_type=evidence_type,
            evidence_label=evidence_type.value.lower(),
            classification_hint=RraoClassification.OTHER_RESIDUAL_RISK,
        ),
        profile=RraoRegulatoryProfile.EU_CRR3,
    )

    assert decision.classification is RraoClassification.OTHER_RESIDUAL_RISK
    assert decision.risk_weight_key == "OTHER_0_1_PERCENT"
    assert decision.citations == ("eu_rts_2022_2328_article_2_annex",)


@pytest.mark.parametrize("exclusion_reason", EU_ARTICLE_3_EXCLUSION_REASONS)
def test_eu_article_3_non_presumptive_risks_are_cited_zero_capital_records(
    exclusion_reason: RraoExclusionReason,
) -> None:
    result = calculate_rrao_capital(
        (
            eu_position(
                position_id=f"eu-{exclusion_reason.value.lower()}",
                evidence_type=RraoEvidenceType.EXPLICIT_EXCLUSION,
                evidence_label=exclusion_reason.value.lower(),
                classification_hint=RraoClassification.EXCLUDED,
                exclusion_reason=exclusion_reason,
                exclusion_evidence_id=f"{exclusion_reason.value.lower()}-evidence",
            ),
        ),
        context=eu_context(),
    )

    assert result.total_rrao == 0.0
    assert result.lines == ()
    assert result.excluded_lines[0].exclusion_reason is exclusion_reason
    assert result.excluded_lines[0].risk_weight == 0.0
    assert result.excluded_lines[0].citations == ("eu_rts_2022_2328_article_3",)


@pytest.mark.parametrize("exclusion_reason", EU_ARTICLE_325U_4_EXCLUSION_REASONS)
def test_eu_article_325u_4_exemptions_are_cited_zero_capital_records(
    exclusion_reason: RraoExclusionReason,
) -> None:
    result = calculate_rrao_capital(
        (
            eu_position(
                position_id=f"eu-{exclusion_reason.value.lower()}",
                evidence_type=RraoEvidenceType.EXPLICIT_EXCLUSION,
                evidence_label=exclusion_reason.value.lower(),
                classification_hint=RraoClassification.EXCLUDED,
                exclusion_reason=exclusion_reason,
                exclusion_evidence_id=f"{exclusion_reason.value.lower()}-evidence",
            ),
        ),
        context=eu_context(),
    )

    assert result.total_rrao == 0.0
    assert result.lines == ()
    assert result.excluded_lines[0].exclusion_reason is exclusion_reason
    assert result.excluded_lines[0].risk_weight == 0.0
    assert result.excluded_lines[0].citations == ("eu_crr_325u_4",)


def test_eu_profile_rejects_us_specific_gap_risk_evidence() -> None:
    with pytest.raises(RraoInputError, match="no RRAO evidence rule"):
        classify_rrao_position(
            eu_position(
                position_id="eu-gap-risk",
                evidence_type=RraoEvidenceType.GAP_RISK,
                evidence_label="gap risk",
                classification_hint=RraoClassification.OTHER_RESIDUAL_RISK,
            ),
            profile=RraoRegulatoryProfile.EU_CRR3,
        )
