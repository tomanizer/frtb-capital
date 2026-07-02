"""Typed resolved artifact metadata inputs for orchestration evidence views."""

from __future__ import annotations

from dataclasses import dataclass

from frtb_common import (
    ScenarioSetId,
    ScenarioVectorId,
    ShockDirection,
    ShockId,
    SurfaceId,
    SurfacePointId,
    TimeSeriesId,
)

from frtb_orchestration._validation import OrchestrationInputError
from frtb_orchestration.artifact_evidence import ArtifactEvidenceStatus, SuiteEvidenceComponent


@dataclass(frozen=True)
class SbmShockEvidence:
    """Resolved SBM curvature shock reference for orchestration evidence views."""

    shock_id: ShockId | str
    direction: ShockDirection | str
    risk_class: str
    risk_measure: str
    bucket_id: str
    risk_factor_id: str
    source_row_id: str = ""
    mapping_version: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "shock_id", _coerce_shock_id(self.shock_id))
        object.__setattr__(self, "direction", _coerce_shock_direction(self.direction))
        object.__setattr__(self, "risk_class", _required_text(self.risk_class, "risk_class"))
        object.__setattr__(self, "risk_measure", _required_text(self.risk_measure, "risk_measure"))
        object.__setattr__(self, "bucket_id", _required_text(self.bucket_id, "bucket_id"))
        object.__setattr__(
            self,
            "risk_factor_id",
            _required_text(self.risk_factor_id, "risk_factor_id"),
        )
        object.__setattr__(
            self,
            "source_row_id",
            _optional_text_value(self.source_row_id, "source_row_id"),
        )
        object.__setattr__(
            self,
            "mapping_version",
            _optional_text_value(self.mapping_version, "mapping_version"),
        )


@dataclass(frozen=True)
class ImaScenarioEvidence:
    """Resolved IMA scenario cube and vector identifiers."""

    scenario_cube_id: ScenarioVectorId | str
    scenario_set_id: ScenarioSetId | str = ""
    scenario_vector_ids: tuple[ScenarioVectorId | str, ...] = ()
    source_row_id: str = ""
    mapping_version: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "scenario_cube_id",
            _coerce_scenario_vector_id(self.scenario_cube_id),
        )
        object.__setattr__(
            self,
            "scenario_set_id",
            _coerce_optional_scenario_set_id(self.scenario_set_id),
        )
        vector_ids = tuple(_coerce_scenario_vector_id(value) for value in self.scenario_vector_ids)
        if len(vector_ids) != len(set(vector_ids)):
            raise OrchestrationInputError(
                "scenario_vector_ids contains duplicates",
                field="scenario_vector_ids",
            )
        object.__setattr__(self, "scenario_vector_ids", vector_ids)
        object.__setattr__(
            self,
            "source_row_id",
            _optional_text_value(self.source_row_id, "source_row_id"),
        )
        object.__setattr__(
            self,
            "mapping_version",
            _optional_text_value(self.mapping_version, "mapping_version"),
        )


@dataclass(frozen=True)
class TimelineEvidence:
    """Resolved time-series evidence reference or explicit unavailable state."""

    component: SuiteEvidenceComponent
    role: str
    time_series_id: TimeSeriesId | str = ""
    status: ArtifactEvidenceStatus = ArtifactEvidenceStatus.AVAILABLE
    reason: str = ""
    risk_factor_id: str = ""
    source_component: str = ""
    source_field: str = ""
    source_row_id: str = ""
    mapping_version: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "component", _coerce_evidence_component(self.component))
        object.__setattr__(self, "role", _required_text(self.role, "role"))
        object.__setattr__(self, "status", _coerce_evidence_status(self.status))
        object.__setattr__(
            self,
            "time_series_id",
            _coerce_optional_time_series_id(self.time_series_id),
        )
        object.__setattr__(self, "reason", _optional_text_value(self.reason, "reason"))
        object.__setattr__(
            self,
            "risk_factor_id",
            _optional_text_value(self.risk_factor_id, "risk_factor_id"),
        )
        object.__setattr__(
            self,
            "source_component",
            _optional_text_value(self.source_component, "source_component"),
        )
        object.__setattr__(
            self,
            "source_field",
            _optional_text_value(self.source_field, "source_field"),
        )
        object.__setattr__(
            self,
            "source_row_id",
            _optional_text_value(self.source_row_id, "source_row_id"),
        )
        object.__setattr__(
            self,
            "mapping_version",
            _optional_text_value(self.mapping_version, "mapping_version"),
        )
        if self.status is ArtifactEvidenceStatus.AVAILABLE and not self.time_series_id:
            raise OrchestrationInputError(
                "available timeline evidence requires time_series_id",
                field="time_series_id",
            )
        if self.status is not ArtifactEvidenceStatus.AVAILABLE and not self.reason:
            raise OrchestrationInputError(
                "no-data or unsupported timeline evidence requires reason",
                field="reason",
            )


@dataclass(frozen=True)
class SurfaceEvidence:
    """Resolved surface or surface-point evidence for a component view."""

    component: SuiteEvidenceComponent
    role: str
    surface_id: SurfaceId | str
    source_component: str
    source_field: str
    surface_point_ids: tuple[SurfacePointId | str, ...] = ()
    risk_factor_id: str = ""
    source_row_id: str = ""
    mapping_version: str = ""
    axis_1: str = ""
    axis_2: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "component", _coerce_evidence_component(self.component))
        object.__setattr__(self, "role", _required_text(self.role, "role"))
        object.__setattr__(self, "surface_id", _coerce_surface_id(self.surface_id))
        object.__setattr__(
            self,
            "source_component",
            _required_text(self.source_component, "source_component"),
        )
        object.__setattr__(self, "source_field", _required_text(self.source_field, "source_field"))
        point_ids = tuple(_coerce_surface_point_id(value) for value in self.surface_point_ids)
        if len(point_ids) != len(set(point_ids)):
            raise OrchestrationInputError(
                "surface_point_ids contains duplicates",
                field="surface_point_ids",
            )
        object.__setattr__(self, "surface_point_ids", point_ids)
        object.__setattr__(
            self,
            "risk_factor_id",
            _optional_text_value(self.risk_factor_id, "risk_factor_id"),
        )
        object.__setattr__(
            self,
            "source_row_id",
            _optional_text_value(self.source_row_id, "source_row_id"),
        )
        object.__setattr__(
            self,
            "mapping_version",
            _optional_text_value(self.mapping_version, "mapping_version"),
        )
        object.__setattr__(self, "axis_1", _optional_text_value(self.axis_1, "axis_1"))
        object.__setattr__(self, "axis_2", _optional_text_value(self.axis_2, "axis_2"))


def _coerce_evidence_component(value: SuiteEvidenceComponent | str) -> SuiteEvidenceComponent:
    try:
        return value if isinstance(value, SuiteEvidenceComponent) else SuiteEvidenceComponent(value)
    except ValueError as exc:
        raise OrchestrationInputError(
            f"invalid evidence component: {value}",
            field="component",
        ) from exc


def _coerce_evidence_status(value: ArtifactEvidenceStatus | str) -> ArtifactEvidenceStatus:
    try:
        return value if isinstance(value, ArtifactEvidenceStatus) else ArtifactEvidenceStatus(value)
    except ValueError as exc:
        raise OrchestrationInputError(
            f"invalid artifact evidence status: {value}",
            field="status",
        ) from exc


def _coerce_shock_direction(value: ShockDirection | str) -> ShockDirection:
    try:
        return value if isinstance(value, ShockDirection) else ShockDirection(value)
    except ValueError as exc:
        raise OrchestrationInputError(
            f"invalid shock direction: {value}",
            field="direction",
        ) from exc


def _coerce_shock_id(value: ShockId | str) -> ShockId:
    return value if isinstance(value, ShockId) else ShockId(_required_text(value, "shock_id"))


def _coerce_scenario_vector_id(value: ScenarioVectorId | str) -> ScenarioVectorId:
    return (
        value
        if isinstance(value, ScenarioVectorId)
        else ScenarioVectorId(_required_text(value, "scenario_vector_id"))
    )


def _coerce_optional_scenario_set_id(value: ScenarioSetId | str) -> ScenarioSetId | str:
    if isinstance(value, ScenarioSetId):
        return value
    text = _optional_text_value(value, "scenario_set_id")
    return ScenarioSetId(text) if text else ""


def _coerce_optional_time_series_id(value: TimeSeriesId | str) -> TimeSeriesId | str:
    if isinstance(value, TimeSeriesId):
        return value
    text = _optional_text_value(value, "time_series_id")
    return TimeSeriesId(text) if text else ""


def _coerce_surface_id(value: SurfaceId | str) -> SurfaceId:
    return value if isinstance(value, SurfaceId) else SurfaceId(_required_text(value, "surface_id"))


def _coerce_surface_point_id(value: SurfacePointId | str) -> SurfacePointId:
    return (
        value
        if isinstance(value, SurfacePointId)
        else SurfacePointId(_required_text(value, "surface_point_id"))
    )


def _required_text(value: object, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise OrchestrationInputError(f"{field} must be non-empty text", field=field)
    return value.strip()


def _optional_text_value(value: object, field: str) -> str:
    if not isinstance(value, str):
        raise OrchestrationInputError(f"{field} must be text", field=field)
    return value.strip()


__all__ = [
    "ImaScenarioEvidence",
    "SbmShockEvidence",
    "SurfaceEvidence",
    "TimelineEvidence",
]
