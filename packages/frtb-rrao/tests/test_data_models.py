from __future__ import annotations

from dataclasses import FrozenInstanceError
from datetime import date

import pytest

from frtb_rrao import (
    RraoBackToBackMatch,
    RraoCalculationContext,
    RraoCapitalLine,
    RraoCapitalResult,
    RraoCitation,
    RraoClassification,
    RraoClassificationDecision,
    RraoEvidenceType,
    RraoExclusionReason,
    RraoInvestmentFundDescriptor,
    RraoInvestmentFundExposureType,
    RraoInvestmentFundMethod,
    RraoPosition,
    RraoRegulatoryProfile,
    RraoSourceLineage,
    RraoSubtotal,
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


def sample_position() -> RraoPosition:
    return RraoPosition(
        position_id="pos-001",
        source_row_id="row-001",
        desk_id="rates-exotics",
        legal_entity="LE-001",
        gross_effective_notional=1_000_000.0,
        currency="USD",
        evidence_type=RraoEvidenceType.EXOTIC_UNDERLYING,
        evidence_label="weather derivative",
        classification_hint=RraoClassification.EXOTIC,
        lineage=sample_lineage(),
        citations=("basel_mar23_2",),
    )


def test_rrao_enums_have_stable_wire_values() -> None:
    assert RraoClassification.EXOTIC == "EXOTIC"
    assert RraoClassification.OTHER_RESIDUAL_RISK == "OTHER_RESIDUAL_RISK"
    assert RraoEvidenceType.NO_MATURITY_OPTIONALITY == "NO_MATURITY_OPTIONALITY"
    assert RraoEvidenceType.PATH_DEPENDENT_OPTION == "PATH_DEPENDENT_OPTION"
    assert RraoExclusionReason.EXACT_THIRD_PARTY_BACK_TO_BACK == "EXACT_THIRD_PARTY_BACK_TO_BACK"
    assert (
        RraoExclusionReason.EU_ARTICLE_3_INDEX_OPTION_CORRELATION
        == "EU_ARTICLE_3_INDEX_OPTION_CORRELATION"
    )
    assert RraoRegulatoryProfile.US_NPR_2_0 == "US_NPR_2_0"
    assert RraoInvestmentFundMethod.BACKSTOP_FUND_METHOD == "BACKSTOP_FUND_METHOD"
    assert RraoInvestmentFundExposureType.EXOTIC_EXPOSURE == "EXOTIC_EXPOSURE"


def test_rrao_position_is_frozen_and_carries_lineage() -> None:
    position = sample_position()

    assert position.position_id == "pos-001"
    assert position.lineage == sample_lineage()
    assert position.citations == ("basel_mar23_2",)
    with pytest.raises(FrozenInstanceError):
        position.currency = "EUR"  # type: ignore[misc]


def test_investment_fund_descriptor_is_frozen_and_carries_linkage() -> None:
    descriptor = RraoInvestmentFundDescriptor(
        fund_id="fund-001",
        section_205_method=RraoInvestmentFundMethod.BACKSTOP_FUND_METHOD,
        included_exposure_type=RraoInvestmentFundExposureType.OTHER_RESIDUAL_RISK,
        mandate_evidence_id="mandate-001",
        section_205_evidence_id="section-205-001",
        fund_gross_effective_notional=10_000_000.0,
        included_exposure_ratio=0.25,
    )

    assert descriptor.fund_id == "fund-001"
    assert descriptor.section_205_method is RraoInvestmentFundMethod.BACKSTOP_FUND_METHOD
    with pytest.raises(FrozenInstanceError):
        descriptor.fund_id = "fund-002"  # type: ignore[misc]


def test_back_to_back_match_is_frozen_and_explicit() -> None:
    match = RraoBackToBackMatch(
        match_group_id="match-group-001",
        matched_position_id="position-b",
    )

    assert match.match_group_id == "match-group-001"
    assert match.matched_position_id == "position-b"
    with pytest.raises(FrozenInstanceError):
        match.matched_position_id = "position-c"  # type: ignore[misc]


def test_public_result_model_covers_decisions_lines_subtotals_and_context() -> None:
    citation = RraoCitation(
        source_id="basel_mar23",
        paragraph="MAR23.8(2)(a)",
        url="https://www.bis.org/basel_framework/chapter/MAR/23.htm",
    )
    context = RraoCalculationContext(
        run_id="run-001",
        calculation_date=date(2026, 5, 29),
        base_currency="USD",
        profile=RraoRegulatoryProfile.US_NPR_2_0,
    )
    decision = RraoClassificationDecision(
        position_id="pos-001",
        classification=RraoClassification.EXOTIC,
        evidence_type=RraoEvidenceType.EXOTIC_UNDERLYING,
        reason_code="EXOTIC_UNDERLYING",
        risk_weight_key="EXOTIC_1_PERCENT",
        citations=("basel_mar23_8_2_a",),
    )
    line = RraoCapitalLine(
        position_id=decision.position_id,
        classification=decision.classification,
        evidence_type=decision.evidence_type,
        gross_effective_notional=1_000_000.0,
        risk_weight=0.01,
        add_on=10_000.0,
        currency="USD",
        is_excluded=False,
        reason_code=decision.reason_code,
        citations=decision.citations,
    )
    subtotal = RraoSubtotal(
        subtotal_key="EXOTIC",
        subtotal_type="classification",
        gross_effective_notional=1_000_000.0,
        add_on=10_000.0,
        position_ids=("pos-001",),
    )
    result = RraoCapitalResult(
        run_id=context.run_id,
        calculation_date=context.calculation_date,
        base_currency=context.base_currency,
        profile_id=context.profile,
        profile_hash="profile-hash",
        input_hash="input-hash",
        lines=(line,),
        excluded_lines=(),
        subtotals=(subtotal,),
        total_rrao=10_000.0,
        citations=(citation.source_id,),
    )

    assert result.lines == (line,)
    assert result.excluded_lines == ()
    assert result.subtotals == (subtotal,)
    assert result.total_rrao == 10_000.0
