import ast
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
CAPITAL_IMPORTS = {
    "frtb_orchestration",
    "frtb_cva",
    "frtb_drc",
    "frtb_ima",
    "frtb_result_store",
    "frtb_rrao",
    "frtb_sbm",
}
CAPITAL_PACKAGE_BY_IMPORT = {
    "frtb_cva": "frtb-cva",
    "frtb_drc": "frtb-drc",
    "frtb_ima": "frtb-ima",
    "frtb_rrao": "frtb-rrao",
    "frtb_sbm": "frtb-sbm",
}


def imported_top_level_modules(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name.split(".", maxsplit=1)[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            modules.add(node.module.split(".", maxsplit=1)[0])
    return modules


def test_capital_packages_do_not_import_sibling_capital_packages() -> None:
    # Orchestration is included in CAPITAL_IMPORTS to prevent component packages
    # importing upward into the aggregator, but it is intentionally omitted from
    # CAPITAL_PACKAGE_BY_IMPORT because orchestration may compose components.
    # This AST guard catches source imports in capital component src trees.
    # The root import-linter layers contract (`make import-lint`) enforces the
    # same graph across installed package modules, including orchestration.
    for import_name, package_name in CAPITAL_PACKAGE_BY_IMPORT.items():
        src_root = REPO_ROOT / "packages" / package_name / "src"
        assert src_root.is_dir(), f"Source directory not found: {src_root}"
        imported_capital_modules: set[str] = set()
        for path in src_root.rglob("*.py"):
            imported_capital_modules.update(imported_top_level_modules(path) & CAPITAL_IMPORTS)

        assert imported_capital_modules <= {import_name}


def test_common_does_not_import_capital_packages() -> None:
    src_root = REPO_ROOT / "packages" / "frtb-common" / "src"
    assert src_root.is_dir(), f"Source directory not found: {src_root}"
    imported_capital_modules: set[str] = set()
    for path in src_root.rglob("*.py"):
        imported_capital_modules.update(imported_top_level_modules(path) & CAPITAL_IMPORTS)

    assert imported_capital_modules == set()


def test_result_store_does_not_import_capital_or_orchestration_packages() -> None:
    src_root = REPO_ROOT / "packages" / "frtb-result-store" / "src"
    assert src_root.is_dir(), f"Source directory not found: {src_root}"
    forbidden_imports = CAPITAL_IMPORTS - {"frtb_result_store"}
    imported_forbidden_modules: set[str] = set()
    for path in src_root.rglob("*.py"):
        imported_forbidden_modules.update(imported_top_level_modules(path) & forbidden_imports)

    assert imported_forbidden_modules == set()


def test_artifact_metadata_lookup_remains_outside_capital_and_orchestration_packages() -> None:
    # Time-series, shock, scenario-vector, and surface metadata is persisted and
    # served by frtb-result-store. Capital packages and orchestration may carry
    # stable IDs/provenance, but must not import storage lookup APIs.
    guarded_packages = (
        "frtb-common",
        "frtb-cva",
        "frtb-drc",
        "frtb-ima",
        "frtb-orchestration",
        "frtb-rrao",
        "frtb-sbm",
    )
    offenders: list[str] = []
    for package_name in guarded_packages:
        src_root = REPO_ROOT / "packages" / package_name / "src"
        assert src_root.is_dir(), f"Source directory not found: {src_root}"
        for path in src_root.rglob("*.py"):
            if "frtb_result_store" in imported_top_level_modules(path):
                offenders.append(str(path.relative_to(REPO_ROOT)))

    assert offenders == []


def test_enterprise_hierarchy_read_model_stays_outside_component_packages() -> None:
    component_packages = (
        "frtb-cva",
        "frtb-drc",
        "frtb-ima",
        "frtb-rrao",
        "frtb-sbm",
    )
    result_store_src = REPO_ROOT / "packages" / "frtb-result-store" / "src" / "frtb_result_store"
    forbidden_module_names = {path.name for path in result_store_src.glob("org_hierarchy*.py")} | {
        "hierarchy.py",
        "store_hierarchy_rows.py",
    }
    offenders: list[str] = []

    for package_name in component_packages:
        src_root = REPO_ROOT / "packages" / package_name / "src"
        assert src_root.is_dir(), f"Source directory not found: {src_root}"
        for path in src_root.rglob("*.py"):
            if path.name in forbidden_module_names:
                offenders.append(str(path.relative_to(REPO_ROOT)))
            elif "frtb_result_store" in imported_top_level_modules(path):
                offenders.append(str(path.relative_to(REPO_ROOT)))

    assert offenders == []
