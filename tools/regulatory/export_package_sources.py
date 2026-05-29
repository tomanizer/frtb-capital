from __future__ import annotations

import argparse
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SOURCES = ROOT / "docs" / "regulatory" / "sources.yml"
CROSSWALK_DIR = ROOT / "docs" / "regulatory" / "crosswalk"


def clean_scalar(value: str) -> str:
    return value.split(" #", 1)[0].strip().strip("'\"")


def source_blocks() -> dict[str, list[str]]:
    lines = SOURCES.read_text(encoding="utf-8").splitlines()
    blocks: dict[str, list[str]] = {}
    current_id: str | None = None
    current: list[str] = []

    for line in lines:
        if line.startswith("  - id: "):
            if current_id is not None:
                blocks[current_id] = current
            current_id = clean_scalar(line.split(":", 1)[1])
            current = [line]
        elif current_id is not None:
            current.append(line)

    if current_id is not None:
        blocks[current_id] = current
    return blocks


def source_refs(component: str) -> list[str]:
    crosswalk = CROSSWALK_DIR / f"{component}.yml"
    lines = crosswalk.read_text(encoding="utf-8").splitlines()
    refs: list[str] = []
    collecting = False
    key_indent = 0

    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue

        if stripped == "source_refs:":
            collecting = True
            key_indent = len(line) - len(line.lstrip())
            continue

        if not collecting:
            continue

        indent = len(line) - len(line.lstrip())
        if stripped.startswith("- "):
            ref = clean_scalar(stripped[2:])
            if ref not in refs:
                refs.append(ref)
            continue

        if indent <= key_indent:
            collecting = False

    return refs


def render_manifest(component: str) -> str:
    blocks = source_blocks()
    refs = source_refs(component)
    missing = [ref for ref in refs if ref not in blocks]
    if missing:
        missing_csv = ", ".join(missing)
        raise ValueError(f"unknown source refs for {component}: {missing_csv}")

    header = [
        "schema_version: 1",
        f"name: {component.upper().replace('-', '_')}_REGULATORY_SOURCES",
        f"component: {component}",
        "suite_source_register: docs/regulatory/sources.yml",
        "derivation_status: generated_from_suite_corpus",
        "sources:",
    ]
    body: list[str] = []
    for ref in refs:
        body.extend(blocks[ref])
    return "\n".join(header + body) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Export package-local regulatory sources.")
    parser.add_argument("component", help="Component id, for example frtb-ima or frtb-sbm")
    parser.add_argument("--output", type=Path, help="Optional output path. Defaults to stdout.")
    args = parser.parse_args()

    rendered = render_manifest(args.component)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
