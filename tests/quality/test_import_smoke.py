from __future__ import annotations

from pathlib import Path

from scripts.ci import import_smoke


def test_import_smoke_success_from_registry_fixture(tmp_path: Path, monkeypatch) -> None:
    _write_module(tmp_path, "qc_smoke_ok", "")
    _write_registry(tmp_path, ["qc_smoke_ok"])
    monkeypatch.syspath_prepend(str(tmp_path))

    import_names = import_smoke.import_roots_from_registry(
        Path("docs/quality/package_maturity.toml"),
        root=tmp_path,
    )
    failures = import_smoke.run_import_smoke(import_names)

    assert import_names == ["qc_smoke_ok"]
    assert failures == []


def test_import_smoke_reports_all_failures_with_exception_details(
    tmp_path: Path,
    monkeypatch,
) -> None:
    _write_module(tmp_path, "qc_smoke_broken", "raise RuntimeError('broken import')\n")
    _write_registry(tmp_path, ["qc_smoke_broken", "qc_smoke_missing"])
    monkeypatch.syspath_prepend(str(tmp_path))

    failures = import_smoke.run_import_smoke(
        import_smoke.import_roots_from_registry(
            Path("docs/quality/package_maturity.toml"),
            root=tmp_path,
        )
    )

    assert import_smoke.failures_to_jsonable(failures) == [
        {
            "import_name": "qc_smoke_broken",
            "exception_type": "RuntimeError",
            "message": "broken import",
        },
        {
            "import_name": "qc_smoke_missing",
            "exception_type": "ModuleNotFoundError",
            "message": "No module named 'qc_smoke_missing'",
        },
    ]


def _write_module(root: Path, import_name: str, body: str) -> None:
    package_dir = root / import_name
    package_dir.mkdir(parents=True)
    (package_dir / "__init__.py").write_text(body, encoding="utf-8")


def _write_registry(root: Path, import_names: list[str]) -> None:
    registry = root / "docs/quality/package_maturity.toml"
    registry.parent.mkdir(parents=True)
    entries = [
        "\n".join(
            [
                "[[packages]]",
                f'package = "{import_name.replace("_", "-")}"',
                f'import_name = "{import_name}"',
                f'path = "packages/{import_name.replace("_", "-")}"',
                f'module_docs = "docs/modules/{import_name.replace("_", "-")}"',
                'maturity = "shared"',
                'component_type = "shared"',
                "",
            ]
        )
        for import_name in import_names
    ]
    registry.write_text("schema_version = 1\n\n" + "\n".join(entries), encoding="utf-8")
