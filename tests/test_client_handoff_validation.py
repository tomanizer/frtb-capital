from __future__ import annotations

import json
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

from scripts.validate_client_handoff import main as validate_handoff_main


def test_validate_client_handoff_accepts_drc_nonsec_fixture(tmp_path: Path) -> None:
    input_path = (
        _repo_root()
        / "packages/frtb-drc/tests/fixtures/handoff/drc_nonsec_minimal.parquet"
    )
    first_output = tmp_path / "first"
    second_output = tmp_path / "second"

    assert _run_cli("frtb_drc", "nonsec", input_path, first_output) == 0
    assert _run_cli("frtb_drc", "nonsec", input_path, second_output) == 0

    first_summary = _json(first_output / "summary.json")
    second_summary = _json(second_output / "summary.json")
    assert first_summary["accepted_rows"] == 1
    assert first_summary["rejected_rows"] == 0
    assert first_summary["batch_built"] is True
    assert first_summary["source_hash"] == second_summary["source_hash"]
    assert first_summary["handoff_hash"] == second_summary["handoff_hash"]
    assert pq.read_table(first_output / "accepted.parquet").num_rows == 1
    assert _json(first_output / "diagnostics.json") == []


def test_validate_client_handoff_accepts_rrao_inline_file(tmp_path: Path) -> None:
    input_path = tmp_path / "rrao.parquet"
    pq.write_table(_rrao_table(), input_path)
    output_dir = tmp_path / "out"

    assert _run_cli("frtb_rrao", "positions", input_path, output_dir) == 0

    summary = _json(output_dir / "summary.json")
    assert summary["package"] == "frtb_rrao"
    assert summary["handoff_id"] == "positions"
    assert summary["accepted_rows"] == 1
    assert summary["rejected_rows"] == 0


def test_validate_client_handoff_rejects_missing_required_column(tmp_path: Path) -> None:
    bad_input = tmp_path / "bad.parquet"
    pq.write_table(pa.table({"source_row_id": ["row-1"]}), bad_input)
    output_dir = tmp_path / "bad-out"

    assert _run_cli("frtb_drc", "nonsec", bad_input, output_dir) == 1

    diagnostics = _json(output_dir / "diagnostics.json")
    assert diagnostics == [
        {
            "code": "HANDOFF_NORMALIZATION_ERROR",
            "column_name": None,
            "message": "Required column 'position_id' is missing",
            "row_id": None,
            "severity": "error",
        }
    ]
    summary = _json(output_dir / "summary.json")
    assert summary["accepted_rows"] == 0
    assert summary["rejected_rows"] == 1
    assert (output_dir / "rejected.parquet").exists()


def _run_cli(package: str, handoff: str, input_path: Path, output_dir: Path) -> int:
    return validate_handoff_main(
        (
            "--package",
            package,
            "--handoff",
            handoff,
            "--input",
            str(input_path),
            "--output-dir",
            str(output_dir),
        )
    )


def _rrao_table() -> pa.Table:
    return pa.table(
        {
            "position_id": ["rrao-1"],
            "source_row_id": ["row-rrao-1"],
            "desk_id": ["exotics"],
            "legal_entity": ["bank-na"],
            "gross_effective_notional": pa.array([125.0], type=pa.float64()),
            "currency": ["USD"],
            "evidence_type": ["EXOTIC_UNDERLYING"],
            "evidence_label": ["single exotic underlying"],
            "classification_hint": ["EXOTIC"],
            "notional_source": ["client-feed"],
            "lineage_source_system": ["synthetic"],
            "lineage_source_file": ["rrao.csv"],
            "lineage_source_row_id": ["row-rrao-1"],
        }
    )


def _json(path: Path) -> object:
    return json.loads(path.read_text())


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]
