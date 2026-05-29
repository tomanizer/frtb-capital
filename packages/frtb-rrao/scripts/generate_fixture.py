"""Generate the deterministic RRAO sample-book v1 integration fixture.

Usage (from the packages/frtb-rrao directory or the monorepo root):
    python scripts/generate_fixture.py [--output tests/fixtures/rrao_sample_book_v1]

The fixture covers every evidence type supported by the model, multiple desks
and legal entities, investment-fund positions (US NPR only), supervisor-directed
inclusion, and the full set of exclusion reasons available under US NPR 2.0.
It is intentionally richer than rrao_v1 to give notebooks meaningful spread
across the classification tree.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import date
from pathlib import Path

from frtb_rrao import (
    RraoBackToBackMatch,
    RraoCalculationContext,
    RraoClassification,
    RraoEvidenceType,
    RraoExclusionReason,
    RraoInvestmentFundDescriptor,
    RraoInvestmentFundExposureType,
    RraoInvestmentFundMethod,
    RraoPosition,
    RraoRegulatoryProfile,
    RraoSourceLineage,
    calculate_rrao_capital,
    serialize_rrao_result,
)

_FIXTURE_VERSION = "1"
_CALCULATION_DATE = date(2026, 3, 31)
_BASE_CURRENCY = "USD"
_RUN_ID = "rrao-sample-book-v1"

CONTEXT = RraoCalculationContext(
    run_id=_RUN_ID,
    calculation_date=_CALCULATION_DATE,
    base_currency=_BASE_CURRENCY,
    profile=RraoRegulatoryProfile.US_NPR_2_0,
)


def _lineage(row_id: str, source_file: str = "sample_book.json") -> RraoSourceLineage:
    return RraoSourceLineage(
        source_system="synthetic-rrao-sample-book",
        source_file=source_file,
        source_row_id=row_id,
        source_column_map=(
            ("evidence_type", "evidence_type"),
            ("gross_effective_notional", "gross_effective_notional"),
        ),
    )


# ---------------------------------------------------------------------------
# Positions
# ---------------------------------------------------------------------------

POSITIONS: tuple[RraoPosition, ...] = (
    # -----------------------------------------------------------------------
    # Group A: Exotic Underlyings (desk-exotics, LE-IB-NY)
    # Basel MAR23.2 / US NPR __.211(a)(1): instruments with exotic underlyings
    # Risk weight: 1.0%
    # -----------------------------------------------------------------------
    RraoPosition(
        position_id="exotic-longevity-001",
        source_row_id="sb-001",
        desk_id="desk-exotics",
        legal_entity="LE-IB-NY",
        gross_effective_notional=50_000_000.0,
        currency=_BASE_CURRENCY,
        evidence_type=RraoEvidenceType.EXOTIC_UNDERLYING,
        evidence_label="longevity risk swap — mortality/survival rate as non-traded underlying",
        lineage=_lineage("sb-001"),
        classification_hint=RraoClassification.EXOTIC,
    ),
    RraoPosition(
        position_id="exotic-temperature-001",
        source_row_id="sb-002",
        desk_id="desk-exotics",
        legal_entity="LE-IB-NY",
        gross_effective_notional=25_000_000.0,
        currency=_BASE_CURRENCY,
        evidence_type=RraoEvidenceType.EXOTIC_UNDERLYING,
        evidence_label="weather derivative — cumulative cooling degree-days on non-exchange venue",
        lineage=_lineage("sb-002"),
        classification_hint=RraoClassification.EXOTIC,
    ),
    RraoPosition(
        position_id="exotic-nat-cat-001",
        source_row_id="sb-003",
        desk_id="desk-exotics",
        legal_entity="LE-IB-NY",
        gross_effective_notional=10_000_000.0,
        currency=_BASE_CURRENCY,
        evidence_type=RraoEvidenceType.EXOTIC_UNDERLYING,
        evidence_label="pandemic catastrophe swap — parametric trigger on WHO-declared event",
        lineage=_lineage("sb-003"),
        classification_hint=RraoClassification.EXOTIC,
    ),
    RraoPosition(
        position_id="exotic-carbon-001",
        source_row_id="sb-004",
        desk_id="desk-exotics",
        legal_entity="LE-IB-NY",
        gross_effective_notional=15_000_000.0,
        currency=_BASE_CURRENCY,
        evidence_type=RraoEvidenceType.EXOTIC_UNDERLYING,
        evidence_label="carbon credit derivative — voluntary market registry reference price",
        lineage=_lineage("sb-004"),
        classification_hint=RraoClassification.EXOTIC,
    ),
    # -----------------------------------------------------------------------
    # Group B: Gap Risk — Structured Products (desk-structured, LE-IB-NY)
    # Basel MAR23.3(i) / US NPR __.211(a)(2): gap risk
    # Risk weight: 0.1%
    # -----------------------------------------------------------------------
    RraoPosition(
        position_id="gap-autocall-001",
        source_row_id="sb-005",
        desk_id="desk-structured",
        legal_entity="LE-IB-NY",
        gross_effective_notional=200_000_000.0,
        currency=_BASE_CURRENCY,
        evidence_type=RraoEvidenceType.GAP_RISK,
        evidence_label="single-stock auto-callable — soft barrier knock-in, gap at barrier",
        lineage=_lineage("sb-005"),
        classification_hint=RraoClassification.OTHER_RESIDUAL_RISK,
    ),
    RraoPosition(
        position_id="gap-barrier-note-001",
        source_row_id="sb-006",
        desk_id="desk-structured",
        legal_entity="LE-IB-NY",
        gross_effective_notional=150_000_000.0,
        currency=_BASE_CURRENCY,
        evidence_type=RraoEvidenceType.GAP_RISK,
        evidence_label="equity-linked structured note — down-and-in put, large barrier gap",
        lineage=_lineage("sb-006"),
        classification_hint=RraoClassification.OTHER_RESIDUAL_RISK,
    ),
    # -----------------------------------------------------------------------
    # Group C: Correlation Risk (desk-structured, LE-IB-NY)
    # Basel MAR23.3(ii) / US NPR __.211(a)(2): correlation risk
    # Risk weight: 0.1%
    # -----------------------------------------------------------------------
    RraoPosition(
        position_id="corr-swap-equity-001",
        source_row_id="sb-007",
        desk_id="desk-structured",
        legal_entity="LE-IB-NY",
        gross_effective_notional=35_000_000.0,
        currency=_BASE_CURRENCY,
        evidence_type=RraoEvidenceType.CORRELATION_RISK,
        evidence_label="equity correlation swap — realised vs implied pairwise correlation",
        lineage=_lineage("sb-007"),
        classification_hint=RraoClassification.OTHER_RESIDUAL_RISK,
    ),
    RraoPosition(
        position_id="corr-dispersion-001",
        source_row_id="sb-008",
        desk_id="desk-structured",
        legal_entity="LE-IB-NY",
        gross_effective_notional=20_000_000.0,
        currency=_BASE_CURRENCY,
        evidence_type=RraoEvidenceType.CORRELATION_RISK,
        evidence_label="equity dispersion via variance swaps — long index / short single-stocks",
        lineage=_lineage("sb-008"),
        classification_hint=RraoClassification.OTHER_RESIDUAL_RISK,
    ),
    # -----------------------------------------------------------------------
    # Group D: Multiple Strikes/Barriers (desk-structured, LE-IB-NY)
    # Basel MAR23.3(iv) / US NPR __.211(a)(2): multiple strike/barrier optionality
    # Risk weight: 0.1%
    # -----------------------------------------------------------------------
    RraoPosition(
        position_id="structured-multi-barrier-001",
        source_row_id="sb-009",
        desk_id="desk-structured",
        legal_entity="LE-IB-NY",
        gross_effective_notional=120_000_000.0,
        currency=_BASE_CURRENCY,
        evidence_type=RraoEvidenceType.MULTIPLE_STRIKE_OR_BARRIER_OPTIONALITY,
        evidence_label="step-down auto-callable — multiple annual barrier schedule, 5 dates",
        lineage=_lineage("sb-009"),
        classification_hint=RraoClassification.OTHER_RESIDUAL_RISK,
    ),
    # -----------------------------------------------------------------------
    # Group E: CTP Baskets — 3+ Underlyings (desk-ctp, LE-IB-LDN)
    # Basel MAR23.3(v) / US NPR __.211(a)(2): CTP with 3+ underlyings
    # Risk weight: 0.1%
    # -----------------------------------------------------------------------
    RraoPosition(
        position_id="ctp-basket-4under-001",
        source_row_id="sb-010",
        desk_id="desk-ctp",
        legal_entity="LE-IB-LDN",
        gross_effective_notional=100_000_000.0,
        currency=_BASE_CURRENCY,
        evidence_type=RraoEvidenceType.CTP_THREE_OR_MORE_UNDERLYINGS,
        evidence_label="CDX IG 4-name CTP protection basket — first-to-default",
        lineage=_lineage("sb-010"),
        classification_hint=RraoClassification.OTHER_RESIDUAL_RISK,
        is_ctp_hedge=True,
        underlying_count=4,
    ),
    RraoPosition(
        position_id="ctp-rainbow-3eq-001",
        source_row_id="sb-011",
        desk_id="desk-ctp",
        legal_entity="LE-IB-LDN",
        gross_effective_notional=75_000_000.0,
        currency=_BASE_CURRENCY,
        evidence_type=RraoEvidenceType.CTP_THREE_OR_MORE_UNDERLYINGS,
        evidence_label="3-equity rainbow worst-of option in CTP book — correlation-driven payoff",
        lineage=_lineage("sb-011"),
        classification_hint=RraoClassification.OTHER_RESIDUAL_RISK,
        is_ctp_hedge=True,
        underlying_count=3,
    ),
    # -----------------------------------------------------------------------
    # Group F: Non-Replicable Optionality (desk-ctp, LE-IB-LDN)
    # Basel MAR23.3(vi) / US NPR __.211(a)(2): non-replicable optionality
    # Risk weight: 0.1%
    # -----------------------------------------------------------------------
    RraoPosition(
        position_id="nro-illiquid-vol-001",
        source_row_id="sb-012",
        desk_id="desk-ctp",
        legal_entity="LE-IB-LDN",
        gross_effective_notional=45_000_000.0,
        currency=_BASE_CURRENCY,
        evidence_type=RraoEvidenceType.NON_REPLICABLE_OPTIONALITY,
        evidence_label="option on private equity fund NAV — non-replicable via listed or OTC vol",
        lineage=_lineage("sb-012"),
        classification_hint=RraoClassification.OTHER_RESIDUAL_RISK,
    ),
    # -----------------------------------------------------------------------
    # Group G: Behavioural Risk (desk-mortgages, LE-RTL-NY)
    # Basel MAR23.3(iii) / US NPR __.211(a)(2): behavioural risk
    # Risk weight: 0.1%
    # -----------------------------------------------------------------------
    RraoPosition(
        position_id="behav-agency-mbs-001",
        source_row_id="sb-013",
        desk_id="desk-mortgages",
        legal_entity="LE-RTL-NY",
        gross_effective_notional=500_000_000.0,
        currency=_BASE_CURRENCY,
        evidence_type=RraoEvidenceType.BEHAVIOURAL_RISK,
        evidence_label="agency MBS pipeline — prepayment-model sensitivity beyond convexity hedges",
        lineage=_lineage("sb-013"),
        classification_hint=RraoClassification.OTHER_RESIDUAL_RISK,
    ),
    RraoPosition(
        position_id="behav-callable-deposit-001",
        source_row_id="sb-014",
        desk_id="desk-mortgages",
        legal_entity="LE-RTL-NY",
        gross_effective_notional=300_000_000.0,
        currency=_BASE_CURRENCY,
        evidence_type=RraoEvidenceType.BEHAVIOURAL_RISK,
        evidence_label="callable retail time deposit — holder early-redemption optionality",
        lineage=_lineage("sb-014"),
        classification_hint=RraoClassification.OTHER_RESIDUAL_RISK,
    ),
    # -----------------------------------------------------------------------
    # Group H: Supervisor Directed (desk-supervisory, LE-IB-NY)
    # US NPR __.211(a)(4) only — not in Basel MAR23 or EU CRR3
    # Risk weight: 0.1%
    # -----------------------------------------------------------------------
    RraoPosition(
        position_id="supdir-complex-deriv-001",
        source_row_id="sb-015",
        desk_id="desk-supervisory",
        legal_entity="LE-IB-NY",
        gross_effective_notional=75_000_000.0,
        currency=_BASE_CURRENCY,
        evidence_type=RraoEvidenceType.SUPERVISOR_DIRECTIVE,
        evidence_label="complex hybrid derivative — supervisory direction ref SUPDIR-2026-001",
        lineage=_lineage("sb-015"),
        classification_hint=RraoClassification.SUPERVISOR_DIRECTED,
        supervisor_directive_id="SUPDIR-2026-001",
    ),
    # -----------------------------------------------------------------------
    # Group I: Investment-Fund Exposures (desk-funds, LE-IB-NY)
    # US NPR __.211(a)(3) / __.205(e)(3)(iii) only
    # Gross effective notional = fund_gross x included_exposure_ratio (validated)
    # Risk weight: 1.0% for EXOTIC portion, 0.1% for OTHER_RESIDUAL_RISK portion
    # -----------------------------------------------------------------------
    RraoPosition(
        position_id="fund-alpha-exotic-001",
        source_row_id="sb-016",
        desk_id="desk-funds",
        legal_entity="LE-IB-NY",
        gross_effective_notional=30_000_000.0,  # $200M x 0.15
        currency=_BASE_CURRENCY,
        evidence_type=RraoEvidenceType.INVESTMENT_FUND_EXPOSURE,
        evidence_label="Fund Alpha — backstop-method included exotic exposure portion",
        lineage=RraoSourceLineage(
            source_system="synthetic-rrao-sample-book",
            source_file="sample_book.json",
            source_row_id="sb-016",
            source_column_map=(
                ("FundID", "investment_fund_descriptor.fund_id"),
                ("Section205Method", "investment_fund_descriptor.section_205_method"),
                ("IncludedExposureRatio", "investment_fund_descriptor.included_exposure_ratio"),
                ("IncludedGrossNotional", "gross_effective_notional"),
            ),
        ),
        classification_hint=RraoClassification.EXOTIC,
        is_investment_fund_exposure=True,
        investment_fund_descriptor=RraoInvestmentFundDescriptor(
            fund_id="FUND-ALPHA-001",
            section_205_method=RraoInvestmentFundMethod.BACKSTOP_FUND_METHOD,
            included_exposure_type=RraoInvestmentFundExposureType.EXOTIC_EXPOSURE,
            mandate_evidence_id="MANDATE-ALPHA-RRAO-2026",
            section_205_evidence_id="BACKSTOP-ALPHA-2026",
            fund_gross_effective_notional=200_000_000.0,
            included_exposure_ratio=0.15,
            look_through_available=False,
            mandate_allows_rrao_exposures=True,
        ),
        citations=("us_npr_211_a_3", "us_npr_205_e_3_iii"),
    ),
    RraoPosition(
        position_id="fund-beta-residual-001",
        source_row_id="sb-017",
        desk_id="desk-funds",
        legal_entity="LE-IB-NY",
        gross_effective_notional=80_000_000.0,  # $320M x 0.25
        currency=_BASE_CURRENCY,
        evidence_type=RraoEvidenceType.INVESTMENT_FUND_EXPOSURE,
        evidence_label="Fund Beta — backstop-method included other-residual-risk exposure portion",
        lineage=RraoSourceLineage(
            source_system="synthetic-rrao-sample-book",
            source_file="sample_book.json",
            source_row_id="sb-017",
            source_column_map=(
                ("FundID", "investment_fund_descriptor.fund_id"),
                ("Section205Method", "investment_fund_descriptor.section_205_method"),
                ("IncludedExposureRatio", "investment_fund_descriptor.included_exposure_ratio"),
                ("IncludedGrossNotional", "gross_effective_notional"),
            ),
        ),
        classification_hint=RraoClassification.OTHER_RESIDUAL_RISK,
        is_investment_fund_exposure=True,
        investment_fund_descriptor=RraoInvestmentFundDescriptor(
            fund_id="FUND-BETA-001",
            section_205_method=RraoInvestmentFundMethod.BACKSTOP_FUND_METHOD,
            included_exposure_type=RraoInvestmentFundExposureType.OTHER_RESIDUAL_RISK,
            mandate_evidence_id="MANDATE-BETA-RRAO-2026",
            section_205_evidence_id="BACKSTOP-BETA-2026",
            fund_gross_effective_notional=320_000_000.0,
            included_exposure_ratio=0.25,
            look_through_available=False,
            mandate_allows_rrao_exposures=True,
        ),
        citations=("us_npr_211_a_3", "us_npr_205_e_3_iii"),
    ),
    # -----------------------------------------------------------------------
    # Group J: Common Exclusions — Basel + US NPR (desk-exclusions, LE-IB-NY)
    # -----------------------------------------------------------------------
    RraoPosition(
        position_id="excl-listed-spx-opt-001",
        source_row_id="sb-018",
        desk_id="desk-exclusions",
        legal_entity="LE-IB-NY",
        gross_effective_notional=200_000_000.0,
        currency=_BASE_CURRENCY,
        evidence_type=RraoEvidenceType.EXPLICIT_EXCLUSION,
        evidence_label="listed S&P 500 index option on CME — exchange-listed exclusion",
        lineage=_lineage("sb-018"),
        classification_hint=RraoClassification.EXCLUDED,
        exclusion_reason=RraoExclusionReason.LISTED,
        exclusion_evidence_id="EXCL-LISTED-CME-SPX-2026",
    ),
    RraoPosition(
        position_id="excl-lch-irs-001",
        source_row_id="sb-019",
        desk_id="desk-exclusions",
        legal_entity="LE-IB-NY",
        gross_effective_notional=1_000_000_000.0,
        currency=_BASE_CURRENCY,
        evidence_type=RraoEvidenceType.EXPLICIT_EXCLUSION,
        evidence_label="USD interest rate swap — LCH-cleared, eligible as CCP/QCCP clearable",
        lineage=_lineage("sb-019"),
        classification_hint=RraoClassification.EXCLUDED,
        exclusion_reason=RraoExclusionReason.CCP_OR_QCCP_CLEARABLE,
        exclusion_evidence_id="EXCL-LCH-IRS-USD-2026",
    ),
    RraoPosition(
        position_id="excl-vanilla-call-001",
        source_row_id="sb-020",
        desk_id="desk-exclusions",
        legal_entity="LE-IB-NY",
        gross_effective_notional=50_000_000.0,
        currency=_BASE_CURRENCY,
        evidence_type=RraoEvidenceType.EXPLICIT_EXCLUSION,
        evidence_label="European call on AAPL — single underlying, non-path-dependent, excluded",
        lineage=_lineage("sb-020"),
        classification_hint=RraoClassification.EXCLUDED,
        exclusion_reason=RraoExclusionReason.TWO_OR_FEWER_UNDERLYINGS_NON_PATH_DEPENDENT_OPTION,
        exclusion_evidence_id="EXCL-VANILLA-CALL-AAPL-2026",
        underlying_count=1,
        is_path_dependent=False,
    ),
    # Back-to-back pair: a temperature derivative traded identically with a third party.
    # Validation requires evidence_type=EXPLICIT_EXCLUSION for all exclusion_reason positions.
    # The excluded instrument type (temperature exotic) is captured in the evidence_label.
    RraoPosition(
        position_id="excl-btb-weather-A",
        source_row_id="sb-021",
        desk_id="desk-exclusions",
        legal_entity="LE-IB-NY",
        gross_effective_notional=25_000_000.0,
        currency=_BASE_CURRENCY,
        evidence_type=RraoEvidenceType.EXPLICIT_EXCLUSION,
        evidence_label="temperature degree-day option — original client trade, btb excluded",
        lineage=_lineage("sb-021"),
        classification_hint=RraoClassification.EXCLUDED,
        exclusion_reason=RraoExclusionReason.EXACT_THIRD_PARTY_BACK_TO_BACK,
        exclusion_evidence_id="BTB-WEATHER-2026",
        back_to_back_match=RraoBackToBackMatch(
            match_group_id="btb-weather-001",
            matched_position_id="excl-btb-weather-B",
        ),
    ),
    RraoPosition(
        position_id="excl-btb-weather-B",
        source_row_id="sb-022",
        desk_id="desk-exclusions",
        legal_entity="LE-IB-NY",
        gross_effective_notional=25_000_000.0,
        currency=_BASE_CURRENCY,
        evidence_type=RraoEvidenceType.EXPLICIT_EXCLUSION,
        evidence_label="temperature degree-day option — third-party hedge leg, btb excluded",
        lineage=_lineage("sb-022"),
        classification_hint=RraoClassification.EXCLUDED,
        exclusion_reason=RraoExclusionReason.EXACT_THIRD_PARTY_BACK_TO_BACK,
        exclusion_evidence_id="BTB-WEATHER-2026",
        back_to_back_match=RraoBackToBackMatch(
            match_group_id="btb-weather-001",
            matched_position_id="excl-btb-weather-A",
        ),
    ),
    # -----------------------------------------------------------------------
    # Group K: US NPR-Only Exclusions (desk-exclusions-us, LE-IB-NY)
    # These positions would fail under Basel MAR23 — referenced in notebook 04.
    # -----------------------------------------------------------------------
    RraoPosition(
        position_id="excl-deliverable-fx-001",
        source_row_id="sb-023",
        desk_id="desk-exclusions",
        legal_entity="LE-IB-NY",
        gross_effective_notional=100_000_000.0,
        currency=_BASE_CURRENCY,
        evidence_type=RraoEvidenceType.EXPLICIT_EXCLUSION,
        evidence_label="deliverable EUR/USD forward — qualifying hedge-pair deliverable exclusion",
        lineage=_lineage("sb-023"),
        classification_hint=RraoClassification.EXCLUDED,
        exclusion_reason=RraoExclusionReason.DELIVERABLE_HEDGE_PAIR,
        exclusion_evidence_id="EXCL-DLV-EURUSD-FWD-2026",
    ),
    RraoPosition(
        position_id="excl-us-tsy-option-001",
        source_row_id="sb-024",
        desk_id="desk-exclusions",
        legal_entity="LE-IB-NY",
        gross_effective_notional=250_000_000.0,
        currency=_BASE_CURRENCY,
        evidence_type=RraoEvidenceType.EXPLICIT_EXCLUSION,
        evidence_label="swaption on 10Y US Treasury rate — U.S. government debt exclusion",
        lineage=_lineage("sb-024"),
        classification_hint=RraoClassification.EXCLUDED,
        exclusion_reason=RraoExclusionReason.GOVERNMENT_OR_GSE_DEBT,
        exclusion_evidence_id="EXCL-UST-SWAPTION-2026",
    ),
    RraoPosition(
        position_id="excl-fallback-capital-001",
        source_row_id="sb-025",
        desk_id="desk-exclusions",
        legal_entity="LE-IB-NY",
        gross_effective_notional=45_000_000.0,
        currency=_BASE_CURRENCY,
        evidence_type=RraoEvidenceType.EXPLICIT_EXCLUSION,
        evidence_label="structured note — subject to separate fallback capital treatment",
        lineage=_lineage("sb-025"),
        classification_hint=RraoClassification.EXCLUDED,
        exclusion_reason=RraoExclusionReason.FALLBACK_CAPITAL_REQUIREMENT,
        exclusion_evidence_id="EXCL-FALLBACK-NOTE-2026",
    ),
)


def _positions_payload() -> dict[str, object]:
    return {
        "context": {
            "run_id": CONTEXT.run_id,
            "calculation_date": CONTEXT.calculation_date.isoformat(),
            "base_currency": CONTEXT.base_currency,
            "profile": CONTEXT.profile.value,
        },
        "fixture_notes": (
            "Synthetic deterministic sample book. 25 positions across 7 desks, "
            "3 legal entities, and all evidence types supported by US NPR 2.0. "
            "Positions sb-015 (SUPERVISOR_DIRECTIVE), sb-016/017 (INVESTMENT_FUND_EXPOSURE), "
            "and sb-023/024/025 (US-NPR-only exclusion reasons) are not compatible with "
            "Basel MAR23 — see notebook 04 for multi-profile comparison."
        ),
        "positions": [_position_to_dict(p) for p in POSITIONS],
    }


def _position_to_dict(position: RraoPosition) -> dict[str, object]:
    d: dict[str, object] = {
        "position_id": position.position_id,
        "source_row_id": position.source_row_id,
        "desk_id": position.desk_id,
        "legal_entity": position.legal_entity,
        "gross_effective_notional": position.gross_effective_notional,
        "currency": position.currency,
        "evidence_type": position.evidence_type.value,
        "evidence_label": position.evidence_label,
        "classification_hint": position.classification_hint.value
        if position.classification_hint is not None
        else None,
        "exclusion_reason": position.exclusion_reason.value
        if position.exclusion_reason is not None
        else None,
        "exclusion_evidence_id": position.exclusion_evidence_id,
        "supervisor_directive_id": position.supervisor_directive_id,
        "underlying_count": position.underlying_count,
        "is_path_dependent": position.is_path_dependent,
        "is_ctp_hedge": position.is_ctp_hedge,
        "is_investment_fund_exposure": position.is_investment_fund_exposure,
        "notional_source": position.notional_source,
        "citations": list(position.citations),
    }
    if position.back_to_back_match is not None:
        d["back_to_back_match"] = {
            "match_group_id": position.back_to_back_match.match_group_id,
            "matched_position_id": position.back_to_back_match.matched_position_id,
        }
    if position.investment_fund_descriptor is not None:
        desc = position.investment_fund_descriptor
        d["investment_fund_descriptor"] = {
            "fund_id": desc.fund_id,
            "section_205_method": desc.section_205_method.value,
            "included_exposure_type": desc.included_exposure_type.value,
            "mandate_evidence_id": desc.mandate_evidence_id,
            "section_205_evidence_id": desc.section_205_evidence_id,
            "fund_gross_effective_notional": desc.fund_gross_effective_notional,
            "included_exposure_ratio": desc.included_exposure_ratio,
            "look_through_available": desc.look_through_available,
            "mandate_allows_rrao_exposures": desc.mandate_allows_rrao_exposures,
        }
    return d


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        default="tests/fixtures/rrao_sample_book_v1",
        help="Output directory for fixture files",
    )
    args = parser.parse_args()
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Write positions.json
    positions_path = output_dir / "positions.json"
    positions_path.write_text(
        json.dumps(_positions_payload(), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print(f"wrote {positions_path}")

    # Compute expected outputs under US NPR 2.0
    result = calculate_rrao_capital(POSITIONS, context=CONTEXT)
    expected_path = output_dir / "expected_outputs.json"
    expected_path.write_text(
        json.dumps(serialize_rrao_result(result), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print(f"wrote {expected_path}")

    # Write manifest.json
    manifest = {
        "schema_version": "rrao_sample_book_fixture_v1",
        "generator": "scripts/generate_fixture.py",
        "generator_command": (f"python scripts/generate_fixture.py --output {args.output}"),
        "generator_version": _FIXTURE_VERSION,
        "profile": CONTEXT.profile.value,
        "calculation_date": CONTEXT.calculation_date.isoformat(),
        "position_count": len(POSITIONS),
        "total_rrao_usd": result.total_rrao,
        "files": {
            "positions.json": {"sha256": _sha256(positions_path)},
            "expected_outputs.json": {"sha256": _sha256(expected_path)},
        },
    }
    manifest_path = output_dir / "manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print(f"wrote {manifest_path}")
    print(f"total RRAO: USD {result.total_rrao:,.0f}")


if __name__ == "__main__":
    main()
