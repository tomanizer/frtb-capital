"""Check local Markdown links without external dependencies."""

from __future__ import annotations

import re
from pathlib import Path

LINK_RE = re.compile(r"(?<!!)\[[^\]]+\]\(([^)]+)\)")
SKIP_PREFIXES = ("#", "http://", "https://", "mailto:")


def _markdown_files(root: Path) -> list[Path]:
    return sorted(
        path
        for path in root.rglob("*.md")
        if ".git" not in path.parts and ".venv" not in path.parts
    )


def _base_dir(root: Path, path: Path) -> Path:
    if path.relative_to(root).as_posix() == ".github/PULL_REQUEST_TEMPLATE.md":
        return root
    return path.parent


def _target_exists(root: Path, source: Path, target: str) -> bool:
    target = target.strip()
    if not target or target.startswith(SKIP_PREFIXES):
        return True
    target = target.split("#", 1)[0]
    if not target:
        return True
    if target.startswith("<") and target.endswith(">"):
        target = target[1:-1]
    return (_base_dir(root, source) / target).resolve().exists()


def main() -> None:
    root = Path.cwd().resolve()
    missing: list[tuple[Path, str]] = []
    files = _markdown_files(root)
    for path in files:
        text = path.read_text(encoding="utf-8")
        for match in LINK_RE.finditer(text):
            target = match.group(1)
            if not _target_exists(root, path, target):
                missing.append((path.relative_to(root), target))

    if missing:
        for path, target in missing:
            print(f"{path}: missing {target}")
        raise SystemExit(1)

    print(f"checked {len(files)} markdown files; all local links resolve")


if __name__ == "__main__":
    main()
