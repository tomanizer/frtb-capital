from __future__ import annotations

import subprocess
from pathlib import Path

from scripts.ci.check_dead_code import build_report, collect_dead_code_errors


def test_dead_code_guard_detects_unused_changed_private_function(tmp_path: Path) -> None:
    _init_repo(tmp_path)
    module = _runtime_module(tmp_path, "capital.py")
    module.write_text(
        """
def public_entrypoint() -> int:
    return 1


def _unused_helper() -> int:
    return 2
""".lstrip(),
        encoding="utf-8",
    )

    report = build_report(tmp_path, "HEAD", ["packages"])
    errors = collect_dead_code_errors(report)

    assert any("_unused_helper" in error and "no external reference" in error for error in errors)


def test_dead_code_guard_allows_private_function_referenced_by_test(tmp_path: Path) -> None:
    _init_repo(tmp_path)
    module = _runtime_module(tmp_path, "capital.py")
    module.write_text(
        """
def _helper() -> int:
    return 2
""".lstrip(),
        encoding="utf-8",
    )
    tests_dir = tmp_path / "packages" / "demo" / "tests"
    tests_dir.mkdir(parents=True)
    (tests_dir / "test_capital.py").write_text(
        """
from demo.capital import _helper


def test_helper() -> None:
    assert _helper() == 2
""".lstrip(),
        encoding="utf-8",
    )

    report = build_report(tmp_path, "HEAD", ["packages"])
    errors = collect_dead_code_errors(report)

    assert errors == []


def test_dead_code_guard_detects_unreferenced_runtime_module(tmp_path: Path) -> None:
    _init_repo(tmp_path)
    module = _runtime_module(tmp_path, "_new_module.py")
    module.write_text("VALUE = 1\n", encoding="utf-8")

    report = build_report(tmp_path, "HEAD", ["packages"])
    errors = collect_dead_code_errors(report)

    assert any("new runtime module is not imported" in error for error in errors)


def test_dead_code_guard_resolves_relative_imported_runtime_module(tmp_path: Path) -> None:
    _init_repo(tmp_path)
    module = _runtime_module(tmp_path, "_new_module.py")
    module.write_text("VALUE = 1\n", encoding="utf-8")
    package_init = module.parent / "__init__.py"
    package_init.write_text("from . import _new_module\n", encoding="utf-8")

    report = build_report(tmp_path, "HEAD", ["packages"])
    errors = collect_dead_code_errors(report)

    assert errors == []


def _runtime_module(root: Path, name: str) -> Path:
    source = root / "packages" / "demo" / "src" / "demo"
    source.mkdir(parents=True, exist_ok=True)
    (source / "__init__.py").write_text("", encoding="utf-8")
    return source / name


def _init_repo(path: Path) -> None:
    _git(path, "init")
    _git(path, "config", "user.email", "agent@example.com")
    _git(path, "config", "user.name", "Agent")
    (path / "README.md").write_text("base\n", encoding="utf-8")
    _git(path, "add", ".")
    _git(path, "commit", "-m", "base")


def _git(cwd: Path, *args: str) -> None:
    subprocess.run(("git", *args), cwd=cwd, check=True, capture_output=True, text=True)
