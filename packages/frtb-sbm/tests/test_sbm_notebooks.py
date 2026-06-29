from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_ROOT = PACKAGE_ROOT.parents[1]
NOTEBOOK_ROOT = PACKAGE_ROOT / "notebooks"
WORKSPACE_SRC_PATHS = tuple(sorted((WORKSPACE_ROOT / "packages").glob("*/src")))

for path in (
    PACKAGE_ROOT / "examples",
    PACKAGE_ROOT,
    PACKAGE_ROOT / "src",
    *WORKSPACE_SRC_PATHS,
    WORKSPACE_ROOT,
):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from frtb_sbm import calculate_sbm_capital  # noqa: E402
from frtb_sbm.arrow_batch import calculate_sbm_portfolio_capital_from_arrow_tables  # noqa: E402
from sbm_notebook_data import (  # noqa: E402
    arrow_tables_for_sensitivities,
    notebook_context,
    portfolio_sample_sensitivities,
)


def test_notebook_arrow_batch_example_matches_row_api() -> None:
    context = notebook_context("sbm-notebook-test")
    sensitivities = portfolio_sample_sensitivities()

    row_result = calculate_sbm_capital(sensitivities, context=context)
    calculation = calculate_sbm_portfolio_capital_from_arrow_tables(
        arrow_tables_for_sensitivities(sensitivities),
        context=context,
    )

    assert calculation.result.total_capital == pytest.approx(row_result.total_capital)
    assert len(calculation.result.input_hash) == 64
    int(calculation.result.input_hash, 16)
    assert calculation.result.input_hash_algorithm == "arrow-columnar-v2-portfolio"
    assert calculation.result.input_hash != row_result.input_hash
    assert calculation.accepted_row_dataclasses_materialized == 0


@pytest.mark.parametrize("notebook_path", sorted(NOTEBOOK_ROOT.glob("*.ipynb")))
def test_sbm_notebook_code_cells_execute(
    notebook_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(WORKSPACE_ROOT)
    try:
        notebook = json.loads(notebook_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        pytest.fail(f"{notebook_path.name} is not valid notebook JSON: {exc}")
    namespace = {"__name__": "__main__"}

    for index, cell in enumerate(notebook["cells"], start=1):
        if cell.get("cell_type") != "code":
            continue
        source = "".join(cell.get("source", []))
        exec(compile(source, f"{notebook_path.name}:cell-{index}", "exec"), namespace)
