"""Classify changed paths for GitHub Actions job selection."""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path


def _git_lines(args: list[str]) -> list[str]:
    result = subprocess.run(
        ["git", *args],
        check=True,
        text=True,
        encoding="utf-8",
        stdout=subprocess.PIPE,
    )
    return [line for line in result.stdout.splitlines() if line]


def _diff_name_only(diff_base: str) -> list[str]:
    try:
        return _git_lines(["diff", "--name-only", f"{diff_base}...HEAD"])
    except subprocess.CalledProcessError:
        return _git_lines(["diff", "--name-only", diff_base, "HEAD"])


def _changed_paths() -> tuple[str, set[str]]:
    event_name = os.environ.get("GITHUB_EVENT_NAME", "")
    if event_name == "schedule":
        return event_name, set()

    if event_name != "pull_request":
        return event_name, set(_git_lines(["ls-files"]))

    event_path = os.environ.get("GITHUB_EVENT_PATH")
    base_ref = os.environ.get("GITHUB_BASE_REF", "main")
    base_sha = ""
    if event_path:
        payload = json.loads(Path(event_path).read_text())
        base_sha = payload.get("pull_request", {}).get("base", {}).get("sha", "")

    diff_base = ""
    if base_sha:
        exists = subprocess.run(
            ["git", "rev-parse", "--verify", "--quiet", f"{base_sha}^0"],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        if exists.returncode == 0:
            diff_base = base_sha
        else:
            fetch = subprocess.run(
                ["git", "fetch", "--depth=1", "origin", base_sha],
                check=False,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            if fetch.returncode == 0:
                diff_base = base_sha

    if not diff_base:
        diff_base = f"origin/{base_ref}"
        exists = subprocess.run(
            ["git", "rev-parse", "--verify", "--quiet", diff_base],
            check=False,
            stdout=subprocess.DEVNULL,
        )
        if exists.returncode != 0:
            subprocess.run(["git", "fetch", "origin", base_ref], check=True)

    return event_name, set(_diff_name_only(diff_base))


def _matches(path: str, prefixes: tuple[str, ...], suffixes: tuple[str, ...] = ()) -> bool:
    return path.startswith(prefixes) or path.endswith(suffixes)


def _is_agent_instruction_path(path: str) -> bool:
    return (
        path == ".github/copilot-instructions.md"
        or path.startswith(".github/instructions/")
        or path.startswith(".cursor/")
        or path.startswith(".grok/")
    )


def _is_runtime_or_test_path(path: str) -> bool:
    parts = Path(path).parts
    return (
        len(parts) >= 3
        and parts[0] == "packages"
        and not path.endswith((".md", ".yml", ".yaml", ".ipynb"))
        and ("src" in parts or "tests" in parts or path.endswith("/pyproject.toml"))
    )


def _classify(paths: set[str], event_name: str) -> dict[str, bool]:
    if event_name == "schedule":
        return {
            "full": False,
            "docs": False,
            "code": False,
            "test": False,
            "dependency": True,
            "notebooks": False,
            "examples": False,
            "workflow": False,
        }

    full = event_name != "pull_request"
    workflow = any(_matches(path, (".github/workflows/", "scripts/ci/")) for path in paths)
    dependency = any(
        path in {"pyproject.toml", "uv.lock", ".github/dependabot.yml"}
        or path.endswith("/pyproject.toml")
        for path in paths
    )
    agent_instructions = any(_is_agent_instruction_path(path) for path in paths)
    code = any(
        _matches(
            path,
            (
                "packages/",
                "scripts/",
            ),
        )
        and not path.endswith((".md", ".yml", ".yaml", ".ipynb"))
        for path in paths
    ) or any(path in {"Makefile", "pyproject.toml", "uv.lock"} for path in paths)
    test = any(
        _is_runtime_or_test_path(path)
        or (path.startswith("tests/") and not path.endswith((".md", ".yml", ".yaml", ".ipynb")))
        or (path.startswith("scripts/") and path.endswith(".py"))
        or path in {"Makefile", "pyproject.toml", "uv.lock"}
        for path in paths
    )
    docs = any(
        path.endswith((".md", ".yml", ".yaml"))
        or path.startswith(("docs/", ".github/PULL_REQUEST_TEMPLATE.md"))
        or _is_agent_instruction_path(path)
        for path in paths
    )
    notebooks = any(
        path.startswith("packages/frtb-ima/notebooks/")
        or path.startswith("packages/frtb-ima/tests/fixtures/")
        or path.startswith("packages/frtb-ima/src/")
        or path in {"packages/frtb-ima/pyproject.toml", "uv.lock"}
        or path.startswith("packages/frtb-ima/scripts/")
        for path in paths
    )
    examples = any(
        path.startswith("packages/frtb-ima/examples/")
        or path.startswith("packages/frtb-ima/src/")
        or path.startswith("packages/frtb-ima/tests/fixtures/")
        or path in {"packages/frtb-ima/pyproject.toml", "uv.lock"}
        for path in paths
    )

    if full or workflow:
        return {
            "full": full,
            "docs": True,
            "code": True,
            "test": True,
            "dependency": True,
            "notebooks": True,
            "examples": True,
            "workflow": workflow,
        }

    return {
        "full": False,
        "docs": docs,
        "code": code or dependency or agent_instructions,
        "test": test or dependency,
        "dependency": dependency,
        "notebooks": notebooks,
        "examples": examples,
        "workflow": workflow,
    }


def _write_outputs(outputs: dict[str, bool], paths: set[str]) -> None:
    output_path = os.environ.get("GITHUB_OUTPUT")
    lines = [f"{key}={str(value).lower()}" for key, value in sorted(outputs.items())]
    lines.append(f"changed_count={len(paths)}")
    if output_path:
        with Path(output_path).open("a", encoding="utf-8") as handle:
            for line in lines:
                handle.write(f"{line}\n")
    else:
        for line in lines:
            print(line)


def main() -> None:
    event_name, paths = _changed_paths()
    outputs = _classify(paths, event_name)
    _write_outputs(outputs, paths)


if __name__ == "__main__":
    main()
