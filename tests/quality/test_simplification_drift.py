from __future__ import annotations

from pathlib import Path

from scripts.ci.check_simplification_drift import check_repo


def _write_module(repo_root: Path, relative_path: str, source: str) -> None:
    path = repo_root / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(source, encoding="utf-8")


def test_simplification_drift_reports_common_batch_top_level_exports(tmp_path: Path) -> None:
    _write_module(
        tmp_path,
        "packages/frtb-common/src/frtb_common/__init__.py",
        "\n".join(
            [
                "from frtb_common.batch_arrays import object_array",
                "",
                "__all__ = [",
                '    "object_array",',
                "]",
                "",
            ]
        ),
    )

    findings = check_repo(tmp_path)

    assert [(finding.code, finding.subject, finding.line_number) for finding in findings] == [
        ("COMMON_BATCH_TOP_LEVEL_EXPORT", "object_array", 1),
        ("COMMON_BATCH_TOP_LEVEL_EXPORT", "object_array", 4),
    ]


def test_simplification_drift_flags_only_ast_pass_through_wrappers(tmp_path: Path) -> None:
    _write_module(
        tmp_path,
        "packages/frtb-sbm/src/frtb_sbm/batch.py",
        "\n".join(
            [
                "import frtb_common.batch_arrays as _batch_arrays",
                "",
                "def _object_array(values, *, copy):",
                "    return _batch_arrays.object_array(values, copy=copy)",
                "",
                "def _sbm_object_array(values, field, *, copy):",
                "    array = _batch_arrays.object_array(values, copy=copy)",
                "    if array.ndim != 1:",
                "        raise ValueError(field)",
                "    return array",
                "",
            ]
        ),
    )

    findings = check_repo(tmp_path)

    assert [(finding.code, finding.subject) for finding in findings] == [
        ("PASS_THROUGH_COMMON_HELPER_WRAPPER", "_object_array")
    ]


def test_simplification_drift_accepts_inline_suppression_with_reason(tmp_path: Path) -> None:
    _write_module(
        tmp_path,
        "packages/frtb-rrao/src/frtb_rrao/_batch_columns.py",
        "\n".join(
            [
                "import frtb_common.batch_arrays as ba",
                "",
                "def _object_array(values, *, copy):  # simplify-audit: keep - compatibility shim",
                "    return ba.object_array(values, copy=copy)",
                "",
            ]
        ),
    )

    assert check_repo(tmp_path) == ()


def test_simplification_drift_rejects_suppression_without_reason(tmp_path: Path) -> None:
    _write_module(
        tmp_path,
        "packages/frtb-rrao/src/frtb_rrao/_batch_columns.py",
        "\n".join(
            [
                "import frtb_common.batch_arrays as ba",
                "",
                "def _object_array(values, *, copy):  # simplify-audit: keep",
                "    return ba.object_array(values, copy=copy)",
                "",
            ]
        ),
    )

    findings = check_repo(tmp_path)

    assert sorted((finding.code, finding.subject) for finding in findings) == [
        ("PASS_THROUGH_COMMON_HELPER_WRAPPER", "_object_array"),
        ("SUPPRESSION_MISSING_REASON", "simplify-audit: keep"),
    ]


def test_simplification_drift_reports_stale_arrow_converter_names(tmp_path: Path) -> None:
    _write_module(
        tmp_path,
        "packages/frtb-cva/src/frtb_cva/arrow_handoff.py",
        "\n".join(
            [
                "def _object_array_from_arrow_column(column):",
                "    return column.to_numpy(zero_copy_only=False)",
                "",
            ]
        ),
    )
    _write_module(
        tmp_path,
        "packages/frtb-common/src/frtb_common/arrow_conversion.py",
        "\n".join(
            [
                "def _object_array_from_arrow_column(column):",
                "    return column.to_numpy(zero_copy_only=False)",
                "",
            ]
        ),
    )

    findings = check_repo(tmp_path)

    assert [(finding.code, finding.subject) for finding in findings] == [
        ("STALE_ARROW_CONVERTER_REIMPLEMENTATION", "_object_array_from_arrow_column")
    ]


def test_simplification_drift_reports_batch_aliases_reintroduced_with_common_helpers(
    tmp_path: Path,
) -> None:
    _write_module(
        tmp_path,
        "packages/frtb-drc/src/frtb_drc/batch.py",
        "\n".join(
            [
                "import frtb_common.batch_arrays as ba",
                "",
                "ObjectArray = object",
                "",
            ]
        ),
    )
    _write_module(
        tmp_path,
        "packages/frtb-sbm/src/frtb_sbm/batch.py",
        "\n".join(
            [
                "ObjectArray = object",
                "",
                "def _object_array(values, field, *, copy):",
                "    array = list(values)",
                "    if len(array) == 0:",
                "        raise ValueError(field)",
                "    return array",
                "",
            ]
        ),
    )

    findings = check_repo(tmp_path)

    assert [(finding.code, finding.subject) for finding in findings] == [
        ("LOCAL_BATCH_ALIAS_WITH_COMMON_HELPERS", "ObjectArray")
    ]
