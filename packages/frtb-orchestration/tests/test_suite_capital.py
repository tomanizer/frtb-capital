"""End-to-end suite capital aggregation tests.

Fixture overview
----------------
All tests use a synthetic Basel-family suite:
- IMA:  one IMA-eligible desk + one SA-fallback desk, PRA_UK_CRR profile
- SA:   SBM (BASEL_MAR21) + DRC (BASEL_MAR22) + RRAO (BASEL_MAR23)
- CVA:  BA-CVA reduced, BASEL_MAR50_2020 profile

Expected total = IMA 100.0 + SA (42 + DRC + RRAO) + CVA.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from datetime import date, datetime

import pytest
from frtb_common import (
    AttributionMethod,
    CapitalContribution,
    ComponentCapitalSummary,
    ImplementationStatus,
    StandardisedComponent,
    ValidationStatus,
)
from frtb_common.attribution import ReconciliationStatus
from frtb_common.contribution_bundle import ComponentContributionBundle
from frtb_cva import (
    CreditQuality as CvaCreditQuality,
)
from frtb_cva import (
    CvaCalculationContext,
    CvaCounterparty,
    CvaMethod,
    CvaNettingSet,
    CvaRegulatoryProfile,
    CvaSector,
    calculate_cva_capital,
)
from frtb_drc import (
    BASEL_MAR22_PROFILE_ID,
    DefaultDirection,
    DrcCalculationContext,
    DrcInstrumentType,
    DrcPosition,
    DrcRiskClass,
    DrcSeniority,
    DrcSourceLineage,
    calculate_drc_capital,
)
from frtb_drc import (
    CreditQuality as DrcCreditQuality,
)
from frtb_drc import to_component_summary as drc_to_component_summary
from frtb_orchestration import (
    PACKAGE_METADATA,
    CvaCapitalSummary,
    ImaCapitalSummary,
    OrchestrationInputError,
    StandardisedApproachCapitalResult,
    SuiteAttributionReport,
    SuiteAttributionResult,
    SuiteAttributionSummary,
    SuiteCapitalResult,
    aggregate_suite_attribution,
    build_suite_attribution_report,
    calculate_suite_capital,
    compose_standardised_approach_capital,
    recognise_cva_summary,
    recognise_ima_summary,
    suite_attribution_residual_records,
    suite_attribution_unsupported_records,
    suite_jurisdiction_family,
    summarise_suite_attribution,
    top_suite_attribution_contributors,
)
from frtb_rrao import (
    RraoCalculationContext,
    RraoClassification,
    RraoEvidenceType,
    RraoPosition,
    RraoRegulatoryProfile,
    RraoSourceLineage,
    calculate_rrao_capital,
)
from frtb_rrao import to_component_summary as rrao_to_component_summary

# ── Fixed hash sentinels for synthetic IMA fixtures ───────────────────────────
_POLICY_HASH = "a" * 64
_INPUT_HASH = "b" * 64

# ── Calculation date shared across all fixture components ─────────────────────
_CALC_DATE = date(2026, 3, 31)
_BASE_CCY = "USD"

# ── Expected IMA capital in the synthetic fixture ─────────────────────────────
_IMA_CAPITAL = 100.0


# ── Component fixture helpers ─────────────────────────────────────────────────


def synthetic_ima_summary(
    *,
    total_ima_capital: float = _IMA_CAPITAL,
    calculation_date: date = _CALC_DATE,
    base_currency: str = _BASE_CCY,
    profile_id: str = "PRA_UK_CRR",
    ima_eligible_desk_count: int = 1,
    sa_fallback_desk_count: int = 1,
    run_id: str = "ima-suite-run",
    citations: tuple[str, ...] = ("MAR31.25",),
) -> ImaCapitalSummary:
    return ImaCapitalSummary(
        package_name="frtb-ima",
        run_id=run_id,
        calculation_date=calculation_date,
        base_currency=base_currency,
        profile_id=profile_id,
        total_ima_capital=total_ima_capital,
        ima_eligible_desk_count=ima_eligible_desk_count,
        sa_fallback_desk_count=sa_fallback_desk_count,
        policy_hash=_POLICY_HASH,
        input_hash=_INPUT_HASH,
        citations=citations,
        warnings=(),
    )


def synthetic_sa_result(
    *,
    calculation_date: date = _CALC_DATE,
    base_currency: str = _BASE_CCY,
    sbm_capital: float = 42.0,
    run_id: str = "sa-suite-run",
) -> StandardisedApproachCapitalResult:
    """Build an SA result using real RRAO/DRC calculations + synthetic SBM."""

    rrao = rrao_to_component_summary(
        calculate_rrao_capital(
            (
                RraoPosition(
                    position_id="rrao-suite-001",
                    source_row_id="row-001",
                    desk_id="desk-sa-fallback",
                    legal_entity="LE-001",
                    gross_effective_notional=500_000.0,
                    currency="USD",
                    evidence_type=RraoEvidenceType.EXOTIC_UNDERLYING,
                    evidence_label="longevity derivative",
                    lineage=RraoSourceLineage(
                        source_system="suite-test",
                        source_file="rrao.csv",
                        source_row_id="row-001",
                        source_column_map=(("gross", "gross_effective_notional"),),
                    ),
                    classification_hint=RraoClassification.EXOTIC,
                ),
            ),
            context=RraoCalculationContext(
                run_id=f"{run_id}-rrao",
                calculation_date=calculation_date,
                base_currency=base_currency,
                profile=RraoRegulatoryProfile.BASEL_MAR23,
            ),
        )
    )
    drc = drc_to_component_summary(
        calculate_drc_capital(
            (
                DrcPosition(
                    position_id="drc-suite-001",
                    source_row_id="row-001",
                    desk_id="desk-sa-fallback",
                    legal_entity="LE-001",
                    risk_class=DrcRiskClass.NON_SECURITISATION,
                    instrument_type=DrcInstrumentType.BOND,
                    default_direction=DefaultDirection.LONG,
                    issuer_id="issuer-001",
                    tranche_id=None,
                    index_series_id=None,
                    bucket_key="CORPORATE",
                    seniority=DrcSeniority.SENIOR_DEBT,
                    credit_quality=DrcCreditQuality.BBB,
                    notional=100.0,
                    market_value=100.0,
                    cumulative_pnl=0.0,
                    maturity_years=1.0,
                    currency="USD",
                    lineage=DrcSourceLineage(
                        source_system="suite-test",
                        source_file="drc.csv",
                        source_row_id="row-001",
                        source_column_map={"notional": "notional"},
                    ),
                    citation_ids=("MAR22",),
                ),
            ),
            context=DrcCalculationContext(
                run_id=f"{run_id}-drc",
                calculation_date=calculation_date,
                base_currency=base_currency,
                profile_id=BASEL_MAR22_PROFILE_ID,
            ),
        )
    )
    sbm = ComponentCapitalSummary(
        component=StandardisedComponent.SBM,
        package_name="frtb-sbm",
        run_id=f"{run_id}-sbm",
        calculation_date=calculation_date,
        base_currency=base_currency,
        profile_id="BASEL_MAR21",
        total_capital=sbm_capital,
        profile_hash="profile-hash-sbm",
        input_hash="input-hash-sbm",
        line_count=3,
        excluded_line_count=0,
        subtotal_count=1,
        citations=("MAR21.4",),
    )
    return compose_standardised_approach_capital(
        sbm_summary=sbm,
        drc_summary=drc,
        rrao_summary=rrao,
        run_id=run_id,
    )


def synthetic_cva_summary(
    *,
    calculation_date: date = _CALC_DATE,
    base_currency: str = _BASE_CCY,
    run_id: str = "cva-suite-run",
) -> CvaCapitalSummary:
    counterparty = CvaCounterparty(
        counterparty_id="ctp-suite-1",
        desk_id="desk-cva",
        legal_entity="LE-001",
        sector=CvaSector.OTHER,
        credit_quality=CvaCreditQuality.INVESTMENT_GRADE,
        region="EMEA",
        source_row_id="row-ctp-1",
    )
    netting_set = CvaNettingSet(
        netting_set_id="ns-suite-1",
        counterparty_id="ctp-suite-1",
        ead=500_000.0,
        effective_maturity=2.0,
        discount_factor=1.0,
        currency="USD",
        sign_convention="non_negative",
        uses_imm_ead=False,
        source_row_id="row-ns-1",
    )
    context = CvaCalculationContext(
        run_id=run_id,
        calculation_date=calculation_date,
        base_currency=base_currency,
        profile=CvaRegulatoryProfile.BASEL_MAR50_2020,
        method=CvaMethod.BA_CVA_REDUCED,
    )
    result = calculate_cva_capital(context, (counterparty,), (netting_set,))
    return recognise_cva_summary(result)


def synthetic_contribution_bundle(
    component: str,
    component_total: float,
    *,
    source_id: str | None = None,
    citations: tuple[str, ...] = ("ADR 0038",),
) -> ComponentContributionBundle:
    contribution = CapitalContribution(
        contribution_id=f"attr-{component}",
        source_id=source_id or f"{component}-source",
        source_level="component",
        bucket_key=None,
        category=component.upper().replace("-", "_"),
        base_amount=component_total,
        marginal_multiplier=1.0,
        contribution=component_total,
        method=AttributionMethod.ANALYTICAL_EULER,
        citations=citations,
        input_hash=f"input-hash-{component}",
        profile_hash=f"profile-hash-{component}",
        reconciliation_status=ReconciliationStatus.RECONCILED,
    )
    return ComponentContributionBundle(
        component=component,
        contributions=(contribution,),
        component_total=component_total,
        component_input_hash=f"input-hash-{component}",
        component_profile_hash=f"profile-hash-{component}",
    )


def synthetic_attribution_record(
    *,
    contribution_id: str,
    source_id: str,
    source_level: str,
    category: str,
    contribution: float | None,
    residual: float = 0.0,
    method: AttributionMethod = AttributionMethod.ANALYTICAL_EULER,
    reason: str = "",
    bucket_key: str | None = None,
) -> CapitalContribution:
    return CapitalContribution(
        contribution_id=contribution_id,
        source_id=source_id,
        source_level=source_level,
        bucket_key=bucket_key,
        category=category,
        base_amount=(contribution or 0.0) + residual,
        marginal_multiplier=1.0 if method == AttributionMethod.ANALYTICAL_EULER else None,
        contribution=contribution,
        method=method,
        residual=residual,
        reason=reason,
        citations=("ADR 0038",),
        input_hash=f"input-hash-{source_id}",
        profile_hash=f"profile-hash-{source_id}",
        reconciliation_status=(
            ReconciliationStatus.PARTIAL_RESIDUAL
            if method in {AttributionMethod.RESIDUAL, AttributionMethod.UNSUPPORTED}
            or residual != 0.0
            else ReconciliationStatus.RECONCILED
        ),
    )


def synthetic_contribution_bundle_from_records(
    component: str,
    records: tuple[CapitalContribution, ...],
    *,
    component_total: float | None = None,
) -> ComponentContributionBundle:
    total = (
        math.fsum((record.contribution or 0.0) + record.residual for record in records)
        if component_total is None
        else component_total
    )
    return ComponentContributionBundle(
        component=component,
        contributions=records,
        component_total=total,
        component_input_hash=f"input-hash-{component}",
        component_profile_hash=f"profile-hash-{component}",
    )


def top_level_attribution_bundles(
    ima: ImaCapitalSummary,
    sa: StandardisedApproachCapitalResult,
    cva: CvaCapitalSummary,
) -> tuple[ComponentContributionBundle, ...]:
    return (
        synthetic_contribution_bundle("frtb_ima", ima.total_ima_capital),
        synthetic_contribution_bundle("frtb_sa", sa.total_capital),
        synthetic_contribution_bundle("frtb_cva", cva.total_cva_capital),
    )


def decomposed_attribution_bundles(
    ima: ImaCapitalSummary,
    sa: StandardisedApproachCapitalResult,
    cva: CvaCapitalSummary,
) -> tuple[ComponentContributionBundle, ...]:
    subtotals = {subtotal.component: subtotal.total_capital for subtotal in sa.component_subtotals}
    return (
        synthetic_contribution_bundle("frtb_ima", ima.total_ima_capital),
        synthetic_contribution_bundle("frtb_sbm", subtotals[StandardisedComponent.SBM]),
        synthetic_contribution_bundle("frtb_drc", subtotals[StandardisedComponent.DRC]),
        synthetic_contribution_bundle("frtb_rrao", subtotals[StandardisedComponent.RRAO]),
        synthetic_contribution_bundle("frtb_cva", cva.total_cva_capital),
    )


# ── Happy-path tests ──────────────────────────────────────────────────────────


def test_calculate_suite_capital_returns_result_with_correct_totals() -> None:
    ima = synthetic_ima_summary()
    sa = synthetic_sa_result()
    cva = synthetic_cva_summary()

    result = calculate_suite_capital(ima_summary=ima, sa_result=sa, cva_summary=cva)

    assert isinstance(result, SuiteCapitalResult)
    expected_total = math.fsum([_IMA_CAPITAL, sa.total_capital, cva.total_cva_capital])
    assert result.total_capital == pytest.approx(expected_total)
    assert result.ima_capital == pytest.approx(_IMA_CAPITAL)
    assert result.sa_capital == pytest.approx(sa.total_capital)
    assert result.cva_capital == pytest.approx(cva.total_cva_capital)


def test_calculate_suite_capital_deterministic_run_id_derivation() -> None:
    ima = synthetic_ima_summary(run_id="ima-run")
    sa = synthetic_sa_result(run_id="sa-run")
    cva = synthetic_cva_summary(run_id="cva-run")

    result = calculate_suite_capital(ima_summary=ima, sa_result=sa, cva_summary=cva)

    assert result.run_id == "suite:ima-run:sa-run:cva-run"


def test_calculate_suite_capital_explicit_run_id() -> None:
    ima = synthetic_ima_summary()
    sa = synthetic_sa_result()
    cva = synthetic_cva_summary()

    result = calculate_suite_capital(
        ima_summary=ima, sa_result=sa, cva_summary=cva, run_id="custom-suite-run"
    )

    assert result.run_id == "custom-suite-run"


def test_suite_result_audit_fields_preserved() -> None:
    ima = synthetic_ima_summary()
    sa = synthetic_sa_result()
    cva = synthetic_cva_summary()

    result = calculate_suite_capital(ima_summary=ima, sa_result=sa, cva_summary=cva)

    assert result.calculation_date == _CALC_DATE
    assert result.base_currency == _BASE_CCY
    assert result.suite_profile_family == "BASEL"
    assert result.ima_summary is ima
    assert result.sa_result is sa
    assert result.cva_summary is cva


def test_suite_result_citations_merged_from_all_components() -> None:
    ima = synthetic_ima_summary(citations=("MAR31.25",))
    sa = synthetic_sa_result()
    cva = synthetic_cva_summary()

    result = calculate_suite_capital(ima_summary=ima, sa_result=sa, cva_summary=cva)

    assert "MAR31.25" in result.citations
    assert "MAR21.4" in result.citations


def test_suite_result_as_dict_reconciles() -> None:
    ima = synthetic_ima_summary()
    sa = synthetic_sa_result()
    cva = synthetic_cva_summary()

    result = calculate_suite_capital(ima_summary=ima, sa_result=sa, cva_summary=cva)
    payload = result.as_dict()

    assert payload["total_capital"] == pytest.approx(result.total_capital)
    assert payload["ima_capital"] == pytest.approx(result.ima_capital)
    assert payload["sa_capital"] == pytest.approx(result.sa_capital)
    assert payload["cva_capital"] == pytest.approx(result.cva_capital)
    assert payload["suite_profile_family"] == "BASEL"
    assert payload["calculation_date"] == _CALC_DATE.isoformat()
    assert isinstance(payload["ima_summary"], dict)
    assert isinstance(payload["sa_result"], dict)
    assert isinstance(payload["cva_summary"], dict)


def test_suite_result_total_reconciles_to_subtotals() -> None:
    """SuiteCapitalResult __post_init__ enforces the reconciliation invariant."""
    ima = synthetic_ima_summary(total_ima_capital=100.0)
    sa = synthetic_sa_result(sbm_capital=42.0)
    cva = synthetic_cva_summary()

    result = calculate_suite_capital(ima_summary=ima, sa_result=sa, cva_summary=cva)

    recomputed = math.fsum([result.ima_capital, result.sa_capital, result.cva_capital])
    assert math.isclose(result.total_capital, recomputed, rel_tol=1e-12, abs_tol=1e-12)


def test_suite_result_has_ima_eligible_and_sa_fallback_desks() -> None:
    """The IMA summary carries desk-level eligibility counts; SA fallback routes are separate."""
    ima = synthetic_ima_summary(ima_eligible_desk_count=2, sa_fallback_desk_count=1)
    sa = synthetic_sa_result()
    cva = synthetic_cva_summary()

    result = calculate_suite_capital(ima_summary=ima, sa_result=sa, cva_summary=cva)

    assert result.ima_summary.ima_eligible_desk_count == 2
    assert result.ima_summary.sa_fallback_desk_count == 1


def test_suite_result_sa_subtotals_cover_sbm_drc_rrao() -> None:
    """SA result must contain SBM, DRC, and RRAO subtotals in aggregation order."""
    ima = synthetic_ima_summary()
    sa = synthetic_sa_result()
    cva = synthetic_cva_summary()

    result = calculate_suite_capital(ima_summary=ima, sa_result=sa, cva_summary=cva)

    components = [subtotal.component for subtotal in result.sa_result.component_subtotals]
    assert StandardisedComponent.SBM in components
    assert StandardisedComponent.DRC in components
    assert StandardisedComponent.RRAO in components


# ── Suite attribution aggregation tests ──────────────────────────────────────


def test_calculate_suite_capital_attaches_top_level_attribution_result() -> None:
    ima = synthetic_ima_summary()
    sa = synthetic_sa_result()
    cva = synthetic_cva_summary()
    bundles = top_level_attribution_bundles(ima, sa, cva)

    result = calculate_suite_capital(
        ima_summary=ima,
        sa_result=sa,
        cva_summary=cva,
        component_contribution_bundles=bundles,
    )

    assert isinstance(result.attribution_result, SuiteAttributionResult)
    attribution = result.attribution_result
    assert attribution.component_bundles == bundles
    assert attribution.component_bundles[0] is bundles[0]
    assert attribution.suite_total_capital == pytest.approx(result.total_capital)
    assert attribution.suite_residual.method == AttributionMethod.RESIDUAL
    assert attribution.suite_residual.residual == pytest.approx(0.0)
    assert attribution.suite_residual.reconciliation_status == ReconciliationStatus.RECONCILED


def test_suite_attribution_preserves_incoming_contribution_fields() -> None:
    ima = synthetic_ima_summary()
    sa = synthetic_sa_result()
    cva = synthetic_cva_summary()
    bundle = synthetic_contribution_bundle(
        "frtb_ima",
        ima.total_ima_capital,
        source_id="desk-ima-001",
        citations=("MAR31.25", "ADR 0038"),
    )
    bundles = (
        bundle,
        synthetic_contribution_bundle("frtb_sa", sa.total_capital),
        synthetic_contribution_bundle("frtb_cva", cva.total_cva_capital),
    )
    incoming_record = bundle.contributions[0]

    result = calculate_suite_capital(
        ima_summary=ima,
        sa_result=sa,
        cva_summary=cva,
        component_contribution_bundles=bundles,
    )

    preserved = result.attribution_result.component_bundles[0].contributions[0]  # type: ignore[union-attr]
    assert preserved is incoming_record
    assert preserved.contribution == incoming_record.contribution
    assert preserved.base_amount == incoming_record.base_amount
    assert preserved.method == incoming_record.method
    assert preserved.source_id == "desk-ima-001"
    assert preserved.citations == ("MAR31.25", "ADR 0038")


def test_aggregate_suite_attribution_accepts_decomposed_sa_component_bundles() -> None:
    ima = synthetic_ima_summary()
    sa = synthetic_sa_result()
    cva = synthetic_cva_summary()
    suite = calculate_suite_capital(ima_summary=ima, sa_result=sa, cva_summary=cva)
    bundles = decomposed_attribution_bundles(ima, sa, cva)

    attribution = aggregate_suite_attribution(suite_result=suite, component_bundles=bundles)

    assert [bundle.component for bundle in attribution.component_bundles] == [
        "frtb_ima",
        "frtb_sbm",
        "frtb_drc",
        "frtb_rrao",
        "frtb_cva",
    ]
    assert attribution.suite_residual.residual == pytest.approx(0.0)


def test_aggregate_suite_attribution_emits_non_zero_suite_residual() -> None:
    ima = synthetic_ima_summary()
    sa = synthetic_sa_result()
    cva = synthetic_cva_summary()
    suite = calculate_suite_capital(ima_summary=ima, sa_result=sa, cva_summary=cva)
    bundles = top_level_attribution_bundles(ima, sa, cva)

    attribution = aggregate_suite_attribution(
        suite_result=suite,
        component_bundles=bundles,
        suite_total_capital=suite.total_capital + 7.5,
    )

    assert attribution.suite_total_capital == pytest.approx(suite.total_capital + 7.5)
    assert attribution.suite_residual.method == AttributionMethod.RESIDUAL
    assert attribution.suite_residual.residual == pytest.approx(7.5)
    assert attribution.suite_residual.reconciliation_status == ReconciliationStatus.PARTIAL_RESIDUAL
    assert "cross-component interactions" in attribution.suite_residual.reason


def test_suite_attribution_rejects_component_total_mismatch() -> None:
    ima = synthetic_ima_summary()
    sa = synthetic_sa_result()
    cva = synthetic_cva_summary()
    suite = calculate_suite_capital(ima_summary=ima, sa_result=sa, cva_summary=cva)
    bundles = (
        synthetic_contribution_bundle("frtb_ima", ima.total_ima_capital + 1.0),
        synthetic_contribution_bundle("frtb_sa", sa.total_capital),
        synthetic_contribution_bundle("frtb_cva", cva.total_cva_capital),
    )

    with pytest.raises(OrchestrationInputError, match="component_total") as exc_info:
        aggregate_suite_attribution(suite_result=suite, component_bundles=bundles)
    assert exc_info.value.field == "component_bundles"


def test_suite_attribution_rejects_incomplete_component_set() -> None:
    ima = synthetic_ima_summary()
    sa = synthetic_sa_result()
    cva = synthetic_cva_summary()
    suite = calculate_suite_capital(ima_summary=ima, sa_result=sa, cva_summary=cva)
    bundles = (
        synthetic_contribution_bundle("frtb_ima", ima.total_ima_capital),
        synthetic_contribution_bundle("frtb_sa", sa.total_capital),
    )

    with pytest.raises(OrchestrationInputError, match="complete suite attribution"):
        aggregate_suite_attribution(suite_result=suite, component_bundles=bundles)


def test_suite_attribution_result_as_dict_is_json_serialisable() -> None:
    ima = synthetic_ima_summary()
    sa = synthetic_sa_result()
    cva = synthetic_cva_summary()
    result = calculate_suite_capital(
        ima_summary=ima,
        sa_result=sa,
        cva_summary=cva,
        component_contribution_bundles=top_level_attribution_bundles(ima, sa, cva),
    )

    payload = result.as_dict()

    json.dumps(payload, sort_keys=True)
    assert payload["attribution_result"]["suite_total_capital"] == pytest.approx(  # type: ignore[index]
        result.total_capital
    )


def test_build_suite_attribution_report_top_level_payload_is_json_serialisable() -> None:
    ima = synthetic_ima_summary()
    sa = synthetic_sa_result()
    cva = synthetic_cva_summary()
    suite = calculate_suite_capital(ima_summary=ima, sa_result=sa, cva_summary=cva)
    bundles = top_level_attribution_bundles(ima, sa, cva)

    report = build_suite_attribution_report(suite_result=suite, component_bundles=bundles)
    payload = report.as_dict()

    assert isinstance(report, SuiteAttributionReport)
    assert report.run_id == suite.run_id
    assert report.suite_total_capital == pytest.approx(suite.total_capital)
    assert report.component_set == ("frtb_ima", "frtb_sa", "frtb_cva")
    assert [component.component for component in report.components] == [
        "frtb_ima",
        "frtb_sa",
        "frtb_cva",
    ]
    assert report.components[0].contributions[0] is bundles[0].contributions[0]
    assert report.contribution_records[-1] is report.suite_residual
    assert report.suite_residual.reconciliation_status == ReconciliationStatus.RECONCILED
    assert report.reconciliation_status == ReconciliationStatus.RECONCILED
    json.dumps(payload, sort_keys=True)
    assert payload["component_set"] == ["frtb_ima", "frtb_sa", "frtb_cva"]
    assert payload["contribution_record_count"] == 4


def test_build_suite_attribution_report_orders_decomposed_components_canonically() -> None:
    ima = synthetic_ima_summary()
    sa = synthetic_sa_result()
    cva = synthetic_cva_summary()
    suite = calculate_suite_capital(ima_summary=ima, sa_result=sa, cva_summary=cva)
    bundles = tuple(reversed(decomposed_attribution_bundles(ima, sa, cva)))

    report = build_suite_attribution_report(suite_result=suite, component_bundles=bundles)

    assert report.component_set == (
        "frtb_ima",
        "frtb_sbm",
        "frtb_drc",
        "frtb_rrao",
        "frtb_cva",
    )
    assert [component.component for component in report.components] == list(report.component_set)
    assert [component.contributions[0].contribution_id for component in report.components] == [
        "attr-frtb_ima",
        "attr-frtb_sbm",
        "attr-frtb_drc",
        "attr-frtb_rrao",
        "attr-frtb_cva",
    ]
    original_by_component = {bundle.component: bundle.contributions[0] for bundle in bundles}
    assert report.components[0].contributions[0] is original_by_component["frtb_ima"]


def test_build_suite_attribution_report_surfaces_residual_reason() -> None:
    ima = synthetic_ima_summary()
    sa = synthetic_sa_result()
    cva = synthetic_cva_summary()
    suite = calculate_suite_capital(ima_summary=ima, sa_result=sa, cva_summary=cva)
    bundles = top_level_attribution_bundles(ima, sa, cva)

    report = build_suite_attribution_report(
        suite_result=suite,
        component_bundles=bundles,
        suite_total_capital=suite.total_capital + 7.5,
    )

    assert report.suite_total_capital == pytest.approx(suite.total_capital + 7.5)
    assert report.suite_residual.residual == pytest.approx(7.5)
    assert report.reconciliation_status == ReconciliationStatus.PARTIAL_RESIDUAL
    assert report.residual_reason == report.suite_residual.reason
    assert "cross-component interactions" in report.residual_reason


def test_build_suite_attribution_report_rejects_duplicate_component_bundle() -> None:
    ima = synthetic_ima_summary()
    sa = synthetic_sa_result()
    cva = synthetic_cva_summary()
    suite = calculate_suite_capital(ima_summary=ima, sa_result=sa, cva_summary=cva)
    bundles = (
        synthetic_contribution_bundle("frtb_ima", ima.total_ima_capital),
        synthetic_contribution_bundle("ima", ima.total_ima_capital),
        synthetic_contribution_bundle("frtb_sa", sa.total_capital),
        synthetic_contribution_bundle("frtb_cva", cva.total_cva_capital),
    )

    with pytest.raises(OrchestrationInputError, match="duplicate contribution bundle"):
        build_suite_attribution_report(suite_result=suite, component_bundles=bundles)


def test_build_suite_attribution_report_rejects_partial_component_set() -> None:
    ima = synthetic_ima_summary()
    sa = synthetic_sa_result()
    cva = synthetic_cva_summary()
    suite = calculate_suite_capital(ima_summary=ima, sa_result=sa, cva_summary=cva)
    bundles = (
        synthetic_contribution_bundle("frtb_ima", ima.total_ima_capital),
        synthetic_contribution_bundle("frtb_cva", cva.total_cva_capital),
    )

    with pytest.raises(OrchestrationInputError, match="complete suite attribution"):
        build_suite_attribution_report(suite_result=suite, component_bundles=bundles)


def test_summarise_suite_attribution_top_level_groups_include_drillthrough_ids() -> None:
    ima = synthetic_ima_summary()
    sa = synthetic_sa_result()
    cva = synthetic_cva_summary()
    suite = calculate_suite_capital(ima_summary=ima, sa_result=sa, cva_summary=cva)
    bundles = top_level_attribution_bundles(ima, sa, cva)
    report = build_suite_attribution_report(suite_result=suite, component_bundles=bundles)

    summary = summarise_suite_attribution(report, top_n=2)
    payload = summary.as_dict()

    assert isinstance(summary, SuiteAttributionSummary)
    assert len(summary.top_contributors) == 2
    assert {row.group_key for row in summary.contributors_by_component} == {
        "frtb_ima",
        "frtb_sa",
        "frtb_cva",
        "suite",
    }
    component_rows = {row.group_key: row for row in summary.contributors_by_component}
    assert component_rows["frtb_ima"].contribution_ids == ("attr-frtb_ima",)
    assert component_rows["frtb_ima"].source_ids == ("frtb_ima-source",)
    source_level_rows = {row.group_key: row for row in summary.contributors_by_source_level}
    assert source_level_rows["component"].record_count == 3
    assert source_level_rows["suite"].contribution_ids == (report.suite_residual.contribution_id,)
    json.dumps(payload, sort_keys=True)


def test_top_suite_attribution_contributors_uses_stable_tie_sorting() -> None:
    ima = synthetic_ima_summary()
    sa = synthetic_sa_result()
    cva = synthetic_cva_summary()
    suite = calculate_suite_capital(ima_summary=ima, sa_result=sa, cva_summary=cva)
    ima_bundle = synthetic_contribution_bundle_from_records(
        "frtb_ima",
        (
            synthetic_attribution_record(
                contribution_id="ima-desk-b",
                source_id="desk-b",
                source_level="desk",
                category="IMA_DESK",
                contribution=50.0,
            ),
            synthetic_attribution_record(
                contribution_id="ima-desk-a",
                source_id="desk-a",
                source_level="desk",
                category="IMA_DESK",
                contribution=50.0,
            ),
        ),
    )
    report = build_suite_attribution_report(
        suite_result=suite,
        component_bundles=(
            ima_bundle,
            synthetic_contribution_bundle("frtb_sa", sa.total_capital),
            synthetic_contribution_bundle("frtb_cva", cva.total_cva_capital),
        ),
    )

    rows = top_suite_attribution_contributors(report, top_n=10)
    ima_rows = [row.contribution_id for row in rows if row.component == "frtb_ima"]

    assert ima_rows == ["ima-desk-a", "ima-desk-b"]


def test_suite_attribution_residual_records_include_zero_and_negative_residuals() -> None:
    ima = synthetic_ima_summary()
    sa = synthetic_sa_result()
    cva = synthetic_cva_summary()
    suite = calculate_suite_capital(ima_summary=ima, sa_result=sa, cva_summary=cva)
    bundles = top_level_attribution_bundles(ima, sa, cva)
    zero_report = build_suite_attribution_report(suite_result=suite, component_bundles=bundles)
    negative_report = build_suite_attribution_report(
        suite_result=suite,
        component_bundles=bundles,
        suite_total_capital=suite.total_capital - 2.5,
    )

    zero_rows = suite_attribution_residual_records(zero_report)
    negative_rows = suite_attribution_residual_records(negative_report)

    assert len(zero_rows) == 1
    assert zero_rows[0].component == "suite"
    assert zero_rows[0].amount == pytest.approx(0.0)
    assert negative_rows[0].component == "suite"
    assert negative_rows[0].residual == pytest.approx(-2.5)
    assert negative_rows[0].absolute_amount == pytest.approx(2.5)
    assert negative_rows[0].reconciliation_status == ReconciliationStatus.PARTIAL_RESIDUAL


def test_suite_attribution_unsupported_records_preserve_reason_and_ids() -> None:
    ima = synthetic_ima_summary()
    sa = synthetic_sa_result()
    cva = synthetic_cva_summary()
    suite = calculate_suite_capital(ima_summary=ima, sa_result=sa, cva_summary=cva)
    unsupported = synthetic_attribution_record(
        contribution_id="sa-unsupported-curvature",
        source_id="curvature-branch",
        source_level="branch",
        category="UNSUPPORTED_CURVATURE",
        contribution=None,
        residual=3.25,
        method=AttributionMethod.UNSUPPORTED,
        reason="component marks curvature scenario selection unsupported for exact Euler",
        bucket_key="GIRR",
    )
    sa_supported = synthetic_attribution_record(
        contribution_id="sa-supported",
        source_id="sa-supported",
        source_level="component",
        category="SA_SUPPORTED",
        contribution=sa.total_capital - 3.25,
    )
    report = build_suite_attribution_report(
        suite_result=suite,
        component_bundles=(
            synthetic_contribution_bundle("frtb_ima", ima.total_ima_capital),
            synthetic_contribution_bundle_from_records("frtb_sa", (sa_supported, unsupported)),
            synthetic_contribution_bundle("frtb_cva", cva.total_cva_capital),
        ),
    )

    rows = suite_attribution_unsupported_records(report)
    summary = summarise_suite_attribution(report)

    assert len(rows) == 1
    assert rows[0].component == "frtb_sa"
    assert rows[0].source_id == "curvature-branch"
    assert rows[0].bucket_key == "GIRR"
    assert rows[0].method == AttributionMethod.UNSUPPORTED
    assert "unsupported for exact Euler" in rows[0].reason
    assert summary.unsupported_records == rows
    assert summary.unsupported_records[0].contribution_id == "sa-unsupported-curvature"


def test_summarise_suite_attribution_supports_decomposed_component_sets() -> None:
    ima = synthetic_ima_summary()
    sa = synthetic_sa_result()
    cva = synthetic_cva_summary()
    suite = calculate_suite_capital(ima_summary=ima, sa_result=sa, cva_summary=cva)
    report = build_suite_attribution_report(
        suite_result=suite,
        component_bundles=decomposed_attribution_bundles(ima, sa, cva),
    )

    summary = summarise_suite_attribution(report, top_n=20)

    assert summary.component_set == (
        "frtb_ima",
        "frtb_sbm",
        "frtb_drc",
        "frtb_rrao",
        "frtb_cva",
    )
    assert {row.group_key for row in summary.contributors_by_component} == {
        "frtb_ima",
        "frtb_sbm",
        "frtb_drc",
        "frtb_rrao",
        "frtb_cva",
        "suite",
    }
    assert {row.component for row in summary.top_contributors} >= {"frtb_sbm", "frtb_drc"}


# ── Deterministic expected-output hash ───────────────────────────────────────


def test_suite_result_deterministic_output_hash() -> None:
    """Stable fixture hash: run twice and get the same total capital."""
    ima = synthetic_ima_summary(total_ima_capital=100.0)
    sa = synthetic_sa_result(sbm_capital=42.0)
    cva = synthetic_cva_summary()

    result_a = calculate_suite_capital(ima_summary=ima, sa_result=sa, cva_summary=cva)
    result_b = calculate_suite_capital(ima_summary=ima, sa_result=sa, cva_summary=cva)

    assert result_a.total_capital == result_b.total_capital
    assert result_a.ima_capital == result_b.ima_capital
    assert result_a.sa_capital == result_b.sa_capital
    assert result_a.cva_capital == result_b.cva_capital


# ── Fail-closed validation tests ─────────────────────────────────────────────


def test_suite_capital_rejects_wrong_ima_summary_type() -> None:
    sa = synthetic_sa_result()
    cva = synthetic_cva_summary()

    with pytest.raises(OrchestrationInputError, match="ima_summary must be an ImaCapitalSummary"):
        calculate_suite_capital(ima_summary=object(), sa_result=sa, cva_summary=cva)  # type: ignore[arg-type]


def test_suite_capital_rejects_wrong_sa_result_type() -> None:
    ima = synthetic_ima_summary()
    cva = synthetic_cva_summary()

    with pytest.raises(
        OrchestrationInputError, match="sa_result must be a StandardisedApproachCapitalResult"
    ):
        calculate_suite_capital(ima_summary=ima, sa_result=object(), cva_summary=cva)  # type: ignore[arg-type]


def test_suite_capital_rejects_wrong_cva_summary_type() -> None:
    ima = synthetic_ima_summary()
    sa = synthetic_sa_result()

    with pytest.raises(OrchestrationInputError, match="cva_summary must be a CvaCapitalSummary"):
        calculate_suite_capital(ima_summary=ima, sa_result=sa, cva_summary=object())  # type: ignore[arg-type]


def test_suite_capital_rejects_mixed_calculation_dates() -> None:
    ima = synthetic_ima_summary(calculation_date=date(2026, 1, 31))
    sa = synthetic_sa_result()
    cva = synthetic_cva_summary()

    with pytest.raises(OrchestrationInputError, match="calculation_date"):
        calculate_suite_capital(ima_summary=ima, sa_result=sa, cva_summary=cva)


def test_suite_capital_rejects_mixed_base_currencies() -> None:
    ima = synthetic_ima_summary(base_currency="EUR")
    sa = synthetic_sa_result()
    cva = synthetic_cva_summary()

    with pytest.raises(OrchestrationInputError, match="base_currency"):
        calculate_suite_capital(ima_summary=ima, sa_result=sa, cva_summary=cva)


def test_suite_capital_rejects_mixed_jurisdiction_families() -> None:
    # IMA is US_NPR (FED_NPR_2_0), SA/CVA are BASEL — must fail
    ima = synthetic_ima_summary(profile_id="FED_NPR_2_0")
    sa = synthetic_sa_result()
    cva = synthetic_cva_summary()

    with pytest.raises(OrchestrationInputError, match="jurisdiction family"):
        calculate_suite_capital(ima_summary=ima, sa_result=sa, cva_summary=cva)


def test_suite_capital_rejects_unknown_ima_profile() -> None:
    ima = synthetic_ima_summary(profile_id="UNKNOWN_REGIME_XYZ")
    sa = synthetic_sa_result()
    cva = synthetic_cva_summary()

    with pytest.raises(OrchestrationInputError, match="not recognised as a known suite"):
        calculate_suite_capital(ima_summary=ima, sa_result=sa, cva_summary=cva)


def test_suite_capital_rejects_empty_run_id_override() -> None:
    ima = synthetic_ima_summary()
    sa = synthetic_sa_result()
    cva = synthetic_cva_summary()

    with pytest.raises(OrchestrationInputError, match="run_id"):
        calculate_suite_capital(ima_summary=ima, sa_result=sa, cva_summary=cva, run_id="")


# ── ImaCapitalSummary validation tests ───────────────────────────────────────


def test_ima_capital_summary_validates_non_negative_total() -> None:
    with pytest.raises(OrchestrationInputError, match="total_ima_capital"):
        ImaCapitalSummary(
            package_name="frtb-ima",
            run_id="run",
            calculation_date=_CALC_DATE,
            base_currency="USD",
            profile_id="PRA_UK_CRR",
            total_ima_capital=-1.0,
            ima_eligible_desk_count=1,
            sa_fallback_desk_count=0,
            policy_hash=_POLICY_HASH,
            input_hash=_INPUT_HASH,
            citations=(),
        )


def test_ima_capital_summary_validates_date_type() -> None:
    with pytest.raises(OrchestrationInputError, match="calculation_date"):
        ImaCapitalSummary(
            package_name="frtb-ima",
            run_id="run",
            calculation_date="2026-03-31",  # type: ignore[arg-type]
            base_currency="USD",
            profile_id="PRA_UK_CRR",
            total_ima_capital=100.0,
            ima_eligible_desk_count=1,
            sa_fallback_desk_count=0,
            policy_hash=_POLICY_HASH,
            input_hash=_INPUT_HASH,
            citations=(),
        )


def test_ima_capital_summary_validates_non_finite_total() -> None:
    with pytest.raises(OrchestrationInputError, match="total_ima_capital"):
        ImaCapitalSummary(
            package_name="frtb-ima",
            run_id="run",
            calculation_date=_CALC_DATE,
            base_currency="USD",
            profile_id="PRA_UK_CRR",
            total_ima_capital=float("nan"),
            ima_eligible_desk_count=1,
            sa_fallback_desk_count=0,
            policy_hash=_POLICY_HASH,
            input_hash=_INPUT_HASH,
            citations=(),
        )


# ── recognise_ima_summary duck-typing tests ───────────────────────────────────


@dataclass
class _FakeImaAuditLog:
    """Minimal audit-log-shaped object for recognise_ima_summary tests."""

    run_id: str = "fake-ima-run"
    as_of_date: date = _CALC_DATE
    base_currency: str = "USD"
    regime: str = "PRA_UK_CRR"
    total_market_risk_capital: float = 200.0
    policy_hash: str = _POLICY_HASH
    inputs_hash: str = _INPUT_HASH
    desk_count: int = 3
    citations: tuple[str, ...] = ("MAR31.25",)
    warnings: tuple[str, ...] = ()


def test_recognise_ima_summary_from_audit_log_shape() -> None:
    fake = _FakeImaAuditLog()

    summary = recognise_ima_summary(fake)

    assert isinstance(summary, ImaCapitalSummary)
    assert summary.run_id == "fake-ima-run"
    assert summary.calculation_date == _CALC_DATE
    assert summary.base_currency == "USD"
    assert summary.profile_id == "PRA_UK_CRR"
    assert summary.total_ima_capital == 200.0
    assert summary.policy_hash == _POLICY_HASH
    assert summary.input_hash == _INPUT_HASH
    assert summary.ima_eligible_desk_count == 3
    assert summary.sa_fallback_desk_count == 0


def test_recognise_ima_summary_prefers_direct_field_names_over_aliases() -> None:
    @dataclass
    class DirectShape:
        run_id: str = "direct-run"
        calculation_date: date = _CALC_DATE
        base_currency: str = "USD"
        profile_id: str = "ECB_CRR3"
        total_ima_capital: float = 300.0
        policy_hash: str = _POLICY_HASH
        input_hash: str = _INPUT_HASH
        ima_eligible_desk_count: int = 2
        sa_fallback_desk_count: int = 1
        as_of_date: date = date(2000, 1, 1)  # ignored in favour of calculation_date
        regime: str = "FED_NPR_2_0"  # ignored in favour of profile_id
        citations: tuple[str, ...] = ("MAR31.25",)

    summary = recognise_ima_summary(DirectShape())

    assert summary.calculation_date == _CALC_DATE
    assert summary.profile_id == "ECB_CRR3"
    assert summary.input_hash == _INPUT_HASH


def test_recognise_ima_summary_normalizes_datetime_date_fields() -> None:
    @dataclass
    class DatetimeShape:
        run_id: str = "datetime-run"
        calculation_date: datetime = datetime(2026, 3, 31, 12, 30)
        base_currency: str = "USD"
        profile_id: str = "PRA_UK_CRR"
        total_ima_capital: float = 300.0
        policy_hash: str = _POLICY_HASH
        input_hash: str = _INPUT_HASH
        citations: tuple[str, ...] = ("MAR31.25",)

    summary = recognise_ima_summary(DatetimeShape())

    assert summary.calculation_date == _CALC_DATE
    assert type(summary.calculation_date) is date


def test_calculate_suite_capital_accepts_datetime_equivalent_ima_date() -> None:
    ima = synthetic_ima_summary(calculation_date=datetime(2026, 3, 31, 12, 30))

    result = calculate_suite_capital(
        ima_summary=ima,
        sa_result=synthetic_sa_result(),
        cva_summary=synthetic_cva_summary(),
    )

    assert result.calculation_date == _CALC_DATE


def test_recognise_ima_summary_preserves_single_text_citation() -> None:
    @dataclass
    class SingleTextCitationShape:
        run_id: str = "single-citation-run"
        calculation_date: date = _CALC_DATE
        base_currency: str = "USD"
        profile_id: str = "PRA_UK_CRR"
        total_ima_capital: float = 300.0
        policy_hash: str = _POLICY_HASH
        input_hash: str = _INPUT_HASH
        citations: str = "MAR31.25"

    summary = recognise_ima_summary(SingleTextCitationShape())

    assert summary.citations == ("MAR31.25",)


def test_recognise_ima_summary_rejects_non_iterable_desk_records_cleanly() -> None:
    @dataclass
    class BadDeskRecordsShape:
        run_id: str = "bad-desk-records-run"
        calculation_date: date = _CALC_DATE
        base_currency: str = "USD"
        profile_id: str = "PRA_UK_CRR"
        total_ima_capital: float = 300.0
        policy_hash: str = _POLICY_HASH
        input_hash: str = _INPUT_HASH
        desk_records: int = 1
        citations: tuple[str, ...] = ("MAR31.25",)

    with pytest.raises(OrchestrationInputError, match="desk_records must be an iterable"):
        recognise_ima_summary(BadDeskRecordsShape())


def test_recognise_ima_summary_rejects_missing_required_field() -> None:
    with pytest.raises(OrchestrationInputError, match="missing required"):
        recognise_ima_summary(object())


# ── suite_jurisdiction_family tests ──────────────────────────────────────────


@pytest.mark.parametrize(
    ("profile_id", "expected_family"),
    [
        ("FED_NPR_2_0", "US_NPR"),
        ("ECB_CRR3", "EU_CRR3"),
        ("PRA_UK_CRR", "BASEL"),
        ("BASEL_MAR50_2020", "BASEL"),
        ("US_NPR20_VB", "US_NPR"),
        ("EU_CRR3_CVA", "EU_CRR3"),
        ("UK_PRA_CVA", "BASEL"),
        ("BASEL_MAR21", "BASEL"),
        ("US_NPR_2_0", "US_NPR"),
        ("EU_CRR3", "EU_CRR3"),
    ],
)
def test_suite_jurisdiction_family_maps_known_profiles(
    profile_id: str, expected_family: str
) -> None:
    assert suite_jurisdiction_family(profile_id) == expected_family


def test_suite_jurisdiction_family_rejects_unknown_profile() -> None:
    with pytest.raises(OrchestrationInputError, match="not recognised as a known suite"):
        suite_jurisdiction_family("UNKNOWN_XYZ")


# ── PACKAGE_METADATA status assertions ───────────────────────────────────────


def test_package_metadata_reflects_implemented_status() -> None:
    assert PACKAGE_METADATA.implementation_status is ImplementationStatus.IMPLEMENTED
    assert PACKAGE_METADATA.validation_status is ValidationStatus.PENDING
