"""Guard ADR 0033 public vocabulary and ADR filename prefixes."""

from __future__ import annotations

import ast
import re
from dataclasses import dataclass
from pathlib import Path

PUBLIC_HANDOFF_RE = re.compile(r"handoff|Handoff|HANDOFF")
ADR_PREFIX_RE = re.compile(r"^(\d{4})-")
ROOT = Path.cwd()

COMPATIBILITY_ALLOWLIST = {
    "ComponentHandoffError",
    "ComponentResultHandoff",
    "CvaResultHandoff",
    "HandoffColumnArray",
    "ManifestHandoffRoute",
    "ManifestHandoffValidation",
    "NormalizedTabularHandoff",
    "STANDARDISED_REQUIRED_HANDOFF_KEYS",
    "TabularHandoffError",
    "ToComponentHandoffCallable",
    "handoff_specs_to_arrow_schema",
    "handoff_specs_to_json_schema",
    "normalized_handoff_hash",
    "read_handoff_columns",
    "to_orchestration_handoff",
}

COMPATIBILITY_ALLOWLIST_PATTERNS = (
    re.compile(r"^[A-Z0-9_]+_HANDOFF$"),
    re.compile(r"^[A-Z0-9_]+_HANDOFF_COLUMN_SPECS$"),
    re.compile(r"^build_[a-z0-9_]+_from_handoff$"),
    re.compile(r"^calculate_sbm_capital_from_[a-z0-9_]+_handoff$"),
    re.compile(r"^calculate_sbm_portfolio_capital_from_handoffs$"),
)


@dataclass(frozen=True)
class Finding:
    path: Path
    symbol: str

    def render(self) -> str:
        return f"{self.path.relative_to(ROOT)}: public handoff symbol {self.symbol!r}"


def main() -> int:
    findings = list(public_handoff_symbol_findings(ROOT / "packages"))
    adr_collisions = duplicate_adr_prefixes(ROOT / "docs" / "decisions")

    for finding in findings:
        print(finding.render())
    for prefix, files in adr_collisions.items():
        joined = ", ".join(path.name for path in files)
        print(f"docs/decisions: duplicate ADR prefix {prefix}: {joined}")

    if findings or adr_collisions:
        return 1
    print("ADR 0033 vocabulary guard passed.")
    return 0


def public_handoff_symbol_findings(packages_root: Path) -> tuple[Finding, ...]:
    findings: list[Finding] = []
    for source in sorted(packages_root.glob("*/src/**/*.py")):
        tree = ast.parse(source.read_text(encoding="utf-8"), filename=str(source))
        for symbol in _public_symbols(tree):
            if PUBLIC_HANDOFF_RE.search(symbol) and not _is_allowed_compatibility(symbol):
                findings.append(Finding(source, symbol))
    return tuple(findings)


def duplicate_adr_prefixes(decisions_dir: Path) -> dict[str, tuple[Path, ...]]:
    by_prefix: dict[str, list[Path]] = {}
    for path in sorted(decisions_dir.glob("*.md")):
        match = ADR_PREFIX_RE.match(path.name)
        if match is None:
            continue
        by_prefix.setdefault(match.group(1), []).append(path)
    return {prefix: tuple(paths) for prefix, paths in by_prefix.items() if len(paths) > 1}


def _public_symbols(tree: ast.Module) -> tuple[str, ...]:
    symbols: list[str] = []
    for node in tree.body:
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
            if not node.name.startswith("_"):
                symbols.append(node.name)
            continue
        if isinstance(node, ast.Assign):
            for target in node.targets:
                symbols.extend(_target_names(target))
            if _assigns_all(node):
                symbols.extend(_string_sequence(node.value))
        elif isinstance(node, ast.AnnAssign):
            symbols.extend(_target_names(node.target))
    return tuple(dict.fromkeys(symbols))


def _target_names(target: ast.expr) -> tuple[str, ...]:
    if isinstance(target, ast.Name) and not target.id.startswith("_"):
        return (target.id,)
    if isinstance(target, ast.Tuple):
        return tuple(
            name
            for child in target.elts
            for name in _target_names(child)
            if not name.startswith("_")
        )
    return ()


def _assigns_all(node: ast.Assign) -> bool:
    return any(isinstance(target, ast.Name) and target.id == "__all__" for target in node.targets)


def _string_sequence(node: ast.expr) -> tuple[str, ...]:
    if isinstance(node, ast.List | ast.Tuple):
        return tuple(
            item.value
            for item in node.elts
            if isinstance(item, ast.Constant) and isinstance(item.value, str)
        )
    return ()


def _is_allowed_compatibility(symbol: str) -> bool:
    return symbol in COMPATIBILITY_ALLOWLIST or any(
        pattern.match(symbol) for pattern in COMPATIBILITY_ALLOWLIST_PATTERNS
    )


if __name__ == "__main__":
    raise SystemExit(main())
