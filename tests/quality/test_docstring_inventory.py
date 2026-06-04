from __future__ import annotations

import json
from pathlib import Path

from scripts.ci import check_docstring_baseline as baseline
from scripts.ci import check_docstring_inventory as inventory


def _write(repo_root: Path, relative_path: str, source: str) -> None:
    path = repo_root / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(source, encoding="utf-8")


def _base_package(repo_root: Path) -> None:
    _write(
        repo_root,
        "packages/frtb-demo/src/frtb_demo/__init__.py",
        '"""Demo package."""\n',
    )


def test_docstring_inventory_reports_module_and_public_object_gaps(tmp_path: Path) -> None:
    _base_package(tmp_path)
    _write(
        tmp_path,
        "packages/frtb-demo/src/frtb_demo/capital.py",
        "\n".join(
            [
                "def calculate_capital(value):",
                "    return value",
                "",
                "def _private_helper(value):",
                "    return value",
                "",
                "class CapitalResult:",
                "    def describe(self):",
                "        return 'capital'",
                "",
            ]
        ),
    )

    findings = inventory.scan_repo(tmp_path)

    assert [(finding.rule, finding.object_type, finding.object_name) for finding in findings] == [
        ("MISSING_MODULE_DOCSTRING", "module", "frtb_demo.capital"),
        ("MISSING_PUBLIC_DOCSTRING", "function", "calculate_capital"),
        ("MISSING_PUBLIC_DOCSTRING", "class", "CapitalResult"),
        ("MISSING_PUBLIC_DOCSTRING", "method", "CapitalResult.describe"),
    ]


def test_docstring_inventory_treats_exported_private_names_as_public(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "packages/frtb-demo/src/frtb_demo/__init__.py",
        "\n".join(
            [
                '"""Demo package."""',
                "from frtb_demo.private_api import _exported_private",
                "",
                "__all__ = ['_exported_private']",
                "",
            ]
        ),
    )
    _write(
        tmp_path,
        "packages/frtb-demo/src/frtb_demo/private_api.py",
        "\n".join(
            [
                '"""Private implementation exposed as a package API."""',
                "",
                "def _exported_private(value):",
                "    return value",
                "",
            ]
        ),
    )

    findings = inventory.scan_repo(tmp_path)

    assert [(finding.rule, finding.object_name) for finding in findings] == [
        ("MISSING_PUBLIC_DOCSTRING", "_exported_private")
    ]


def test_docstring_inventory_does_not_treat_private_init_imports_as_public(
    tmp_path: Path,
) -> None:
    _write(
        tmp_path,
        "packages/frtb-demo/src/frtb_demo/__init__.py",
        "\n".join(
            [
                '"""Demo package."""',
                "from frtb_demo.private_api import _internal_helper",
                "",
            ]
        ),
    )
    _write(
        tmp_path,
        "packages/frtb-demo/src/frtb_demo/private_api.py",
        "\n".join(
            [
                '"""Private implementation details."""',
                "",
                "def _internal_helper(value):",
                "    return value",
                "",
            ]
        ),
    )

    assert inventory.scan_repo(tmp_path) == ()


def test_docstring_inventory_treats_maturity_entrypoints_as_public(tmp_path: Path) -> None:
    _base_package(tmp_path)
    _write(
        tmp_path,
        "docs/quality/package_maturity.toml",
        "\n".join(
            [
                "schema_version = 1",
                "",
                "[[packages]]",
                'package = "frtb-demo"',
                'import_name = "frtb_demo"',
                'path = "packages/frtb-demo"',
                'module_docs = "docs/modules/frtb-demo"',
                'maturity = "partial_runtime"',
                'component_type = "capital"',
                'calculation_entrypoint = "frtb_demo:_registry_entrypoint"',
                "",
            ]
        ),
    )
    _write(
        tmp_path,
        "packages/frtb-demo/src/frtb_demo/entrypoints.py",
        "\n".join(
            [
                '"""Registry entrypoints."""',
                "",
                "def _registry_entrypoint():",
                "    return 1",
                "",
            ]
        ),
    )

    findings = inventory.scan_repo(tmp_path)

    assert [(finding.rule, finding.object_name) for finding in findings] == [
        ("MISSING_PUBLIC_DOCSTRING", "_registry_entrypoint")
    ]


def test_docstring_inventory_reports_missing_numpy_sections(tmp_path: Path) -> None:
    _base_package(tmp_path)
    _write(
        tmp_path,
        "packages/frtb-demo/src/frtb_demo/sections.py",
        "\n".join(
            [
                '"""Section examples."""',
                "",
                "def calculate_bucket_capital(value: float) -> float:",
                '    """Aggregate weighted sensitivities into one bucket result."""',
                "    return value",
                "",
                "class Calculator:",
                '    """Capital calculator."""',
                "",
                "    def total(self) -> float:",
                '        """Return the current total."""',
                "        return 1.0",
                "",
            ]
        ),
    )

    findings = inventory.scan_repo(tmp_path)

    assert [(finding.rule, finding.object_name) for finding in findings] == [
        ("MISSING_PARAMETERS_SECTION", "calculate_bucket_capital"),
        ("MISSING_RETURNS_SECTION", "calculate_bucket_capital"),
        ("MISSING_RETURNS_SECTION", "Calculator.total"),
    ]


def test_docstring_inventory_accepts_numpy_sections_and_private_helpers(tmp_path: Path) -> None:
    _base_package(tmp_path)
    _write(
        tmp_path,
        "packages/frtb-demo/src/frtb_demo/complete.py",
        "\n".join(
            [
                '"""Complete docstring examples."""',
                "",
                "def calculate_bucket_capital(value: float) -> float:",
                '    """Aggregate weighted sensitivities into one bucket result.',
                "",
                "    Parameters",
                "    ----------",
                "    value : float",
                "        Weighted sensitivity total.",
                "",
                "    Returns",
                "    -------",
                "    float",
                "        Bucket capital.",
                '    """',
                "    return value",
                "",
                "def _private_helper(value):",
                "    return value",
                "",
            ]
        ),
    )

    assert inventory.scan_repo(tmp_path) == ()


def test_docstring_inventory_accepts_yields_section_for_generators(tmp_path: Path) -> None:
    _base_package(tmp_path)
    _write(
        tmp_path,
        "packages/frtb-demo/src/frtb_demo/generators.py",
        "\n".join(
            [
                '"""Generator docstring examples."""',
                "",
                "def iter_capital_values(values) -> Iterator[float]:",
                '    """Yield capital values from the supplied sequence.',
                "",
                "    Parameters",
                "    ----------",
                "    values : Sequence[float]",
                "        Capital values to expose.",
                "",
                "    Yields",
                "    ------",
                "    float",
                "        One capital value at a time.",
                '    """',
                "    yield from values",
                "",
            ]
        ),
    )

    assert inventory.scan_repo(tmp_path) == ()


def test_docstring_inventory_reports_trivial_docstrings(tmp_path: Path) -> None:
    _base_package(tmp_path)
    _write(
        tmp_path,
        "packages/frtb-demo/src/frtb_demo/trivial.py",
        "\n".join(
            [
                '"""Trivial docstring examples."""',
                "",
                "def calculate_capital() -> float:",
                '    """Calculate capital."""',
                "    return 1.0",
                "",
            ]
        ),
    )

    findings = inventory.scan_repo(tmp_path)

    assert sorted((finding.rule, finding.object_name) for finding in findings) == [
        ("MISSING_RETURNS_SECTION", "calculate_capital"),
        ("TRIVIAL_DOCSTRING", "calculate_capital"),
    ]


def test_docstring_inventory_main_report_mode_writes_json_without_failing(
    tmp_path: Path,
    capsys,
) -> None:
    _base_package(tmp_path)
    _write(
        tmp_path,
        "packages/frtb-demo/src/frtb_demo/missing.py",
        "def public_function():\n    pass\n",
    )
    report_path = tmp_path / "dist" / "docstrings.json"

    exit_code = inventory.main(
        [
            "--root",
            str(tmp_path),
            "--json-output",
            str(report_path),
        ]
    )

    assert exit_code == 0
    assert "docstring inventory:" in capsys.readouterr().out
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["schema_version"] == 1
    assert report["packages"]["frtb-demo"]["finding_count"] == 2


def test_docstring_inventory_fail_on_findings_returns_nonzero(tmp_path: Path) -> None:
    _base_package(tmp_path)
    _write(
        tmp_path,
        "packages/frtb-demo/src/frtb_demo/missing.py",
        "def public_function():\n    pass\n",
    )

    assert inventory.main(["--root", str(tmp_path), "--quiet", "--fail-on-findings"]) == 1


def test_docstring_baseline_blocks_new_missing_public_docstrings(
    tmp_path: Path,
    capsys,
) -> None:
    _base_package(tmp_path)
    baseline_path = tmp_path / "docs" / "quality" / "docstrings" / "baseline.json"
    _write(
        tmp_path,
        "packages/frtb-demo/src/frtb_demo/complete.py",
        "\n".join(
            [
                '"""Complete module."""',
                "",
                "def calculate_capital():",
                '    """Calculate capital from documented inputs."""',
                "    return None",
                "",
            ]
        ),
    )
    assert (
        baseline.main(
            [
                "--root",
                str(tmp_path),
                "--baseline",
                str(baseline_path),
                "--update-baseline",
                "--quiet",
            ]
        )
        == 0
    )

    _write(
        tmp_path,
        "packages/frtb-demo/src/frtb_demo/new_gap.py",
        "\n".join(
            [
                '"""New module with an undocumented public API."""',
                "",
                "def calculate_gap():",
                "    return None",
                "",
            ]
        ),
    )

    assert (
        baseline.main(
            [
                "--root",
                str(tmp_path),
                "--baseline",
                str(baseline_path),
                "--quiet",
            ]
        )
        == 1
    )
    assert "new hard-gated docstring gap" in capsys.readouterr().err


def test_docstring_baseline_keeps_numpy_sections_report_only(
    tmp_path: Path,
) -> None:
    _base_package(tmp_path)
    baseline_path = tmp_path / "docs" / "quality" / "docstrings" / "baseline.json"
    _write(
        tmp_path,
        "packages/frtb-demo/src/frtb_demo/sections.py",
        "\n".join(
            [
                '"""Section module."""',
                "",
                "def calculate_capital():",
                '    """Return a documented capital value.',
                "",
                "    Returns",
                "    -------",
                "    float",
                "        Capital value.",
                '    """',
                "    return 1.0",
                "",
            ]
        ),
    )
    assert (
        baseline.main(
            [
                "--root",
                str(tmp_path),
                "--baseline",
                str(baseline_path),
                "--update-baseline",
                "--quiet",
            ]
        )
        == 0
    )

    _write(
        tmp_path,
        "packages/frtb-demo/src/frtb_demo/sections.py",
        "\n".join(
            [
                '"""Section module."""',
                "",
                "def calculate_capital(value: float) -> float:",
                '    """Return a documented capital value."""',
                "    return value",
                "",
            ]
        ),
    )

    assert (
        baseline.main(
            [
                "--root",
                str(tmp_path),
                "--baseline",
                str(baseline_path),
                "--quiet",
            ]
        )
        == 0
    )


def test_docstring_baseline_blocks_stale_hard_gaps(
    tmp_path: Path,
    capsys,
) -> None:
    _base_package(tmp_path)
    baseline_path = tmp_path / "docs" / "quality" / "docstrings" / "baseline.json"
    _write(
        tmp_path,
        "packages/frtb-demo/src/frtb_demo/missing.py",
        "\n".join(
            [
                "def calculate_gap():",
                "    return None",
                "",
            ]
        ),
    )
    assert (
        baseline.main(
            [
                "--root",
                str(tmp_path),
                "--baseline",
                str(baseline_path),
                "--update-baseline",
                "--quiet",
            ]
        )
        == 0
    )

    _write(
        tmp_path,
        "packages/frtb-demo/src/frtb_demo/missing.py",
        "\n".join(
            [
                '"""Documented module."""',
                "",
                "def calculate_gap():",
                '    """Provide the documented gap calculation."""',
                "    return None",
                "",
            ]
        ),
    )

    assert (
        baseline.main(
            [
                "--root",
                str(tmp_path),
                "--baseline",
                str(baseline_path),
                "--quiet",
            ]
        )
        == 1
    )
    assert "stale hard-gated baseline entry" in capsys.readouterr().err


def test_docstring_baseline_reports_malformed_baseline(
    tmp_path: Path,
    capsys,
) -> None:
    _base_package(tmp_path)
    baseline_path = tmp_path / "docs" / "quality" / "docstrings" / "baseline.json"
    baseline_path.parent.mkdir(parents=True, exist_ok=True)
    baseline_path.write_text('{"schema_version": 1, "packages": []}', encoding="utf-8")

    assert (
        baseline.main(
            [
                "--root",
                str(tmp_path),
                "--baseline",
                str(baseline_path),
                "--quiet",
            ]
        )
        == 1
    )
    assert "baseline packages must be a JSON object" in capsys.readouterr().err
