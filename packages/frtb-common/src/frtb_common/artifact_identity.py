"""Stable identifiers for stored analytical artifacts.

This module defines lightweight identifiers and axis primitives for time-series,
shock, scenario-vector, and surface metadata. The objects are metadata carriers
only: they do not load market data, interpolate surfaces, generate shocks, or
perform capital calculations.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from math import isfinite


class ArtifactIdentityError(ValueError):
    """Raised when an artifact identifier or coordinate is not audit-stable."""


class ShockDirection(StrEnum):
    """Canonical direction labels for persisted shock definitions."""

    UP = "UP"
    DOWN = "DOWN"
    ABSOLUTE = "ABSOLUTE"
    RELATIVE = "RELATIVE"
    PARALLEL = "PARALLEL"


class SurfaceAxisKind(StrEnum):
    """Supported coordinate representations for surface axes."""

    LABEL = "LABEL"
    NUMERIC = "NUMERIC"


@dataclass(frozen=True, slots=True)
class _StableArtifactId:
    """Base value object for stable artifact identifiers."""

    value: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "value", _require_non_empty_text(self.value, "value"))

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True, slots=True)
class TimeSeriesId(_StableArtifactId):
    """Stable identifier for an observed or calculated time series."""


@dataclass(frozen=True, slots=True)
class ScenarioId(_StableArtifactId):
    """Stable identifier for one scenario observation."""


@dataclass(frozen=True, slots=True)
class ScenarioSetId(_StableArtifactId):
    """Stable identifier for an ordered set of scenario observations."""


@dataclass(frozen=True, slots=True)
class ScenarioVectorId(_StableArtifactId):
    """Stable identifier for a scenario vector or cube artifact."""


@dataclass(frozen=True, slots=True)
class ShockId(_StableArtifactId):
    """Stable identifier for a persisted shock definition."""


@dataclass(frozen=True, slots=True)
class SurfaceId(_StableArtifactId):
    """Stable identifier for a persisted surface or grid artifact."""


@dataclass(frozen=True, slots=True)
class SurfacePointId(_StableArtifactId):
    """Stable identifier for one coordinate point on a persisted surface."""


@dataclass(frozen=True, slots=True)
class SurfaceAxisName:
    """Canonical name of a surface axis such as expiry, tenor, or moneyness."""

    value: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "value", _require_non_empty_text(self.value, "value"))

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True, slots=True)
class SurfaceCoordinate:
    """One validated coordinate on a labelled or numeric surface axis."""

    axis_name: SurfaceAxisName | str
    value: str | int | float
    kind: SurfaceAxisKind | str = SurfaceAxisKind.LABEL
    unit: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "axis_name", _coerce_axis_name(self.axis_name))
        object.__setattr__(self, "kind", _coerce_axis_kind(self.kind))
        object.__setattr__(self, "unit", _optional_text(self.unit, "unit"))
        if self.kind is SurfaceAxisKind.NUMERIC:
            object.__setattr__(self, "value", _require_numeric_coordinate(self.value))
        else:
            object.__setattr__(
                self,
                "value",
                _require_non_empty_text(str(self.value), "value"),
            )


@dataclass(frozen=True, slots=True)
class SurfacePointCoordinates:
    """Validated two-axis coordinates for one persisted surface point."""

    surface_id: SurfaceId | str
    surface_point_id: SurfacePointId | str
    axis_1: SurfaceCoordinate
    axis_2: SurfaceCoordinate

    def __post_init__(self) -> None:
        object.__setattr__(self, "surface_id", _coerce_surface_id(self.surface_id))
        object.__setattr__(
            self,
            "surface_point_id",
            _coerce_surface_point_id(self.surface_point_id),
        )
        if not isinstance(self.axis_1, SurfaceCoordinate):
            raise ArtifactIdentityError("axis_1 must be a SurfaceCoordinate")
        if not isinstance(self.axis_2, SurfaceCoordinate):
            raise ArtifactIdentityError("axis_2 must be a SurfaceCoordinate")
        if self.axis_1.axis_name == self.axis_2.axis_name:
            raise ArtifactIdentityError("surface point axes must be distinct")


def _require_non_empty_text(value: object, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ArtifactIdentityError(f"{field} must be non-empty text")
    return value.strip()


def _optional_text(value: object, field: str) -> str:
    if not isinstance(value, str):
        raise ArtifactIdentityError(f"{field} must be text")
    return value.strip()


def _coerce_axis_name(value: SurfaceAxisName | str) -> SurfaceAxisName:
    return value if isinstance(value, SurfaceAxisName) else SurfaceAxisName(value)


def _coerce_axis_kind(value: SurfaceAxisKind | str) -> SurfaceAxisKind:
    try:
        return SurfaceAxisKind(value)
    except ValueError as exc:
        raise ArtifactIdentityError(f"invalid surface axis kind: {value}") from exc


def _coerce_surface_id(value: SurfaceId | str) -> SurfaceId:
    return value if isinstance(value, SurfaceId) else SurfaceId(value)


def _coerce_surface_point_id(value: SurfacePointId | str) -> SurfacePointId:
    return value if isinstance(value, SurfacePointId) else SurfacePointId(value)


def _require_numeric_coordinate(value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise ArtifactIdentityError("numeric surface coordinates require int or float values")
    coordinate = float(value)
    if not isfinite(coordinate):
        raise ArtifactIdentityError("numeric surface coordinates must be finite")
    return coordinate


__all__ = [
    "ArtifactIdentityError",
    "ScenarioId",
    "ScenarioSetId",
    "ScenarioVectorId",
    "ShockDirection",
    "ShockId",
    "SurfaceAxisKind",
    "SurfaceAxisName",
    "SurfaceCoordinate",
    "SurfaceId",
    "SurfacePointId",
    "SurfacePointCoordinates",
    "TimeSeriesId",
]
