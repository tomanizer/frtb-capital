from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest
from frtb_common import (
    ArtifactIdentityError,
    ScenarioId,
    ScenarioSetId,
    ScenarioVectorId,
    ShockDirection,
    ShockId,
    SurfaceAxisKind,
    SurfaceAxisName,
    SurfaceCoordinate,
    SurfaceId,
    SurfacePointCoordinates,
    SurfacePointId,
    TimeSeriesId,
)


def test_artifact_identifiers_are_stable_value_objects() -> None:
    assert TimeSeriesId(" rfet-usd-5y ").value == "rfet-usd-5y"
    assert str(ShockId("sbm-curvature-up")) == "sbm-curvature-up"
    assert ScenarioId("scenario-001") == ScenarioId("scenario-001")
    assert ScenarioSetId("historical-window-2024") == ScenarioSetId("historical-window-2024")
    assert ScenarioVectorId("ima-pl-cube:desk-a:2024") == ScenarioVectorId(
        "ima-pl-cube:desk-a:2024"
    )
    assert SurfaceId("usd-swaption-vol") != SurfacePointId("usd-swaption-vol")


def test_artifact_identifiers_are_immutable() -> None:
    identifier = ScenarioVectorId("ima-pl-cube:desk-a:2024")

    with pytest.raises(FrozenInstanceError):
        identifier.value = "changed"  # type: ignore[misc]


def test_artifact_identifiers_reject_blank_values() -> None:
    with pytest.raises(ArtifactIdentityError, match="non-empty text"):
        TimeSeriesId(" ")


def test_surface_coordinate_validates_label_and_numeric_axes() -> None:
    label = SurfaceCoordinate(
        axis_name=SurfaceAxisName("option_tenor"),
        value="3M",
        kind=SurfaceAxisKind.LABEL,
    )
    numeric = SurfaceCoordinate(axis_name="moneyness", value=0.0, kind="NUMERIC", unit="delta")

    assert label.axis_name.value == "option_tenor"
    assert label.value == "3M"
    assert numeric.value == 0.0
    assert numeric.unit == "delta"


def test_surface_point_coordinates_validate_two_distinct_axes() -> None:
    point = SurfacePointCoordinates(
        surface_id="surface-usd-swaption-vol",
        surface_point_id="surface-usd-swaption-vol:3m:5y",
        axis_1=SurfaceCoordinate(axis_name="option_tenor", value="3M"),
        axis_2=SurfaceCoordinate(axis_name="underlying_tenor", value="5Y"),
    )

    assert point.surface_id == SurfaceId("surface-usd-swaption-vol")
    assert point.surface_point_id == SurfacePointId("surface-usd-swaption-vol:3m:5y")
    assert point.axis_1.axis_name.value == "option_tenor"
    assert point.axis_2.axis_name.value == "underlying_tenor"


def test_surface_point_coordinates_reject_duplicate_axes() -> None:
    with pytest.raises(ArtifactIdentityError, match="axes must be distinct"):
        SurfacePointCoordinates(
            surface_id="surface-usd-swaption-vol",
            surface_point_id="surface-usd-swaption-vol:3m:5y",
            axis_1=SurfaceCoordinate(axis_name="tenor", value="3M"),
            axis_2=SurfaceCoordinate(axis_name="tenor", value="5Y"),
        )


def test_surface_coordinate_rejects_invalid_numeric_axis_values() -> None:
    with pytest.raises(ArtifactIdentityError, match="require int or float"):
        SurfaceCoordinate(axis_name="expiry", value="1Y", kind=SurfaceAxisKind.NUMERIC)
    with pytest.raises(ArtifactIdentityError, match="finite"):
        SurfaceCoordinate(axis_name="expiry", value=float("nan"), kind=SurfaceAxisKind.NUMERIC)


def test_surface_coordinate_rejects_invalid_label_axis_values() -> None:
    with pytest.raises(ArtifactIdentityError, match="string, int, or float"):
        SurfaceCoordinate(axis_name="expiry", value=None)  # type: ignore[arg-type]
    with pytest.raises(ArtifactIdentityError, match="string, int, or float"):
        SurfaceCoordinate(axis_name="expiry", value=True)  # type: ignore[arg-type]
    with pytest.raises(ArtifactIdentityError, match="string, int, or float"):
        SurfaceCoordinate(axis_name="expiry", value=["1Y"])  # type: ignore[arg-type]


def test_shock_direction_is_a_canonical_string_enum() -> None:
    assert ShockDirection.UP.value == "UP"
    assert ShockDirection("DOWN") is ShockDirection.DOWN
