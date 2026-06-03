"""Changed-test guard for shallow, duplicate, or oversized tests."""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import sys
from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

try:  # Supports both `python scripts/ci/...` and package-style test imports.
    from .quality_helpers import function_payload, git, merge_base, parent_map, qualified_name
except ImportError:  # pragma: no cover - exercised by direct script execution.
    from quality_helpers import function_payload, git, merge_base, parent_map, qualified_name

SCHEMA_VERSION = 1
DEFAULT_PATHS = ("packages", "tests")
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
FIXTURE_NAME_MARKERS = ("fixture", "fixtures", "golden", "snapshot", "snapshots")


@dataclass(frozen=True)
class Thresholds:
    """Thresholds for changed-test value checks."""

    test_file_loc_growth: int = 500
    fixture_file_bytes: int = 50_000
    duplicate_test_body_lines: int = 3


@dataclass(frozen=True)
class TestRecord:
    """A normalized changed test function."""

    path: str
    name: str
    line: int
    end_line: int
    lines: int
    digest: str
    has_value_assertion: bool

    @property
    def key(self) -> str:
        return f"{self.path}:{self.name}:{self.line}"


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--base-ref", default="origin/main")
    parser.add_argument("--json-output", type=Path)
    parser.add_argument("--quiet", action="store_true")
    parser.add_argument("--paths", nargs="*", default=list(DEFAULT_PATHS))
    args = parser.parse_args(argv)

    root = args.root.resolve()
    thresholds = Thresholds()
    report = build_report(root, args.base_ref, args.paths, thresholds)
    if args.json_output:
        _write_json(args.json_output, report)

    errors = collect_test_value_errors(report)
    if errors:
        print("Changed-test value guard failed:", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        print(
            "Add tests that exercise observable behavior, remove duplicate test bodies, "
            "or split large fixtures into reviewed evidence.",
            file=sys.stderr,
        )
        return 1

    if not args.quiet:
        metrics = report["metrics"]
        print(
            "Changed-test value guard passed: "
            f"{metrics['changed_test_files']} test file(s), "
            f"{metrics['changed_test_functions']} changed test function(s)."
        )
    return 0


def build_report(
    root: Path,
    base_ref: str,
    paths: Sequence[str],
    thresholds: Thresholds,
) -> dict[str, Any]:
    base = _merge_base(root, base_ref)
    changed_paths = _changed_paths(root, base, paths)
    evidence = _collect_changed_test_evidence(root, base, changed_paths, thresholds)
    duplicate_groups = _duplicate_test_groups(
        evidence["records"],
        thresholds.duplicate_test_body_lines,
    )

    return {
        "schema_version": SCHEMA_VERSION,
        "description": "Changed-test value guard report.",
        "base_ref": base_ref,
        "merge_base": base,
        "paths": list(paths),
        "thresholds": {
            "test_file_loc_growth": thresholds.test_file_loc_growth,
            "fixture_file_bytes": thresholds.fixture_file_bytes,
            "duplicate_test_body_lines": thresholds.duplicate_test_body_lines,
        },
        "metrics": _metrics_for_report(changed_paths, evidence, duplicate_groups),
        "changed_tests": dict(sorted(evidence["changed_tests"].items())),
        "tests_without_value_assertions": dict(
            sorted(evidence["tests_without_value_assertions"].items())
        ),
        "duplicate_test_groups": duplicate_groups,
        "file_growth": dict(sorted(evidence["file_growth"].items())),
        "large_fixtures": dict(sorted(evidence["large_fixtures"].items())),
    }


def _collect_changed_test_evidence(
    root: Path,
    base: str,
    changed_paths: Sequence[str],
    thresholds: Thresholds,
) -> dict[str, Any]:
    changed_tests: dict[str, dict[str, Any]] = {}
    tests_without_value_assertions: dict[str, dict[str, Any]] = {}
    file_growth: dict[str, dict[str, Any]] = {}
    large_fixtures: dict[str, dict[str, Any]] = {}
    changed_records: list[TestRecord] = []
    for relative in changed_paths:
        current_path = root / relative
        if not current_path.exists():
            continue
        current_text = current_path.read_text(encoding="utf-8", errors="replace")
        base_text = _git_show(root, base, relative)

        if _is_test_python_file(relative):
            current_loc = _logical_loc(current_text)
            base_loc = _logical_loc(base_text or "")
            loc_delta = current_loc - base_loc
            if loc_delta > thresholds.test_file_loc_growth:
                file_growth[relative] = {
                    "current_loc": current_loc,
                    "base_loc": base_loc,
                    "loc_delta": loc_delta,
                    "growth_budget": thresholds.test_file_loc_growth,
                }
            base_records = {
                record.name: record for record in _test_records_from_text(relative, base_text or "")
            }
            for record in _test_records_from_text(relative, current_text):
                previous = base_records.get(record.name)
                if previous is not None and previous.digest == record.digest:
                    continue
                payload = function_payload(record)
                changed_tests[record.key] = payload
                changed_records.append(record)
                if not record.has_value_assertion:
                    tests_without_value_assertions[record.key] = payload
        elif _is_fixture_path(relative):
            base_size = len(bytes(base_text or "", "utf-8"))
            current_size = current_path.stat().st_size
            size_delta = current_size - base_size
            if size_delta > thresholds.fixture_file_bytes:
                large_fixtures[relative] = {
                    "current_bytes": current_size,
                    "base_bytes": base_size,
                    "byte_delta": size_delta,
                    "growth_budget": thresholds.fixture_file_bytes,
                }
    return {
        "changed_tests": changed_tests,
        "tests_without_value_assertions": tests_without_value_assertions,
        "file_growth": file_growth,
        "large_fixtures": large_fixtures,
        "records": changed_records,
    }


def _duplicate_test_groups(
    changed_records: Sequence[TestRecord],
    minimum_lines: int,
) -> list[dict[str, Any]]:
    duplicate_groups: list[dict[str, Any]] = []
    by_digest: dict[str, list[TestRecord]] = defaultdict(list)
    for record in changed_records:
        if record.lines >= minimum_lines:
            by_digest[record.digest].append(record)
    for digest, records in by_digest.items():
        if len(records) > 1:
            duplicate_groups.append(
                {
                    "digest": digest,
                    "locations": [
                        function_payload(record)
                        for record in sorted(records, key=lambda item: item.key)
                    ],
                }
            )

    duplicate_groups.sort(key=lambda item: item["locations"][0]["key"])
    return duplicate_groups


def _metrics_for_report(
    changed_paths: Sequence[str],
    evidence: Mapping[str, Any],
    duplicate_groups: Sequence[Mapping[str, Any]],
) -> dict[str, int]:
    return {
        "changed_files": len(changed_paths),
        "changed_test_files": sum(1 for path in changed_paths if _is_test_python_file(path)),
        "changed_test_functions": len(_as_mapping(evidence["changed_tests"])),
        "tests_without_value_assertions": len(
            _as_mapping(evidence["tests_without_value_assertions"])
        ),
        "duplicate_test_groups": len(duplicate_groups),
        "large_fixture_files": len(_as_mapping(evidence["large_fixtures"])),
        "test_files_over_growth_budget": len(_as_mapping(evidence["file_growth"])),
    }


def collect_test_value_errors(report: Mapping[str, Any]) -> list[str]:
    errors: list[str] = []
    for key, payload in _mapping(report, "tests_without_value_assertions").items():
        data = _as_mapping(payload)
        errors.append(f"{key} has no value assertion or pytest.raises check")
    for group in _sequence(report.get("duplicate_test_groups", ())):
        locations = _sequence(_as_mapping(group).get("locations", ()))
        joined = ", ".join(str(_as_mapping(location)["key"]) for location in locations)
        errors.append(f"duplicate changed test body: {joined}")
    for path, payload in _mapping(report, "file_growth").items():
        data = _as_mapping(payload)
        errors.append(
            f"{path} grew by {data['loc_delta']} logical LOC (budget +{data['growth_budget']})"
        )
    for path, payload in _mapping(report, "large_fixtures").items():
        data = _as_mapping(payload)
        errors.append(
            f"{path} fixture grew by {data['byte_delta']} bytes (budget +{data['growth_budget']})"
        )
    return errors


def _test_records_from_text(relative: str, text: str) -> list[TestRecord]:
    if not text:
        return []
    try:
        tree = ast.parse(text, filename=relative)
    except SyntaxError:
        return []
    parents = parent_map(tree)
    records: list[TestRecord] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            continue
        if not node.name.startswith("test_"):
            continue
        body = _body_without_docstring(node.body)
        lines = int((node.end_lineno or node.lineno) - node.lineno + 1)
        records.append(
            TestRecord(
                path=relative,
                name=qualified_name(node, parents),
                line=node.lineno,
                end_line=int(node.end_lineno or node.lineno),
                lines=lines,
                digest=_function_digest(body),
                has_value_assertion=_has_value_assertion(body),
            )
        )
    return records


def _has_value_assertion(body: Sequence[ast.stmt]) -> bool:
    for node in ast.walk(ast.Module(body=list(body), type_ignores=[])):
        if isinstance(node, ast.Assert):
            return True
        if isinstance(node, ast.With):
            if any(_is_pytest_raises(item.context_expr) for item in node.items):
                return True
        if isinstance(node, ast.Call) and _is_assertion_call(node):
            return True
    return False


def _is_pytest_raises(node: ast.AST) -> bool:
    if not isinstance(node, ast.Call):
        return False
    if isinstance(node.func, ast.Attribute):
        return (
            node.func.attr == "raises"
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "pytest"
        )
    return isinstance(node.func, ast.Name) and node.func.id == "raises"


def _is_assertion_call(node: ast.Call) -> bool:
    return isinstance(node.func, ast.Attribute) and node.func.attr.startswith("assert")


def _body_without_docstring(nodes: Sequence[ast.stmt]) -> list[ast.stmt]:
    if nodes and isinstance(nodes[0], ast.Expr) and isinstance(nodes[0].value, ast.Constant):
        if isinstance(nodes[0].value.value, str):
            return list(nodes[1:])
    return list(nodes)


def _function_digest(body: Sequence[ast.stmt]) -> str:
    normalized = "\n".join(ast.dump(node, include_attributes=False) for node in body)
    return hashlib.sha256(bytes(normalized, "utf-8")).hexdigest()[:16]


def _changed_paths(root: Path, base: str, paths: Sequence[str]) -> list[str]:
    pathspecs = tuple(paths)
    changed = set(_git_lines(root, "diff", "--name-only", "--diff-filter=ACMRT", base, "--"))
    changed.update(_git_lines(root, "ls-files", "--others", "--exclude-standard"))
    return sorted(
        path
        for path in changed
        if _matches_pathspec(path, pathspecs)
        and not any(part in SKIPPED_DIRS for part in Path(path).parts)
        and (_is_test_python_file(path) or _is_fixture_path(path))
    )


def _is_test_python_file(relative: str) -> bool:
    path = Path(relative)
    return path.suffix == ".py" and ("tests" in path.parts or path.name.startswith("test_"))


def _is_fixture_path(relative: str) -> bool:
    path = Path(relative)
    parts = {part.lower() for part in path.parts}
    return bool(parts.intersection(FIXTURE_NAME_MARKERS)) and path.suffix != ".py"


def _logical_loc(text: str) -> int:
    return sum(
        1 for line in text.splitlines() if line.strip() and not line.lstrip().startswith("#")
    )


def _merge_base(root: Path, base_ref: str) -> str:
    return merge_base(root, base_ref, "test-value")


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


def _sequence(payload: object) -> Sequence[object]:
    if isinstance(payload, Sequence) and not isinstance(payload, str):
        return payload
    return ()


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
