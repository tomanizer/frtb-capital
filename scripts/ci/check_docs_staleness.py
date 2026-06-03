"""Flag stale roadmap and risky placeholder wording in current evidence docs."""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

CURRENT_DOC_GLOBS = (
    "docs/README.md",
    "docs/VALIDATION_PACK.md",
    "docs/modules/README.md",
    "docs/modules/*/README.md",
    "docs/modules/*/PRD.md",
    "docs/modules/*/PUBLIC_API.md",
    "docs/modules/*/REGULATORY_REQUIREMENTS.md",
    "docs/modules/*/MODEL_DOCUMENTATION.md",
    "docs/modules/*/model_documentation/*.md",
    "docs/regulatory/profiles/*.md",
    "docs/quality/PACKAGE_STATUS.md",
    "packages/*/docs/*.md",
)

ALLOWLIST_PATHS = {
    Path("docs/DOCUMENTATION_OWNERSHIP.md"),
    Path("docs/DOCUMENTATION_AUDIT.md"),
    Path("docs/regulatory/CORPUS_POLICY.md"),
    Path("docs/quality/QUALITY_CONTROL_PLANE_REQUIREMENTS.md"),
}

PLACEHOLDER_ALLOWED_CONTEXT = (
    "fail closed",
    "fail-closed",
    "unsupported",
    "must not",
    "do not use",
    "does not make",
    "not silently",
    "source status",
    "status value",
    "historical",
    "manifest",
)


@dataclass(frozen=True)
class Finding:
    path: Path
    line_number: int
    rule: str
    line: str


STALE_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "stale-scaffold-status",
        re.compile(r"\b(importable scaffolds?|scaffolded packages?)\b", re.IGNORECASE),
    ),
    (
        "future-docs-needed",
        re.compile(
            r"^(?=.*\b(?:future docs?|future documentation|validation-pack pages?)\b)"
            r"(?=.*\b(?:need|needs|should|must|will)\b)"
            r"(?=.*\b(?:add|added|create|created|exist)\b)",
            re.IGNORECASE,
        ),
    ),
    (
        "future-package-work",
        re.compile(r"\bfuture package work\b", re.IGNORECASE),
    ),
    (
        "no-validation-pack-yet",
        re.compile(r"\bno model validation pack yet\b", re.IGNORECASE),
    ),
    (
        "generic-prototype-wording",
        re.compile(
            r"\bprototype outputs\b|\bprototype model-validation evidence\b|"
            r"\bprototype regulatory capital\b",
            re.IGNORECASE,
        ),
    ),
)

PLACEHOLDER_PATTERN = re.compile(r"\bplaceholders?\b", re.IGNORECASE)


def _is_allowlisted(path: Path) -> bool:
    try:
        relative = path.relative_to(ROOT)
    except ValueError:
        return False
    return relative in ALLOWLIST_PATHS


def _iter_scan_files() -> list[Path]:
    files: set[Path] = set()
    for pattern in CURRENT_DOC_GLOBS:
        for path in ROOT.glob(pattern):
            if path.is_file() and not _is_allowlisted(path):
                files.add(path)
    return sorted(files)


def _placeholder_is_allowed(line: str) -> bool:
    lowered = line.lower()
    return any(token in lowered for token in PLACEHOLDER_ALLOWED_CONTEXT)


def scan_file(path: Path) -> list[Finding]:
    """Return staleness findings for one Markdown file."""

    findings: list[Finding] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        stripped = line.strip()
        for rule, pattern in STALE_PATTERNS:
            if pattern.search(stripped):
                findings.append(
                    Finding(path=path, line_number=line_number, rule=rule, line=stripped)
                )
        if PLACEHOLDER_PATTERN.search(stripped) and not _placeholder_is_allowed(stripped):
            findings.append(
                Finding(
                    path=path,
                    line_number=line_number,
                    rule="placeholder-without-status",
                    line=stripped,
                )
            )
    return findings


def scan_current_docs() -> list[Finding]:
    """Return findings across the configured current evidence docs."""

    findings: list[Finding] = []
    for path in _iter_scan_files():
        findings.extend(scan_file(path))
    return findings


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args(argv)

    findings = scan_current_docs()
    if findings:
        print(
            "ERROR: risky documentation staleness wording found. "
            "Link to the canonical source, mark the page historical, or tie "
            "placeholder/status wording to explicit fail-closed behavior.",
            file=sys.stderr,
        )
        for finding in findings:
            relative = finding.path.relative_to(ROOT)
            print(
                f"ERROR: {relative}:{finding.line_number}: {finding.rule}: {finding.line}",
                file=sys.stderr,
            )
        return 1

    print("documentation staleness lint: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
