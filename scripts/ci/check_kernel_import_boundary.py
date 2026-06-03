"""Fail if dataframe or Arrow runtimes leak into capital runtime kernels."""

from __future__ import annotations

import argparse
import ast
from dataclasses import dataclass
from pathlib import Path
from typing import NoReturn

BANNED_IMPORT_ROOTS = frozenset({"pandas", "polars", "pyarrow"})

ALLOWED_RUNTIME_FILENAMES = frozenset(
    {
        "adapter.py",
        "adapters.py",
        "arrow.py",
        "arrow_conversion.py",
        "arrow_handoff.py",
        "crif.py",
        "handoff.py",
        "io.py",
        "tabular.py",
    }
)

ALLOWED_RUNTIME_DIRS = frozenset(
    {
        "adapter",
        "adapters",
        "handoff",
        "io",
        "tabular",
    }
)

ALLOWED_RUNTIME_RELATIVE_PATHS = frozenset(
    {
        "frtb_common/handoff_schema.py",
        "frtb_orchestration/manifest.py",
    }
)

APPROVED_IO_PACKAGE_SRC_ROOTS = frozenset(
    {
        Path("packages/frtb-result-store/src"),
    }
)

ALLOWED_RUNTIME_SUFFIXES = (
    "_adapter.py",
    "_adapters.py",
    "_handoff.py",
    "_io.py",
)


@dataclass(frozen=True)
class ImportViolation:
    path: Path
    line_number: int
    imported_root: str


def main() -> NoReturn:
    parser = argparse.ArgumentParser(
        description=(
            "Check package runtime modules for banned pandas/polars/pyarrow imports outside "
            "explicit adapter and handoff boundaries."
        )
    )
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=Path.cwd(),
        help="Repository root. Defaults to the current working directory.",
    )
    args = parser.parse_args()

    repo_root = args.repo_root.resolve()
    violations = check_repo(repo_root)
    if violations:
        print("Banned dataframe/Arrow imports found outside adapter and handoff boundaries:")
        for violation in violations:
            display_path = violation.path.relative_to(repo_root)
            print(f"- {display_path}:{violation.line_number} imports {violation.imported_root!r}")
        raise SystemExit(1)

    print("Kernel import boundary kept")
    raise SystemExit(0)


def check_repo(repo_root: Path) -> tuple[ImportViolation, ...]:
    package_src_roots = sorted(repo_root.glob("packages/*/src"))
    violations: list[ImportViolation] = []
    for src_root in package_src_roots:
        if _is_approved_io_package_src_root(src_root, repo_root):
            continue
        for path in sorted(src_root.rglob("*.py")):
            if _is_allowed_runtime_handoff_path(path, src_root):
                continue
            violations.extend(_banned_imports_in_file(path))
    return tuple(violations)


def _is_approved_io_package_src_root(src_root: Path, repo_root: Path) -> bool:
    return src_root.relative_to(repo_root) in APPROVED_IO_PACKAGE_SRC_ROOTS


def _is_allowed_runtime_handoff_path(path: Path, src_root: Path) -> bool:
    relative = path.relative_to(src_root)
    if relative.as_posix() in ALLOWED_RUNTIME_RELATIVE_PATHS:
        return True
    if path.name in ALLOWED_RUNTIME_FILENAMES:
        return True
    if path.name.endswith(ALLOWED_RUNTIME_SUFFIXES):
        return True
    return any(part in ALLOWED_RUNTIME_DIRS for part in relative.parts[:-1])


def _banned_imports_in_file(path: Path) -> tuple[ImportViolation, ...]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    violations: list[ImportViolation] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Import | ast.ImportFrom):
            continue
        imported_roots = _imported_roots(node)
        for imported_root in imported_roots & BANNED_IMPORT_ROOTS:
            violations.append(
                ImportViolation(
                    path=path,
                    line_number=node.lineno,
                    imported_root=imported_root,
                )
            )
    return tuple(violations)


def _imported_roots(node: ast.Import | ast.ImportFrom) -> frozenset[str]:
    if isinstance(node, ast.Import):
        return frozenset(alias.name.split(".", maxsplit=1)[0] for alias in node.names)
    if node.level > 0:
        return frozenset()
    if node.module:
        return frozenset({node.module.split(".", maxsplit=1)[0]})
    return frozenset()


if __name__ == "__main__":
    main()
