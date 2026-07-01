from __future__ import annotations

from datetime import date
from pathlib import Path
from urllib.parse import unquote, urlparse

import pyarrow as pa
import pyarrow.parquet as pq
from fastapi.testclient import TestClient
from frtb_result_store import (
    ArtifactType,
    ArtifactWriteRequest,
    DuckDbParquetResultStore,
    FrtbComponent,
    artifact_schema_for,
    create_result_store_app,
)

from fixtures.result_store_bundle import sample_bundle, run_with_id


def test_common_artifact_schemas_stage_timeline_shock_scenario_and_surface(
    tmp_path: Path,
) -> None:
    run = run_with_id("run-artifact-metadata")
    store = DuckDbParquetResultStore(tmp_path / "result-store")
    requests = _metadata_artifact_requests(run.run_id)

    store.write_bundle(sample_bundle(run), artifact_requests=requests)

    refs = {
        ArtifactType(ref.artifact_type): ref
        for ref in store.artifact_refs(run.run_id)
        if ArtifactType(ref.artifact_type)
        in {
            ArtifactType.TIME_SERIES,
            ArtifactType.SHOCK_DEFINITION,
            ArtifactType.SCENARIO_VECTOR_METADATA,
            ArtifactType.SURFACE_GRID,
        }
    }
    assert set(refs) == {
        ArtifactType.TIME_SERIES,
        ArtifactType.SHOCK_DEFINITION,
        ArtifactType.SCENARIO_VECTOR_METADATA,
        ArtifactType.SURFACE_GRID,
    }
    assert refs[ArtifactType.TIME_SERIES].partition_keys == ("time_series_id",)
    assert refs[ArtifactType.SURFACE_GRID].metadata["schema_id"] == "common.surface_grid.v1"

    surface_path = Path(unquote(urlparse(refs[ArtifactType.SURFACE_GRID].uri).path))
    surface_rows = pq.read_table(surface_path).to_pylist()
    assert surface_rows[0]["axis_1_name"] == "option_tenor"
    assert surface_rows[0]["axis_2_value"] == "5Y"


def test_metadata_artifact_ids_are_stable_and_partition_sensitive(tmp_path: Path) -> None:
    run = run_with_id("run-artifact-identity")
    first = DuckDbParquetResultStore(tmp_path / "first-store")
    second = DuckDbParquetResultStore(tmp_path / "second-store")
    changed_partition = DuckDbParquetResultStore(tmp_path / "changed-partition-store")

    first.write_bundle(
        sample_bundle(run),
        artifact_requests=(
            _scenario_vector_request(
                run_id=run.run_id,
                scenario_vector_id="scenario-vector-rtpl",
                label="RTPL day 1",
            ),
        ),
    )
    second.write_bundle(
        sample_bundle(run),
        artifact_requests=(
            _scenario_vector_request(
                run_id=run.run_id,
                scenario_vector_id="scenario-vector-rtpl",
                label="RTPL day 1",
            ),
        ),
    )
    changed_partition.write_bundle(
        sample_bundle(run),
        artifact_requests=(
            _scenario_vector_request(
                run_id=run.run_id,
                scenario_vector_id="scenario-vector-hpl",
                label="HPL day 1",
            ),
        ),
    )

    first_ref = first.artifact_refs(
        run.run_id,
        artifact_type=ArtifactType.SCENARIO_VECTOR_METADATA,
    )[0]
    second_ref = second.artifact_refs(
        run.run_id,
        artifact_type=ArtifactType.SCENARIO_VECTOR_METADATA,
    )[0]
    changed_ref = changed_partition.artifact_refs(
        run.run_id,
        artifact_type=ArtifactType.SCENARIO_VECTOR_METADATA,
    )[0]

    assert first_ref.artifact_id == second_ref.artifact_id
    assert first_ref.schema_fingerprint == second_ref.schema_fingerprint
    assert first_ref.metadata["partition_values"] == {
        "scenario_set_id": "scenario-set-250d",
        "scenario_vector_id": "scenario-vector-rtpl",
    }
    assert changed_ref.artifact_id != first_ref.artifact_id


def test_artifact_metadata_api_serves_timelines_shocks_scenarios_and_surfaces(
    tmp_path: Path,
) -> None:
    run = run_with_id("run-artifact-metadata-api")
    store = DuckDbParquetResultStore(tmp_path / "result-store")
    store.write_bundle(
        sample_bundle(run),
        artifact_requests=_metadata_artifact_requests(run.run_id),
    )
    client = TestClient(create_result_store_app(store))

    assert len(client.get(f"/runs/{run.run_id}/time-series").json()["time_series"]) == 1
    timeline = client.get(f"/runs/{run.run_id}/time-series/ts-rfet-usd-5y/points").json()
    assert timeline["rows"][0]["source_row_id"] == "rfet-row-001"

    shock = client.get(f"/runs/{run.run_id}/shocks/shock-sbm-curvature-up").json()
    assert shock["rows"][0]["shock_direction"] == "UP"

    scenario = client.get(
        f"/runs/{run.run_id}/scenario-vectors/scenario-vector-rtpl/metadata"
    ).json()
    assert scenario["rows"][0]["scenario_label"] == "RTPL day 1"

    surface = client.get(
        f"/runs/{run.run_id}/surfaces/surface-usd-swaption-vol/slice",
        params={"axis_1_value": "3M"},
    ).json()
    assert surface["rows"][0]["axis_2_value"] == "5Y"

    missing = client.get(f"/runs/{run.run_id}/shocks/missing-shock")
    assert missing.status_code == 404


def _metadata_artifact_requests(run_id: str) -> tuple[ArtifactWriteRequest, ...]:
    return (
        _time_series_request(run_id),
        _shock_request(run_id),
        _scenario_vector_request(
            run_id=run_id,
            scenario_vector_id="scenario-vector-rtpl",
            label="RTPL day 1",
        ),
        _surface_request(run_id),
    )


def _time_series_request(run_id: str) -> ArtifactWriteRequest:
    return _request(
        schema_id="common.time_series.v1",
        artifact_type=ArtifactType.TIME_SERIES,
        component=FrtbComponent.IMA,
        hint="rfet-observations",
        partitions={"time_series_id": "ts-rfet-usd-5y"},
        rows=[
            {
                "run_id": run_id,
                "time_series_id": "ts-rfet-usd-5y",
                "observation_date": date(2026, 6, 1),
                "value_name": "real_price_observation",
                "value": 1.0,
                "currency": "USD",
                "risk_factor_id": "rf-girr-usd-5y",
                "scenario_id": None,
                "mapping_version": "risk-factor-map-v1",
                "source_row_id": "rfet-row-001",
            }
        ],
    )


def _shock_request(run_id: str) -> ArtifactWriteRequest:
    return _request(
        schema_id="common.shock_definition.v1",
        artifact_type=ArtifactType.SHOCK_DEFINITION,
        component=FrtbComponent.SBM,
        hint="sbm-curvature-up",
        partitions={"shock_id": "shock-sbm-curvature-up"},
        rows=[
            {
                "run_id": run_id,
                "shock_id": "shock-sbm-curvature-up",
                "shock_direction": "UP",
                "shock_type": "ABSOLUTE",
                "magnitude": 125.0,
                "unit": "bp",
                "risk_factor_id": "rf-girr-usd-5y",
                "scenario_id": None,
                "mapping_version": "shock-map-v1",
                "regulatory_rule_id": "MAR21.96",
                "source_row_id": "shock-row-001",
            }
        ],
    )


def _surface_request(run_id: str) -> ArtifactWriteRequest:
    return _request(
        schema_id="common.surface_grid.v1",
        artifact_type=ArtifactType.SURFACE_GRID,
        component=FrtbComponent.SBM,
        hint="usd-swaption-vol-surface",
        partitions={"surface_id": "surface-usd-swaption-vol"},
        rows=[
            {
                "run_id": run_id,
                "surface_id": "surface-usd-swaption-vol",
                "surface_point_id": "surface-usd-swaption-vol:3m:5y",
                "axis_1_name": "option_tenor",
                "axis_1_value": "3M",
                "axis_2_name": "underlying_tenor",
                "axis_2_value": "5Y",
                "value_name": "implied_volatility",
                "value": 0.21,
                "unit": "decimal",
                "risk_factor_id": "rf-girr-usd-swaption-3m-5y",
                "mapping_version": "surface-map-v1",
                "source_row_id": "surface-row-001",
            }
        ],
    )


def _request(
    *,
    schema_id: str,
    artifact_type: ArtifactType,
    component: FrtbComponent,
    hint: str,
    partitions: dict[str, str],
    rows: list[dict[str, object]],
) -> ArtifactWriteRequest:
    schema = artifact_schema_for(schema_id)
    return ArtifactWriteRequest(
        artifact_id_hint=hint,
        artifact_type=artifact_type,
        component=component,
        schema_id=schema.schema_id,
        chunks=(pa.Table.from_pylist(rows, schema=schema.arrow_schema),),
        partition_values=partitions,
        metadata={"fixture": "timeseries-shock-surface"},
    )


def _scenario_vector_request(
    *,
    run_id: str,
    scenario_vector_id: str,
    label: str,
) -> ArtifactWriteRequest:
    return _request(
        schema_id="common.scenario_vector_metadata.v1",
        artifact_type=ArtifactType.SCENARIO_VECTOR_METADATA,
        component=FrtbComponent.IMA,
        hint="ima-scenario-vector",
        partitions={
            "scenario_set_id": "scenario-set-250d",
            "scenario_vector_id": scenario_vector_id,
        },
        rows=[
            {
                "run_id": run_id,
                "scenario_set_id": "scenario-set-250d",
                "scenario_vector_id": scenario_vector_id,
                "scenario_id": "scenario-2026-06-01",
                "observation_date": date(2026, 6, 1),
                "scenario_label": label,
                "mapping_version": "scenario-map-v1",
                "source_row_id": f"{scenario_vector_id}-row-001",
            }
        ],
    )
