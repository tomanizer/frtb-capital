import ast
import math
from datetime import date
from pathlib import Path

import pytest
from frtb_common import (
    ComponentHandoffError,
    ComponentResultHandoff,
    ImplementationStatus,
    NotImplementedCapitalComponentError,
    StandardisedComponent,
    ValidationStatus,
)
from frtb_drc import (
    US_NPR_2_0_PROFILE_ID,
    CreditQuality,
    DefaultDirection,
    DrcCalculationContext,
    DrcInstrumentType,
    DrcPosition,
    DrcRiskClass,
    DrcSeniority,
    DrcSourceLineage,
    calculate_drc_capital,
)
from frtb_drc import to_orchestration_handoff as drc_to_orchestration_handoff
from frtb_ima import DeskEligibilityStatus
from frtb_orchestration import (
    PACKAGE_METADATA,
    OrchestrationInputError,
    StandardisedApproachCapitalResult,
    StandardisedComponentSubtotal,
    StandardisedFallbackRoute,
    __version__,
    calculate_suite_capital,
    compose_standardised_approach_capital,
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
from frtb_rrao import to_orchestration_handoff as rrao_to_orchestration_handoff

ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = ROOT / "src" / "frtb_orchestration"


def test_orchestration_package_imports_with_partial_status() -> None:
    assert isinstance(__version__, str)
    assert PACKAGE_METADATA.package_name == "frtb-orchestration"
    assert PACKAGE_METADATA.import_name == "frtb_orchestration"
    assert PACKAGE_METADATA.implementation_status is ImplementationStatus.PARTIAL
    assert PACKAGE_METADATA.validation_status is ValidationStatus.PENDING


def test_suite_capital_aggregation_fails_explicitly() -> None:
    with pytest.raises(NotImplementedCapitalComponentError, match="suite capital aggregation"):
        calculate_suite_capital()


def test_rrao_adapter_produces_shared_handoff() -> None:
    result = sample_rrao_result()

    handoff = rrao_to_orchestration_handoff(result)

    assert isinstance(handoff, ComponentResultHandoff)
    assert handoff.component is StandardisedComponent.RRAO
    assert handoff.package_name == "frtb-rrao"
    assert handoff.run_id == "orchestration-rrao-run"
    assert handoff.calculation_date == date(2026, 3, 31)
    assert handoff.base_currency == "USD"
    assert handoff.profile_id == "US_NPR_2_0"
    assert handoff.total_capital == result.total_rrao
    assert handoff.profile_hash == result.profile_hash
    assert handoff.input_hash == result.input_hash
    assert handoff.line_count == len(result.lines)
    assert handoff.excluded_line_count == len(result.excluded_lines)
    assert handoff.subtotal_count == len(result.subtotals)
    assert "us_npr_211_a_1" in handoff.citations
    assert handoff.warnings == result.warnings


def test_drc_adapter_produces_shared_handoff() -> None:
    result = sample_drc_result()

    handoff = drc_to_orchestration_handoff(result)

    assert isinstance(handoff, ComponentResultHandoff)
    assert handoff.component is StandardisedComponent.DRC
    assert handoff.package_name == "frtb-drc"
    assert handoff.run_id == "orchestration-drc-run"
    assert handoff.profile_id == US_NPR_2_0_PROFILE_ID
    assert handoff.total_capital == result.total_drc
    assert handoff.line_count == result.input_count
    assert handoff.excluded_line_count == result.rejected_input_count
    assert handoff.subtotal_count == len(result.categories)
    assert "US_NPR_210_SCOPE" in handoff.citations


def test_component_handoff_rejects_invalid_total() -> None:
    with pytest.raises(ComponentHandoffError, match="total_capital must be finite"):
        sbm_handoff(total_capital=float("inf"))


def test_standardised_approach_aggregation_requires_missing_component_outputs() -> None:
    rrao = rrao_to_orchestration_handoff(sample_rrao_result())

    with pytest.raises(NotImplementedCapitalComponentError, match="SBM, DRC"):
        compose_standardised_approach_capital(rrao_handoff=rrao)


def test_standardised_approach_aggregation_sums_components() -> None:
    rrao_result = sample_rrao_result()
    drc_result = sample_drc_result()
    rrao = rrao_to_orchestration_handoff(rrao_result)  # US_NPR_2_0
    drc = drc_to_orchestration_handoff(drc_result)  # US_NPR_2_0
    sbm = sbm_handoff(profile_id="US_NPR_2_0")

    result = compose_standardised_approach_capital(
        sbm_handoff=sbm,
        drc_handoff=drc,
        rrao_handoff=rrao,
        run_id="sa-composed-run",
    )

    assert isinstance(result, StandardisedApproachCapitalResult)
    assert result.run_id == "sa-composed-run"
    assert result.calculation_date == date(2026, 3, 31)
    assert result.base_currency == "USD"
    assert result.jurisdiction_family == "US_NPR"
    assert result.total_capital == pytest.approx(
        sbm.total_capital + drc_result.total_drc + rrao_result.total_rrao
    )
    assert [subtotal.component for subtotal in result.component_subtotals] == [
        StandardisedComponent.SBM,
        StandardisedComponent.DRC,
        StandardisedComponent.RRAO,
    ]
    assert result.component_subtotals[0].total_capital == sbm.total_capital
    assert "MAR21.4" in result.citations
    assert "US_NPR_210_SCOPE" in result.citations
    assert "us_npr_211_a_1" in result.citations
    assert result.as_dict()["total_capital"] == pytest.approx(result.total_capital)


@pytest.mark.parametrize(
    ("sbm_profile", "drc_profile", "rrao_profile", "family"),
    (
        ("BASEL_MAR21", "BASEL_MAR22", "BASEL_MAR23", "BASEL"),
        ("US_NPR_2_0", "US_NPR_2_0", "US_NPR_2_0", "US_NPR"),
        ("EU_CRR3", "EU_CRR3", "EU_CRR3", "EU_CRR3"),
    ),
)
def test_sa_aggregation_accepts_supported_jurisdiction_families(
    sbm_profile: str,
    drc_profile: str,
    rrao_profile: str,
    family: str,
) -> None:
    result = compose_standardised_approach_capital(
        sbm_handoff=component_handoff(
            StandardisedComponent.SBM, profile_id=sbm_profile, total=10.0
        ),
        drc_handoff=component_handoff(
            StandardisedComponent.DRC, profile_id=drc_profile, total=20.0
        ),
        rrao_handoff=component_handoff(
            StandardisedComponent.RRAO, profile_id=rrao_profile, total=30.0
        ),
    )

    assert result.jurisdiction_family == family
    assert result.total_capital == pytest.approx(60.0)


def test_sa_aggregation_records_non_ima_desk_fallback_routes() -> None:
    result = compose_standardised_approach_capital(
        sbm_handoff=sbm_handoff(profile_id="US_NPR_2_0"),
        drc_handoff=drc_to_orchestration_handoff(sample_drc_result()),
        rrao_handoff=rrao_to_orchestration_handoff(sample_rrao_result()),
        ima_desk_eligibility={
            "desk-zeta": DeskEligibilityStatus.SA_FALLBACK,
            "desk-alpha": "SA_FALLBACK",
            "desk-model": DeskEligibilityStatus.IMA_ELIGIBLE,
        },
    )

    assert result.fallback_routes == (
        StandardisedFallbackRoute(desk_id="desk-alpha"),
        StandardisedFallbackRoute(desk_id="desk-zeta"),
    )
    assert result.as_dict()["fallback_routes"] == [
        {
            "desk_id": "desk-alpha",
            "source_eligibility_status": "SA_FALLBACK",
            "route": "STANDARDISED_APPROACH",
            "reason_code": "ima_desk_not_model_eligible",
        },
        {
            "desk_id": "desk-zeta",
            "source_eligibility_status": "SA_FALLBACK",
            "route": "STANDARDISED_APPROACH",
            "reason_code": "ima_desk_not_model_eligible",
        },
    ]


def test_sa_aggregation_rejects_invalid_run_id() -> None:
    with pytest.raises(OrchestrationInputError, match="run_id"):
        compose_standardised_approach_capital(
            sbm_handoff=sbm_handoff(profile_id="US_NPR_2_0"),
            drc_handoff=drc_to_orchestration_handoff(sample_drc_result()),
            rrao_handoff=rrao_to_orchestration_handoff(sample_rrao_result()),
            run_id="",
        )


def test_sa_aggregation_rejects_unknown_ima_eligibility_status() -> None:
    with pytest.raises(OrchestrationInputError, match="unsupported eligibility status"):
        compose_standardised_approach_capital(
            sbm_handoff=sbm_handoff(profile_id="US_NPR_2_0"),
            drc_handoff=drc_to_orchestration_handoff(sample_drc_result()),
            rrao_handoff=rrao_to_orchestration_handoff(sample_rrao_result()),
            ima_desk_eligibility={"desk-1": "REMEDIATION"},
        )


def test_sa_aggregation_rejects_mixed_base_currencies() -> None:
    with pytest.raises(OrchestrationInputError, match="base_currency"):
        compose_standardised_approach_capital(
            sbm_handoff=sbm_handoff(profile_id="US_NPR_2_0", base_currency="EUR"),
            drc_handoff=drc_to_orchestration_handoff(sample_drc_result()),
            rrao_handoff=rrao_to_orchestration_handoff(sample_rrao_result()),
        )


def test_sa_aggregation_rejects_negative_component_capital() -> None:
    with pytest.raises(OrchestrationInputError, match="non-negative"):
        compose_standardised_approach_capital(
            sbm_handoff=sbm_handoff(profile_id="US_NPR_2_0", total_capital=-1.0),
            drc_handoff=drc_to_orchestration_handoff(sample_drc_result()),
            rrao_handoff=rrao_to_orchestration_handoff(sample_rrao_result()),
        )


def test_standardised_fallback_route_validates_fixed_route_invariants() -> None:
    with pytest.raises(OrchestrationInputError, match="desk_id"):
        StandardisedFallbackRoute(desk_id="")

    with pytest.raises(OrchestrationInputError, match="SA_FALLBACK"):
        StandardisedFallbackRoute(
            desk_id="desk-1",
            source_eligibility_status="IMA_ELIGIBLE",
        )

    with pytest.raises(OrchestrationInputError, match="STANDARDISED_APPROACH"):
        StandardisedFallbackRoute(
            desk_id="desk-1",
            route="IMA",
        )


def test_standardised_result_validates_reconciliation_invariants() -> None:
    result = compose_standardised_approach_capital(
        sbm_handoff=sbm_handoff(profile_id="US_NPR_2_0"),
        drc_handoff=drc_to_orchestration_handoff(sample_drc_result()),
        rrao_handoff=rrao_to_orchestration_handoff(sample_rrao_result()),
    )

    with pytest.raises(OrchestrationInputError, match="reconcile"):
        StandardisedApproachCapitalResult(
            run_id=result.run_id,
            calculation_date=result.calculation_date,
            base_currency=result.base_currency,
            jurisdiction_family=result.jurisdiction_family,
            total_capital=result.total_capital + 1.0,
            component_subtotals=result.component_subtotals,
            fallback_routes=result.fallback_routes,
            citations=result.citations,
            warnings=result.warnings,
        )

    with pytest.raises(OrchestrationInputError, match="SBM, DRC, and RRAO"):
        StandardisedApproachCapitalResult(
            run_id=result.run_id,
            calculation_date=result.calculation_date,
            base_currency=result.base_currency,
            jurisdiction_family=result.jurisdiction_family,
            total_capital=result.component_subtotals[0].total_capital,
            component_subtotals=(result.component_subtotals[0],),
            fallback_routes=result.fallback_routes,
            citations=result.citations,
            warnings=result.warnings,
        )


def test_standardised_result_reconciliation_tolerates_large_capital_roundoff() -> None:
    subtotals = (
        component_subtotal(StandardisedComponent.SBM, 1_000_000_000_000_000.0),
        component_subtotal(StandardisedComponent.DRC, 2_000_000_000_000_000.0),
        component_subtotal(StandardisedComponent.RRAO, 3_000_000_000_000_000.0),
    )
    expected = math.fsum(subtotal.total_capital for subtotal in subtotals)

    result = StandardisedApproachCapitalResult(
        run_id="sa-large-run",
        calculation_date=date(2026, 3, 31),
        base_currency="USD",
        jurisdiction_family="US_NPR",
        total_capital=expected + 1_000.0,
        component_subtotals=subtotals,
        fallback_routes=(),
        citations=("component-citation",),
    )

    assert result.total_capital == expected + 1_000.0


def test_standardised_component_subtotal_validates_audit_fields() -> None:
    with pytest.raises(OrchestrationInputError, match="total_capital"):
        StandardisedComponentSubtotal(
            component=StandardisedComponent.SBM,
            package_name="frtb-sbm",
            run_id="run",
            profile_id="US_NPR_2_0",
            profile_hash="profile-hash",
            input_hash="input-hash",
            total_capital=-1.0,
            line_count=1,
            excluded_line_count=0,
            subtotal_count=1,
        )


def test_sa_composition_rejects_mixed_jurisdiction_profiles() -> None:
    """ADR 0022: SA components from different jurisdiction families must be rejected."""
    rrao = rrao_to_orchestration_handoff(sample_rrao_result())  # US_NPR_2_0
    drc = drc_to_orchestration_handoff(sample_drc_result())  # US_NPR_2_0
    sbm = sbm_handoff(profile_id="BASEL_MAR21")  # different family -- must be rejected

    with pytest.raises(OrchestrationInputError, match="mixed profiles"):
        compose_standardised_approach_capital(
            sbm_handoff=sbm,
            drc_handoff=drc,
            rrao_handoff=rrao,
        )


def test_sa_composition_rejects_unknown_profile_id() -> None:
    """Unrecognised profile_id must fail closed rather than silently pass."""
    rrao = rrao_to_orchestration_handoff(sample_rrao_result())
    sbm = sbm_handoff(profile_id="UNKNOWN_PROFILE_XYZ")

    with pytest.raises(OrchestrationInputError, match="not recognised as a known SA jurisdiction"):
        compose_standardised_approach_capital(sbm_handoff=sbm, rrao_handoff=rrao)


def test_sa_composition_accepts_consistent_basel_family() -> None:
    """RRAO BASEL_MAR23 and SBM BASEL_MAR21 are the same jurisdiction family (ADR 0022)."""
    rrao_basel = rrao_to_orchestration_handoff(
        sample_rrao_result(profile=RraoRegulatoryProfile.BASEL_MAR23)
    )
    sbm = sbm_handoff(profile_id="BASEL_MAR21")  # same BASEL family as RRAO -- passes guard

    # Jurisdiction guard passes; aggregation fails because DRC is still missing.
    with pytest.raises(NotImplementedCapitalComponentError, match="DRC"):
        compose_standardised_approach_capital(sbm_handoff=sbm, rrao_handoff=rrao_basel)


def test_compose_rejects_handoff_in_wrong_component_slot() -> None:
    rrao = rrao_to_orchestration_handoff(sample_rrao_result())

    with pytest.raises(OrchestrationInputError, match="SBM was expected"):
        compose_standardised_approach_capital(sbm_handoff=rrao)


def test_orchestration_runtime_does_not_import_sibling_packages() -> None:
    forbidden_prefixes = ("frtb_rrao", "frtb_drc", "frtb_sbm", "frtb_cva", "frtb_ima")
    for source_file in SOURCE_ROOT.rglob("*.py"):
        tree = ast.parse(source_file.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                assert not any(
                    alias.name.startswith(prefix)
                    for alias in node.names
                    for prefix in forbidden_prefixes
                ), source_file
            if isinstance(node, ast.ImportFrom):
                module = node.module
                assert module is None or not any(
                    module.startswith(prefix) for prefix in forbidden_prefixes
                ), source_file


def test_orchestration_runtime_does_not_import_private_batch_internals() -> None:
    forbidden_modules = {
        "frtb_cva.batch",
        "frtb_drc.batch",
        "frtb_rrao.batch",
        "frtb_sbm.batch",
    }
    for source_file in SOURCE_ROOT.rglob("*.py"):
        tree = ast.parse(source_file.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                assert not any(
                    alias.name == forbidden_module or alias.name.startswith(f"{forbidden_module}.")
                    for alias in node.names
                    for forbidden_module in forbidden_modules
                ), source_file
            if isinstance(node, ast.ImportFrom):
                module = node.module
                assert module is None or not any(
                    module == forbidden_module or module.startswith(f"{forbidden_module}.")
                    for forbidden_module in forbidden_modules
                ), source_file


def sbm_handoff(
    *,
    profile_id: str = "US_NPR_2_0",
    total_capital: float = 42.0,
    base_currency: str = "USD",
) -> ComponentResultHandoff:
    """Build a synthetic SBM handoff directly on the shared public contract.

    SBM capital is only implemented for BASEL_MAR21, so non-Basel jurisdiction
    guard tests construct the contract type directly rather than running SBM.
    """

    return component_handoff(
        component=StandardisedComponent.SBM,
        profile_id=profile_id,
        total=total_capital,
        package_name="frtb-sbm",
        run_id="orchestration-sbm-run",
        base_currency=base_currency,
        citations=("MAR21.4",),
    )


def component_handoff(
    component: StandardisedComponent,
    *,
    profile_id: str,
    total: float,
    package_name: str | None = None,
    run_id: str | None = None,
    base_currency: str = "USD",
    citations: tuple[str, ...] = ("component-citation",),
) -> ComponentResultHandoff:
    return ComponentResultHandoff(
        component=component,
        package_name=package_name or f"frtb-{component.value.lower()}",
        run_id=run_id or f"orchestration-{component.value.lower()}-run",
        calculation_date=date(2026, 3, 31),
        base_currency=base_currency,
        profile_id=profile_id,
        total_capital=total,
        profile_hash="profile-hash",
        input_hash="input-hash",
        line_count=1,
        excluded_line_count=0,
        subtotal_count=1,
        citations=citations,
        warnings=(),
    )


def component_subtotal(
    component: StandardisedComponent,
    total_capital: float,
) -> StandardisedComponentSubtotal:
    return StandardisedComponentSubtotal(
        component=component,
        package_name=f"frtb-{component.value.lower()}",
        run_id=f"run-{component.value.lower()}",
        profile_id="US_NPR_2_0",
        profile_hash="profile-hash",
        input_hash="input-hash",
        total_capital=total_capital,
        line_count=1,
        excluded_line_count=0,
        subtotal_count=1,
    )


def sample_rrao_result(profile: RraoRegulatoryProfile = RraoRegulatoryProfile.US_NPR_2_0):
    return calculate_rrao_capital(
        (
            RraoPosition(
                position_id="rrao-handoff-001",
                source_row_id="row-001",
                desk_id="desk-rrao",
                legal_entity="LE-001",
                gross_effective_notional=1_000_000.0,
                currency="USD",
                evidence_type=RraoEvidenceType.EXOTIC_UNDERLYING,
                evidence_label="longevity derivative",
                lineage=RraoSourceLineage(
                    source_system="orchestration-test",
                    source_file="rrao.csv",
                    source_row_id="row-001",
                    source_column_map=(("gross", "gross_effective_notional"),),
                ),
                classification_hint=RraoClassification.EXOTIC,
            ),
        ),
        context=RraoCalculationContext(
            run_id="orchestration-rrao-run",
            calculation_date=date(2026, 3, 31),
            base_currency="USD",
            profile=profile,
        ),
    )


def sample_drc_result():
    return calculate_drc_capital(
        (
            DrcPosition(
                position_id="drc-handoff-001",
                source_row_id="row-001",
                desk_id="desk-drc",
                legal_entity="LE-001",
                risk_class=DrcRiskClass.NON_SECURITISATION,
                instrument_type=DrcInstrumentType.BOND,
                default_direction=DefaultDirection.LONG,
                issuer_id="issuer-001",
                tranche_id=None,
                index_series_id=None,
                bucket_key="CORPORATE",
                seniority=DrcSeniority.SENIOR_DEBT,
                credit_quality=CreditQuality.INVESTMENT_GRADE,
                notional=100.0,
                market_value=100.0,
                cumulative_pnl=0.0,
                maturity_years=1.0,
                currency="USD",
                lineage=DrcSourceLineage(
                    source_system="orchestration-test",
                    source_file="drc.csv",
                    source_row_id="row-001",
                    source_column_map={"notional": "notional"},
                ),
                citation_ids=("US_NPR_210_SCOPE",),
            ),
        ),
        context=DrcCalculationContext(
            run_id="orchestration-drc-run",
            calculation_date=date(2026, 3, 31),
            base_currency="USD",
            profile_id=US_NPR_2_0_PROFILE_ID,
        ),
    )
