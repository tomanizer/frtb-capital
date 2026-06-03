"""Detect low-value wrapper and helper-surface drift after simplification work."""

from __future__ import annotations

import argparse
import ast
from dataclasses import dataclass
from pathlib import Path

SUPPRESSION_MARKER = "simplify-audit: keep"

BATCH_ARRAY_HELPERS = frozenset(
    {
        "BatchArrayCoercionError",
        "bool_array",
        "coerce_bool_value",
        "float_array_from_numpy",
        "immutable_float_array",
        "immutable_object_array",
        "object_array",
        "optional_bool_object_array",
        "readonly_array",
    }
)
BATCH_ARRAY_FUNCTIONS = BATCH_ARRAY_HELPERS - {"BatchArrayCoercionError"}
ARROW_CONVERSION_FUNCTIONS = frozenset(
    {
        "arrow_bool_array",
        "arrow_bool_or_object_array",
        "arrow_float64_array",
        "arrow_float64_array_with_nulls",
        "arrow_object_array",
        "read_arrow_columns",
    }
)
PASS_THROUGH_TARGETS = {
    "frtb_common.arrow_conversion": ARROW_CONVERSION_FUNCTIONS,
    "frtb_common.batch_arrays": BATCH_ARRAY_FUNCTIONS,
}

BATCH_ALIAS_NAMES = frozenset(
    {
        "ArrayInput",
        "ArrayScalarT",
        "BoolArray",
        "ColumnInput",
        "FloatArray",
        "NullableColumnInput",
        "ObjectArray",
    }
)

STALE_ARROW_CONVERTER_NAMES = frozenset(
    {
        "_arrow_bool_array",
        "_arrow_float64_array",
        "_arrow_float64_array_with_nulls",
        "_arrow_object_array",
        "_bool_array_from_arrow",
        "_bool_array_from_arrow_column",
        "_float64_array_from_arrow",
        "_float64_array_from_arrow_column",
        "_object_array_from_arrow",
        "_object_array_from_arrow_column",
    }
)


@dataclass(frozen=True)
class SimplificationFinding:
    path: Path
    line_number: int
    code: str
    subject: str
    reason: str


@dataclass(frozen=True)
class ImportAliases:
    module_aliases: dict[str, str]
    function_aliases: dict[str, tuple[str, str]]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=Path.cwd(),
        help="Repository root. Defaults to the current working directory.",
    )
    parser.add_argument(
        "--scan-path",
        type=Path,
        action="append",
        default=[],
        help=(
            "File or directory to scan, relative to the repository root. "
            "Defaults to all package runtime source files."
        ),
    )
    parser.add_argument(
        "--report-only",
        action="store_true",
        help="Print findings without failing.",
    )
    args = parser.parse_args(argv)

    repo_root = args.repo_root.resolve()
    findings = check_repo(repo_root, scan_paths=tuple(args.scan_path))
    if findings:
        print("Simplification drift findings:")
        for finding in findings:
            display_path = finding.path.relative_to(repo_root)
            print(
                f"- {display_path}:{finding.line_number} "
                f"{finding.code} {finding.subject}: {finding.reason}"
            )
        return 0 if args.report_only else 1

    print("Simplification drift audit kept")
    return 0


def check_repo(
    repo_root: Path,
    *,
    scan_paths: tuple[Path, ...] = (),
) -> tuple[SimplificationFinding, ...]:
    files = _scan_files(repo_root, scan_paths)
    findings: list[SimplificationFinding] = []
    for path in files:
        findings.extend(_findings_in_file(path, repo_root))
    return tuple(
        sorted(findings, key=lambda item: (item.path.as_posix(), item.line_number, item.code))
    )


def _scan_files(repo_root: Path, scan_paths: tuple[Path, ...]) -> tuple[Path, ...]:
    if scan_paths:
        paths: list[Path] = []
        for raw_path in scan_paths:
            path = raw_path if raw_path.is_absolute() else repo_root / raw_path
            if path.is_dir():
                paths.extend(sorted(path.rglob("*.py")))
            elif path.suffix == ".py":
                paths.append(path)
        return tuple(sorted(path.resolve() for path in paths))

    return tuple(sorted(path.resolve() for path in repo_root.glob("packages/*/src/**/*.py")))


def _findings_in_file(path: Path, repo_root: Path) -> tuple[SimplificationFinding, ...]:
    try:
        source = path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError) as exc:
        return (
            SimplificationFinding(
                path=path,
                line_number=1,
                code="SIMPLIFICATION_AUDIT_READ_ERROR",
                subject=path.name,
                reason=str(exc),
            ),
        )
    lines = source.splitlines()
    try:
        tree = ast.parse(source, filename=str(path))
    except SyntaxError as exc:
        return (
            SimplificationFinding(
                path=path,
                line_number=exc.lineno or 1,
                code="SIMPLIFICATION_AUDIT_PARSE_ERROR",
                subject=path.name,
                reason=str(exc),
            ),
        )

    findings: list[SimplificationFinding] = []
    findings.extend(_missing_suppression_reason_findings(path, lines))
    findings.extend(_common_batch_export_findings(path, repo_root, tree, lines))

    aliases = _import_aliases(tree)
    package_name = _package_name(path, repo_root)
    for node in ast.walk(tree):
        if not isinstance(node, ast.FunctionDef):
            continue
        if _is_suppressed(lines, node):
            continue
        if finding := _pass_through_wrapper_finding(path, node, aliases):
            findings.append(finding)
        if finding := _stale_arrow_converter_finding(path, package_name, node):
            findings.append(finding)

    if path.name == "batch.py":
        findings.extend(_batch_alias_findings(path, tree, aliases, lines))

    return tuple(findings)


def _missing_suppression_reason_findings(
    path: Path,
    lines: list[str],
) -> tuple[SimplificationFinding, ...]:
    findings: list[SimplificationFinding] = []
    for line_number, line in enumerate(lines, start=1):
        if SUPPRESSION_MARKER not in line:
            continue
        if _suppression_reason(line) is None:
            findings.append(
                SimplificationFinding(
                    path=path,
                    line_number=line_number,
                    code="SUPPRESSION_MISSING_REASON",
                    subject=SUPPRESSION_MARKER,
                    reason="suppression marker must include a justification after the marker",
                )
            )
    return tuple(findings)


def _common_batch_export_findings(
    path: Path,
    repo_root: Path,
    tree: ast.Module,
    lines: list[str],
) -> tuple[SimplificationFinding, ...]:
    if path != (repo_root / "packages/frtb-common/src/frtb_common/__init__.py").resolve():
        return ()

    findings: list[SimplificationFinding] = []
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.ImportFrom)
            and _resolved_module(node) == "frtb_common.batch_arrays"
        ):
            if _is_suppressed(lines, node):
                continue
            for alias in node.names:
                if alias.name in BATCH_ARRAY_HELPERS:
                    findings.append(
                        SimplificationFinding(
                            path=path,
                            line_number=node.lineno,
                            code="COMMON_BATCH_TOP_LEVEL_EXPORT",
                            subject=alias.name,
                            reason=(
                                "batch array helpers must stay under "
                                "`frtb_common.batch_arrays`, not top-level `frtb_common`"
                            ),
                        )
                    )
        elif isinstance(node, ast.Assign):
            findings.extend(_all_batch_export_findings(path, node, lines))
    return tuple(findings)


def _all_batch_export_findings(
    path: Path,
    node: ast.Assign,
    lines: list[str],
) -> tuple[SimplificationFinding, ...]:
    if not any(isinstance(target, ast.Name) and target.id == "__all__" for target in node.targets):
        return ()
    if _is_suppressed(lines, node):
        return ()
    if not isinstance(node.value, ast.List | ast.Tuple):
        return ()

    findings: list[SimplificationFinding] = []
    for item in node.value.elts:
        if not isinstance(item, ast.Constant) or not isinstance(item.value, str):
            continue
        if item.value not in BATCH_ARRAY_HELPERS:
            continue
        findings.append(
            SimplificationFinding(
                path=path,
                line_number=item.lineno,
                code="COMMON_BATCH_TOP_LEVEL_EXPORT",
                subject=item.value,
                reason=(
                    "`frtb_common.__all__` must not re-export internal batch array helpers; "
                    "import them from `frtb_common.batch_arrays`"
                ),
            )
        )
    return tuple(findings)


def _pass_through_wrapper_finding(
    path: Path,
    node: ast.FunctionDef,
    aliases: ImportAliases,
) -> SimplificationFinding | None:
    if node.decorator_list or not node.name.startswith("_"):
        return None
    body = _function_body_without_docstring(node)
    if len(body) != 1 or not isinstance(body[0], ast.Return):
        return None
    if not isinstance(body[0].value, ast.Call):
        return None

    target = _call_target(body[0].value, aliases)
    if target is None:
        return None
    module, helper_name = target
    if helper_name not in PASS_THROUGH_TARGETS.get(module, frozenset()):
        return None
    if not _forwards_only_unmodified_parameters(body[0].value, node):
        return None

    return SimplificationFinding(
        path=path,
        line_number=node.lineno,
        code="PASS_THROUGH_COMMON_HELPER_WRAPPER",
        subject=node.name,
        reason=(
            f"function only returns `{module}.{helper_name}(...)` with unmodified parameters; "
            "call the common helper directly or add package-specific behavior"
        ),
    )


def _stale_arrow_converter_finding(
    path: Path,
    package_name: str | None,
    node: ast.FunctionDef,
) -> SimplificationFinding | None:
    if package_name == "frtb-common" or node.name not in STALE_ARROW_CONVERTER_NAMES:
        return None
    return SimplificationFinding(
        path=path,
        line_number=node.lineno,
        code="STALE_ARROW_CONVERTER_REIMPLEMENTATION",
        subject=node.name,
        reason=(
            "private Arrow-to-array converter name matches the stale per-package decoder pattern; "
            "use `frtb_common.arrow_conversion` or `read_arrow_columns`"
        ),
    )


def _batch_alias_findings(
    path: Path,
    tree: ast.Module,
    aliases: ImportAliases,
    lines: list[str],
) -> tuple[SimplificationFinding, ...]:
    has_common_helpers = "frtb_common.batch_arrays" in aliases.module_aliases.values() or any(
        module == "frtb_common.batch_arrays"
        for module, _helper in aliases.function_aliases.values()
    )
    if not has_common_helpers:
        return ()

    findings: list[SimplificationFinding] = []
    for node in ast.walk(tree):
        alias_name = _assigned_name(node)
        if alias_name is None or alias_name not in BATCH_ALIAS_NAMES:
            continue
        if _is_suppressed(lines, node):
            continue
        findings.append(
            SimplificationFinding(
                path=path,
                line_number=node.lineno,
                code="LOCAL_BATCH_ALIAS_WITH_COMMON_HELPERS",
                subject=alias_name,
                reason=(
                    "`batch.py` imports `frtb_common.batch_arrays` but defines local array "
                    "aliases; import aliases from a package `_batch_columns` module or from "
                    "the common helper module"
                ),
            )
        )
    return tuple(findings)


def _import_aliases(tree: ast.Module) -> ImportAliases:
    module_aliases: dict[str, str] = {}
    function_aliases: dict[str, tuple[str, str]] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                module_name = alias.name
                if alias.asname:
                    module_aliases[alias.asname] = module_name
                else:
                    top_level = module_name.split(".", maxsplit=1)[0]
                    module_aliases[top_level] = top_level
        elif isinstance(node, ast.ImportFrom):
            module_name = _resolved_module(node)
            if module_name is None:
                continue
            for alias in node.names:
                local_name = alias.asname or alias.name
                if module_name == "frtb_common" and alias.name in {
                    "arrow_conversion",
                    "batch_arrays",
                }:
                    module_aliases[local_name] = f"frtb_common.{alias.name}"
                elif module_name in PASS_THROUGH_TARGETS:
                    function_aliases[local_name] = (module_name, alias.name)
    return ImportAliases(module_aliases=module_aliases, function_aliases=function_aliases)


def _resolved_module(node: ast.ImportFrom) -> str | None:
    if node.level == 0:
        return node.module
    if node.level == 1 and node.module == "batch_arrays":
        return "frtb_common.batch_arrays"
    return None


def _call_target(call: ast.Call, aliases: ImportAliases) -> tuple[str, str] | None:
    func = call.func
    if isinstance(func, ast.Name):
        return aliases.function_aliases.get(func.id)
    if not isinstance(func, ast.Attribute):
        return None

    if isinstance(func.value, ast.Name):
        module = aliases.module_aliases.get(func.value.id)
        if module in PASS_THROUGH_TARGETS:
            return module, func.attr
    elif (
        isinstance(func.value, ast.Attribute)
        and isinstance(func.value.value, ast.Name)
        and aliases.module_aliases.get(func.value.value.id) == "frtb_common"
    ):
        module = f"frtb_common.{func.value.attr}"
        if module in PASS_THROUGH_TARGETS:
            return module, func.attr
    return None


def _function_body_without_docstring(node: ast.FunctionDef) -> list[ast.stmt]:
    body = list(node.body)
    if (
        body
        and isinstance(body[0], ast.Expr)
        and isinstance(body[0].value, ast.Constant)
        and isinstance(body[0].value.value, str)
    ):
        return body[1:]
    return body


def _forwards_only_unmodified_parameters(call: ast.Call, node: ast.FunctionDef) -> bool:
    args = node.args
    positional_parameters = [arg.arg for arg in (*args.posonlyargs, *args.args)]
    parameter_names = _parameter_names(node)
    forwarded: list[str] = []
    for index, arg in enumerate(call.args):
        if not isinstance(arg, ast.Name):
            return False
        if index >= len(positional_parameters) or arg.id != positional_parameters[index]:
            return False
        forwarded.append(arg.id)
    for keyword in call.keywords:
        if keyword.arg is None or not isinstance(keyword.value, ast.Name):
            return False
        if keyword.arg != keyword.value.id:
            return False
        forwarded.append(keyword.arg)
    return bool(forwarded) and set(forwarded) == parameter_names


def _parameter_names(node: ast.FunctionDef) -> frozenset[str]:
    args = node.args
    names = [arg.arg for arg in (*args.posonlyargs, *args.args, *args.kwonlyargs)]
    if args.vararg is not None:
        names.append(args.vararg.arg)
    if args.kwarg is not None:
        names.append(args.kwarg.arg)
    return frozenset(names)


def _assigned_name(node: ast.AST) -> str | None:
    if (
        isinstance(node, ast.Assign)
        and len(node.targets) == 1
        and isinstance(node.targets[0], ast.Name)
    ):
        return node.targets[0].id
    if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
        return node.target.id
    return None


def _is_suppressed(lines: list[str], node: ast.AST) -> bool:
    start = getattr(node, "lineno", 1) or 1
    end = getattr(node, "end_lineno", None) or start
    return any(
        SUPPRESSION_MARKER in line and _suppression_reason(line) is not None
        for line in lines[start - 1 : end]
    )


def _suppression_reason(line: str) -> str | None:
    if SUPPRESSION_MARKER not in line:
        return None
    reason = line.split(SUPPRESSION_MARKER, maxsplit=1)[1].strip()
    reason = reason.lstrip(":- \t").strip()
    return reason or None


def _package_name(path: Path, repo_root: Path) -> str | None:
    try:
        relative = path.relative_to(repo_root)
    except ValueError:
        return None
    if len(relative.parts) >= 2 and relative.parts[0] == "packages":
        return relative.parts[1]
    return None


if __name__ == "__main__":
    raise SystemExit(main())
