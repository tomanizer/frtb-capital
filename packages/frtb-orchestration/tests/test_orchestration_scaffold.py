import ast
from datetime import date
from pathlib import Path

import pytest
from frtb_common import (
    ImplementationStatus,
    NotImplementedCapitalComponentError,
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
from frtb_orchestration import (
    PACKAGE_METADATA,
    OrchestrationInputError,
    StandardisedComponent,
    __version__,
    calculate_suite_capital,
    compose_standardised_approach_capital,
    recognise_drc_result,
    recognise_rrao_result,
    recognise_sbm_result,
)
from frtb_rrao import (
    RraoCalculationContext,
    RraoCapitalResult,
    RraoClassification,
    RraoEvidenceType,
    RraoPosition,
    RraoRegulatoryProfile,
    RraoSourceLineage,
    calculate_rrao_capital,
)

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


def test_orchestration_can_recognise_public_rrao_result_shape() -> None:
    result = sample_rrao_result()

    handoff = recognise_rrao_result(result)

    assert handoff.component is StandardisedComponent.RRAO
    assert handoff.package_name == "frtb-rrao"
    assert handoff.run_id == "orchestration-rrao-run"
    assert handoff.calculation_date == date(2026, 3, 31)
    assert handoff.base_currency == "USD"
    assert handoff.profile_id == "US_NPR_2_0"
    assert handoff.total_capital == 10_000.0
    assert handoff.profile_hash == result.profile_hash
    assert handoff.input_hash == result.input_hash
    assert handoff.line_count == 1
    assert handoff.excluded_line_count == 0
    assert handoff.subtotal_count == len(result.subtotals)
    assert "us_npr_211_a_1" in handoff.citations
    assert handoff.warnings == result.warnings


def test_orchestration_can_recognise_public_drc_result_shape() -> None:
    result = sample_drc_result()

    handoff = recognise_drc_result(result)

    assert handoff.component is StandardisedComponent.DRC
    assert handoff.package_name == "frtb-drc"
    assert handoff.run_id == "orchestration-drc-run"
    assert handoff.calculation_date == date(2026, 3, 31)
    assert handoff.base_currency == "USD"
    assert handoff.profile_id == US_NPR_2_0_PROFILE_ID
    assert handoff.total_capital == result.total_drc
    assert handoff.profile_hash == result.profile_hash
    assert handoff.input_hash == result.input_hash
    assert handoff.line_count == result.input_count
    assert handoff.excluded_line_count == result.rejected_input_count
    assert handoff.subtotal_count == len(result.categories)
    assert "US_NPR_210_SCOPE" in handoff.citations
    assert handoff.warnings == result.warnings


def test_orchestration_can_recognise_planned_sbm_result_shape() -> None:
    result = MinimalResult(
        package_name=None,
        run_id="orchestration-sbm-run",
        calculation_date=date(2026, 3, 31),
        base_currency="USD",
        profile_id="BASEL_MAR21",
        total_sbm=42.0,
        profile_hash="profile-hash",
        input_hash="input-hash",
        sensitivity_count=None,
        unsupported_count=None,
        sensitivities=(object(), object(), object()),
        unsupported_features=(object(),),
        risk_class_results=(object(), object()),
        citations=("MAR21.4",),
        warnings=("unsupported curvature path excluded from this synthetic shape",),
    )

    handoff = recognise_sbm_result(result)

    assert handoff.component is StandardisedComponent.SBM
    assert handoff.package_name == "frtb-sbm"
    assert handoff.run_id == "orchestration-sbm-run"
    assert handoff.total_capital == 42.0
    assert handoff.line_count == 3
    assert handoff.excluded_line_count == 1
    assert handoff.subtotal_count == 2
    assert handoff.citations == ("MAR21.4",)


def test_standardised_approach_aggregation_requires_missing_component_outputs() -> None:
    result = sample_rrao_result()

    with pytest.raises(NotImplementedCapitalComponentError, match="SBM, DRC"):
        compose_standardised_approach_capital(rrao_result=result)


def test_sa_aggregation_remains_unimplemented_with_placeholder_components() -> None:
    rrao_result = sample_rrao_result()   # profile_id="US_NPR_2_0"
    drc_result = sample_drc_result()     # profile_id="US_NPR_2_0"
    sbm_result = MinimalResult(
        run_id="orchestration-sbm-run",
        calculation_date=date(2026, 3, 31),
        base_currency="USD",
        profile_id="US_NPR_2_0",        # consistent with RRAO and DRC
        total_sbm=42.0,
        profile_hash="profile-hash",
        input_hash="input-hash",
        sensitivities=(object(),),
        unsupported_features=(),
        risk_class_results=(object(),),
        citations=("MAR21.4",),
        warnings=(),
    )

    with pytest.raises(NotImplementedCapitalComponentError, match="aggregation arithmetic"):
        compose_standardised_approach_capital(
            sbm_result=sbm_result,
            drc_result=drc_result,
            rrao_result=rrao_result,
        )


def test_sa_composition_rejects_mixed_jurisdiction_profiles() -> None:
    """ADR 0022: SA components from different jurisdiction families must be rejected."""
    rrao_result = sample_rrao_result()   # profile_id="US_NPR_2_0"
    drc_result = sample_drc_result()     # profile_id="US_NPR_2_0"
    sbm_result = MinimalResult(
        run_id="orchestration-sbm-run",
        calculation_date=date(2026, 3, 31),
        base_currency="USD",
        profile_id="BASEL_MAR21",        # different jurisdiction family -- must be rejected
        total_sbm=42.0,
        profile_hash="profile-hash",
        input_hash="input-hash",
        sensitivities=(object(),),
        unsupported_features=(),
        risk_class_results=(object(),),
        citations=("MAR21.4",),
        warnings=(),
    )

    with pytest.raises(OrchestrationInputError, match="mixed profiles"):
        compose_standardised_approach_capital(
            sbm_result=sbm_result,
            drc_result=drc_result,
            rrao_result=rrao_result,
        )


def test_sa_composition_rejects_unknown_profile_id() -> None:
    """Unrecognised profile_id must fail closed rather than silently pass."""
    rrao_result = sample_rrao_result()
    sbm_result = MinimalResult(
        run_id="orchestration-sbm-run",
        calculation_date=date(2026, 3, 31),
        base_currency="USD",
        profile_id="UNKNOWN_PROFILE_XYZ",
        total_sbm=42.0,
        profile_hash="profile-hash",
        input_hash="input-hash",
        sensitivities=(object(),),
        unsupported_features=(),
        risk_class_results=(object(),),
        citations=(),
        warnings=(),
    )

    with pytest.raises(OrchestrationInputError, match="not recognised as a known SA jurisdiction"):
        compose_standardised_approach_capital(
            sbm_result=sbm_result,
            rrao_result=rrao_result,
        )


def test_sa_composition_accepts_consistent_basel_family() -> None:
    """RRAO BASEL_MAR23 and SBM BASEL_MAR21 are the same jurisdiction family (ADR 0022)."""
    rrao_basel = calculate_rrao_capital(
        (
            RraoPosition(
                position_id="rrao-basel-001",
                source_row_id="row-001",
                desk_id="desk-rrao",
                legal_entity="LE-001",
                gross_effective_notional=500_000.0,
                currency="USD",
                evidence_type=RraoEvidenceType.EXOTIC_UNDERLYING,
                evidence_label="weather derivative",
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
            run_id="basel-rrao-run",
            calculation_date=date(2026, 3, 31),
            base_currency="USD",
            profile=RraoRegulatoryProfile.BASEL_MAR23,
        ),
    )
    sbm_result = MinimalResult(
        run_id="basel-sbm-run",
        calculation_date=date(2026, 3, 31),
        base_currency="USD",
        profile_id="BASEL_MAR21",        # same BASEL family as RRAO -- must pass guard
        total_sbm=100.0,
        profile_hash="ph",
        input_hash="ih",
        sensitivities=(object(),),
        unsupported_features=(),
        risk_class_results=(object(),),
        citations=(),
        warnings=(),
    )

    # Jurisdiction guard passes; aggregation fails because DRC is still missing
    with pytest.raises(NotImplementedCapitalComponentError, match="DRC"):
        compose_standardised_approach_capital(
            sbm_result=sbm_result,
            rrao_result=rrao_basel,
        )


def test_m1_contract_boundary_recognises_all_sa_component_handoffs() -> None:
    """ADR 0018 M1: each SA component handoff is recognised before aggregation."""

    rrao_result = sample_rrao_result()
    drc_result = sample_drc_result()

    rrao_handoff = recognise_rrao_result(rrao_result)
    drc_handoff = recognise_drc_result(drc_result)

    assert rrao_handoff.component is StandardisedComponent.RRAO
    assert drc_handoff.component is StandardisedComponent.DRC
    assert rrao_handoff.total_capital == rrao_result.total_rrao
    assert drc_handoff.total_capital == drc_result.total_drc


def test_rrao_handoff_rejects_invalid_result_shape() -> None:
    with pytest.raises(OrchestrationInputError, match="missing required field total_rrao"):
        recognise_rrao_result(
            MinimalResult(
                run_id="bad-rrao",
                calculation_date=date(2026, 3, 31),
                base_currency="USD",
                profile_id="US_NPR_2_0",
                profile_hash="profile",
                input_hash="input",
                lines=(),
                excluded_lines=(),
                subtotals=(),
                citations=(),
                warnings=(),
            )
        )


def test_drc_handoff_rejects_invalid_result_shape() -> None:
    with pytest.raises(OrchestrationInputError, match="missing required field total_drc"):
        recognise_drc_result(
            MinimalResult(
                run_id="bad-drc",
                calculation_date=date(2026, 3, 31),
                base_currency="USD",
                profile_id=US_NPR_2_0_PROFILE_ID,
                profile_hash="profile",
                input_hash="input",
                input_count=0,
                rejected_input_count=0,
                categories=(),
                citations=(),
                warnings=(),
            )
        )


def test_sbm_handoff_rejects_invalid_result_shape() -> None:
    with pytest.raises(
        OrchestrationInputError, match="SBM result is missing required field total_sbm"
    ):
        recognise_sbm_result(
            MinimalResult(
                run_id="bad-sbm",
                calculation_date=date(2026, 3, 31),
                base_currency="USD",
                profile_id="BASEL_MAR21",
                profile_hash="profile",
                input_hash="input",
                sensitivities=(),
                unsupported_features=(),
                risk_class_results=(),
                citations=(),
                warnings=(),
            )
        )


def test_sbm_handoff_rejects_invalid_optional_package_name_with_component_context() -> None:
    with pytest.raises(
        OrchestrationInputError,
        match="SBM result field package_name must be non-empty text",
    ):
        recognise_sbm_result(
            MinimalResult(
                package_name="",
                run_id="bad-sbm",
                calculation_date=date(2026, 3, 31),
                base_currency="USD",
                profile_id="BASEL_MAR21",
                total_sbm=42.0,
                profile_hash="profile",
                input_hash="input",
                sensitivities=(),
                unsupported_features=(),
                risk_class_results=(),
                citations=(),
                warnings=(),
            )
        )


def test_orchestration_runtime_does_not_import_sibling_packages() -> None:
    for source_file in SOURCE_ROOT.rglob("*.py"):
        tree = ast.parse(source_file.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                assert not any(alias.name.startswith("frtb_rrao") for alias in node.names), (
                    source_file
                )
                assert not any(alias.name.startswith("frtb_drc") for alias in node.names), (
                    source_file
                )
                assert not any(alias.name.startswith("frtb_sbm") for alias in node.names), (
                    source_file
                )
            if isinstance(node, ast.ImportFrom):
                assert node.module is None or not node.module.startswith("frtb_rrao"), source_file
                assert node.module is None or not node.module.startswith("frtb_drc"), source_file
                assert node.module is None or not node.module.startswith("frtb_sbm"), source_file


def sample_rrao_result() -> RraoCapitalResult:
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
            profile=RraoRegulatoryProfile.US_NPR_2_0,
        ),
    )


def sample_drc_result() -> object:
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


class MinimalResult:
    def __init__(self, **fields: object) -> None:
        self.__dict__.update(fields)
