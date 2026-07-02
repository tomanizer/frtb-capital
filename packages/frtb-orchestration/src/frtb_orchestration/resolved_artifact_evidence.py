"""Resolved artifact metadata builders for suite evidence views.

This module converts already resolved time-series, shock, scenario-vector, and
surface identifiers into the generic artifact evidence rows owned by
``frtb_orchestration.artifact_evidence``. It composes metadata only and does not
query result stores, fetch artifact payloads, source market data, generate
shocks, or interpolate surfaces.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from frtb_common import (
    ScenarioSetId,
    ScenarioVectorId,
    ShockDirection,
    ShockId,
    SurfaceId,
    SurfacePointId,
    TimeSeriesId,
)

from frtb_orchestration._suite_attribution_models import SuiteCapitalResult
from frtb_orchestration.artifact_evidence import (
    ArtifactEvidenceKind,
    ArtifactEvidenceRef,
    SuiteArtifactEvidenceView,
    SuiteEvidenceComponent,
    build_suite_artifact_evidence_view,
)
from frtb_orchestration.artifact_evidence_inputs import (
    ImaScenarioEvidence,
    SbmShockEvidence,
    SurfaceEvidence,
    TimelineEvidence,
)

_ArtifactId = ScenarioSetId | ScenarioVectorId | ShockId | SurfaceId | SurfacePointId | TimeSeriesId


def build_resolved_artifact_evidence_view(
    suite_result: SuiteCapitalResult,
    *,
    sbm_shocks: Sequence[SbmShockEvidence] = (),
    ima_scenarios: Sequence[ImaScenarioEvidence] = (),
    timelines: Sequence[TimelineEvidence] = (),
    surfaces: Sequence[SurfaceEvidence] = (),
    extra_refs: Sequence[ArtifactEvidenceRef] = (),
) -> SuiteArtifactEvidenceView:
    """Compose a suite evidence view from resolved component artifact metadata.

    Parameters
    ----------
    suite_result : SuiteCapitalResult
        Completed suite capital result that supplies run context.
    sbm_shocks : Sequence[SbmShockEvidence], optional
        Resolved SBM curvature shock identifiers supplied by component or
        result-store metadata.
    ima_scenarios : Sequence[ImaScenarioEvidence], optional
        Resolved IMA scenario cube/vector identifiers.
    timelines : Sequence[TimelineEvidence], optional
        Resolved timeline identifiers or explicit no-data states.
    surfaces : Sequence[SurfaceEvidence], optional
        Resolved volatility or other surface identifiers.
    extra_refs : Sequence[ArtifactEvidenceRef], optional
        Already-built evidence references for component families not covered by
        the typed helpers.

    Returns
    -------
    SuiteArtifactEvidenceView
        Component-grouped evidence view without fetching artifact payloads.
    """

    refs = (
        *build_sbm_shock_evidence_refs(sbm_shocks),
        *build_ima_scenario_evidence_refs(ima_scenarios),
        *build_timeline_evidence_refs(timelines),
        *build_surface_evidence_refs(surfaces),
        *tuple(extra_refs),
    )
    return build_suite_artifact_evidence_view(suite_result, refs)


def build_sbm_shock_evidence_refs(
    shocks: Sequence[SbmShockEvidence],
) -> tuple[ArtifactEvidenceRef, ...]:
    """Return artifact refs for resolved SBM curvature shock identifiers.

    Parameters
    ----------
    shocks : Sequence[SbmShockEvidence]
        Resolved SBM curvature shock metadata supplied by component or
        result-store read models.

    Returns
    -------
    tuple[ArtifactEvidenceRef, ...]
        Deterministically ordered shock evidence references.
    """

    return tuple(_sbm_shock_ref(shock) for shock in sorted(tuple(shocks), key=_shock_sort_key))


def build_ima_scenario_evidence_refs(
    scenarios: Sequence[ImaScenarioEvidence],
) -> tuple[ArtifactEvidenceRef, ...]:
    """Return artifact refs for resolved IMA scenario cube/vector identifiers.

    Parameters
    ----------
    scenarios : Sequence[ImaScenarioEvidence]
        Resolved IMA scenario cube, set, and vector metadata.

    Returns
    -------
    tuple[ArtifactEvidenceRef, ...]
        Deterministically ordered scenario cube and vector references.
    """

    refs: list[ArtifactEvidenceRef] = []
    for scenario in sorted(tuple(scenarios), key=_ima_scenario_sort_key):
        refs.append(_ima_scenario_cube_ref(scenario))
        refs.extend(_ima_scenario_vector_refs(scenario))
    return tuple(refs)


def build_timeline_evidence_refs(
    timelines: Sequence[TimelineEvidence],
) -> tuple[ArtifactEvidenceRef, ...]:
    """Return artifact refs for resolved time-series evidence metadata.

    Parameters
    ----------
    timelines : Sequence[TimelineEvidence]
        Resolved time-series IDs or explicit no-data/unsupported states.

    Returns
    -------
    tuple[ArtifactEvidenceRef, ...]
        Deterministically ordered timeline evidence references.
    """

    return tuple(
        _timeline_ref(timeline) for timeline in sorted(tuple(timelines), key=_timeline_sort_key)
    )


def build_surface_evidence_refs(
    surfaces: Sequence[SurfaceEvidence],
) -> tuple[ArtifactEvidenceRef, ...]:
    """Return artifact refs for resolved surface and surface-point metadata.

    Parameters
    ----------
    surfaces : Sequence[SurfaceEvidence]
        Resolved surface IDs and optional surface-point IDs.

    Returns
    -------
    tuple[ArtifactEvidenceRef, ...]
        Deterministically ordered surface and surface-point references.
    """

    refs: list[ArtifactEvidenceRef] = []
    for surface in sorted(tuple(surfaces), key=_surface_sort_key):
        refs.append(_surface_ref(surface))
        refs.extend(_surface_point_refs(surface))
    return tuple(refs)


def _sbm_shock_ref(shock: SbmShockEvidence) -> ArtifactEvidenceRef:
    shock_id = _artifact_id_value(shock.shock_id)
    shock_direction = _shock_direction_value(shock.direction)
    direction = shock_direction.lower()
    return ArtifactEvidenceRef(
        component=SuiteEvidenceComponent.SBM,
        kind=ArtifactEvidenceKind.SHOCK,
        role=f"sbm_curvature_{direction}:{shock.risk_factor_id}",
        artifact_id=shock_id,
        source_component="frtb-sbm",
        source_field=f"SbmSensitivity.{direction}_shock_id",
        partition_values=_partition_values(
            risk_class=shock.risk_class,
            risk_measure=shock.risk_measure,
            bucket_id=shock.bucket_id,
            risk_factor_id=shock.risk_factor_id,
            shock_direction=shock_direction,
            source_row_id=shock.source_row_id,
            mapping_version=shock.mapping_version,
        ),
    )


def _ima_scenario_cube_ref(scenario: ImaScenarioEvidence) -> ArtifactEvidenceRef:
    scenario_cube_id = _artifact_id_value(scenario.scenario_cube_id)
    return ArtifactEvidenceRef(
        component=SuiteEvidenceComponent.IMA,
        kind=ArtifactEvidenceKind.SCENARIO_VECTOR,
        role=f"ima_scenario_cube:{scenario_cube_id}",
        artifact_id=scenario_cube_id,
        source_component="frtb-ima",
        source_field="ScenarioCube.artifact_id",
        partition_values=_partition_values(
            scenario_set_id=_artifact_id_value(scenario.scenario_set_id),
            scenario_vector_count=str(len(scenario.scenario_vector_ids)),
            source_row_id=scenario.source_row_id,
            mapping_version=scenario.mapping_version,
        ),
    )


def _ima_scenario_vector_refs(scenario: ImaScenarioEvidence) -> tuple[ArtifactEvidenceRef, ...]:
    scenario_cube_id = _artifact_id_value(scenario.scenario_cube_id)
    scenario_set_id = _artifact_id_value(scenario.scenario_set_id)
    return tuple(
        ArtifactEvidenceRef(
            component=SuiteEvidenceComponent.IMA,
            kind=ArtifactEvidenceKind.SCENARIO_VECTOR,
            role=f"ima_scenario_vector:{scenario_cube_id}:{index:04d}",
            artifact_id=_artifact_id_value(scenario_vector_id),
            source_component="frtb-ima",
            source_field="ScenarioCube.scenario_vector_ids",
            partition_values=_partition_values(
                scenario_cube_id=scenario_cube_id,
                scenario_set_id=scenario_set_id,
                scenario_index=str(index),
                source_row_id=scenario.source_row_id,
                mapping_version=scenario.mapping_version,
            ),
        )
        for index, scenario_vector_id in enumerate(scenario.scenario_vector_ids)
    )


def _timeline_ref(timeline: TimelineEvidence) -> ArtifactEvidenceRef:
    artifact_id = _artifact_id_value(timeline.time_series_id)
    suffix = timeline.risk_factor_id or artifact_id or timeline.status.value.lower()
    return ArtifactEvidenceRef(
        component=timeline.component,
        kind=ArtifactEvidenceKind.TIME_SERIES,
        role=f"{timeline.role}:{suffix}",
        artifact_id=artifact_id,
        status=timeline.status,
        source_component=timeline.source_component,
        source_field=timeline.source_field,
        reason=timeline.reason,
        partition_values=_partition_values(
            risk_factor_id=timeline.risk_factor_id,
            source_row_id=timeline.source_row_id,
            mapping_version=timeline.mapping_version,
        ),
    )


def _surface_ref(surface: SurfaceEvidence) -> ArtifactEvidenceRef:
    surface_id = _artifact_id_value(surface.surface_id)
    return ArtifactEvidenceRef(
        component=surface.component,
        kind=ArtifactEvidenceKind.SURFACE,
        role=f"{surface.role}:{surface_id}",
        artifact_id=surface_id,
        source_component=surface.source_component,
        source_field=surface.source_field,
        partition_values=_partition_values(
            risk_factor_id=surface.risk_factor_id,
            source_row_id=surface.source_row_id,
            mapping_version=surface.mapping_version,
            axis_1=surface.axis_1,
            axis_2=surface.axis_2,
            surface_point_count=str(len(surface.surface_point_ids)),
        ),
    )


def _surface_point_refs(surface: SurfaceEvidence) -> tuple[ArtifactEvidenceRef, ...]:
    surface_id = _artifact_id_value(surface.surface_id)
    return tuple(
        ArtifactEvidenceRef(
            component=surface.component,
            kind=ArtifactEvidenceKind.SURFACE,
            role=f"{surface.role}_point:{surface_id}:{index:04d}",
            artifact_id=_artifact_id_value(surface_point_id),
            source_component=surface.source_component,
            source_field=surface.source_field,
            partition_values=_partition_values(
                surface_id=surface_id,
                risk_factor_id=surface.risk_factor_id,
                source_row_id=surface.source_row_id,
                mapping_version=surface.mapping_version,
                axis_1=surface.axis_1,
                axis_2=surface.axis_2,
                surface_point_index=str(index),
            ),
        )
        for index, surface_point_id in enumerate(surface.surface_point_ids)
    )


def _partition_values(**values: str) -> Mapping[str, str]:
    return {key: value for key, value in values.items() if value}


def _shock_sort_key(shock: SbmShockEvidence) -> tuple[str, str, str, str, str, str]:
    return (
        shock.risk_class,
        shock.risk_measure,
        shock.bucket_id,
        shock.risk_factor_id,
        _shock_direction_value(shock.direction),
        _artifact_id_value(shock.shock_id),
    )


def _ima_scenario_sort_key(scenario: ImaScenarioEvidence) -> tuple[str, str]:
    return (
        _artifact_id_value(scenario.scenario_cube_id),
        _artifact_id_value(scenario.scenario_set_id),
    )


def _timeline_sort_key(timeline: TimelineEvidence) -> tuple[str, str, str, str]:
    return (
        timeline.component.value,
        timeline.role,
        timeline.risk_factor_id,
        _artifact_id_value(timeline.time_series_id),
    )


def _surface_sort_key(surface: SurfaceEvidence) -> tuple[str, str, str, str]:
    return (
        surface.component.value,
        surface.role,
        _artifact_id_value(surface.surface_id),
        surface.risk_factor_id,
    )


def _artifact_id_value(value: _ArtifactId | str) -> str:
    return value.value if isinstance(value, _ArtifactId) else value


def _shock_direction_value(value: ShockDirection | str) -> str:
    return value.value if isinstance(value, ShockDirection) else value


__all__ = [
    "build_ima_scenario_evidence_refs",
    "build_resolved_artifact_evidence_view",
    "build_sbm_shock_evidence_refs",
    "build_surface_evidence_refs",
    "build_timeline_evidence_refs",
]
