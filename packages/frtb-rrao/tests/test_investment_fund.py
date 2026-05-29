from __future__ import annotations

from dataclasses import FrozenInstanceError, replace
from datetime import date

import pytest
from frtb_rrao import (
    RraoCalculationContext,
    RraoClassification,
    RraoEvidenceType,
    RraoInputError,
    RraoInvestmentFundDescriptor,
    RraoInvestmentFundExposureType,
    RraoInvestmentFundMethod,
    RraoPosition,
    RraoRegulatoryProfile,
    RraoSourceLineage,
    calculate_rrao_capital,
    classify_rrao_position,
)


def sample_lineage() -> RraoSourceLineage:
    return RraoSourceLineage(
        source_system="synthetic-risk",
        source_file="investment-funds.csv",
        source_row_id="fund-row-001",
        source_column_map=(
            ("FundID", "investment_fund_descriptor.fund_id"),
            ("Section205Method", "investment_fund_descriptor.section_205_method"),
            ("MandateEvidenceID", "investment_fund_descriptor.mandate_evidence_id"),
            ("IncludedExposureRatio", "investment_fund_descriptor.included_exposure_ratio"),
            ("IncludedGrossNotional", "gross_effective_notional"),
        ),
    )


def sample_descriptor(
    exposure_type: RraoInvestmentFundExposureType,
    **overrides: object,
) -> RraoInvestmentFundDescriptor:
    fields = {
        "fund_id": "fund-001",
        "section_205_method": RraoInvestmentFundMethod.BACKSTOP_FUND_METHOD,
        "included_exposure_type": exposure_type,
        "mandate_evidence_id": "mandate-permits-rrao-001",
        "section_205_evidence_id": "backstop-method-001",
        "fund_gross_effective_notional": 10_000_000.0,
        "included_exposure_ratio": 0.25,
    }
    fields.update(overrides)
    return RraoInvestmentFundDescriptor(**fields)  # type: ignore[arg-type]


def sample_position(
    exposure_type: RraoInvestmentFundExposureType = (
        RraoInvestmentFundExposureType.OTHER_RESIDUAL_RISK
    ),
    **overrides: object,
) -> RraoPosition:
    classification_hint = (
        RraoClassification.EXOTIC
        if exposure_type is RraoInvestmentFundExposureType.EXOTIC_EXPOSURE
        else RraoClassification.OTHER_RESIDUAL_RISK
    )
    fields = {
        "position_id": "fund-pos-001",
        "source_row_id": "fund-row-001",
        "desk_id": "equity-funds",
        "legal_entity": "LE-002",
        "gross_effective_notional": 2_500_000.0,
        "currency": "USD",
        "evidence_type": RraoEvidenceType.INVESTMENT_FUND_EXPOSURE,
        "evidence_label": "investment fund mandate permits residual-risk exposure types",
        "lineage": sample_lineage(),
        "classification_hint": classification_hint,
        "is_investment_fund_exposure": True,
        "investment_fund_descriptor": sample_descriptor(exposure_type),
        "citations": ("us_npr_211_a_3", "us_npr_205_e_3_iii"),
    }
    fields.update(overrides)
    return RraoPosition(**fields)  # type: ignore[arg-type]


def sample_context() -> RraoCalculationContext:
    return RraoCalculationContext(
        run_id="fund-run-001",
        calculation_date=date(2026, 3, 31),
        base_currency="USD",
        profile=RraoRegulatoryProfile.US_NPR_2_0,
    )


def test_investment_fund_other_residual_portion_uses_point_one_percent() -> None:
    result = calculate_rrao_capital((sample_position(),), context=sample_context())

    line = result.lines[0]
    assert result.excluded_lines == ()
    assert line.classification is RraoClassification.OTHER_RESIDUAL_RISK
    assert line.evidence_type is RraoEvidenceType.INVESTMENT_FUND_EXPOSURE
    assert line.risk_weight == 0.001
    assert line.add_on == 2500.0
    assert line.reason_code == "US_NPR_INVESTMENT_FUND_OTHER_RESIDUAL_PORTION"
    assert "us_npr_211_a_3" in line.citations
    assert "us_npr_205_e_3_iii" in line.citations
    assert "us_npr_211_c_1_ii" in line.citations


def test_investment_fund_exotic_portion_uses_one_percent() -> None:
    result = calculate_rrao_capital(
        (sample_position(RraoInvestmentFundExposureType.EXOTIC_EXPOSURE),),
        context=sample_context(),
    )

    line = result.lines[0]
    assert line.classification is RraoClassification.EXOTIC
    assert line.risk_weight == 0.01
    assert line.add_on == 25_000.0
    assert line.reason_code == "US_NPR_INVESTMENT_FUND_EXOTIC_PORTION"
    assert "us_npr_211_c_1_i" in line.citations


@pytest.mark.parametrize(
    ("position", "match"),
    [
        (
            sample_position(investment_fund_descriptor=None),
            "investment fund descriptor",
        ),
        (
            sample_position(is_investment_fund_exposure=False),
            "investment fund exposure flag",
        ),
        (
            sample_position(
                investment_fund_descriptor=sample_descriptor(
                    RraoInvestmentFundExposureType.OTHER_RESIDUAL_RISK,
                    mandate_evidence_id="",
                )
            ),
            "mandate_evidence_id",
        ),
        (
            sample_position(
                investment_fund_descriptor=sample_descriptor(
                    RraoInvestmentFundExposureType.OTHER_RESIDUAL_RISK,
                    section_205_method=RraoInvestmentFundMethod.HYPOTHETICAL_PORTFOLIO,
                )
            ),
            "__.205\\(e\\)\\(3\\)\\(iii\\)",
        ),
        (
            sample_position(
                investment_fund_descriptor=sample_descriptor(
                    RraoInvestmentFundExposureType.OTHER_RESIDUAL_RISK,
                    look_through_available=True,
                )
            ),
            "non-look-through",
        ),
        (
            sample_position(
                investment_fund_descriptor=sample_descriptor(
                    RraoInvestmentFundExposureType.OTHER_RESIDUAL_RISK,
                    mandate_allows_rrao_exposures=False,
                )
            ),
            "mandate evidence",
        ),
        (
            sample_position(gross_effective_notional=1_000_000.0),
            "investment-fund included portion",
        ),
    ],
)
def test_investment_fund_inputs_fail_closed_when_linkage_is_partial(
    position: RraoPosition,
    match: str,
) -> None:
    with pytest.raises(RraoInputError, match=match):
        calculate_rrao_capital((position,), context=sample_context())


def test_investment_fund_classification_hint_must_match_cited_portion() -> None:
    with pytest.raises(RraoInputError, match="classification hint conflicts"):
        classify_rrao_position(
            sample_position(
                RraoInvestmentFundExposureType.EXOTIC_EXPOSURE,
                classification_hint=RraoClassification.OTHER_RESIDUAL_RISK,
            )
        )


def test_basel_profile_rejects_us_investment_fund_inclusion_path() -> None:
    for profile in (RraoRegulatoryProfile.BASEL_MAR23, RraoRegulatoryProfile.EU_CRR3):
        with pytest.raises(RraoInputError, match="no RRAO investment-fund rule"):
            classify_rrao_position(sample_position(), profile=profile)


def test_descriptor_is_frozen() -> None:
    descriptor = sample_descriptor(RraoInvestmentFundExposureType.OTHER_RESIDUAL_RISK)

    with pytest.raises(FrozenInstanceError, match="cannot assign"):
        descriptor.fund_id = "other-fund"  # type: ignore[misc]
    assert replace(descriptor, included_exposure_ratio=0.1).included_exposure_ratio == 0.1
