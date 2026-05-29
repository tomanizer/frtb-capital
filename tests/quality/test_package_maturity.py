from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

import pytest

from scripts.ci import check_package_maturity as maturity


def test_valid_registry_loads_and_all_profiles_pass(tmp_path: Path, monkeypatch) -> None:
    entries = [
        _make_package(
            tmp_path,
            package="qc-implemented",
            import_name="qc_implemented",
            profile="implemented",
            implementation="IMPLEMENTED",
            validation="AVAILABLE",
            required_tests=("public-api",),
        ),
        _make_package(
            tmp_path,
            package="qc-partial",
            import_name="qc_partial",
            profile="partial_runtime",
            implementation="PARTIAL",
            validation="PENDING",
            required_tests=("public-api", "unsupported-runtime-paths"),
        ),
        _make_package(
            tmp_path,
            package="qc-scaffold",
            import_name="qc_scaffold",
            profile="scaffolded",
            implementation="SCAFFOLDED",
            validation="NOT_STARTED",
            required_tests=("scaffold-boundary",),
        ),
        _make_package(
            tmp_path,
            package="qc-orchestration",
            import_name="qc_orchestration",
            profile="orchestration_partial",
            implementation="PARTIAL",
            validation="PENDING",
            required_tests=("orchestration-boundary",),
            component_type="orchestration",
        ),
        _make_package(
            tmp_path,
            package="qc-common",
            import_name="qc_common",
            profile="shared",
            implementation=None,
            validation=None,
            required_tests=("regulatory-helpers",),
            component_type="shared",
        ),
    ]
    _write_registry(tmp_path, entries)
    monkeypatch.syspath_prepend(str(tmp_path))

    registry = maturity.load_registry(root=tmp_path)
    results = maturity.check_registry(registry, root=tmp_path)

    assert [entry.package for entry in registry.packages] == [
        "qc-implemented",
        "qc-partial",
        "qc-scaffold",
        "qc-orchestration",
        "qc-common",
    ]
    assert all(result.passed for result in results)


def test_duplicate_package_entries_fail_registry_validation(tmp_path: Path, monkeypatch) -> None:
    entry = _make_package(
        tmp_path,
        package="qc-duplicate",
        import_name="qc_duplicate",
        profile="shared",
        implementation=None,
        validation=None,
        required_tests=("regulatory-helpers",),
        component_type="shared",
    )
    _write_registry(tmp_path, [entry, entry])
    monkeypatch.syspath_prepend(str(tmp_path))

    results = maturity.check_registry(maturity.load_registry(root=tmp_path), root=tmp_path)

    assert all("unique-package-names" in result.failed_requirement_ids for result in results)


def test_duplicate_import_names_fail_registry_validation(tmp_path: Path, monkeypatch) -> None:
    first = _make_package(
        tmp_path,
        package="qc-first",
        import_name="qc_same_import",
        profile="shared",
        implementation=None,
        validation=None,
        required_tests=("regulatory-helpers",),
        component_type="shared",
    )
    second = _make_package(
        tmp_path,
        package="qc-second",
        import_name="qc_same_import",
        profile="shared",
        implementation=None,
        validation=None,
        required_tests=("regulatory-helpers",),
        component_type="shared",
    )
    _write_registry(tmp_path, [first, second])
    monkeypatch.syspath_prepend(str(tmp_path))

    results = maturity.check_registry(maturity.load_registry(root=tmp_path), root=tmp_path)

    assert any("unique-import-names" in result.failed_requirement_ids for result in results)


def test_unknown_maturity_profile_fails(tmp_path: Path, monkeypatch) -> None:
    entry = _make_package(
        tmp_path,
        package="qc-unknown-profile",
        import_name="qc_unknown_profile",
        profile="shared",
        implementation=None,
        validation=None,
        required_tests=("regulatory-helpers",),
        component_type="shared",
    ).replace('maturity = "shared"', 'maturity = "future"')
    _write_registry(tmp_path, [entry])
    monkeypatch.syspath_prepend(str(tmp_path))

    result = _single_result(tmp_path)

    assert "known-maturity-profile" in result.failed_requirement_ids


def test_missing_package_path_fails(tmp_path: Path, monkeypatch) -> None:
    entry = _make_package(
        tmp_path,
        package="qc-missing-path",
        import_name="qc_missing_path",
        profile="shared",
        implementation=None,
        validation=None,
        required_tests=("regulatory-helpers",),
        component_type="shared",
    ).replace('path = "packages/qc-missing-path"', 'path = "packages/not-present"')
    _write_registry(tmp_path, [entry])
    monkeypatch.syspath_prepend(str(tmp_path))

    result = _single_result(tmp_path)

    assert "package-path" in result.failed_requirement_ids
    assert "package-path-name" in result.failed_requirement_ids


def test_package_directory_omitted_from_registry_fails(tmp_path: Path, monkeypatch) -> None:
    entry = _make_package(
        tmp_path,
        package="qc-listed",
        import_name="qc_listed",
        profile="shared",
        implementation=None,
        validation=None,
        required_tests=("regulatory-helpers",),
        component_type="shared",
    )
    (tmp_path / "packages/qc-omitted").mkdir(parents=True)
    _write_registry(tmp_path, [entry])
    monkeypatch.syspath_prepend(str(tmp_path))

    result = _single_result(tmp_path)

    assert "package-directory-omitted:qc-omitted" in result.failed_requirement_ids


def test_missing_packages_directory_reports_registry_mismatch(
    tmp_path: Path,
    monkeypatch,
) -> None:
    _write_import_module(
        tmp_path,
        package="qc-no-packages",
        import_name="qc_no_packages",
        implementation=None,
        validation=None,
        with_metadata=False,
    )
    entry = _registry_entry(
        package="qc-no-packages",
        import_name="qc_no_packages",
        profile="shared",
        component_type="shared",
        required_tests=(),
    )
    _write_registry(tmp_path, [entry])
    monkeypatch.syspath_prepend(str(tmp_path))

    result = _single_result(tmp_path)

    assert "package-directory-extra" in result.failed_requirement_ids


def test_metadata_mismatch_fails(tmp_path: Path, monkeypatch) -> None:
    entry = _make_package(
        tmp_path,
        package="qc-metadata",
        import_name="qc_metadata",
        profile="implemented",
        implementation="IMPLEMENTED",
        validation="AVAILABLE",
        required_tests=("public-api",),
        metadata_package_name="wrong-package",
    )
    _write_registry(tmp_path, [entry])
    monkeypatch.syspath_prepend(str(tmp_path))

    result = _single_result(tmp_path)

    assert "metadata-package-name" in result.failed_requirement_ids


def test_required_test_ids_must_be_present_and_unique(tmp_path: Path, monkeypatch) -> None:
    entry = _make_package(
        tmp_path,
        package="qc-tests",
        import_name="qc_tests",
        profile="implemented",
        implementation="IMPLEMENTED",
        validation="AVAILABLE",
        required_tests=("public-api", "public-api"),
    )
    _write_registry(tmp_path, [entry])
    monkeypatch.syspath_prepend(str(tmp_path))

    result = _single_result(tmp_path)

    assert "required-tests-unique" in result.failed_requirement_ids


def test_missing_required_test_path_fails(tmp_path: Path, monkeypatch) -> None:
    entry = _make_package(
        tmp_path,
        package="qc-missing-test",
        import_name="qc_missing_test",
        profile="implemented",
        implementation="IMPLEMENTED",
        validation="AVAILABLE",
        required_tests=("public-api",),
        write_required_tests=False,
    )
    _write_registry(tmp_path, [entry])
    monkeypatch.syspath_prepend(str(tmp_path))

    result = _single_result(tmp_path)

    assert "required-test-path:public-api" in result.failed_requirement_ids


def test_requirement_registry_accepts_yaml_extension(tmp_path: Path, monkeypatch) -> None:
    entry = _make_package(
        tmp_path,
        package="qc-yaml",
        import_name="qc_yaml",
        profile="implemented",
        implementation="IMPLEMENTED",
        validation="AVAILABLE",
        required_tests=("public-api",),
        requirement_extension=".yaml",
    )
    _write_registry(tmp_path, [entry])
    monkeypatch.syspath_prepend(str(tmp_path))

    result = _single_result(tmp_path)

    assert result.passed


def test_unknown_package_selection_fails(tmp_path: Path, monkeypatch) -> None:
    entry = _make_package(
        tmp_path,
        package="qc-select",
        import_name="qc_select",
        profile="shared",
        implementation=None,
        validation=None,
        required_tests=("regulatory-helpers",),
        component_type="shared",
    )
    _write_registry(tmp_path, [entry])
    monkeypatch.syspath_prepend(str(tmp_path))

    with pytest.raises(ValueError, match="unknown package"):
        maturity.check_registry(
            maturity.load_registry(root=tmp_path),
            root=tmp_path,
            package="qc-absent",
        )


def test_json_output_includes_package_status_and_failed_requirement_ids(
    tmp_path: Path,
    monkeypatch,
) -> None:
    entry = _make_package(
        tmp_path,
        package="qc-json",
        import_name="qc_json",
        profile="shared",
        implementation=None,
        validation=None,
        required_tests=(),
        component_type="shared",
    )
    _write_registry(tmp_path, [entry])
    monkeypatch.syspath_prepend(str(tmp_path))

    results = maturity.check_registry(maturity.load_registry(root=tmp_path), root=tmp_path)
    report_path = tmp_path / "dist/quality/package-maturity.json"
    maturity.write_json_report(results, report_path)

    assert maturity.results_to_jsonable(results) == {
        "packages": [
            {
                "package": "qc-json",
                "passed": False,
                "failed_requirement_ids": ["required-test:regulatory-helpers"],
            }
        ]
    }
    assert '"package": "qc-json"' in report_path.read_text(encoding="utf-8")


def _single_result(tmp_path: Path) -> maturity.PackageCheckResult:
    results = maturity.check_registry(maturity.load_registry(root=tmp_path), root=tmp_path)
    assert len(results) == 1
    return results[0]


def _make_package(
    root: Path,
    *,
    package: str,
    import_name: str,
    profile: str,
    implementation: str | None,
    validation: str | None,
    required_tests: Iterable[str],
    component_type: str = "capital",
    metadata_package_name: str | None = None,
    write_required_tests: bool = True,
    requirement_extension: str = ".yml",
) -> str:
    package_dir = root / "packages" / package
    source_dir = package_dir / "src" / import_name
    source_dir.mkdir(parents=True)
    for filename in ("README.md", "CHANGELOG.md", "AGENTS.md"):
        (package_dir / filename).write_text(f"# {package}\n", encoding="utf-8")
    (source_dir / "__init__.py").write_text("", encoding="utf-8")

    module_docs = root / "docs/modules" / package
    module_docs.mkdir(parents=True)
    (module_docs / "README.md").write_text(f"# {package}\n", encoding="utf-8")

    tests_dir = package_dir / "tests"
    tests_dir.mkdir(parents=True)
    for test_id in required_tests:
        if write_required_tests:
            _test_path(package_dir, import_name, profile, test_id).write_text(
                "def test_placeholder():\n    assert True\n",
                encoding="utf-8",
            )

    if profile == "implemented":
        (package_dir / "docs").mkdir()
        (package_dir / "docs/REGULATORY_TRACEABILITY.md").write_text("trace\n", encoding="utf-8")
        (package_dir / "docs/REGULATORY_ASSUMPTIONS.md").write_text(
            "assumptions\n",
            encoding="utf-8",
        )
        (module_docs / "model_documentation").mkdir()
        (module_docs / "model_documentation/README.md").write_text("model\n", encoding="utf-8")
        (module_docs / "requirements").mkdir()
        (module_docs / f"requirements/BASEL_FRTB_TEST{requirement_extension}").write_text(
            "x\n",
            encoding="utf-8",
        )
    elif profile == "partial_runtime":
        for filename in (
            "ARCHITECTURE_AND_DATA_DESIGN.md",
            "DETAILED_REQUIREMENTS.md",
            "ISSUE_BREAKDOWN.md",
            "REGULATORY_REQUIREMENTS.md",
        ):
            (module_docs / filename).write_text("evidence\n", encoding="utf-8")
        (module_docs / "requirements").mkdir()
        (module_docs / "requirements/BASEL_FRTB_TEST.yml").write_text("x\n", encoding="utf-8")
    elif profile == "scaffolded":
        (module_docs / "PRD.md").write_text("prd\n", encoding="utf-8")
        (module_docs / "requirements").mkdir()
        (module_docs / "requirements/BASEL_FRTB_TEST.yml").write_text("x\n", encoding="utf-8")
    elif profile == "shared":
        (package_dir / "pyproject.toml").write_text(
            '[tool.setuptools.package-data]\nqc = ["py.typed"]\n',
            encoding="utf-8",
        )
        (source_dir / "py.typed").write_text("", encoding="utf-8")
        (source_dir / "regulatory").mkdir()
        (source_dir / "regulatory/policy_citations.py").write_text("", encoding="utf-8")

    _write_import_module(
        root,
        package=metadata_package_name or package,
        import_name=import_name,
        implementation=implementation,
        validation=validation,
        with_metadata=component_type != "shared",
    )
    return _registry_entry(
        package=package,
        import_name=import_name,
        profile=profile,
        component_type=component_type,
        required_tests=required_tests,
    )


def _test_path(package_dir: Path, import_name: str, profile: str, test_id: str) -> Path:
    if profile == "partial_runtime" and test_id in {"public-api", "unsupported-runtime-paths"}:
        return package_dir / "tests/test_drc_public_api.py"
    if profile == "orchestration_partial":
        return package_dir / "tests/test_orchestration_scaffold.py"
    if profile == "scaffolded":
        return package_dir / "tests" / f"test_{import_name.removeprefix('frtb_')}_scaffold.py"
    if profile == "implemented":
        return package_dir / "tests/test_public_api.py"
    return package_dir / "tests/test_regulatory_policy_citations.py"


def _write_import_module(
    root: Path,
    *,
    package: str,
    import_name: str,
    implementation: str | None,
    validation: str | None,
    with_metadata: bool,
) -> None:
    package_dir = root / import_name
    package_dir.mkdir(exist_ok=True)
    if with_metadata:
        body = f"""
from frtb_common import CapitalComponentMetadata, ImplementationStatus, ValidationStatus

PACKAGE_METADATA = CapitalComponentMetadata(
    package_name={package!r},
    import_name={import_name!r},
    component_name="quality fixture",
    implementation_status=ImplementationStatus.{implementation},
    validation_status=ValidationStatus.{validation},
)

def calculate_capital(*args, **kwargs):
    raise RuntimeError("entry point must not execute")
"""
    else:
        body = ""
    (package_dir / "__init__.py").write_text(body.lstrip(), encoding="utf-8")


def _registry_entry(
    *,
    package: str,
    import_name: str,
    profile: str,
    component_type: str,
    required_tests: Iterable[str],
) -> str:
    lines = [
        "[[packages]]",
        f'package = "{package}"',
        f'import_name = "{import_name}"',
        f'path = "packages/{package}"',
        f'module_docs = "docs/modules/{package}"',
        f'maturity = "{profile}"',
        f'component_type = "{component_type}"',
    ]
    if component_type != "shared":
        lines.extend(
            [
                f'metadata_object = "{import_name}:PACKAGE_METADATA"',
                f'calculation_entrypoint = "{import_name}:calculate_capital"',
            ]
        )
    for test_id in required_tests:
        required_test_path = _test_path(
            Path("packages") / package,
            import_name,
            profile,
            test_id,
        ).as_posix()
        lines.extend(
            [
                "",
                "[[packages.required_tests]]",
                f'id = "{test_id}"',
                f'path = "{required_test_path}"',
            ]
        )
    return "\n".join(lines) + "\n"


def _write_registry(root: Path, entries: Iterable[str]) -> None:
    registry = root / "docs/quality/package_maturity.toml"
    registry.parent.mkdir(parents=True, exist_ok=True)
    registry.write_text("schema_version = 1\n\n" + "\n".join(entries), encoding="utf-8")
