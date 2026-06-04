"""Inventory runtime package docstring gaps without enforcing a full cleanup."""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

try:  # Supports direct script execution and package-style test imports.
    from .docstring_inventory import DEFAULT_PATHS, DocstringFinding, scan_repo
except ImportError:  # pragma: no cover - exercised by direct script execution.
    from docstring_inventory import DEFAULT_PATHS, DocstringFinding, scan_repo

SCHEMA_VERSION = 1


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--json-output", type=Path)
    parser.add_argument("--package", help="Scan one package directory name, such as frtb-sbm.")
    parser.add_argument("--paths", nargs="*", default=list(DEFAULT_PATHS))
    parser.add_argument(
        "--fail-on-findings",
        action="store_true",
        help="Return non-zero when findings exist. Default report mode exits zero.",
    )
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args(argv)

    root = args.root.resolve()
    findings = scan_repo(root, paths=args.paths, package=args.package)
    report = build_report(findings, paths=args.paths)
    if args.json_output:
        _write_json(args.json_output, report)
    if not args.quiet:
        _print_report(findings, report)
    return 1 if findings and args.fail_on_findings else 0


def build_report(
    findings: Sequence[DocstringFinding],
    *,
    paths: Sequence[str] = DEFAULT_PATHS,
) -> dict[str, Any]:
    """Return a deterministic JSON-ready report payload."""

    by_package: dict[str, list[DocstringFinding]] = defaultdict(list)
    by_rule = Counter(finding.rule for finding in findings)
    for finding in findings:
        by_package[finding.package].append(finding)
    return {
        "schema_version": SCHEMA_VERSION,
        "description": "Runtime package docstring inventory report.",
        "paths": list(paths),
        "metrics": {
            "total_findings": len(findings),
            "packages_with_findings": len(by_package),
            "findings_by_rule": dict(sorted(by_rule.items())),
        },
        "packages": {
            package: {
                "finding_count": len(package_findings),
                "findings": [_finding_payload(finding) for finding in package_findings],
            }
            for package, package_findings in sorted(by_package.items())
        },
    }


def _finding_payload(finding: DocstringFinding) -> dict[str, object]:
    return {
        "package": finding.package,
        "path": finding.path,
        "line": finding.line,
        "rule": finding.rule,
        "object_type": finding.object_type,
        "object_name": finding.object_name,
        "message": finding.message,
    }


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _print_report(findings: Sequence[DocstringFinding], report: Mapping[str, Any]) -> None:
    metrics = report["metrics"]
    print(
        "docstring inventory: "
        f"{metrics['total_findings']} finding(s) across "
        f"{metrics['packages_with_findings']} package(s)"
    )
    for finding in findings:
        print(
            f"{finding.path}:{finding.line}: {finding.rule}: "
            f"{finding.object_name}: {finding.message}"
        )


if __name__ == "__main__":
    raise SystemExit(main())
