"""Changed-code guard for high-confidence dead private symbols and modules."""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import sys
import warnings
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

try:  # Supports both `python scripts/ci/...` and package-style test imports.
    from .quality_helpers import function_payload, git, merge_base, parent_map, qualified_name
except ImportError:  # pragma: no cover - exercised by direct script execution.
    from quality_helpers import function_payload, git, merge_base, parent_map, qualified_name

SCHEMA_VERSION = 1
DEFAULT_PATHS = ("packages", "scripts", "tools")
REFERENCE_PATHS = ("packages", "scripts", "tests", "tools")
SKIPPED_DIRS = {
    ".git",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    "__pycache__",
    "build",
    "dist",
    "mutants",
}


@dataclass(frozen=True)
class DefinitionRecord:
    """A changed function or class definition."""

    path: str
    name: str
    line: int
    end_line: int
    lines: int
    kind: str
    digest: str

    @property
    def key(self) -> str:
        return f"{self.path}:{self.name}:{self.line}"


@dataclass(frozen=True)
class ReferenceRecord:
    """A symbol reference found in Python source."""

    path: str
    name: str
    line: int


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--base-ref", default="origin/main")
    parser.add_argument("--json-output", type=Path)
    parser.add_argument("--quiet", action="store_true")
    parser.add_argument("--paths", nargs="*", default=list(DEFAULT_PATHS))
    args = parser.parse_args(argv)

    root = args.root.resolve()
    report = build_report(root, args.base_ref, args.paths)
    if args.json_output:
        _write_json(args.json_output, report)

    errors = collect_dead_code_errors(report)
    if errors:
        print("Changed-code dead-code guard failed:", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        print(
            "Remove unused private symbols, call them from real code/tests, or expose new "
            "runtime modules through a reviewed import boundary.",
            file=sys.stderr,
        )
        return 1

    if not args.quiet:
        metrics = report["metrics"]
        print(
            "Changed-code dead-code guard passed: "
            f"{metrics['changed_private_definitions']} changed private definition(s), "
            f"{metrics['new_runtime_modules']} new runtime module(s)."
        )
    return 0


def build_report(root: Path, base_ref: str, paths: Sequence[str]) -> dict[str, Any]:
    base = _merge_base(root, base_ref)
    changed_paths = _changed_python_paths(root, base, paths)
    current_python_paths = list(_iter_python_files(root, REFERENCE_PATHS))
    references = _collect_references(root, current_python_paths)
    import_refs = _collect_import_references(root, current_python_paths)
    changed_definitions = _changed_private_definitions(root, base, changed_paths)
    unused_definitions = {
        record.key: function_payload(record) | {"kind": record.kind}
        for record in changed_definitions
        if not _has_external_reference(record, references)
    }
    new_modules = _new_runtime_modules(root, base, changed_paths)
    unreferenced_modules = {
        module_path: payload
        for module_path, payload in new_modules.items()
        if not _module_is_referenced(payload, import_refs)
    }

    return {
        "schema_version": SCHEMA_VERSION,
        "description": "Changed-code dead-code guard report.",
        "base_ref": base_ref,
        "merge_base": base,
        "paths": list(paths),
        "metrics": {
            "changed_python_files": len(changed_paths),
            "changed_private_definitions": len(changed_definitions),
            "unused_private_definitions": len(unused_definitions),
            "new_runtime_modules": len(new_modules),
            "unreferenced_runtime_modules": len(unreferenced_modules),
        },
        "unused_private_definitions": dict(sorted(unused_definitions.items())),
        "unreferenced_runtime_modules": dict(sorted(unreferenced_modules.items())),
    }


def collect_dead_code_errors(report: Mapping[str, Any]) -> list[str]:
    errors: list[str] = []
    for key, payload in _mapping(report, "unused_private_definitions").items():
        data = _as_mapping(payload)
        errors.append(f"{key} changed private {data['kind']} has no external reference")
    for path, payload in _mapping(report, "unreferenced_runtime_modules").items():
        data = _as_mapping(payload)
        errors.append(f"{path} new runtime module is not imported as {data['module']}")
    return errors


def _changed_private_definitions(
    root: Path,
    base: str,
    changed_paths: Sequence[str],
) -> list[DefinitionRecord]:
    records: list[DefinitionRecord] = []
    for relative in changed_paths:
        if _is_test_or_example_path(relative):
            continue
        current_text = (root / relative).read_text(encoding="utf-8", errors="replace")
        base_by_name = {
            record.name: record
            for record in _definition_records(relative, _git_show(root, base, relative) or "")
        }
        for record in _definition_records(relative, current_text):
            previous = base_by_name.get(record.name)
            if previous is not None and previous.digest == record.digest:
                continue
            if _is_private_name(record.name.rsplit(".", maxsplit=1)[-1]):
                records.append(record)
    return records


def _definition_records(relative: str, text: str) -> list[DefinitionRecord]:
    if not text:
        return []
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", SyntaxWarning)
            tree = ast.parse(text, filename=relative)
    except SyntaxError:
        return []
    parents = parent_map(tree)
    records: list[DefinitionRecord] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            records.append(_definition_record(relative, node, parents, "function"))
        elif isinstance(node, ast.ClassDef):
            records.append(_definition_record(relative, node, parents, "class"))
    return records


def _definition_record(
    relative: str,
    node: ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef,
    parents: Mapping[ast.AST, ast.AST],
    kind: str,
) -> DefinitionRecord:
    lines = int((node.end_lineno or node.lineno) - node.lineno + 1)
    return DefinitionRecord(
        path=relative,
        name=qualified_name(node, parents),
        line=node.lineno,
        end_line=int(node.end_lineno or node.lineno),
        lines=lines,
        kind=kind,
        digest=_node_digest(node),
    )


def _collect_references(root: Path, paths: Sequence[Path]) -> dict[str, list[ReferenceRecord]]:
    references: dict[str, list[ReferenceRecord]] = {}
    for path in paths:
        relative = path.relative_to(root).as_posix()
        for record in _references_from_text(
            relative, path.read_text(encoding="utf-8", errors="replace")
        ):
            references.setdefault(record.name, []).append(record)
    return references


def _references_from_text(relative: str, text: str) -> list[ReferenceRecord]:
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", SyntaxWarning)
            tree = ast.parse(text, filename=relative)
    except SyntaxError:
        return []
    records: list[ReferenceRecord] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load):
            records.append(ReferenceRecord(relative, node.id, node.lineno))
        elif isinstance(node, ast.Attribute) and isinstance(node.ctx, ast.Load):
            records.append(ReferenceRecord(relative, node.attr, node.lineno))
    return records


def _has_external_reference(
    definition: DefinitionRecord,
    references: Mapping[str, Sequence[ReferenceRecord]],
) -> bool:
    leaf_name = definition.name.rsplit(".", maxsplit=1)[-1]
    for reference in references.get(leaf_name, ()):
        if reference.path != definition.path:
            return True
        if not definition.line <= reference.line <= definition.end_line:
            return True
    return False


def _new_runtime_modules(
    root: Path, base: str, changed_paths: Sequence[str]
) -> dict[str, dict[str, Any]]:
    modules: dict[str, dict[str, Any]] = {}
    for relative in changed_paths:
        if not _is_runtime_package_module(relative) or _git_show(root, base, relative) is not None:
            continue
        module = _module_name_for_runtime_path(relative)
        if module:
            modules[relative] = {"module": module, "leaf": module.rsplit(".", maxsplit=1)[-1]}
    return modules


def _collect_import_references(root: Path, paths: Sequence[Path]) -> set[str]:
    imports: set[str] = set()
    for path in paths:
        imports.update(_imports_from_text(path.read_text(encoding="utf-8", errors="replace")))
    return imports


def _imports_from_text(text: str) -> set[str]:
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", SyntaxWarning)
            tree = ast.parse(text)
    except SyntaxError:
        return set()
    imports: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.add(node.module)
            imports.update(f"{node.module}.{alias.name}" for alias in node.names)
    return imports


def _module_is_referenced(module_payload: Mapping[str, Any], imports: set[str]) -> bool:
    module = str(module_payload["module"])
    return any(imported == module or imported.startswith(f"{module}.") for imported in imports)


def _changed_python_paths(root: Path, base: str, paths: Sequence[str]) -> list[str]:
    changed = set(_git_lines(root, "diff", "--name-only", "--diff-filter=ACMRT", base, "--"))
    changed.update(_git_lines(root, "ls-files", "--others", "--exclude-standard"))
    return sorted(
        path
        for path in changed
        if path.endswith(".py")
        and _matches_pathspec(path, paths)
        and not any(part in SKIPPED_DIRS for part in Path(path).parts)
    )


def _iter_python_files(root: Path, paths: Sequence[str]) -> list[Path]:
    files: list[Path] = []
    for raw_path in paths:
        base = root / raw_path
        if not base.exists():
            continue
        files.extend(
            path
            for path in sorted(base.rglob("*.py"))
            if not any(part in SKIPPED_DIRS for part in path.parts)
        )
    return files


def _is_private_name(name: str) -> bool:
    return name.startswith("_") and not (name.startswith("__") and name.endswith("__"))


def _is_test_or_example_path(relative: str) -> bool:
    parts = Path(relative).parts
    return "tests" in parts or "examples" in parts or Path(relative).name.startswith("test_")


def _is_runtime_package_module(relative: str) -> bool:
    parts = Path(relative).parts
    return (
        len(parts) >= 5
        and parts[0] == "packages"
        and parts[2] == "src"
        and parts[-1] != "__init__.py"
        and "tests" not in parts
        and "examples" not in parts
    )


def _module_name_for_runtime_path(relative: str) -> str | None:
    parts = Path(relative).with_suffix("").parts
    if len(parts) < 5 or parts[2] != "src":
        return None
    return ".".join(parts[3:])


def _node_digest(node: ast.AST) -> str:
    return hashlib.sha256(ast.dump(node, include_attributes=False).encode("utf-8")).hexdigest()[:16]


def _merge_base(root: Path, base_ref: str) -> str:
    return merge_base(root, base_ref, "dead-code")


def _git_show(root: Path, revision: str, relative: str) -> str | None:
    result = git(root, "show", f"{revision}:{relative}")
    if result.returncode != 0:
        return None
    return result.stdout


def _git_lines(root: Path, *args: str) -> list[str]:
    result = git(root, *args)
    if result.returncode != 0:
        return []
    return [line for line in result.stdout.splitlines() if line]


def _matches_pathspec(path: str, pathspecs: Sequence[str]) -> bool:
    return any(
        path == pathspec or path.startswith(f"{pathspec.rstrip('/')}/") for pathspec in pathspecs
    )


def _mapping(payload: Mapping[str, Any], key: str) -> Mapping[str, Any]:
    value = payload.get(key, {})
    if not isinstance(value, Mapping):
        return {}
    return value


def _as_mapping(payload: object) -> Mapping[str, Any]:
    if not isinstance(payload, Mapping):
        raise ValueError("expected mapping payload")
    return payload


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
