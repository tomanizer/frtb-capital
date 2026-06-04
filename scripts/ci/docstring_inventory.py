"""AST mechanics for runtime package docstring inventory."""

from __future__ import annotations

import ast
import re
import tomllib
from collections import defaultdict
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTRY_PATH = Path("docs/quality/package_maturity.toml")
DEFAULT_PATHS = ("packages",)
SECTION_UNDERLINE = re.compile(r"^-{3,}\s*$")
GENERIC_VERBS = {
    "aggregate",
    "build",
    "calculate",
    "check",
    "compute",
    "convert",
    "create",
    "load",
    "parse",
    "return",
    "validate",
}
TRIVIAL_DOCSTRINGS = {
    "todo",
    "tbd",
    "placeholder",
}


@dataclass(frozen=True)
class PackageContext:
    package: str
    path: Path
    src_path: Path
    exported_names: frozenset[str]
    maturity_names: frozenset[str]

    def is_exported(self, name: str) -> bool:
        return name in self.exported_names or name in self.maturity_names


@dataclass(frozen=True)
class DocstringFinding:
    package: str
    path: str
    rule: str
    object_type: str
    object_name: str
    line: int
    message: str

    @property
    def key(self) -> tuple[str, str, int, str, str]:
        return (self.package, self.path, self.line, self.rule, self.object_name)


def scan_repo(
    root: Path = ROOT,
    *,
    paths: Sequence[str] = DEFAULT_PATHS,
    package: str | None = None,
) -> tuple[DocstringFinding, ...]:
    """Return package-scoped docstring inventory findings."""

    contexts = _package_contexts(root)
    if package is not None:
        contexts = {name: context for name, context in contexts.items() if name == package}
    scan_roots = [_resolve_path(root, path) for path in paths]
    findings: list[DocstringFinding] = []
    for context in sorted(contexts.values(), key=lambda item: item.package):
        if not _under_any(context.path, scan_roots):
            continue
        for path in _runtime_python_files(context):
            findings.extend(_scan_module(root, context, path))
    return tuple(sorted(findings, key=lambda finding: finding.key))


def _scan_module(
    root: Path,
    context: PackageContext,
    path: Path,
) -> tuple[DocstringFinding, ...]:
    relative = path.relative_to(root).as_posix()
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        return (
            _finding(
                context,
                relative,
                "READ_ERROR",
                "module",
                _module_name(context, path),
                1,
                f"Could not read module as UTF-8: {exc}",
            ),
        )
    try:
        tree = ast.parse(text, filename=relative)
    except SyntaxError as exc:
        return (
            _finding(
                context,
                relative,
                "PARSE_ERROR",
                "module",
                _module_name(context, path),
                exc.lineno or 1,
                f"Could not parse module: {exc.msg}",
            ),
        )

    findings: list[DocstringFinding] = []
    module_name = _module_name(context, path)
    module_docstring = ast.get_docstring(tree)
    if not _has_meaningful_docstring(module_docstring):
        findings.append(
            _finding(
                context,
                relative,
                "MISSING_MODULE_DOCSTRING",
                "module",
                module_name,
                1,
                "Runtime package module is missing a module docstring.",
            )
        )

    for node in tree.body:
        if isinstance(node, ast.ClassDef):
            is_public = _is_public_top_level(node.name, context)
            if is_public:
                findings.extend(_class_findings(context, relative, node))
        elif isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            if _is_public_top_level(node.name, context):
                findings.extend(_callable_findings(context, relative, node, "function", node.name))
    return tuple(findings)


def _class_findings(
    context: PackageContext,
    relative: str,
    node: ast.ClassDef,
) -> tuple[DocstringFinding, ...]:
    findings: list[DocstringFinding] = []
    docstring = ast.get_docstring(node)
    if not _has_meaningful_docstring(docstring):
        findings.append(
            _finding(
                context,
                relative,
                "MISSING_PUBLIC_DOCSTRING",
                "class",
                node.name,
                node.lineno,
                "Public class is missing a docstring.",
            )
        )
    elif _is_trivial_docstring(node.name, docstring):
        findings.append(
            _finding(
                context,
                relative,
                "TRIVIAL_DOCSTRING",
                "class",
                node.name,
                node.lineno,
                "Public class docstring appears to restate the class name.",
            )
        )

    for child in node.body:
        if isinstance(child, ast.FunctionDef | ast.AsyncFunctionDef) and _is_public_method(
            child.name
        ):
            method_name = f"{node.name}.{child.name}"
            findings.extend(_callable_findings(context, relative, child, "method", method_name))
    return tuple(findings)


def _callable_findings(
    context: PackageContext,
    relative: str,
    node: ast.FunctionDef | ast.AsyncFunctionDef,
    object_type: str,
    object_name: str,
) -> tuple[DocstringFinding, ...]:
    findings: list[DocstringFinding] = []
    docstring = ast.get_docstring(node)
    if not _has_meaningful_docstring(docstring):
        findings.append(
            _finding(
                context,
                relative,
                "MISSING_PUBLIC_DOCSTRING",
                object_type,
                object_name,
                node.lineno,
                f"Public {object_type} is missing a docstring.",
            )
        )
        return tuple(findings)

    if _is_trivial_docstring(node.name, docstring):
        findings.append(
            _finding(
                context,
                relative,
                "TRIVIAL_DOCSTRING",
                object_type,
                object_name,
                node.lineno,
                f"Public {object_type} docstring appears to restate the callable name.",
            )
        )
    if _has_documented_parameters(node) and not _has_numpy_section(docstring, "Parameters"):
        findings.append(
            _finding(
                context,
                relative,
                "MISSING_PARAMETERS_SECTION",
                object_type,
                object_name,
                node.lineno,
                f"Public {object_type} has parameters but no NumPy Parameters section.",
            )
        )
    if _has_meaningful_return(node) and not _has_return_or_yield_section(docstring):
        findings.append(
            _finding(
                context,
                relative,
                "MISSING_RETURNS_SECTION",
                object_type,
                object_name,
                node.lineno,
                f"Public {object_type} returns a value but no NumPy Returns section.",
            )
        )
    return tuple(findings)


def _package_contexts(root: Path) -> dict[str, PackageContext]:
    maturity_names = _maturity_public_names(root)
    contexts: dict[str, PackageContext] = {}
    for package_dir in sorted((root / "packages").glob("*")):
        src_path = package_dir / "src"
        if not package_dir.is_dir() or not src_path.is_dir():
            continue
        package = package_dir.name
        contexts[package] = PackageContext(
            package=package,
            path=package_dir,
            src_path=src_path,
            exported_names=frozenset(_exported_names(src_path)),
            maturity_names=frozenset(maturity_names.get(package, set())),
        )
    return contexts


def _maturity_public_names(root: Path) -> dict[str, set[str]]:
    registry = root / REGISTRY_PATH
    if not registry.exists():
        return {}
    data = tomllib.loads(registry.read_text(encoding="utf-8"))
    names: dict[str, set[str]] = defaultdict(set)
    for raw_package in data.get("packages", []):
        if not isinstance(raw_package, dict):
            continue
        package = raw_package.get("package")
        if not isinstance(package, str):
            continue
        for field in ("metadata_object", "calculation_entrypoint"):
            raw_name = raw_package.get(field)
            if isinstance(raw_name, str) and ":" in raw_name:
                names[package].add(raw_name.split(":", 1)[1].split(".", 1)[0])
    return names


def _exported_names(src_path: Path) -> set[str]:
    names: set[str] = set()
    for init_path in sorted(src_path.glob("*/__init__.py")):
        try:
            tree = ast.parse(init_path.read_text(encoding="utf-8"), filename=str(init_path))
        except (SyntaxError, UnicodeDecodeError):
            continue
        names.update(_all_literal_names(tree))
        for node in tree.body:
            if isinstance(node, ast.ImportFrom):
                for alias in node.names:
                    if alias.name == "*":
                        continue
                    name = alias.asname or alias.name
                    if not name.startswith("_"):
                        names.add(name)
            elif isinstance(node, ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef):
                if not node.name.startswith("_"):
                    names.add(node.name)
            elif isinstance(node, ast.Assign | ast.AnnAssign):
                for name in _assigned_names(node):
                    if not name.startswith("_"):
                        names.add(name)
    return names


def _all_literal_names(tree: ast.Module) -> set[str]:
    names: set[str] = set()
    for node in tree.body:
        value: ast.AST | None = None
        if isinstance(node, ast.Assign) and any(
            _is_name(target, "__all__") for target in node.targets
        ):
            value = node.value
        elif isinstance(node, ast.AnnAssign) and _is_name(node.target, "__all__"):
            value = node.value
        if value is not None:
            names.update(_string_literals(value))
    return names


def _string_literals(node: ast.AST) -> set[str]:
    if isinstance(node, ast.List | ast.Tuple | ast.Set):
        return {
            element.value
            for element in node.elts
            if isinstance(element, ast.Constant) and isinstance(element.value, str)
        }
    return set()


def _assigned_names(node: ast.Assign | ast.AnnAssign) -> set[str]:
    targets: Iterable[ast.AST]
    if isinstance(node, ast.Assign):
        targets = node.targets
    else:
        targets = (node.target,)
    names: set[str] = set()
    for target in targets:
        if isinstance(target, ast.Name):
            names.add(target.id)
    return names


def _runtime_python_files(context: PackageContext) -> tuple[Path, ...]:
    return tuple(
        sorted(path for path in context.src_path.rglob("*.py") if "__pycache__" not in path.parts)
    )


def _is_public_top_level(name: str, context: PackageContext) -> bool:
    return context.is_exported(name) or not name.startswith("_")


def _is_public_method(name: str) -> bool:
    return not name.startswith("_") and not (name.startswith("__") and name.endswith("__"))


def _has_meaningful_docstring(docstring: str | None) -> bool:
    return bool(docstring and docstring.strip())


def _has_documented_parameters(node: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    args = [
        *node.args.posonlyargs,
        *node.args.args,
        *node.args.kwonlyargs,
    ]
    names = [arg.arg for arg in args]
    if node.args.vararg is not None:
        names.append(node.args.vararg.arg)
    if node.args.kwarg is not None:
        names.append(node.args.kwarg.arg)
    return any(name not in {"self", "cls"} for name in names)


def _has_meaningful_return(node: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    if node.returns is not None and not _is_none_annotation(node.returns):
        return True
    return any(
        isinstance(child, ast.Return)
        and child.value is not None
        and not _is_none_constant(child.value)
        for child in _walk_function_body(node)
    )


def _walk_function_body(node: ast.FunctionDef | ast.AsyncFunctionDef) -> Iterable[ast.AST]:
    stack = list(reversed(node.body))
    while stack:
        child = stack.pop()
        yield child
        if isinstance(child, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef | ast.Lambda):
            continue
        stack.extend(reversed(list(ast.iter_child_nodes(child))))


def _is_none_annotation(node: ast.AST) -> bool:
    if _is_none_constant(node):
        return True
    if isinstance(node, ast.Name):
        return node.id == "None"
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value == "None"
    return False


def _is_none_constant(node: ast.AST) -> bool:
    return isinstance(node, ast.Constant) and node.value is None


def _has_numpy_section(docstring: str, section: str) -> bool:
    lines = [line.strip() for line in docstring.splitlines()]
    for index, line in enumerate(lines[:-1]):
        if line == section and SECTION_UNDERLINE.match(lines[index + 1]):
            return True
    return False


def _has_return_or_yield_section(docstring: str) -> bool:
    return _has_numpy_section(docstring, "Returns") or _has_numpy_section(docstring, "Yields")


def _is_trivial_docstring(name: str, docstring: str) -> bool:
    first_line = docstring.strip().splitlines()[0].strip().strip(".")
    normalized = " ".join(_tokens(first_line))
    if normalized in TRIVIAL_DOCSTRINGS:
        return True
    name_tokens = _name_tokens(name)
    doc_tokens = _tokens(first_line)
    if doc_tokens == name_tokens:
        return True
    return len(doc_tokens) > 1 and doc_tokens[0] in GENERIC_VERBS and doc_tokens[1:] == name_tokens


def _name_tokens(name: str) -> list[str]:
    return _tokens(re.sub(r"(?<!^)(?=[A-Z])", " ", name.replace("_", " ")))


def _tokens(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", text.lower())


def _module_name(context: PackageContext, path: Path) -> str:
    relative = path.relative_to(context.src_path)
    if relative.name == "__init__.py":
        return ".".join(relative.parent.parts) or context.package
    return ".".join((*relative.parent.parts, relative.stem))


def _finding(
    context: PackageContext,
    relative: str,
    rule: str,
    object_type: str,
    object_name: str,
    line: int,
    message: str,
) -> DocstringFinding:
    return DocstringFinding(
        package=context.package,
        path=relative,
        rule=rule,
        object_type=object_type,
        object_name=object_name,
        line=line,
        message=message,
    )


def _resolve_path(root: Path, path: str) -> Path:
    return (root / path).resolve()


def _under_any(path: Path, roots: Sequence[Path]) -> bool:
    resolved = path.resolve()
    return any(resolved.is_relative_to(root) for root in roots)


def _is_name(node: ast.AST, name: str) -> bool:
    return isinstance(node, ast.Name) and node.id == name
