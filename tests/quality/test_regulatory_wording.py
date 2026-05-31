from __future__ import annotations

from pathlib import Path

from scripts.ci import check_regulatory_wording as wording


def test_regulatory_wording_allows_policy_guidance_files(tmp_path: Path, monkeypatch) -> None:
    repo_root = tmp_path / "repo"
    docs = repo_root / "docs" / "quality"
    docs.mkdir(parents=True)
    (docs / "note.md").write_text(
        "Use explicit citations instead of working assumption.\n",
        encoding="utf-8",
    )
    (repo_root / "AGENTS.md").write_text(
        'Do not use phrases like "working assumption" as a substitute for citation.\n',
        encoding="utf-8",
    )

    monkeypatch.setattr(wording, "ROOT", repo_root)

    assert wording.main([]) == 0


def test_regulatory_wording_flags_uncited_notebook_language(tmp_path: Path, monkeypatch) -> None:
    repo_root = tmp_path / "repo"
    notebook_dir = repo_root / "packages" / "frtb-ima" / "notebooks"
    notebook_dir.mkdir(parents=True)
    (notebook_dir / "demo.ipynb").write_text(
        """
{
  "cells": [
    {
      "cell_type": "markdown",
      "metadata": {},
      "source": ["This uses a working assumption without citation."]
    }
  ],
  "metadata": {},
  "nbformat": 4,
  "nbformat_minor": 5
}
""".strip(),
        encoding="utf-8",
    )

    monkeypatch.setattr(wording, "ROOT", repo_root)

    assert wording.main([]) == 1
