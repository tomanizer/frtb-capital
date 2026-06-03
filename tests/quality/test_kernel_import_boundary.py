from __future__ import annotations

from pathlib import Path

from scripts.ci.check_kernel_import_boundary import check_repo


def _write_module(repo_root: Path, relative_path: str, source: str) -> None:
    path = repo_root / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(source, encoding="utf-8")


def test_kernel_import_boundary_reports_banned_runtime_import(tmp_path: Path) -> None:
    _write_module(
        tmp_path,
        "packages/frtb-sbm/src/frtb_sbm/aggregation.py",
        "import pyarrow as pa\n",
    )

    violations = check_repo(tmp_path)

    assert len(violations) == 1
    assert violations[0].path == tmp_path / "packages/frtb-sbm/src/frtb_sbm/aggregation.py"
    assert violations[0].line_number == 1
    assert violations[0].imported_root == "pyarrow"


def test_kernel_import_boundary_allows_arrow_and_adapter_imports(tmp_path: Path) -> None:
    _write_module(
        tmp_path,
        "packages/frtb-common/src/frtb_common/arrow_table.py",
        "import pyarrow as pa\n",
    )
    _write_module(
        tmp_path,
        "packages/frtb-common/src/frtb_common/component_summary.py",
        "import pyarrow as pa\n",
    )
    _write_module(
        tmp_path,
        "packages/frtb-common/src/frtb_common/arrow_conversion.py",
        "import pyarrow as pa\n",
    )
    _write_module(
        tmp_path,
        "packages/frtb-sbm/src/frtb_sbm/adapters/crif_arrow.py",
        "from pyarrow import Table\n",
    )
    _write_module(
        tmp_path,
        "packages/frtb-sbm/src/frtb_sbm/crif.py",
        "import pandas as pd\n",
    )
    _write_module(
        tmp_path,
        "packages/frtb-sbm/src/frtb_sbm/aggregation.py",
        "from .pandas import local_helper\n",
    )
    _write_module(
        tmp_path,
        "packages/frtb-common/src/frtb_common/arrow_table_schema.py",
        "import pyarrow as pa\n",
    )
    _write_module(
        tmp_path,
        "packages/frtb-orchestration/src/frtb_orchestration/manifest.py",
        "import pyarrow as pa\n",
    )

    assert check_repo(tmp_path) == ()


def test_kernel_import_boundary_exempts_result_store_io_package(tmp_path: Path) -> None:
    _write_module(
        tmp_path,
        "packages/frtb-result-store/src/frtb_result_store/schema_registry.py",
        "import pyarrow as pa\n",
    )

    assert check_repo(tmp_path) == ()


def test_kernel_import_boundary_detects_dataframe_import_forms(tmp_path: Path) -> None:
    _write_module(
        tmp_path,
        "packages/frtb-cva/src/frtb_cva/capital.py",
        "from pandas import DataFrame\nimport polars.selectors as cs\n",
    )

    violations = check_repo(tmp_path)

    assert [(item.line_number, item.imported_root) for item in violations] == [
        (1, "pandas"),
        (2, "polars"),
    ]
