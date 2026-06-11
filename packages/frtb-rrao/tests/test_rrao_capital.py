from __future__ import annotations

import pytest

import frtb_rrao.capital as capital_module
from frtb_rrao import (
    RraoClassification,
    RraoEvidenceType,
    RraoExclusionReason,
    RraoPosition,
    RraoRegulatoryProfile,
    RraoSourceLineage,
)
from frtb_rrao.capital import (
    build_rrao_capital_lines,
    build_rrao_subtotals,
    included_rrao_total,
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
        lineage=sample_lineage(source_row_id),
    )


def test_build_rrao_capital_lines_applies_exotic_and_other_weights() -> None:
    lines = build_rrao_capital_lines(
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
        ),
        profile=RraoRegulatoryProfile.US_NPR_2_0,
    )

    assert [line.position_id for line in lines] == ["exotic-001", "gap-001"]
    assert lines[0].risk_weight == 0.01
    assert lines[0].add_on == 10_000.0
    assert lines[0].citations == ("us_npr_211_a_1", "us_npr_211_c_1_i")
    assert lines[1].risk_weight == 0.001
    assert lines[1].add_on == 2_000.0
    assert lines[1].citations == ("us_npr_211_a_2", "us_npr_211_c_1_ii")
    assert included_rrao_total(lines) == 12_000.0


def test_build_rrao_capital_lines_uses_batch_capital_kernel(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[object] = []
    original_batch_lines = capital_module._batch_capital_lines_from_validated

    def counting_batch_lines(*args: object, **kwargs: object) -> object:
        calls.append((args, kwargs))
        return original_batch_lines(*args, **kwargs)

    monkeypatch.setattr(capital_module, "_batch_capital_lines_from_validated", counting_batch_lines)

    lines = build_rrao_capital_lines(
        (
            sample_position(
                position_id="pos-001",
                source_row_id="row-001",
                gross_effective_notional=1_000_000.0,
                evidence_type=RraoEvidenceType.EXOTIC_UNDERLYING,
                evidence_label="weather derivative",
                classification_hint=RraoClassification.EXOTIC,
            ),
            sample_position(
                position_id="pos-002",
                source_row_id="row-002",
                gross_effective_notional=2_000_000.0,
                evidence_type=RraoEvidenceType.GAP_RISK,
                evidence_label="gap risk",
                classification_hint=RraoClassification.OTHER_RESIDUAL_RISK,
            ),
        ),
        profile=RraoRegulatoryProfile.US_NPR_2_0,
    )

    assert len(calls) == 1
    assert [line.position_id for line in lines] == ["pos-001", "pos-002"]


def test_excluded_lines_have_zero_add_on_and_remain_visible() -> None:
    lines = build_rrao_capital_lines(
        (
            sample_position(
                position_id="listed-001",
                source_row_id="row-001",
                gross_effective_notional=3_000_000.0,
                evidence_type=RraoEvidenceType.EXPLICIT_EXCLUSION,
                evidence_label="listed option",
                classification_hint=RraoClassification.EXCLUDED,
                exclusion_reason=RraoExclusionReason.LISTED,
                exclusion_evidence_id="exchange-listing-001",
            ),
        )
    )

    assert len(lines) == 1
    assert lines[0].classification is RraoClassification.EXCLUDED
    assert lines[0].is_excluded is True
    assert lines[0].risk_weight == 0.0
    assert lines[0].add_on == 0.0
    assert lines[0].gross_effective_notional == 3_000_000.0
    assert lines[0].exclusion_reason is RraoExclusionReason.LISTED
    assert lines[0].exclusion_evidence_id == "exchange-listing-001"
    assert included_rrao_total(lines) == 0.0


def test_subtotals_are_deterministic_and_reconcile_by_type() -> None:
    lines = build_rrao_capital_lines(
        (
            sample_position(
                position_id="exotic-001",
                source_row_id="row-001",
                gross_effective_notional=1_000_000.0,
                evidence_type=RraoEvidenceType.EXOTIC_UNDERLYING,
                evidence_label="weather derivative",
                classification_hint=RraoClassification.EXOTIC,
                desk_id="desk-a",
                legal_entity="LE-001",
            ),
            sample_position(
                position_id="gap-001",
                source_row_id="row-002",
                gross_effective_notional=2_000_000.0,
                evidence_type=RraoEvidenceType.GAP_RISK,
                evidence_label="gap risk",
                classification_hint=RraoClassification.OTHER_RESIDUAL_RISK,
                desk_id="desk-a",
                legal_entity="LE-001",
            ),
            sample_position(
                position_id="listed-001",
                source_row_id="row-003",
                gross_effective_notional=3_000_000.0,
                evidence_type=RraoEvidenceType.EXPLICIT_EXCLUSION,
                evidence_label="listed option",
                classification_hint=RraoClassification.EXCLUDED,
                desk_id="desk-b",
                legal_entity="LE-002",
                exclusion_reason=RraoExclusionReason.LISTED,
                exclusion_evidence_id="exchange-listing-001",
            ),
        )
    )
    subtotals = build_rrao_subtotals(lines)
    total = included_rrao_total(lines)

    assert [(subtotal.subtotal_type, subtotal.subtotal_key) for subtotal in subtotals] == [
        ("classification", "EXCLUDED"),
        ("classification", "EXOTIC"),
        ("classification", "OTHER_RESIDUAL_RISK"),
        ("evidence_type", "EXOTIC_UNDERLYING"),
        ("evidence_type", "EXPLICIT_EXCLUSION"),
        ("evidence_type", "GAP_RISK"),
        ("desk_id", "desk-a"),
        ("desk_id", "desk-b"),
        ("legal_entity", "LE-001"),
        ("legal_entity", "LE-002"),
    ]
    for subtotal_type in {"classification", "evidence_type", "desk_id", "legal_entity"}:
        assert (
            sum(
                subtotal.add_on for subtotal in subtotals if subtotal.subtotal_type == subtotal_type
            )
            == total
        )


def test_line_addons_do_not_offset_or_diversify() -> None:
    lines = build_rrao_capital_lines(
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
                position_id="exotic-002",
                source_row_id="row-002",
                gross_effective_notional=1_000_000.0,
                evidence_type=RraoEvidenceType.EXOTIC_UNDERLYING,
                evidence_label="longevity derivative",
                classification_hint=RraoClassification.EXOTIC,
            ),
        )
    )

    assert [line.add_on for line in lines] == [10_000.0, 10_000.0]
    assert included_rrao_total(lines) == 20_000.0
