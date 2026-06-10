"""Enforce the committed docstring inventory baseline for hard-gated gaps."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

try:  # Supports direct script execution and package-style test imports.
    from .check_docstring_inventory import SCHEMA_VERSION, build_report
    from .docstring_inventory import DEFAULT_PATHS, DocstringFinding, scan_repo
except ImportError:  # pragma: no cover - exercised by direct script execution.
    from check_docstring_inventory import SCHEMA_VERSION, build_report
    from docstring_inventory import DEFAULT_PATHS, DocstringFinding, scan_repo

DEFAULT_BASELINE = Path("docs/quality/docstrings/baseline.json")
HARD_RULES = frozenset(
    {
        "MISSING_MODULE_DOCSTRING",
        "MISSING_PUBLIC_DOCSTRING",
        "MISSING_PARAMETERS_SECTION",
        "MISSING_RETURNS_SECTION",
    }
)
REPORT_ONLY_RULES = frozenset({"TRIVIAL_DOCSTRING"})
REQUIRED_FINDING_FIELDS = {
    "package",
    "path",
    "line",
    "rule",
    "object_type",
    "object_name",
    "message",
}


@dataclass(frozen=True, order=True)
class FindingKey:
    """Line-independent identity for a docstring finding tracked by the ratchet."""

    package: str
    path: str
    rule: str
    object_type: str
    object_name: str

    def describe(self) -> str:
        """Return a compact location string for quality-control output."""

        return f"{self.path}: {self.rule}: {self.object_type} {self.object_name} ({self.package})"


@dataclass(frozen=True)
class BaselineComparison:
    """Differences between current hard-gated findings and the baseline."""

    new_findings: tuple[FindingKey, ...]
    stale_findings: tuple[FindingKey, ...]

    @property
    def has_errors(self) -> bool:
        """Return whether the baseline ratchet should fail."""

        return bool(self.new_findings or self.stale_findings)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--baseline", type=Path, default=DEFAULT_BASELINE)
    parser.add_argument("--json-output", type=Path)
    parser.add_argument("--paths", nargs="*", default=list(DEFAULT_PATHS))
    parser.add_argument(
        "--update-baseline",
        action="store_true",
        help="Rewrite the committed baseline from the current inventory.",
    )
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args(argv)

    root = args.root.resolve()
    baseline_path = _resolve_path(root, args.baseline)
    findings = scan_repo(root, paths=args.paths)
    report = build_report(findings, paths=args.paths)
    if args.json_output:
        _write_json(args.json_output, report)

    if args.update_baseline:
        _write_json(baseline_path, report)
        if not args.quiet:
            print(f"updated docstring baseline: {baseline_path}")
        return 0

    try:
        baseline = load_baseline(baseline_path)
    except BaselineError as exc:
        print(f"Docstring baseline guard failed: {exc}", file=sys.stderr)
        return 1

    comparison = compare_to_baseline(findings, baseline)
    if comparison.has_errors:
        _print_comparison_errors(comparison)
        return 1

    if not args.quiet:
        tracked_count = len(_hard_keys_from_findings(findings))
        print(f"Docstring baseline guard passed: {tracked_count} hard-gated gap(s) tracked.")
    return 0


class BaselineError(ValueError):
    """Raised when the committed baseline cannot be trusted by the gate."""


def load_baseline(path: Path) -> Mapping[str, Any]:
    """Load and validate a docstring baseline report.

    Parameters
    ----------
    path : Path
        Repository-relative or absolute path to the committed baseline JSON.

    Returns
    -------
    Mapping[str, Any]
        Parsed baseline payload with the expected inventory schema.

    Raises
    ------
    BaselineError
        If the file is missing, malformed, or does not match the inventory
        schema expected by this gate.
    """

    if not path.exists():
        raise BaselineError(f"baseline is missing at {path}; run `make docstring-baseline`")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise BaselineError(f"failed to parse {path}: {exc}") from exc
    validate_baseline(payload)
    return cast(Mapping[str, Any], payload)


def validate_baseline(payload: object) -> None:
    """Validate the baseline shape used by the no-new-gaps ratchet.

    Parameters
    ----------
    payload : object
        Parsed JSON value loaded from the committed baseline.

    Raises
    ------
    BaselineError
        If required schema fields or finding records are missing or invalid.
    """

    if not isinstance(payload, Mapping):
        raise BaselineError("baseline root must be a JSON object")
    payload_map = cast(Mapping[str, Any], payload)
    if payload_map.get("schema_version") != SCHEMA_VERSION:
        raise BaselineError(
            f"unsupported baseline schema_version {payload_map.get('schema_version')!r}"
        )
    packages = payload_map.get("packages")
    if not isinstance(packages, Mapping):
        raise BaselineError("baseline packages must be a JSON object")
    packages_map = cast(Mapping[str, Any], packages)

    seen_keys: set[FindingKey] = set()
    for package, package_payload in packages_map.items():
        if not isinstance(package, str):
            raise BaselineError("baseline package names must be strings")
        if not isinstance(package_payload, Mapping):
            raise BaselineError(f"baseline package {package!r} must be a JSON object")
        package_payload_map = cast(Mapping[str, Any], package_payload)
        findings = package_payload_map.get("findings")
        if not isinstance(findings, list):
            raise BaselineError(f"baseline package {package!r} findings must be a list")
        for index, raw_finding in enumerate(findings):
            finding = _validate_finding(package, index, raw_finding)
            if finding["rule"] not in HARD_RULES:
                continue
            key = _key_from_mapping(finding)
            if key in seen_keys:
                raise BaselineError(f"duplicate hard-gated baseline finding: {key.describe()}")
            seen_keys.add(key)


def compare_to_baseline(
    findings: Sequence[DocstringFinding],
    baseline: Mapping[str, Any],
) -> BaselineComparison:
    """Compare current hard-gated findings with the committed baseline.

    Parameters
    ----------
    findings : Sequence[DocstringFinding]
        Current inventory findings from the AST scanner.
    baseline : Mapping[str, Any]
        Validated baseline report payload.

    Returns
    -------
    BaselineComparison
        New hard-gated gaps and stale tracked gaps.
    """

    current_keys = _hard_keys_from_findings(findings)
    baseline_keys = _hard_keys_from_report(baseline)
    return BaselineComparison(
        new_findings=tuple(sorted(current_keys - baseline_keys)),
        stale_findings=tuple(sorted(baseline_keys - current_keys)),
    )


def _validate_finding(
    package: str,
    index: int,
    raw_finding: object,
) -> Mapping[str, Any]:
    if not isinstance(raw_finding, Mapping):
        raise BaselineError(f"finding {package}[{index}] must be a JSON object")
    finding = cast(Mapping[str, Any], raw_finding)
    missing = REQUIRED_FINDING_FIELDS - set(finding)
    if missing:
        raise BaselineError(
            f"finding {package}[{index}] is missing field(s): {', '.join(sorted(missing))}"
        )
    for field in REQUIRED_FINDING_FIELDS - {"line"}:
        if not isinstance(finding[field], str):
            raise BaselineError(f"finding {package}[{index}].{field} must be a string")
    if not isinstance(finding["line"], int) or finding["line"] < 1:
        raise BaselineError(f"finding {package}[{index}].line must be a positive integer")
    if finding["package"] != package:
        raise BaselineError(f"finding {package}[{index}].package must match its package bucket")
    return finding


def _hard_keys_from_findings(findings: Sequence[DocstringFinding]) -> set[FindingKey]:
    return {
        FindingKey(
            package=finding.package,
            path=finding.path,
            rule=finding.rule,
            object_type=finding.object_type,
            object_name=finding.object_name,
        )
        for finding in findings
        if finding.rule in HARD_RULES
    }


def _hard_keys_from_report(report: Mapping[str, Any]) -> set[FindingKey]:
    keys: set[FindingKey] = set()
    for package_payload in report["packages"].values():
        for finding in package_payload["findings"]:
            if finding["rule"] in HARD_RULES:
                keys.add(_key_from_mapping(finding))
    return keys


def _key_from_mapping(finding: Mapping[str, Any]) -> FindingKey:
    return FindingKey(
        package=finding["package"],
        path=finding["path"],
        rule=finding["rule"],
        object_type=finding["object_type"],
        object_name=finding["object_name"],
    )


def _print_comparison_errors(comparison: BaselineComparison) -> None:
    print("Docstring baseline guard failed:", file=sys.stderr)
    for key in comparison.new_findings:
        print(f"- new hard-gated docstring gap: {key.describe()}", file=sys.stderr)
    for key in comparison.stale_findings:
        print(f"- stale hard-gated baseline entry: {key.describe()}", file=sys.stderr)
    print(
        "Add the missing docstrings, or run `make docstring-baseline` when a "
        "reviewed change intentionally updates the baseline.",
        file=sys.stderr,
    )


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _resolve_path(root: Path, path: Path) -> Path:
    if path.is_absolute():
        return path
    return root / path


if __name__ == "__main__":
    raise SystemExit(main())
