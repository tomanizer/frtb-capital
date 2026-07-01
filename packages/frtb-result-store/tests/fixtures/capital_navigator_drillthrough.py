"""Local drillthrough artifacts for the Capital Navigator result-store fixture."""

from __future__ import annotations

from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

from fixtures.capital_navigator_drillthrough_attribution_rows import ATTRIBUTION_ROWS
from fixtures.capital_navigator_drillthrough_component_rows import (
    CVA_ROWS,
    DRC_ROWS,
    IMA_ROWS,
    IMA_SCENARIO_VECTOR_ROWS,
    RFET_OBSERVATION_TIMELINE_ROWS,
    RRAO_ROWS,
    SBM_CURVATURE_SHOCK_DOWN_ROWS,
    SBM_CURVATURE_SHOCK_UP_ROWS,
    SBM_ROWS,
    USD_SWAPTION_VOL_SURFACE_ROWS,
)


def write_capital_navigator_artifacts(
    run_id: str,
    artifact_root: Path | None,
) -> dict[str, tuple[str, int]]:
    """Write local Parquet drillthrough artifacts and return URI/row-counts."""

    if artifact_root is None:
        return {}
    artifact_root.mkdir(parents=True, exist_ok=True)
    artifacts: dict[str, tuple[str, int]] = {}
    for artifact_id, rows in _ROWS_BY_ARTIFACT.items():
        path = artifact_root / f"{artifact_id}.parquet"
        table = pa.Table.from_pylist([_row_with_run_id(run_id, row) for row in rows])
        pq.write_table(table, path)
        artifacts[artifact_id] = (path.resolve().as_uri(), len(rows))
    return artifacts


def _row_with_run_id(run_id: str, row: dict[str, object]) -> dict[str, object]:
    patched = dict(row)
    patched["run_id"] = run_id
    if patched.get("source_id") == "RUN_ID":
        patched["source_id"] = run_id
    return patched


_ROWS_BY_ARTIFACT = {
    "navigator-ima-pnl-vector": IMA_ROWS,
    "navigator-sbm-sensitivities": SBM_ROWS,
    "navigator-drc-jtd": DRC_ROWS,
    "navigator-rrao-exposures": RRAO_ROWS,
    "navigator-cva-exposures": CVA_ROWS,
    "navigator-suite-attribution": ATTRIBUTION_ROWS,
    "navigator-rfet-observation-timeline": RFET_OBSERVATION_TIMELINE_ROWS,
    "navigator-sbm-curvature-shock-up": SBM_CURVATURE_SHOCK_UP_ROWS,
    "navigator-sbm-curvature-shock-down": SBM_CURVATURE_SHOCK_DOWN_ROWS,
    "navigator-ima-scenario-vector": IMA_SCENARIO_VECTOR_ROWS,
    "navigator-usd-swaption-vol-surface": USD_SWAPTION_VOL_SURFACE_ROWS,
}
