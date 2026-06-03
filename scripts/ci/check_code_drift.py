"""Baseline-gated checks for code-size and duplication drift.

The guard is intentionally mechanical. It does not decide whether a large
feature is valuable; it makes growth, duplicated function bodies, oversized
modules, long functions, and thin pass-through wrappers visible in review.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import re
import sys
import warnings
from collections import Counter, defaultdict
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

try:  # Supports both `python scripts/ci/...` and package-style test imports.
    from .quality_helpers import function_payload, git, merge_base, parent_map, qualified_name
except ImportError:  # pragma: no cover - exercised by direct script execution.
    from quality_helpers import function_payload, git, merge_base, parent_map, qualified_name

SCHEMA_VERSION = 1
DEFAULT_BASELINE = Path("docs/quality/code_drift_baseline.json")
DEFAULT_PATHS = ("packages", "scripts", "tests")
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
DRIFT_MARKER_RE = re.compile(
    r"\b(TODO|FIXME|placeholder|stub|temporary|for now|working assumption|"
    r"not implemented|AI-generated|ChatGPT|Copilot)\b",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class Thresholds:
    """Thresholds that separate ordinary code from drift-control findings."""

    source_file_lines: int = 600
    test_file_lines: int = 800
    script_file_lines: int = 500
    function_lines: int = 90
    duplicate_function_lines: int = 8
    oversized_file_growth: int = 25
    large_function_growth: int = 10
    total_python_loc_growth: int = 1_000
    source_python_loc_growth: int = 600
    test_python_loc_growth: int = 800
    script_python_loc_growth: int = 200
    trivial_wrapper_growth: int = 3
    changed_function_growth: int = 25
    changed_source_loc_growth: int = 300
    changed_test_loc_growth: int = 500
    changed_script_loc_growth: int = 700
    changed_other_loc_growth: int = 200


@dataclass(frozen=True)
class FunctionRecord:
    """A normalized Python function record used by drift checks."""

    path: str
    name: str
    line: int
    end_line: int
    lines: int
    digest: str
    is_trivial_wrapper: bool

    @property
    def key(self) -> str:
        return f"{self.path}:{self.name}:{self.line}"


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--baseline", type=Path, default=DEFAULT_BASELINE)
    parser.add_argument("--json-output", type=Path)
    parser.add_argument("--update-baseline", action="store_true")
    parser.add_argument("--changed", action="store_true")
    parser.add_argument("--base-ref", default="origin/main")
    parser.add_argument("--quiet", action="store_true")
    parser.add_argument("--paths", nargs="*", default=list(DEFAULT_PATHS))
    args = parser.parse_args(argv)

    root = args.root.resolve()
    thresholds = Thresholds()

    if args.changed:
        report = build_changed_report(root, args.base_ref, args.paths, thresholds)
        if args.json_output:
            _write_json(args.json_output, report)
        errors = changed_code_errors(report, thresholds)
        if errors:
            print("Changed-code complexity guard failed:", file=sys.stderr)
            for error in errors:
                print(f"- {error}", file=sys.stderr)
            print(
                "Simplify changed code before merging, or split the change so "
                "new wrappers and large functions are reviewed explicitly.",
                file=sys.stderr,
            )
            return 1
        if not args.quiet:
            metrics = report["metrics"]
            print(
                "Changed-code complexity guard passed: "
                f"{metrics['changed_python_files']} Python file(s), "
                f"{metrics['changed_functions']} changed function(s)."
            )
        return 0

    report = build_report(root, args.paths, thresholds)

    if args.json_output:
        _write_json(args.json_output, report)

    baseline_path = _resolve_path(root, args.baseline)
    if args.update_baseline:
        _write_json(baseline_path, baseline_payload(report))
        if not args.quiet:
            print(f"updated code drift baseline: {baseline_path}")
        return 0

    if not baseline_path.exists():
        print(
            f"code drift baseline is missing: {baseline_path}; "
            "run scripts/ci/check_code_drift.py --update-baseline",
            file=sys.stderr,
        )
        return 1

    baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
    errors = compare_to_baseline(report, baseline, thresholds)
    if errors:
        print("Code drift guard failed:", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        print(
            "If the growth is intentional, simplify first where practical and then "
            "update docs/quality/code_drift_baseline.json in the same reviewed change.",
            file=sys.stderr,
        )
        return 1

    if not args.quiet:
        metrics = report["metrics"]
        print(
            "Code drift guard passed: "
            f"{metrics['total_python_loc']} Python LOC, "
            f"{metrics['duplicate_function_groups']} duplicate function group(s), "
            f"{metrics['large_function_count']} large function(s)."
        )
    return 0


def build_report(root: Path, paths: Sequence[str], thresholds: Thresholds) -> dict[str, Any]:
    py_files = list(_iter_python_files(root, paths))
    function_records = _collect_function_records(root, py_files, thresholds)
    duplicate_groups = _duplicate_function_groups(function_records, thresholds)
    wrappers = [record for record in function_records if record.is_trivial_wrapper]
    large_functions = [
        record for record in function_records if record.lines > thresholds.function_lines
    ]

    loc_by_role: Counter[str] = Counter()
    oversized_files: dict[str, dict[str, Any]] = {}
    drift_markers: dict[str, list[dict[str, Any]]] = {}
    for path in py_files:
        role = _role_for(path.relative_to(root).as_posix())
        text = path.read_text(encoding="utf-8")
        loc = _logical_loc(text)
        loc_by_role[role] += loc
        relative = path.relative_to(root).as_posix()
        limit = _file_line_limit(role, thresholds)
        physical_lines = len(text.splitlines())
        if physical_lines > limit:
            oversized_files[relative] = {
                "lines": physical_lines,
                "limit": limit,
                "role": role,
            }
        markers = _drift_markers_for_text(text)
        if markers:
            drift_markers[relative] = markers

    duplicate_instances = sum(len(group["locations"]) - 1 for group in duplicate_groups)
    metrics = {
        "python_files": len(py_files),
        "total_python_loc": sum(loc_by_role.values()),
        "source_python_loc": loc_by_role["source"],
        "test_python_loc": loc_by_role["test"],
        "script_python_loc": loc_by_role["script"],
        "other_python_loc": loc_by_role["other"],
        "duplicate_function_groups": len(duplicate_groups),
        "duplicate_function_instances": duplicate_instances,
        "large_function_count": len(large_functions),
        "trivial_wrapper_functions": len(wrappers),
        "drift_marker_matches": sum(len(matches) for matches in drift_markers.values()),
    }

    return {
        "schema_version": SCHEMA_VERSION,
        "description": (
            "Baseline for mechanical code-drift controls. Update only when the "
            "growth or duplication is intentional and reviewed."
        ),
        "paths": list(paths),
        "thresholds": _threshold_dict(thresholds),
        "metrics": metrics,
        "oversized_files": dict(sorted(oversized_files.items())),
        "large_functions": {
            record.key: function_payload(record)
            for record in sorted(large_functions, key=lambda item: item.key)
        },
        "trivial_wrappers": {
            record.key: function_payload(record)
            for record in sorted(wrappers, key=lambda item: item.key)
        },
        "duplicate_function_groups": duplicate_groups,
        "drift_markers": dict(sorted(drift_markers.items())),
    }


def build_changed_report(
    root: Path,
    base_ref: str,
    paths: Sequence[str],
    thresholds: Thresholds,
) -> dict[str, Any]:
    base = _merge_base(root, base_ref)
    changed_paths = _changed_python_paths(root, base, paths)
    files: dict[str, dict[str, Any]] = {}
    changed_functions: dict[str, dict[str, Any]] = {}
    trivial_wrappers: dict[str, dict[str, Any]] = {}
    large_functions: dict[str, dict[str, Any]] = {}

    for relative in changed_paths:
        current_path = root / relative
        if not current_path.exists():
            continue
        current_text = current_path.read_text(encoding="utf-8")
        base_text = _git_show(root, base, relative)
        role = _role_for(relative)
        current_loc = _logical_loc(current_text)
        base_loc = _logical_loc(base_text or "")
        files[relative] = {
            "role": role,
            "current_loc": current_loc,
            "base_loc": base_loc,
            "loc_delta": current_loc - base_loc,
            "growth_budget": _changed_loc_budget(role, thresholds),
            "is_new": base_text is None,
        }

        current_records = _function_records_from_text(relative, current_text, thresholds)
        base_by_name = {
            record.name: record
            for record in _function_records_from_text(relative, base_text or "", thresholds)
        }
        for record in current_records:
            previous = base_by_name.get(record.name)
            if previous is not None and previous.digest == record.digest:
                continue
            payload = function_payload(record)
            payload["base_lines"] = previous.lines if previous is not None else 0
            payload["line_delta"] = record.lines - (previous.lines if previous else 0)
            payload["is_new"] = previous is None
            changed_functions[record.key] = payload
            if record.is_trivial_wrapper:
                trivial_wrappers[record.key] = payload
            if record.lines > thresholds.function_lines:
                large_functions[record.key] = payload

    return {
        "schema_version": SCHEMA_VERSION,
        "description": "Changed-code wrapper and complexity guard report.",
        "base_ref": base_ref,
        "merge_base": base,
        "paths": list(paths),
        "thresholds": _threshold_dict(thresholds),
        "metrics": {
            "changed_python_files": len(files),
            "changed_functions": len(changed_functions),
            "changed_trivial_wrappers": len(trivial_wrappers),
            "changed_large_functions": len(large_functions),
        },
        "files": dict(sorted(files.items())),
        "changed_functions": dict(sorted(changed_functions.items())),
        "trivial_wrappers": dict(sorted(trivial_wrappers.items())),
        "large_functions": dict(sorted(large_functions.items())),
    }


def changed_code_errors(
    report: Mapping[str, Any],
    thresholds: Thresholds,
) -> list[str]:
    errors: list[str] = []
    for path, payload in _mapping(report, "files").items():
        data = _as_mapping(payload)
        loc_delta = int(_mapping_value(data, "loc_delta"))
        budget = int(_mapping_value(data, "growth_budget"))
        if loc_delta > budget:
            errors.append(f"{path} grew by {loc_delta} logical LOC (budget +{budget})")

    for key, payload in _mapping(report, "trivial_wrappers").items():
        data = _as_mapping(payload)
        errors.append(f"{key} is a changed trivial wrapper at {data['lines']} line(s)")

    for key, payload in _mapping(report, "large_functions").items():
        data = _as_mapping(payload)
        current_lines = int(_mapping_value(data, "lines"))
        base_lines = int(_mapping_value(data, "base_lines"))
        is_new = bool(_mapping_value(data, "is_new"))
        if is_new or base_lines <= thresholds.function_lines:
            errors.append(
                f"{key} is a changed large function at {current_lines} line(s) "
                f"(limit {thresholds.function_lines})"
            )
        elif current_lines > base_lines + thresholds.changed_function_growth:
            errors.append(
                f"{key} grew from {base_lines} to {current_lines} line(s) "
                f"(budget +{thresholds.changed_function_growth})"
            )
    return errors


def compare_to_baseline(
    report: Mapping[str, Any],
    baseline: Mapping[str, Any],
    thresholds: Thresholds,
) -> list[str]:
    if baseline.get("schema_version") != SCHEMA_VERSION:
        return [
            "unsupported code drift baseline schema "
            f"{baseline.get('schema_version')!r}; expected {SCHEMA_VERSION}"
        ]

    errors: list[str] = []
    current_metrics = _mapping(report, "metrics")
    baseline_metrics = _mapping(baseline, "metrics")
    growth_budgets = {
        "total_python_loc": thresholds.total_python_loc_growth,
        "source_python_loc": thresholds.source_python_loc_growth,
        "test_python_loc": thresholds.test_python_loc_growth,
        "script_python_loc": thresholds.script_python_loc_growth,
        "trivial_wrapper_functions": thresholds.trivial_wrapper_growth,
    }
    for metric, budget in growth_budgets.items():
        errors.extend(_growth_errors(metric, current_metrics, baseline_metrics, budget))

    strict_metrics = (
        "duplicate_function_groups",
        "duplicate_function_instances",
        "large_function_count",
        "drift_marker_matches",
    )
    for metric in strict_metrics:
        errors.extend(_growth_errors(metric, current_metrics, baseline_metrics, 0))

    current_oversized = _mapping(report, "oversized_files")
    baseline_oversized = _mapping(baseline, "oversized_files")
    for path, payload in current_oversized.items():
        current_lines = int(_mapping_value(payload, "lines"))
        if path not in baseline_oversized:
            errors.append(f"{path} is a new oversized file at {current_lines} lines")
            continue
        baseline_lines = int(_mapping_value(baseline_oversized[path], "lines"))
        if current_lines > baseline_lines + thresholds.oversized_file_growth:
            errors.append(
                f"{path} grew from {baseline_lines} to {current_lines} lines "
                f"(budget +{thresholds.oversized_file_growth})"
            )

    current_large = _mapping(report, "large_functions")
    baseline_large = _mapping(baseline, "large_functions")
    for key, payload in current_large.items():
        current_lines = int(_mapping_value(payload, "lines"))
        if key not in baseline_large:
            errors.append(f"{key} is a new large function at {current_lines} lines")
            continue
        baseline_lines = int(_mapping_value(baseline_large[key], "lines"))
        if current_lines > baseline_lines + thresholds.large_function_growth:
            errors.append(
                f"{key} grew from {baseline_lines} to {current_lines} lines "
                f"(budget +{thresholds.large_function_growth})"
            )

    return errors


def baseline_payload(report: Mapping[str, Any]) -> dict[str, Any]:
    """Return the compact versioned payload needed to enforce drift budgets."""

    return {
        "schema_version": SCHEMA_VERSION,
        "description": report["description"],
        "paths": report["paths"],
        "thresholds": report["thresholds"],
        "metrics": report["metrics"],
        "oversized_files": report["oversized_files"],
        "large_functions": report["large_functions"],
    }


def _iter_python_files(root: Path, paths: Sequence[str]) -> Iterable[Path]:
    for raw_path in paths:
        base = _resolve_path(root, Path(raw_path))
        if not base.exists():
            continue
        if base.is_file() and base.suffix == ".py":
            yield base
            continue
        for path in sorted(base.rglob("*.py")):
            if not any(part in SKIPPED_DIRS for part in path.parts):
                yield path


def _merge_base(root: Path, base_ref: str) -> str:
    return merge_base(root, base_ref, "changed-code")


def _changed_python_paths(root: Path, base: str, paths: Sequence[str]) -> list[str]:
    pathspecs = tuple(paths)
    changed = set(_git_lines(root, "diff", "--name-only", "--diff-filter=ACMRT", base, "--"))
    changed.update(_git_lines(root, "ls-files", "--others", "--exclude-standard"))
    return sorted(
        path
        for path in changed
        if path.endswith(".py")
        and _matches_pathspec(path, pathspecs)
        and not any(part in SKIPPED_DIRS for part in Path(path).parts)
    )


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


def _collect_function_records(
    root: Path,
    paths: Sequence[Path],
    thresholds: Thresholds,
) -> list[FunctionRecord]:
    records: list[FunctionRecord] = []
    for path in paths:
        text = path.read_text(encoding="utf-8")
        relative = path.relative_to(root).as_posix()
        records.extend(_function_records_from_text(relative, text, thresholds))
    return records


def _function_records_from_text(
    relative: str,
    text: str,
    thresholds: Thresholds,
) -> list[FunctionRecord]:
    if not text:
        return []
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", SyntaxWarning)
            tree = ast.parse(text, filename=relative)
    except SyntaxError:
        return []
    parents = parent_map(tree)
    records: list[FunctionRecord] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            continue
        body = _body_without_docstring(node.body)
        digest = _function_digest(body)
        lines = int((node.end_lineno or node.lineno) - node.lineno + 1)
        records.append(
            FunctionRecord(
                path=relative,
                name=qualified_name(node, parents),
                line=node.lineno,
                end_line=int(node.end_lineno or node.lineno),
                lines=lines,
                digest=digest,
                is_trivial_wrapper=_is_trivial_wrapper(node, body, thresholds),
            )
        )
    return records


def _duplicate_function_groups(
    records: Sequence[FunctionRecord],
    thresholds: Thresholds,
) -> list[dict[str, Any]]:
    by_digest: dict[str, list[FunctionRecord]] = defaultdict(list)
    for record in records:
        if record.lines >= thresholds.duplicate_function_lines:
            by_digest[record.digest].append(record)

    groups: list[dict[str, Any]] = []
    for digest, digest_records in by_digest.items():
        if len(digest_records) < 2:
            continue
        sorted_records = sorted(digest_records, key=lambda item: item.key)
        groups.append(
            {
                "digest": digest,
                "lines": sorted_records[0].lines,
                "locations": [function_payload(record) for record in sorted_records],
            }
        )
    return sorted(groups, key=lambda item: (item["digest"], item["locations"][0]["key"]))


def _body_without_docstring(nodes: Sequence[ast.stmt]) -> list[ast.stmt]:
    if nodes and isinstance(nodes[0], ast.Expr) and isinstance(nodes[0].value, ast.Constant):
        if isinstance(nodes[0].value.value, str):
            return list(nodes[1:])
    return list(nodes)


def _function_digest(body: Sequence[ast.stmt]) -> str:
    normalized = "\n".join(ast.dump(node, include_attributes=False) for node in body)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:16]


def _is_trivial_wrapper(
    node: ast.FunctionDef | ast.AsyncFunctionDef,
    body: Sequence[ast.stmt],
    thresholds: Thresholds,
) -> bool:
    if node.decorator_list or len(body) != 1 or node.name.startswith("__"):
        return False
    statement = body[0]
    call: ast.Call | None = None
    if isinstance(statement, ast.Return) and isinstance(statement.value, ast.Call):
        call = statement.value
    elif isinstance(statement, ast.Expr) and isinstance(statement.value, ast.Call):
        call = statement.value
    if call is None:
        return False
    if not isinstance(call.func, ast.Name | ast.Attribute):
        return False
    if call.keywords:
        return False
    return _passes_through_arguments(node, call)


def _passes_through_arguments(
    node: ast.FunctionDef | ast.AsyncFunctionDef,
    call: ast.Call,
) -> bool:
    parameter_names = [argument.arg for argument in node.args.posonlyargs]
    parameter_names.extend(argument.arg for argument in node.args.args)
    if node.args.vararg is not None:
        parameter_names.append(node.args.vararg.arg)
    parameter_names.extend(argument.arg for argument in node.args.kwonlyargs)
    if node.args.kwarg is not None:
        parameter_names.append(node.args.kwarg.arg)
    forwarded_names: list[str] = []
    for argument in call.args:
        if isinstance(argument, ast.Name):
            forwarded_names.append(argument.id)
        elif isinstance(argument, ast.Starred) and isinstance(argument.value, ast.Name):
            forwarded_names.append(argument.value.id)
        else:
            return False
    return bool(forwarded_names) and forwarded_names == parameter_names[: len(forwarded_names)]


def _logical_loc(text: str) -> int:
    return sum(
        1 for line in text.splitlines() if line.strip() and not line.lstrip().startswith("#")
    )


def _role_for(relative_path: str) -> str:
    parts = relative_path.split("/")
    if "tests" in parts or Path(relative_path).name.startswith("test_"):
        return "test"
    if parts[0] in {"scripts", "tools", "benchmarks"}:
        return "script"
    if len(parts) >= 3 and parts[0] == "packages" and parts[2] == "src":
        return "source"
    return "other"


def _file_line_limit(role: str, thresholds: Thresholds) -> int:
    if role == "test":
        return thresholds.test_file_lines
    if role == "script":
        return thresholds.script_file_lines
    return thresholds.source_file_lines


def _changed_loc_budget(role: str, thresholds: Thresholds) -> int:
    if role == "source":
        return thresholds.changed_source_loc_growth
    if role == "test":
        return thresholds.changed_test_loc_growth
    if role == "script":
        return thresholds.changed_script_loc_growth
    return thresholds.changed_other_loc_growth


def _drift_markers_for_text(text: str) -> list[dict[str, Any]]:
    matches: list[dict[str, Any]] = []
    for line_number, line in enumerate(text.splitlines(), start=1):
        match = DRIFT_MARKER_RE.search(line)
        if match:
            matches.append({"line": line_number, "marker": match.group(0)})
    return matches


def _growth_errors(
    metric: str,
    current_metrics: Mapping[str, Any],
    baseline_metrics: Mapping[str, Any],
    budget: int,
) -> list[str]:
    current = int(current_metrics.get(metric, 0))
    baseline = int(baseline_metrics.get(metric, 0))
    if current <= baseline + budget:
        return []
    return [f"{metric} grew from {baseline} to {current} (budget +{budget})"]


def _mapping(payload: Mapping[str, Any], key: str) -> Mapping[str, Any]:
    value = payload.get(key, {})
    if not isinstance(value, Mapping):
        return {}
    return value


def _as_mapping(payload: object) -> Mapping[str, Any]:
    if not isinstance(payload, Mapping):
        raise ValueError("expected mapping payload")
    return payload


def _mapping_value(payload: object, key: str) -> object:
    if not isinstance(payload, Mapping) or key not in payload:
        raise ValueError(f"expected mapping with key {key!r}")
    return payload[key]


def _threshold_dict(thresholds: Thresholds) -> dict[str, int]:
    return {
        "source_file_lines": thresholds.source_file_lines,
        "test_file_lines": thresholds.test_file_lines,
        "script_file_lines": thresholds.script_file_lines,
        "function_lines": thresholds.function_lines,
        "duplicate_function_lines": thresholds.duplicate_function_lines,
        "oversized_file_growth": thresholds.oversized_file_growth,
        "large_function_growth": thresholds.large_function_growth,
        "total_python_loc_growth": thresholds.total_python_loc_growth,
        "source_python_loc_growth": thresholds.source_python_loc_growth,
        "test_python_loc_growth": thresholds.test_python_loc_growth,
        "script_python_loc_growth": thresholds.script_python_loc_growth,
        "trivial_wrapper_growth": thresholds.trivial_wrapper_growth,
        "changed_function_growth": thresholds.changed_function_growth,
        "changed_source_loc_growth": thresholds.changed_source_loc_growth,
        "changed_test_loc_growth": thresholds.changed_test_loc_growth,
        "changed_script_loc_growth": thresholds.changed_script_loc_growth,
        "changed_other_loc_growth": thresholds.changed_other_loc_growth,
    }


def _resolve_path(root: Path, path: Path) -> Path:
    if path.is_absolute():
        return path
    return root / path


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
