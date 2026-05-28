"""Tests for fixture audit replay."""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

from frtb_ima.replay import main, replay_audit_file
from scripts.render_audit_report import _audit_log_from_fixture
from tests.capital_run_fixture_workflow import FIXTURE_ROOT


def test_replay_capital_run_fixture_succeeds(tmp_path: Path) -> None:
    audit_path = _write_audit_ndjson(tmp_path)

    report = replay_audit_file(audit_path, FIXTURE_ROOT)

    assert report["status"] == "PASSED"
    assert report["desk_count"] == 1
    assert report["mismatches"] == []


def test_replay_reports_expected_hash_mismatch(tmp_path: Path) -> None:
    audit_path = _write_audit_ndjson(tmp_path)

    report = replay_audit_file(audit_path, FIXTURE_ROOT, expected_inputs_hash="0" * 64)

    assert report["status"] == "FAILED"
    assert _mismatch_names(report) == {"expected_inputs_hash"}


def test_replay_reports_missing_input_artifact(tmp_path: Path) -> None:
    audit_path = _write_audit_ndjson(tmp_path)
    fixture_copy = tmp_path / "capital_run_v1_missing"
    shutil.copytree(FIXTURE_ROOT, fixture_copy)
    (fixture_copy / "scenario_cube.npz").unlink()

    report = replay_audit_file(audit_path, fixture_copy)

    assert report["status"] == "FAILED"
    mismatch = _mismatches(report)[0]
    assert mismatch["name"] == "replay_setup"
    assert mismatch["error_type"] == "FileNotFoundError"


def test_replay_reports_numeric_mismatch(tmp_path: Path) -> None:
    audit_path = _write_audit_ndjson(tmp_path)
    record = json.loads(audit_path.read_text(encoding="utf-8"))
    record["capital"]["models_based_capital"] += 1.0
    audit_path.write_text(json.dumps(record, sort_keys=True) + "\n", encoding="utf-8")

    report = replay_audit_file(audit_path, FIXTURE_ROOT)

    assert report["status"] == "FAILED"
    assert _mismatch_names(report) == {"record[0].capital.models_based_capital"}


def test_replay_reports_missing_audit_field_without_crashing(tmp_path: Path) -> None:
    audit_path = _write_audit_ndjson(tmp_path)
    record = json.loads(audit_path.read_text(encoding="utf-8"))
    del record["capital"]["binding_term"]
    audit_path.write_text(json.dumps(record, sort_keys=True) + "\n", encoding="utf-8")

    report = replay_audit_file(audit_path, FIXTURE_ROOT)

    assert report["status"] == "FAILED"
    assert _mismatch_names(report) == {"record[0].capital.binding_term"}


def test_replay_cli_writes_json_report(tmp_path: Path, capsys: Any) -> None:
    audit_path = _write_audit_ndjson(tmp_path)
    report_path = tmp_path / "replay-report.json"

    exit_code = main(
        [
            "--audit",
            str(audit_path),
            "--fixture",
            str(FIXTURE_ROOT),
            "--json-output",
            str(report_path),
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "Replay PASSED" in captured.err
    assert json.loads(captured.out)["status"] == "PASSED"
    assert json.loads(report_path.read_text(encoding="utf-8"))["status"] == "PASSED"


def _write_audit_ndjson(tmp_path: Path) -> Path:
    path = tmp_path / "capital_run_v1_desk_records.ndjson"
    path.write_text(_audit_log_from_fixture(FIXTURE_ROOT).to_ndjson() + "\n", encoding="utf-8")
    return path


def _mismatches(report: dict[str, object]) -> list[dict[str, object]]:
    mismatches = report["mismatches"]
    assert isinstance(mismatches, list)
    return [item for item in mismatches if isinstance(item, dict)]


def _mismatch_names(report: dict[str, object]) -> set[str]:
    return {str(item["name"]) for item in _mismatches(report)}
