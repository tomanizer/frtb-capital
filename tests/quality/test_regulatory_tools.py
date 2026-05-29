from __future__ import annotations

from tools.regulatory import export_package_sources, lint_regulatory_corpus


def test_linter_reports_duplicate_quoted_source_ids(tmp_path, monkeypatch) -> None:
    sources = tmp_path / "sources.yml"
    sources.write_text(
        "\n".join(
            [
                "sources:",
                "  - id: 'source-a'",
                "    issuer: Basel Committee",
                "    jurisdiction: Basel",
                "    title: Source A",
                "    url: https://example.test/a",
                "    status: final_rule",
                '  - id: "source-a"',
                "    jurisdiction: Basel",
                "    title: Source A duplicate",
                "    url: https://example.test/a-duplicate",
                "    status: final_rule",
                "",
            ]
        ),
        encoding="utf-8",
    )
    crosswalk_dir = tmp_path / "crosswalk"
    regime_dir = tmp_path / "regimes"
    crosswalk_dir.mkdir()
    regime_dir.mkdir()

    monkeypatch.setattr(lint_regulatory_corpus, "SOURCES", sources)
    monkeypatch.setattr(lint_regulatory_corpus, "CROSSWALK_DIR", crosswalk_dir)
    monkeypatch.setattr(lint_regulatory_corpus, "REGIME_DIR", regime_dir)

    errors: list[str] = []
    assert lint_regulatory_corpus.collect_source_ids(errors) == {"source-a"}
    assert "duplicate source id: source-a" in errors
    assert "source-a: missing issuer" in errors


def test_list_values_after_key_tolerates_comments_and_quoted_refs(tmp_path) -> None:
    path = tmp_path / "crosswalk.yml"
    path.write_text(
        "\n".join(
            [
                "component: frtb-ima",
                "source_refs:",
                "  # keep this comment inside the list block",
                "  - 'source-a'",
                '  - "source-b" # inline comment',
                "owner: validation",
                "other_refs:",
                "  - ignored",
                "",
            ]
        ),
        encoding="utf-8",
    )

    assert lint_regulatory_corpus.list_values_after_key(path, "source_refs") == [
        "source-a",
        "source-b",
    ]


def test_export_source_refs_tolerates_comments_and_quoted_refs(tmp_path, monkeypatch) -> None:
    crosswalk_dir = tmp_path / "crosswalk"
    crosswalk_dir.mkdir()
    (crosswalk_dir / "frtb-ima.yml").write_text(
        "\n".join(
            [
                "component: frtb-ima",
                "source_refs:",
                "  # comment",
                "  - 'source-a'",
                '  - "source-b"',
                "notes: stop collecting here",
                "  - ignored",
                "",
            ]
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(export_package_sources, "CROSSWALK_DIR", crosswalk_dir)

    assert export_package_sources.source_refs("frtb-ima") == ["source-a", "source-b"]


def test_linter_reports_unknown_challenger_refs(tmp_path, monkeypatch) -> None:
    sources = tmp_path / "sources.yml"
    sources.write_text(
        "\n".join(
            [
                "sources:",
                "  - id: source-a",
                "    issuer: Basel Committee",
                "    jurisdiction: Basel",
                "    title: Source A",
                "    url: https://example.test/a",
                "    status: final_rule",
                "",
            ]
        ),
        encoding="utf-8",
    )
    challengers = tmp_path / "challenger_models.yml"
    challengers.write_text(
        "\n".join(
            [
                "challengers:",
                "  - id: challenger-a",
                "    repo: example/challenger-a",
                "",
            ]
        ),
        encoding="utf-8",
    )
    crosswalk_dir = tmp_path / "crosswalk"
    regime_dir = tmp_path / "regimes"
    crosswalk_dir.mkdir()
    regime_dir.mkdir()
    crosswalk = crosswalk_dir / "frtb-ima.yml"
    crosswalk.write_text(
        "\n".join(
            [
                "requirements:",
                "  - id: IMA-001",
                "    source_refs:",
                "      - source-a",
                "    challenger_refs:",
                "      - challenger-a",
                "      - missing-challenger",
                "",
            ]
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(lint_regulatory_corpus, "SOURCES", sources)
    monkeypatch.setattr(lint_regulatory_corpus, "CHALLENGERS", challengers)
    monkeypatch.setattr(lint_regulatory_corpus, "CROSSWALK_DIR", crosswalk_dir)
    monkeypatch.setattr(lint_regulatory_corpus, "REGIME_DIR", regime_dir)

    errors: list[str] = []
    source_ids = lint_regulatory_corpus.collect_source_ids(errors)
    challenger_ids = lint_regulatory_corpus.collect_challenger_ids(errors)
    lint_regulatory_corpus.check_references(source_ids, challenger_ids, errors)

    assert f"{crosswalk}: references unknown challenger id missing-challenger" in errors
