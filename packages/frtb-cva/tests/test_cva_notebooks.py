from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

WORKSPACE_ROOT = Path(__file__).resolve().parents[3]
PACKAGE_ROOT = Path(__file__).resolve().parents[1]
NOTEBOOK_DIR = PACKAGE_ROOT / "notebooks"

for path in (
    PACKAGE_ROOT / "examples",
    PACKAGE_ROOT / "src",
    *(WORKSPACE_ROOT / "packages").glob("*/src"),
    WORKSPACE_ROOT,
):
    text = str(path)
    if text not in sys.path:
        sys.path.insert(0, text)

from cva_notebook_data import (  # noqa: E402
    build_ba_arrow_batches,
    build_sa_arrow_batches,
    notebook_context,
    sample_counterparties,
    sample_direct_hedge,
    sample_netting_sets,
    sample_sa_sensitivities,
)
from frtb_cva import (  # noqa: E402
    CvaMethod,
    calculate_cva_capital,
    calculate_cva_capital_from_batches,
    validate_cva_result_reconciliation,
)


def test_cva_notebook_arrow_helpers_match_row_calculations() -> None:
    counterparties = sample_counterparties()
    netting_sets = sample_netting_sets(counterparties)
    hedges = (sample_direct_hedge(),)
    row_context = notebook_context(method=CvaMethod.BA_CVA_FULL, run_id="test-cva-row")
    batch_context = notebook_context(method=CvaMethod.BA_CVA_FULL, run_id="test-cva-batch")

    row_result = calculate_cva_capital(row_context, counterparties, netting_sets, hedges=hedges)
    pack = build_ba_arrow_batches(counterparties, netting_sets, hedges)
    batch_calculation = calculate_cva_capital_from_batches(
        batch_context,
        pack.counterparty_batch,
        pack.netting_set_batch,
        hedges=pack.hedge_batch,
    )

    validate_cva_result_reconciliation(batch_calculation.result)
    assert batch_calculation.result.total_cva_capital == pytest.approx(row_result.total_cva_capital)
    assert batch_calculation.accepted_counterparty_dataclasses_materialized == 0
    assert batch_calculation.accepted_netting_set_dataclasses_materialized == 0
    assert batch_calculation.accepted_hedge_dataclasses_materialized == 0

    sensitivities = sample_sa_sensitivities()
    sa_row = calculate_cva_capital(
        notebook_context(method=CvaMethod.SA_CVA, run_id="test-sa-row", sa_cva_approved=True),
        (),
        (),
        sensitivities=sensitivities,
    )
    sa_pack = build_sa_arrow_batches(sensitivities)
    sa_batch_calculation = calculate_cva_capital_from_batches(
        notebook_context(method=CvaMethod.SA_CVA, run_id="test-sa-batch", sa_cva_approved=True),
        sensitivities=sa_pack.sensitivity_batch,
    )

    validate_cva_result_reconciliation(sa_batch_calculation.result)
    assert sa_batch_calculation.result.total_cva_capital == pytest.approx(sa_row.total_cva_capital)
    assert sa_batch_calculation.accepted_sensitivity_dataclasses_materialized == 0
    assert sa_batch_calculation.accepted_hedge_dataclasses_materialized == 0


@pytest.mark.parametrize("notebook_path", sorted(NOTEBOOK_DIR.glob("*.ipynb")))
def test_cva_notebook_executes(notebook_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    try:
        notebook = json.loads(notebook_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        pytest.fail(f"{notebook_path.name} is not valid notebook JSON: {exc}")

    namespace: dict[str, object] = {"__name__": "__main__"}
    monkeypatch.chdir(WORKSPACE_ROOT)

    for index, cell in enumerate(notebook.get("cells", ())):
        if cell.get("cell_type") != "code":
            continue
        source = cell.get("source", "")
        if isinstance(source, list):
            source = "".join(source)
        exec(compile(str(source), f"{notebook_path.name}:cell-{index}", "exec"), namespace)
