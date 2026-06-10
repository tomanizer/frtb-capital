from __future__ import annotations

from pathlib import Path

from scripts.run_package_demos import (
    discover_demo_scripts,
    package_name,
    shell_join,
    summary_lines,
)


def test_discover_demo_scripts_sorts_by_package(tmp_path: Path) -> None:
    for package in ("frtb-zeta", "frtb-alpha"):
        demo = tmp_path / "packages" / package / "examples" / "run_demo.py"
        demo.parent.mkdir(parents=True)
        demo.write_text("print('demo')\n", encoding="utf-8")

    demos = discover_demo_scripts(tmp_path)

    assert [package_name(path) for path in demos] == ["frtb-alpha", "frtb-zeta"]


def test_summary_lines_prefers_capital_and_completion_lines() -> None:
    output = """
    intro
    Total DRC capital: 1,234.00
    noise
    Demo complete.
    """

    assert summary_lines(output) == ("Total DRC capital: 1,234.00", "Demo complete.")


def test_summary_lines_falls_back_to_first_nonempty_lines() -> None:
    output = "\nfirst\n\nsecond\nthird\n"

    assert summary_lines(output, limit=2) == ("first", "second")


def test_shell_join_quotes_paths_with_spaces() -> None:
    assert shell_join(("uv", "run", "python", "path with spaces/run_demo.py")) == (
        "uv run python 'path with spaces/run_demo.py'"
    )
