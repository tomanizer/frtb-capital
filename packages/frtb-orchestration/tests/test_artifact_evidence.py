"""Tests for suite-level artifact evidence read models."""

from __future__ import annotations

from datetime import date

import frtb_orchestration.artifact_evidence as artifact_evidence
import pytest
from frtb_common import StandardisedComponent
from frtb_orchestration import (
    ArtifactEvidenceKind,
    ArtifactEvidenceRef,
    ArtifactEvidenceStatus,
    CvaCapitalSummary,
    ImaCapitalSummary,
    ImaScenarioEvidence,
    OrchestrationInputError,
    SbmShockEvidence,
    StandardisedApproachCapitalResult,
    StandardisedComponentSubtotal,
    SuiteArtifactEvidenceView,
    SuiteCapitalResult,
    SuiteEvidenceComponent,
    SurfaceEvidence,
    TimelineEvidence,
    build_resolved_artifact_evidence_view,
    build_suite_artifact_evidence_view,
)

AS_OF = date(2026, 6, 30)


def _suite_result() -> SuiteCapitalResult:
    return SuiteCapitalResult(
        run_id="suite-run-1",
        calculation_date=AS_OF,
        base_currency="USD",
        suite_profile_family="US_NPR",
        total_capital=175.0,
        ima_capital=100.0,
        sa_capital=50.0,
        cva_capital=25.0,
        ima_summary=ImaCapitalSummary(
            package_name="frtb-ima",
            run_id="ima-run-1",
            calculation_date=AS_OF,
            base_currency="USD",
            profile_id="US_NPR_2_0",
            total_ima_capital=100.0,
            ima_eligible_desk_count=1,
            sa_fallback_desk_count=0,
            policy_hash="ima-policy",
            input_hash="ima-input",
            citations=("npr-ima",),
        ),
        sa_result=StandardisedApproachCapitalResult(
            run_id="sa-run-1",
            calculation_date=AS_OF,
            base_currency="USD",
            jurisdiction_family="US_NPR",
            total_capital=50.0,
            component_subtotals=(
                _subtotal(StandardisedComponent.SBM, 30.0),
                _subtotal(StandardisedComponent.DRC, 15.0),
                _subtotal(StandardisedComponent.RRAO, 5.0),
            ),
            fallback_routes=(),
            citations=("npr-sa",),
        ),
        cva_summary=CvaCapitalSummary(
            package_name="frtb-cva",
            run_id="cva-run-1",
            calculation_date=AS_OF,
            base_currency="USD",
            profile_id="US_NPR20_VB",
            method="SA_CVA",
            total_cva_capital=25.0,
            ba_cva_reduced_total=None,
            ba_cva_full_total=None,
            sa_cva_total=25.0,
            profile_hash="cva-profile",
            input_hash="cva-input",
            risk_class_count=1,
            counterparty_count=2,
            citations=("npr-cva",),
        ),
        citations=("npr-ima", "npr-sa", "npr-cva"),
    )


def _subtotal(component: StandardisedComponent, total: float) -> StandardisedComponentSubtotal:
    return StandardisedComponentSubtotal(
        component=component,
        package_name=f"frtb-{component.value.lower()}",
        run_id=f"{component.value.lower()}-run-1",
        profile_id="US_NPR_2_0",
        profile_hash=f"{component.value.lower()}-profile",
        input_hash=f"{component.value.lower()}-input",
        total_capital=total,
        line_count=1,
        excluded_line_count=0,
        subtotal_count=1,
    )


def test_suite_artifact_evidence_groups_refs_in_suite_component_order() -> None:
    view = build_suite_artifact_evidence_view(
        _suite_result(),
        (
            ArtifactEvidenceRef(
                component=SuiteEvidenceComponent.CVA,
                kind=ArtifactEvidenceKind.SURFACE,
                role="sa_cva_volatility_surface",
                artifact_id="surface-cva-vol",
                source_component="frtb-cva",
                source_field="SaCvaSensitivity.volatility_surface_id",
            ),
            ArtifactEvidenceRef(
                component=SuiteEvidenceComponent.IMA,
                kind=ArtifactEvidenceKind.TIME_SERIES,
                role="plat_upl",
                artifact_id="ts-ima-upl",
                source_component="frtb-ima",
                source_field="PlaPolicyAssessmentResult.upl_time_series_id",
            ),
            ArtifactEvidenceRef(
                component=SuiteEvidenceComponent.SBM,
                kind=ArtifactEvidenceKind.SHOCK,
                role="curvature_up",
                artifact_id="shock-sbm-curv-up",
                source_component="frtb-sbm",
                source_field="SbmSensitivity.up_shock_id",
                partition_values={"risk_class": "GIRR"},
            ),
            ArtifactEvidenceRef(
                component=SuiteEvidenceComponent.IMA,
                kind=ArtifactEvidenceKind.TIME_SERIES,
                role="rfet_observations",
                status=ArtifactEvidenceStatus.NO_DATA,
                reason="fixture does not include extended RFET observation history",
                partition_values={"time_series_id": "ts-rfet-extended-history"},
            ),
            ArtifactEvidenceRef(
                component=SuiteEvidenceComponent.CVA,
                kind=ArtifactEvidenceKind.SURFACE,
                role="full_cva_surface_cube",
                status=ArtifactEvidenceStatus.UNSUPPORTED,
                reason="full CVA volatility surface cube is outside fixture scope",
            ),
        ),
    )

    payload = view.as_dict()

    assert [component["component"] for component in payload["components"]] == [
        "IMA",
        "SBM",
        "CVA",
    ]
    assert view.component(SuiteEvidenceComponent.SBM).refs[0].artifact_id == ("shock-sbm-curv-up")
    assert payload["components"][1]["refs"][0]["partition_values"] == {"risk_class": "GIRR"}
    assert payload["status_counts"] == {"AVAILABLE": 3, "NO_DATA": 1, "UNSUPPORTED": 1}
    assert payload["components"][0]["status_counts"] == {
        "AVAILABLE": 1,
        "NO_DATA": 1,
        "UNSUPPORTED": 0,
    }


def test_suite_artifact_evidence_preserves_explicit_no_data_state() -> None:
    view = build_suite_artifact_evidence_view(
        _suite_result(),
        (
            ArtifactEvidenceRef(
                component=SuiteEvidenceComponent.IMA,
                kind=ArtifactEvidenceKind.TIME_SERIES,
                role="rfet_observations",
                status=ArtifactEvidenceStatus.NO_DATA,
                reason="fixture does not include RFET observation time series",
            ),
        ),
    )

    payload = view.as_dict()

    assert payload["components"][0]["refs"][0]["status"] == "NO_DATA"
    assert payload["components"][0]["refs"][0]["reason"] == (
        "fixture does not include RFET observation time series"
    )


def test_resolved_artifact_evidence_builder_composes_resolved_artifact_refs() -> None:
    view = _resolved_artifact_view()

    payload = view.as_dict()
    components = {component["component"]: component for component in payload["components"]}
    ima_refs = components["IMA"]["refs"]
    sbm_refs = components["SBM"]["refs"]

    assert payload["status_counts"] == {"AVAILABLE": 8, "NO_DATA": 1, "UNSUPPORTED": 0}
    assert {ref["artifact_id"] for ref in ima_refs if ref["status"] == "AVAILABLE"} == {
        "scenario-cube-ima-run-1",
        "scenario-vector-0001",
        "scenario-vector-0002",
        "ts-rfet-usd-swap-5y",
    }
    assert any(
        ref["status"] == "NO_DATA" and ref["reason"] == "fixture does not include UPL observations"
        for ref in ima_refs
    )
    shock_refs = [ref for ref in sbm_refs if ref["kind"] == "SHOCK"]
    assert [ref["partition_values"]["shock_direction"] for ref in shock_refs] == [
        "DOWN",
        "UP",
    ]
    assert shock_refs[0]["partition_values"]["source_row_id"] == "sbm-row-1"
    surface_ref = next(ref for ref in sbm_refs if ref["artifact_id"] == "surface-sbm-girr-vega")
    assert surface_ref["partition_values"]["axis_1"] == "option_tenor"
    assert surface_ref["partition_values"]["surface_point_count"] == "1"


def _resolved_artifact_view() -> SuiteArtifactEvidenceView:
    return build_resolved_artifact_evidence_view(
        _suite_result(),
        sbm_shocks=_resolved_sbm_shocks(),
        ima_scenarios=_resolved_ima_scenarios(),
        timelines=_resolved_timelines(),
        surfaces=_resolved_surfaces(),
    )


def _resolved_sbm_shocks() -> tuple[SbmShockEvidence, ...]:
    return (
        SbmShockEvidence(
            shock_id="shock-sbm-girr-up",
            direction="UP",
            risk_class="GIRR",
            risk_measure="CURVATURE",
            bucket_id="USD",
            risk_factor_id="rf:girr:usd:5y",
            source_row_id="sbm-row-1",
            mapping_version="map-v1",
        ),
        SbmShockEvidence(
            shock_id="shock-sbm-girr-down",
            direction="DOWN",
            risk_class="GIRR",
            risk_measure="CURVATURE",
            bucket_id="USD",
            risk_factor_id="rf:girr:usd:5y",
            source_row_id="sbm-row-1",
            mapping_version="map-v1",
        ),
    )


def _resolved_ima_scenarios() -> tuple[ImaScenarioEvidence, ...]:
    return (
        ImaScenarioEvidence(
            scenario_cube_id="scenario-cube-ima-run-1",
            scenario_set_id="scenario-set-stress-2026",
            scenario_vector_ids=("scenario-vector-0001", "scenario-vector-0002"),
            source_row_id="scenario-row-1",
            mapping_version="map-v1",
        ),
    )


def _resolved_timelines() -> tuple[TimelineEvidence, ...]:
    return (
        TimelineEvidence(
            component=SuiteEvidenceComponent.IMA,
            role="rfet_observations",
            time_series_id="ts-rfet-usd-swap-5y",
            risk_factor_id="rf:girr:usd:5y",
            source_component="frtb-ima",
            source_field="RFETEvidence.observation_time_series_id",
            source_row_id="rfet-row-1",
            mapping_version="map-v1",
        ),
        TimelineEvidence(
            component=SuiteEvidenceComponent.IMA,
            role="upl",
            status=ArtifactEvidenceStatus.NO_DATA,
            reason="fixture does not include UPL observations",
            source_component="frtb-ima",
            source_field="PlaPolicyAssessmentResult.upl_time_series_id",
        ),
    )


def _resolved_surfaces() -> tuple[SurfaceEvidence, ...]:
    return (
        SurfaceEvidence(
            component=SuiteEvidenceComponent.SBM,
            role="sbm_girr_vega_surface",
            surface_id="surface-sbm-girr-vega",
            source_component="frtb-sbm",
            source_field="SbmSensitivity.surface_id",
            surface_point_ids=("surface-point-5y-1y",),
            risk_factor_id="rf:girr:usd:5y",
            source_row_id="sbm-vega-row-1",
            mapping_version="map-v1",
            axis_1="option_tenor",
            axis_2="underlying_tenor",
        ),
    )


def test_suite_artifact_evidence_rejects_duplicate_component_kind_role() -> None:
    ref = ArtifactEvidenceRef(
        component=SuiteEvidenceComponent.IMA,
        kind=ArtifactEvidenceKind.SCENARIO_VECTOR,
        role="scenario_cube",
        artifact_id="scenario-vector-1",
    )

    with pytest.raises(OrchestrationInputError, match="duplicate artifact evidence ref"):
        build_suite_artifact_evidence_view(_suite_result(), (ref, ref))


def test_suite_artifact_evidence_tolerates_absent_sa_result() -> None:
    suite_result = _suite_result()
    object.__setattr__(suite_result, "sa_result", None)

    view = build_suite_artifact_evidence_view(
        suite_result,
        (
            ArtifactEvidenceRef(
                component=SuiteEvidenceComponent.IMA,
                kind=ArtifactEvidenceKind.TIME_SERIES,
                role="plat_upl",
                artifact_id="ts-ima-upl",
            ),
        ),
    )

    assert [component.component for component in view.components] == [SuiteEvidenceComponent.IMA]


def test_suite_artifact_evidence_rejects_unmapped_sa_component(monkeypatch) -> None:
    monkeypatch.delitem(
        artifact_evidence._SA_COMPONENT_TO_EVIDENCE_COMPONENT,
        StandardisedComponent.SBM,
    )

    with pytest.raises(OrchestrationInputError, match="not mapped"):
        build_suite_artifact_evidence_view(
            _suite_result(),
            (
                ArtifactEvidenceRef(
                    component=SuiteEvidenceComponent.SBM,
                    kind=ArtifactEvidenceKind.SHOCK,
                    role="curvature_up",
                    artifact_id="shock-sbm-curv-up",
                ),
            ),
        )


def test_suite_artifact_evidence_rejects_available_ref_without_artifact_id() -> None:
    with pytest.raises(OrchestrationInputError, match="artifact_id"):
        ArtifactEvidenceRef(
            component=SuiteEvidenceComponent.CVA,
            kind=ArtifactEvidenceKind.SURFACE,
            role="volatility_surface",
        )


def test_suite_artifact_evidence_requires_no_data_reason() -> None:
    with pytest.raises(OrchestrationInputError, match="requires reason"):
        ArtifactEvidenceRef(
            component=SuiteEvidenceComponent.IMA,
            kind=ArtifactEvidenceKind.TIME_SERIES,
            role="upl",
            status=ArtifactEvidenceStatus.NO_DATA,
        )


def test_resolved_artifact_evidence_inputs_fail_closed_for_invalid_metadata() -> None:
    with pytest.raises(OrchestrationInputError, match="time_series_id"):
        TimelineEvidence(component=SuiteEvidenceComponent.IMA, role="rfet_observations")

    with pytest.raises(OrchestrationInputError, match="scenario_vector_ids"):
        ImaScenarioEvidence(
            scenario_cube_id="scenario-cube-ima-run-1",
            scenario_vector_ids=("scenario-vector-0001", "scenario-vector-0001"),
        )
