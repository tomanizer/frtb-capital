"""Validate package maturity registry entries and static evidence files."""

from __future__ import annotations

import argparse
import importlib
import json
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from frtb_common import ImplementationStatus, ValidationStatus

REGISTRY_PATH = Path("docs/quality/package_maturity.toml")
SUPPORTED_PROFILES = {
    "implemented",
    "partial_runtime",
    "scaffolded",
    "orchestration_partial",
    "orchestration_implemented",
    "result_store_partial",
    "shared",
}
SUPPORTED_COMPONENT_TYPES = {"capital", "orchestration", "result_store", "shared"}
ATTRIBUTION_COMPONENT_TYPES = {"capital", "orchestration"}
SUPPORTED_ATTRIBUTION_STATUSES = {
    "documentation_only",
    "allocation_only",
    "shared_projection",
    "full_bundle",
}
ATTRIBUTION_REQUIRED_TEST_IDS: dict[str, set[str]] = {
    "documentation_only": set(),
    "allocation_only": {"attribution", "attribution-reconciliation"},
    "shared_projection": {
        "attribution",
        "attribution-reconciliation",
        "attribution-unsupported-branches",
    },
    "full_bundle": {
        "attribution",
        "attribution-reconciliation",
        "attribution-unsupported-branches",
        "attribution-bundle",
    },
}

EXPECTED_IMPLEMENTATION_STATUS = {
    "implemented": ImplementationStatus.IMPLEMENTED,
    "partial_runtime": ImplementationStatus.PARTIAL,
    "scaffolded": ImplementationStatus.SCAFFOLDED,
    "orchestration_partial": ImplementationStatus.PARTIAL,
    "orchestration_implemented": ImplementationStatus.IMPLEMENTED,
    "result_store_partial": ImplementationStatus.PARTIAL,
}
EXPECTED_VALIDATION_STATUS = {
    "implemented": ValidationStatus.AVAILABLE,
    "partial_runtime": ValidationStatus.PENDING,
    "scaffolded": ValidationStatus.NOT_STARTED,
    "orchestration_partial": ValidationStatus.PENDING,
    "orchestration_implemented": ValidationStatus.PENDING,
    "result_store_partial": ValidationStatus.PENDING,
}
REQUIRED_TEST_IDS = {
    "implemented": {"public-api"},
    "partial_runtime": {"public-api", "unsupported-runtime-paths"},
    "scaffolded": {"scaffold-boundary"},
    "orchestration_partial": {"orchestration-boundary"},
    "orchestration_implemented": {"orchestration-boundary", "suite-capital-end-to-end"},
    "result_store_partial": {"public-api", "duckdb-parquet"},
    "shared": {"regulatory-helpers"},
}


@dataclass(frozen=True)
class RequiredTest:
    """Required package-local test evidence from the registry."""

    id: str
    path: Path


@dataclass(frozen=True)
class PackageEntry:
    """One maturity-registry package entry."""

    package: str
    import_name: str
    path: Path
    module_docs: Path
    maturity: str
    component_type: str
    metadata_object: str | None
    calculation_entrypoint: str | None
    attribution_status: str | None
    required_tests: tuple[RequiredTest, ...]
    notes: str | None = None

    def required_test_ids(self) -> set[str]:
        return {entry.id for entry in self.required_tests}


@dataclass(frozen=True)
class PackageCheckResult:
    """Static check result for one package entry."""

    package: str
    passed: bool
    failed_requirement_ids: tuple[str, ...]


@dataclass(frozen=True)
class Registry:
    """Loaded maturity registry."""

    schema_version: int
    packages: tuple[PackageEntry, ...]


def load_registry(registry_path: Path = REGISTRY_PATH, *, root: Path = Path.cwd()) -> Registry:
    """Load the TOML registry into typed entries without importing packages."""

    data = tomllib.loads((root / registry_path).read_text(encoding="utf-8"))
    schema_version = data.get("schema_version")
    if schema_version != 1:
        raise ValueError(f"{registry_path}: schema_version must be 1")
    raw_packages = data.get("packages")
    if not isinstance(raw_packages, list):
        raise ValueError(f"{registry_path}: missing packages list")

    packages: list[PackageEntry] = []
    for index, raw_package in enumerate(raw_packages, start=1):
        if not isinstance(raw_package, dict):
            raise ValueError(f"{registry_path}: package entry {index} must be a table")
        packages.append(_package_entry_from_raw(raw_package, registry_path, index))
    return Registry(schema_version=schema_version, packages=tuple(packages))


def check_registry(
    registry: Registry,
    *,
    root: Path = Path.cwd(),
    package: str | None = None,
) -> tuple[PackageCheckResult, ...]:
    """Run static registry and evidence checks."""

    selected_entries = _select_entries(registry, package)
    global_errors = _global_registry_errors(registry, root=root)
    results: list[PackageCheckResult] = []
    global_packages = {error_package for error_package, _ in global_errors}

    for entry in selected_entries:
        failed = [
            requirement_id for requirement_id in _entry_requirement_failures(entry, root=root)
        ]
        failed.extend(
            requirement_id
            for error_package, requirement_id in global_errors
            if error_package == entry.package
        )
        if "__registry__" in global_packages:
            failed.extend(
                requirement_id
                for error_package, requirement_id in global_errors
                if error_package == "__registry__"
            )
        results.append(
            PackageCheckResult(
                package=entry.package,
                passed=not failed,
                failed_requirement_ids=tuple(sorted(set(failed))),
            )
        )
    return tuple(results)


def write_json_report(results: tuple[PackageCheckResult, ...], path: Path) -> None:
    """Write deterministic package-level check evidence."""

    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "packages": [
            {
                "package": result.package,
                "passed": result.passed,
                "failed_requirement_ids": list(result.failed_requirement_ids),
            }
            for result in results
        ]
    }
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def results_to_jsonable(results: tuple[PackageCheckResult, ...]) -> dict[str, object]:
    """Return a deterministic JSON-ready result shape."""

    return {
        "packages": [
            {
                "package": result.package,
                "passed": result.passed,
                "failed_requirement_ids": list(result.failed_requirement_ids),
            }
            for result in results
        ]
    }


def _package_entry_from_raw(
    raw_package: dict[str, Any],
    registry_path: Path,
    index: int,
) -> PackageEntry:
    required_fields = [
        "package",
        "import_name",
        "path",
        "module_docs",
        "maturity",
        "component_type",
    ]
    missing = [field for field in required_fields if not isinstance(raw_package.get(field), str)]
    if missing:
        missing_text = ", ".join(missing)
        raise ValueError(
            f"{registry_path}: package entry {index} missing string fields: {missing_text}"
        )

    raw_tests = raw_package.get("required_tests", [])
    if raw_tests is None:
        raw_tests = []
    if not isinstance(raw_tests, list):
        raise ValueError(f"{registry_path}: package entry {index} required_tests must be a list")

    tests: list[RequiredTest] = []
    for test_index, raw_test in enumerate(raw_tests, start=1):
        if not isinstance(raw_test, dict):
            raise ValueError(
                f"{registry_path}: package entry {index} required_tests {test_index} "
                "must be a table"
            )
        test_id = raw_test.get("id")
        test_path = raw_test.get("path")
        if not isinstance(test_id, str) or not isinstance(test_path, str):
            raise ValueError(
                f"{registry_path}: package entry {index} required_tests {test_index} "
                "requires id and path"
            )
        tests.append(RequiredTest(id=test_id, path=Path(test_path)))

    return PackageEntry(
        package=str(raw_package["package"]),
        import_name=str(raw_package["import_name"]),
        path=Path(str(raw_package["path"])),
        module_docs=Path(str(raw_package["module_docs"])),
        maturity=str(raw_package["maturity"]),
        component_type=str(raw_package["component_type"]),
        metadata_object=_optional_string(
            raw_package.get("metadata_object"),
            registry_path=registry_path,
            index=index,
            field="metadata_object",
        ),
        calculation_entrypoint=_optional_string(
            raw_package.get("calculation_entrypoint"),
            registry_path=registry_path,
            index=index,
            field="calculation_entrypoint",
        ),
        attribution_status=_optional_string(
            raw_package.get("attribution_status"),
            registry_path=registry_path,
            index=index,
            field="attribution_status",
        ),
        required_tests=tuple(tests),
        notes=_optional_string(
            raw_package.get("notes"),
            registry_path=registry_path,
            index=index,
            field="notes",
        ),
    )


def _optional_string(
    value: object,
    *,
    registry_path: Path,
    index: int,
    field: str,
) -> str | None:
    if value is None:
        return None
    if isinstance(value, str) and value:
        return value
    raise ValueError(
        f"{registry_path}: package entry {index} optional field {field} must be a non-empty string"
    )


def _select_entries(registry: Registry, package: str | None) -> tuple[PackageEntry, ...]:
    if package is None:
        return registry.packages
    selected = tuple(entry for entry in registry.packages if entry.package == package)
    if not selected:
        raise ValueError(f"unknown package: {package}")
    return selected


def _global_registry_errors(registry: Registry, *, root: Path) -> list[tuple[str, str]]:
    errors: list[tuple[str, str]] = []
    package_names = [entry.package for entry in registry.packages]
    import_names = [entry.import_name for entry in registry.packages]

    errors.extend(_duplicate_errors(package_names, "unique-package-names"))
    errors.extend(_duplicate_errors(import_names, "unique-import-names"))

    packages_dir = root / "packages"
    package_dirs = (
        sorted(path.name for path in packages_dir.iterdir() if path.is_dir())
        if packages_dir.is_dir()
        else []
    )
    registry_packages = sorted(package_names)
    if registry_packages != package_dirs:
        missing = sorted(set(package_dirs).difference(registry_packages))
        extras = sorted(set(registry_packages).difference(package_dirs))
        for package in missing:
            errors.append(("__registry__", f"package-directory-omitted:{package}"))
        for package in extras:
            errors.append((package, "package-directory-extra"))

    for entry in registry.packages:
        if entry.package != entry.path.name:
            errors.append((entry.package, "package-path-name"))
    return errors


def _duplicate_errors(values: list[str], requirement_id: str) -> list[tuple[str, str]]:
    seen: set[str] = set()
    duplicates: set[str] = set()
    for value in values:
        if value in seen:
            duplicates.add(value)
        seen.add(value)
    if not duplicates:
        return []
    return [("__registry__", requirement_id)]


def _entry_requirement_failures(entry: PackageEntry, *, root: Path) -> list[str]:
    failures: list[str] = []
    failures.extend(_basic_registry_failures(entry, root=root))
    failures.extend(_metadata_failures(entry))
    failures.extend(_attribution_failures(entry, root=root))

    profile_checks = {
        "implemented": _implemented_failures,
        "partial_runtime": _partial_runtime_failures,
        "scaffolded": _scaffolded_failures,
        "orchestration_partial": _orchestration_partial_failures,
        "orchestration_implemented": _orchestration_implemented_failures,
        "result_store_partial": _result_store_partial_failures,
        "shared": _shared_failures,
    }
    check = profile_checks.get(entry.maturity)
    if check is None:
        failures.append("known-maturity-profile")
    else:
        failures.extend(check(entry, root=root))
    return failures


def _basic_registry_failures(entry: PackageEntry, *, root: Path) -> list[str]:
    failures: list[str] = []
    if entry.maturity not in SUPPORTED_PROFILES:
        failures.append("known-maturity-profile")
    if entry.component_type not in SUPPORTED_COMPONENT_TYPES:
        failures.append("known-component-type")
    if not (root / entry.path).exists():
        failures.append("package-path")
    if not (root / entry.module_docs).exists():
        failures.append("module-docs")
    if entry.component_type in {"capital", "orchestration", "result_store"}:
        if entry.metadata_object is None:
            failures.append("metadata-object")
    if entry.component_type in {"capital", "orchestration"}:
        if entry.calculation_entrypoint is None:
            failures.append("calculation-entrypoint")
    if entry.component_type == "result_store" and entry.calculation_entrypoint is not None:
        failures.append("result-store-no-calculation-entrypoint")
    if entry.component_type == "shared" and entry.metadata_object is not None:
        failures.append("shared-no-metadata-object")

    failures.extend(_required_test_failures(entry, root=root))
    if not _can_import_module(entry.import_name):
        failures.append("package-import")
    if entry.metadata_object and _import_path(entry.metadata_object) is None:
        failures.append("metadata-object-import")
    if entry.calculation_entrypoint and _import_path(entry.calculation_entrypoint) is None:
        failures.append("calculation-entrypoint-import")
    return failures


def _required_test_failures(entry: PackageEntry, *, root: Path) -> list[str]:
    failures: list[str] = []
    ids = [test.id for test in entry.required_tests]
    if len(ids) != len(set(ids)):
        failures.append("required-tests-unique")
    required_ids = REQUIRED_TEST_IDS.get(entry.maturity, set())
    for required_id in sorted(required_ids.difference(ids)):
        failures.append(f"required-test:{required_id}")
    for required_test in entry.required_tests:
        path = root / required_test.path
        expected_prefix = Path("packages") / entry.package / "tests"
        if not required_test.path.is_relative_to(expected_prefix):
            failures.append(f"required-test-package-local:{required_test.id}")
        if not required_test.path.name.startswith("test_") or required_test.path.suffix != ".py":
            failures.append(f"required-test-file-name:{required_test.id}")
        if not path.exists():
            failures.append(f"required-test-path:{required_test.id}")
    return failures


def _metadata_failures(entry: PackageEntry) -> list[str]:
    if entry.metadata_object is None:
        return []
    metadata = _import_path(entry.metadata_object)
    if metadata is None:
        return []
    failures: list[str] = []
    if getattr(metadata, "package_name", None) != entry.package:
        failures.append("metadata-package-name")
    if getattr(metadata, "import_name", None) != entry.import_name:
        failures.append("metadata-import-name")
    expected_implementation = EXPECTED_IMPLEMENTATION_STATUS.get(entry.maturity)
    if expected_implementation is not None:
        if getattr(metadata, "implementation_status", None) is not expected_implementation:
            failures.append("metadata-implementation-status")
    expected_validation = EXPECTED_VALIDATION_STATUS.get(entry.maturity)
    if expected_validation is not None:
        if getattr(metadata, "validation_status", None) is not expected_validation:
            failures.append("metadata-validation-status")
    return failures


def _attribution_failures(entry: PackageEntry, *, root: Path) -> list[str]:
    failures: list[str] = []
    if entry.component_type not in ATTRIBUTION_COMPONENT_TYPES:
        if entry.attribution_status is not None:
            failures.append("attribution-status-not-applicable")
        return failures

    if entry.attribution_status is None:
        return ["attribution-status"]
    if entry.attribution_status not in SUPPORTED_ATTRIBUTION_STATUSES:
        failures.append("known-attribution-status")
        return failures
    if not (root / entry.path / "ATTRIBUTION.md").exists():
        failures.append("attribution-doc")

    required_ids = ATTRIBUTION_REQUIRED_TEST_IDS[entry.attribution_status]
    entry_test_ids = entry.required_test_ids()
    for required_id in sorted(required_ids.difference(entry_test_ids)):
        failures.append(f"required-test:{required_id}")
    for required_test in entry.required_tests:
        if (
            required_test.id in required_ids
            and _looks_like_placeholder_test(root / required_test.path)
        ):
            failures.append(f"attribution-test-placeholder:{required_test.id}")
    return failures


def _looks_like_placeholder_test(path: Path) -> bool:
    try:
        text = path.read_text(encoding="utf-8").lower()
    except OSError:
        return False
    return "test_placeholder" in text or "assert true" in text or "placeholder" in text


def _implemented_failures(entry: PackageEntry, *, root: Path) -> list[str]:
    failures = _common_package_file_failures(entry, root=root)
    tests_dir = root / entry.path / "tests"
    if not tests_dir.is_dir():
        failures.append("tests-directory")
    if not list(tests_dir.glob("test_*public_api*.py")):
        failures.append("public-api-tests")
    if not _any_exists(
        root,
        entry.path / "docs/REGULATORY_TRACEABILITY.md",
        entry.module_docs / "REGULATORY_TRACEABILITY.md",
    ):
        failures.append("regulatory-traceability")
    if not _any_exists(
        root,
        entry.path / "docs/REGULATORY_ASSUMPTIONS.md",
        entry.module_docs / "REGULATORY_ASSUMPTIONS.md",
    ):
        failures.append("regulatory-assumptions")
    if not (root / entry.module_docs / "model_documentation/README.md").exists():
        failures.append("model-documentation-pack")
    failures.extend(_requirement_registry_failures(entry, root=root))
    failures.extend(_source_root_failures(entry, root=root))
    return failures


def _partial_runtime_failures(entry: PackageEntry, *, root: Path) -> list[str]:
    failures = _common_package_file_failures(entry, root=root)
    if not (root / entry.path / "tests").is_dir():
        failures.append("tests-directory")
    if not list((root / entry.path / "tests").glob("test_*public_api*.py")):
        failures.append("public-api-tests")
    if not (root / entry.module_docs / "ARCHITECTURE_AND_DATA_DESIGN.md").exists():
        failures.append("architecture-data-design")
    if not (root / entry.module_docs / "DETAILED_REQUIREMENTS.md").exists():
        failures.append("detailed-requirements")
    if not _any_exists(
        root,
        entry.module_docs / "ISSUE_BREAKDOWN.md",
        entry.module_docs / "DECISIONS_AND_PLAN.md",
    ):
        failures.append("issue-breakdown-or-decisions")
    if not _any_exists(
        root,
        entry.module_docs / "REGULATORY_REQUIREMENTS.md",
        entry.module_docs / "REGULATORY_TRACEABILITY.md",
    ):
        failures.append("regulatory-requirements-or-traceability")
    failures.extend(_requirement_registry_failures(entry, root=root))
    failures.extend(_source_root_failures(entry, root=root))
    return failures


def _scaffolded_failures(entry: PackageEntry, *, root: Path) -> list[str]:
    failures = _common_package_file_failures(entry, root=root)
    if not (
        root / entry.path / "tests" / f"test_{entry.import_name.removeprefix('frtb_')}_scaffold.py"
    ).exists():
        failures.append("scaffold-test")
    if not _any_exists(
        root, entry.module_docs / "REGULATORY_REQUIREMENTS.md", entry.module_docs / "PRD.md"
    ):
        failures.append("regulatory-requirements-or-prd")
    failures.extend(_requirement_registry_failures(entry, root=root))
    return failures


def _orchestration_partial_failures(entry: PackageEntry, *, root: Path) -> list[str]:
    failures = _common_package_file_failures(entry, root=root)
    tests_dir = root / entry.path / "tests"
    if not tests_dir.is_dir():
        failures.append("tests-directory")
    if not list(tests_dir.glob("test_*orchestration*.py")):
        failures.append("orchestration-tests")
    return failures


def _orchestration_implemented_failures(entry: PackageEntry, *, root: Path) -> list[str]:
    failures = _common_package_file_failures(entry, root=root)
    tests_dir = root / entry.path / "tests"
    if not tests_dir.is_dir():
        failures.append("tests-directory")
    if not list(tests_dir.glob("test_*orchestration*.py")):
        failures.append("orchestration-tests")
    if not list(tests_dir.glob("test_*suite*.py")):
        failures.append("suite-capital-tests")
    return failures


def _result_store_partial_failures(entry: PackageEntry, *, root: Path) -> list[str]:
    failures = _common_package_file_failures(entry, root=root)
    tests_dir = root / entry.path / "tests"
    if not tests_dir.is_dir():
        failures.append("tests-directory")
    if not list(tests_dir.glob("test_*public_api*.py")):
        failures.append("public-api-tests")
    if not list(tests_dir.glob("test_*duckdb*parquet*.py")):
        failures.append("duckdb-parquet-tests")
    if not (root / entry.module_docs / "ARCHITECTURE_AND_DATA_DESIGN.md").exists():
        failures.append("architecture-data-design")
    if not (root / entry.module_docs / "PUBLIC_API.md").exists():
        failures.append("public-api-docs")
    failures.extend(_source_root_failures(entry, root=root))
    return failures


def _shared_failures(entry: PackageEntry, *, root: Path) -> list[str]:
    failures = _common_package_file_failures(entry, root=root)
    if not (root / entry.path / "tests").is_dir():
        failures.append("tests-directory")
    pyproject_path = root / entry.path / "pyproject.toml"
    py_typed = root / entry.path / "src" / entry.import_name / "py.typed"
    if pyproject_path.exists() and "py.typed" in pyproject_path.read_text(encoding="utf-8"):
        if not py_typed.exists():
            failures.append("py-typed")
    policy_helper = root / entry.path / "src" / entry.import_name / "regulatory/policy_citations.py"
    if policy_helper.exists() and "regulatory-helpers" not in entry.required_test_ids():
        failures.append("required-test:regulatory-helpers")
    return failures


def _common_package_file_failures(entry: PackageEntry, *, root: Path) -> list[str]:
    failures: list[str] = []
    for name, requirement_id in (
        ("README.md", "package-readme"),
        ("CHANGELOG.md", "package-changelog"),
        ("AGENTS.md", "package-agents"),
    ):
        if not (root / entry.path / name).exists():
            failures.append(requirement_id)
    if not (root / entry.module_docs).exists():
        failures.append("module-docs")
    return failures


def _requirement_registry_failures(entry: PackageEntry, *, root: Path) -> list[str]:
    module_requirement_dir = root / entry.module_docs / "requirements"
    package_requirement_dir = root / entry.path / "docs" / "requirements"
    has_registry = any(
        requirement_dir.is_dir()
        and (list(requirement_dir.glob("*.yml")) or list(requirement_dir.glob("*.yaml")))
        for requirement_dir in (module_requirement_dir, package_requirement_dir)
    )
    if not has_registry:
        return ["requirement-registry"]
    return []


def _source_root_failures(entry: PackageEntry, *, root: Path) -> list[str]:
    if not (root / entry.path / "src" / entry.import_name).is_dir():
        return ["source-root"]
    return []


def _any_exists(root: Path, *paths: Path) -> bool:
    return any((root / path).exists() for path in paths)


def _can_import_module(module_name: str) -> bool:
    try:
        importlib.import_module(module_name)
    except Exception:
        return False
    return True


def _import_path(import_path: str) -> object | None:
    module_name, separator, object_name = import_path.partition(":")
    if not separator or not module_name or not object_name:
        return None
    try:
        module = importlib.import_module(module_name)
        target: object = module
        for attribute in object_name.split("."):
            target = getattr(target, attribute)
    except Exception:
        return None
    return target


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--registry", type=Path, default=REGISTRY_PATH)
    parser.add_argument("--package")
    parser.add_argument("--json-output", type=Path)
    args = parser.parse_args(argv)

    try:
        registry = load_registry(args.registry)
        results = check_registry(registry, package=args.package)
    except (ValueError, OSError) as exc:
        print(exc)
        return 1

    if args.json_output is not None:
        write_json_report(results, args.json_output)

    for result in results:
        if result.passed:
            print(f"{result.package}: passed")
        else:
            failures = ", ".join(result.failed_requirement_ids)
            print(f"{result.package}: failed: {failures}")
    return 0 if all(result.passed for result in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
