from __future__ import annotations

import json
from datetime import UTC, date, datetime
from pathlib import Path
from urllib.parse import quote

import pyarrow as pa
import pytest
from frtb_result_store import (
    ArtifactType,
    ArtifactWriteRequest,
    CalculationRun,
    CapitalEdge,
    CapitalMeasure,
    CapitalNode,
    DuckDbParquetResultStore,
    EdgeType,
    FrtbComponent,
    NodeType,
    ResultBundle,
    artifact_schema_for,
)
from frtb_result_store.cli import main as result_store_cli_main


def test_read_only_connection_rejects_catalog_writes(tmp_path: Path) -> None:
    store, run = _store_with_artifact(tmp_path, "run-read-only")

    connection = store.read_only_connection()
    try:
        assert connection.execute("SELECT COUNT(*) FROM frtb_result_store_runs").fetchone()[0] == 1
        assert (
            connection.execute("SELECT run_id FROM frtb_result_store_runs").fetchone()[0]
            == run.run_id
        )
        with pytest.raises(Exception, match="Cannot execute statement of type"):
            connection.execute("CREATE TABLE blocked_write(i INTEGER)")
    finally:
        connection.close()


def test_export_run_writes_manifest_parquet_artifacts_and_checksums(tmp_path: Path) -> None:
    store, run = _store_with_artifact(tmp_path, "run-export")

    result = store.export_run(run.run_id, tmp_path / "run-export")

    checksums = json.loads((result.output_path / "checksums.json").read_text(encoding="utf-8"))
    exported_files = set(checksums["files"])
    assert "run_manifest.json" in exported_files
    assert f"parquet/base/runs/{quote(run.run_id, safe='')}.parquet" in exported_files
    assert any(path.startswith("parquet/base/run_status_events/") for path in exported_files)
    assert f"parquet/marts/capital_summary/{quote(run.run_id, safe='')}.parquet" in exported_files
    assert any(path.startswith("parquet/artifacts/") for path in exported_files)
    assert (result.output_path / "checksums.json").exists()
    assert "checksums.json" not in exported_files
    assert not (result.output_path / "catalog.duckdb").exists()
    assert all("catalog.duckdb" not in path for path in exported_files)


def test_admin_cli_inspects_lists_refreshes_exports_and_validates(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    store, run = _store_with_artifact(tmp_path, "run-cli")
    root = store.root

    assert result_store_cli_main(("inspect", str(root))) == 0
    inspect_payload = json.loads(capsys.readouterr().out)
    assert inspect_payload["run_count"] == 1
    assert inspect_payload["catalog_exists"] is True

    assert result_store_cli_main(("list-runs", str(root))) == 0
    runs_payload = json.loads(capsys.readouterr().out)
    assert runs_payload["runs"][0]["run_id"] == run.run_id
    assert runs_payload["runs"][0]["latest_status"] == "CANDIDATE"

    root.joinpath("catalog.duckdb").unlink()
    assert result_store_cli_main(("refresh-catalog", str(root))) == 0
    refresh_payload = json.loads(capsys.readouterr().out)
    assert refresh_payload["refreshed"] is True
    assert root.joinpath("catalog.duckdb").exists()

    export_path = tmp_path / "cli-export"
    assert result_store_cli_main(("export-run", str(root), run.run_id, str(export_path))) == 0
    export_payload = json.loads(capsys.readouterr().out)
    assert export_payload["run_id"] == run.run_id
    assert "run_manifest.json" in export_payload["checksums"]

    assert result_store_cli_main(("validate-store", str(root))) == 0
    validate_payload = json.loads(capsys.readouterr().out)
    assert validate_payload["ok"] is True

    store._mart_path("capital_summary", run.run_id).unlink()
    assert result_store_cli_main(("validate-store", str(root))) == 1
    invalid_payload = json.loads(capsys.readouterr().out)
    assert invalid_payload["ok"] is False
    assert invalid_payload["errors"] == [f"missing mart parquet for {run.run_id}: capital_summary"]


def _store_with_artifact(
    tmp_path: Path,
    run_id: str,
) -> tuple[DuckDbParquetResultStore, CalculationRun]:
    run = _run(run_id)
    schema = artifact_schema_for("ima.pnl_vector.v1")
    request = ArtifactWriteRequest(
        artifact_id_hint="ima-desk-a-pnl",
        artifact_type=ArtifactType.IMA_PNL_VECTOR,
        component=FrtbComponent.IMA,
        schema_id=schema.schema_id,
        chunks=(_ima_pnl_table(schema.arrow_schema, run.run_id),),
        partition_values={
            "desk_id": "rates",
            "portfolio_id": "rates-options",
            "book_id": "rates-core",
        },
        metadata={"source": "admin-test"},
    )
    store = DuckDbParquetResultStore(tmp_path / "result-store")
    store.write_bundle(_bundle(run), artifact_requests=(request,))
    return store, run


def _run(run_id: str) -> CalculationRun:
    return CalculationRun.from_identity(
        as_of_date=date(2026, 6, 3),
        regime_id="US_NPR_2_0",
        base_currency="USD",
        input_snapshot_id=f"snapshot-{run_id}",
        calculation_scope="FIRM",
        engine_version="engine-v1",
        code_version="code-v1",
        calculation_policy_id="policy-us-npr",
        created_at=datetime(2026, 6, 3, 12, 0, tzinfo=UTC),
    )


def _bundle(run: CalculationRun) -> ResultBundle:
    return ResultBundle(
        run=run,
        nodes=(
            CapitalNode(
                run_id=run.run_id,
                node_id="total",
                node_type=NodeType.ROOT,
                component=FrtbComponent.TOP_OF_HOUSE,
                label="Total capital",
                sort_key=0,
            ),
            CapitalNode(
                run_id=run.run_id,
                node_id="ima",
                node_type=NodeType.DESK,
                component=FrtbComponent.IMA,
                label="IMA desk",
                desk_id="rates",
                sort_key=1,
            ),
        ),
        edges=(
            CapitalEdge(
                run_id=run.run_id,
                parent_node_id="total",
                child_node_id="ima",
                edge_type=EdgeType.AGGREGATES,
                sort_key=1,
            ),
        ),
        measures=(
            CapitalMeasure(
                run_id=run.run_id,
                node_id="total",
                measure_name="capital",
                amount=42.0,
                currency="USD",
            ),
            CapitalMeasure(
                run_id=run.run_id,
                node_id="ima",
                measure_name="capital",
                amount=17.0,
                currency="USD",
            ),
        ),
    )


def _ima_pnl_table(schema: pa.Schema, run_id: str) -> pa.Table:
    return pa.table(
        {
            "run_id": [run_id],
            "desk_id": ["rates"],
            "portfolio_id": ["rates-options"],
            "book_id": ["rates-core"],
            "position_id": ["pos-1"],
            "risk_factor_id": ["rf-1"],
            "risk_factor_set_id": [None],
            "scenario_id": ["scenario-1"],
            "observation_date": [date(2026, 6, 1)],
            "liquidity_horizon": [10],
            "pnl_amount": [1.25],
            "currency": ["USD"],
            "tail_flag": [False],
            "source_row_id": ["row-1"],
        },
        schema=schema,
    )
