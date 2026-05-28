import ast
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
CAPITAL_IMPORTS = {
    "frtb_cva",
    "frtb_drc",
    "frtb_ima",
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
    tree = ast.parse(path.read_text(), filename=str(path))
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name.split(".", maxsplit=1)[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            modules.add(node.module.split(".", maxsplit=1)[0])
    return modules


def test_capital_packages_do_not_import_sibling_capital_packages() -> None:
    for import_name, package_name in CAPITAL_PACKAGE_BY_IMPORT.items():
        src_root = REPO_ROOT / "packages" / package_name / "src"
        imported_capital_modules: set[str] = set()
        for path in src_root.rglob("*.py"):
            imported_capital_modules.update(imported_top_level_modules(path) & CAPITAL_IMPORTS)

        assert imported_capital_modules <= {import_name}


def test_common_does_not_import_capital_packages() -> None:
    src_root = REPO_ROOT / "packages" / "frtb-common" / "src"
    imported_capital_modules: set[str] = set()
    for path in src_root.rglob("*.py"):
        imported_capital_modules.update(imported_top_level_modules(path) & CAPITAL_IMPORTS)

    assert imported_capital_modules == set()
