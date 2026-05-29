from __future__ import annotations

import json
from pathlib import Path

from scripts.ci import check_mutation_score as mutation_score


def test_mutation_score_passes_at_killed_only_floor(tmp_path: Path) -> None:
    stats_path = _write_stats(tmp_path, killed=85, total=100)

    result = mutation_score.check_stats_file("frtb-example", stats_path, floor=85.0)

    assert result.passed
    assert result.score == 85.0
    assert result.failed_requirement_ids == ()


def test_mutation_score_compares_at_documented_percentage_precision(tmp_path: Path) -> None:
    stats_path = _write_stats(tmp_path, killed=1413, total=1881)

    result = mutation_score.check_stats_file("frtb-ima", stats_path, floor=75.12)

    assert result.passed
    assert round(result.score, 2) == 75.12


def test_mutation_score_fails_below_floor(tmp_path: Path) -> None:
    stats_path = _write_stats(tmp_path, killed=84, total=100)

    result = mutation_score.check_stats_file("frtb-example", stats_path, floor=85.0)

    assert not result.passed
    assert result.failed_requirement_ids == ("mutation-score-floor",)


def test_mutation_score_reports_missing_stats(tmp_path: Path) -> None:
    result = mutation_score.check_stats_file(
        "frtb-example",
        tmp_path / "missing.json",
        floor=85.0,
    )

    assert not result.passed
    assert result.failed_requirement_ids == ("mutation-stats-readable",)
    assert result.error is not None


def test_mutation_score_reports_non_mapping_stats(tmp_path: Path) -> None:
    stats_path = tmp_path / "mutmut-cicd-stats.json"
    stats_path.write_text("[]", encoding="utf-8")

    result = mutation_score.check_stats_file("frtb-example", stats_path, floor=85.0)

    assert not result.passed
    assert result.failed_requirement_ids == ("mutation-stats-readable",)
    assert result.error == "stats must be a dictionary"


def test_mutation_score_main_strips_package_mappings(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    stats_path = _write_stats(tmp_path, killed=9, total=10)

    exit_code = mutation_score.main(
        [
            "--stats",
            f" frtb-example = {stats_path} ",
            "--floor",
            " frtb-example = 90.0 ",
        ]
    )

    assert exit_code == 0


def test_mutation_score_main_writes_json_report(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    stats_path = _write_stats(tmp_path, killed=9, total=10)
    report_path = tmp_path / "mutation-score.json"

    exit_code = mutation_score.main(
        [
            "--stats",
            f"frtb-example={stats_path}",
            "--floor",
            "frtb-example=90.0",
            "--json-output",
            str(report_path),
        ]
    )

    assert exit_code == 0
    assert json.loads(report_path.read_text(encoding="utf-8")) == {
        "packages": [
            {
                "package": "frtb-example",
                "stats_path": str(stats_path),
                "killed": 9,
                "total": 10,
                "score": 90.0,
                "floor": 90.0,
                "passed": True,
                "failed_requirement_ids": [],
                "error": None,
            }
        ]
    }


def _write_stats(root: Path, *, killed: int, total: int) -> Path:
    stats_path = root / "mutmut-cicd-stats.json"
    stats_path.write_text(
        json.dumps(
            {
                "killed": killed,
                "survived": total - killed,
                "total": total,
                "no_tests": 0,
                "skipped": 0,
                "suspicious": 0,
                "timeout": 0,
                "check_was_interrupted_by_user": False,
                "segfault": 0,
            }
        ),
        encoding="utf-8",
    )
    return stats_path
