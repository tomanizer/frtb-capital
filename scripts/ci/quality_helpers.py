"""Shared mechanics for repository quality-control scripts."""

from __future__ import annotations

import ast
import os
import subprocess
from collections.abc import Mapping
from pathlib import Path
from typing import Any


def git(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ("git", *args),
        cwd=root,
        check=False,
        capture_output=True,
        text=True,
    )


def merge_base(root: Path, base_ref: str, label: str) -> str:
    result = _resolve_base(root, base_ref)
    if result:
        return result
    _fetch_base_ref(root, base_ref)
    result = _resolve_base(root, base_ref)
    if result:
        return result
    result = git(root, "rev-parse", "--verify", "HEAD^1")
    if result.returncode == 0 and result.stdout.strip():
        return result.stdout.strip()
    raise SystemExit(f"could not resolve {label} base ref: {base_ref}")


def _resolve_base(root: Path, base_ref: str) -> str | None:
    result = git(root, "merge-base", "HEAD", base_ref)
    if result.returncode == 0 and result.stdout.strip():
        return result.stdout.strip()
    result = git(root, "rev-parse", "--verify", base_ref)
    if result.returncode == 0 and result.stdout.strip():
        return result.stdout.strip()
    return None


def _fetch_base_ref(root: Path, base_ref: str) -> None:
    branch = os.environ.get("GITHUB_BASE_REF") or base_ref.removeprefix("origin/")
    if not branch or ("/" in branch and branch.startswith("refs/")):
        return
    git(root, "fetch", "--depth=1", "origin", f"{branch}:refs/remotes/origin/{branch}")


def parent_map(tree: ast.AST) -> dict[ast.AST, ast.AST]:
    parents: dict[ast.AST, ast.AST] = {}
    for parent in ast.walk(tree):
        for child in ast.iter_child_nodes(parent):
            parents[child] = parent
    return parents


def qualified_name(
    node: ast.FunctionDef | ast.AsyncFunctionDef,
    parents: Mapping[ast.AST, ast.AST],
) -> str:
    names = [node.name]
    parent = parents.get(node)
    while parent is not None:
        if isinstance(parent, ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef):
            names.append(parent.name)
        parent = parents.get(parent)
    return ".".join(reversed(names))


def function_payload(record: Any) -> dict[str, Any]:
    return {
        "key": record.key,
        "path": record.path,
        "name": record.name,
        "line": record.line,
        "end_line": record.end_line,
        "lines": record.lines,
    }
