from __future__ import annotations

import json
from pathlib import Path

from scripts.ci import check_module_coverage as coverage


def test_implemented_coverage_targets_come_from_registry(tmp_path: Path) -> None:
    _write_registry(
        tmp_path,
        [
            ("frtb-alpha", "frtb_alpha", "implemented"),
            ("frtb-beta", "frtb_beta", "scaffolded"),
        ],
    )

    targets = coverage.implemented_coverage_targets(root=tmp_path)

    assert targets == (
        coverage.CoverageTarget(
            package="frtb-alpha",
            import_name="frtb_alpha",
            source_root=tmp_path / "packages/frtb-alpha/src/frtb_alpha",
        ),
    )


def test_coverage_check_enforces_floor_for_all_implemented_packages(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    monkeypatch.chdir(tmp_path)
    _write_source(tmp_path, "frtb-alpha", "frtb_alpha", ["__init__.py", "calc.py"])
    _write_source(tmp_path, "frtb-beta", "frtb_beta", ["__init__.py", "calc.py"])
    _write_registry(
        tmp_path,
        [
            ("frtb-alpha", "frtb_alpha", "implemented"),
            ("frtb-beta", "frtb_beta", "implemented"),
        ],
    )
    coverage_json = tmp_path / "coverage.json"
    coverage_json.write_text(
        json.dumps(
            {
                "files": {
                    "packages/frtb-alpha/src/frtb_alpha/__init__.py": {
                        "summary": {"percent_covered": 100.0}
                    },
                    "packages/frtb-alpha/src/frtb_alpha/calc.py": {
                        "summary": {"percent_covered": 95.0}
                    },
                    "packages/frtb-beta/src/frtb_beta/__init__.py": {
                        "summary": {"percent_covered": 100.0}
                    },
                    "packages/frtb-beta/src/frtb_beta/calc.py": {
                        "summary": {"percent_covered": 89.9}
                    },
                }
            }
        ),
        encoding="utf-8",
    )

    exit_code = coverage.main([str(coverage_json), "--floor", "90"])

    assert exit_code == 1
    assert "packages/frtb-beta/src/frtb_beta/calc.py: 89.90%" in capsys.readouterr().out


def test_coverage_check_reports_missing_entries(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.chdir(tmp_path)
    _write_source(tmp_path, "frtb-alpha", "frtb_alpha", ["__init__.py", "calc.py"])
    _write_registry(tmp_path, [("frtb-alpha", "frtb_alpha", "implemented")])
    coverage_json = tmp_path / "coverage.json"
    coverage_json.write_text(
        json.dumps(
            {
                "files": {
                    "packages/frtb-alpha/src/frtb_alpha/__init__.py": {
                        "summary": {"percent_covered": 100.0}
                    },
                }
            }
        ),
        encoding="utf-8",
    )

    exit_code = coverage.main([str(coverage_json)])

    assert exit_code == 1
    assert "Missing coverage entries:" in capsys.readouterr().out


def _write_source(root: Path, package: str, import_name: str, files: list[str]) -> None:
    source_root = root / "packages" / package / "src" / import_name
    source_root.mkdir(parents=True)
    for file_name in files:
        (source_root / file_name).write_text("", encoding="utf-8")


def _write_registry(root: Path, packages: list[tuple[str, str, str]]) -> None:
    registry = root / "docs/quality/package_maturity.toml"
    registry.parent.mkdir(parents=True)
    entries = [
        "\n".join(
            [
                "[[packages]]",
                f'package = "{package}"',
                f'import_name = "{import_name}"',
                f'path = "packages/{package}"',
                f'module_docs = "docs/modules/{package}"',
                f'maturity = "{maturity}"',
                'component_type = "capital"',
                "",
            ]
        )
        for package, import_name, maturity in packages
    ]
    registry.write_text("schema_version = 1\n\n" + "\n".join(entries), encoding="utf-8")
