"""Canonical Arrow handoff and cube builders for scenario P&L mapping."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import date

import numpy as np
import pyarrow as pa  # type: ignore[import-untyped]
from frtb_common import NormalizedArrowTable, normalize_arrow_table, normalized_arrow_table_hash

from frtb_ima.adapters._scenario_pnl_mapping_types import (
    IMA_SCENARIO_PNL_VECTOR_ARROW_COLUMN_SPECS,
    IMA_SCENARIO_PNL_VECTOR_TARGET,
    ScenarioPnlVectorBatch,
)
from frtb_ima.data_contracts import ScenarioCube
from frtb_ima.scenario import ScenarioMetadata, ScenarioSetType


def _scenario_pnl_arrow_from_accepted(
    accepted: Sequence[Mapping[str, object]],
    *,
    source_hash: str,
    mapping_hash: str,
) -> NormalizedArrowTable:
    """Build a normalized canonical Arrow handoff from accepted scenario P&L rows.

    Parameters
    ----------
    accepted : Sequence[Mapping[str, object]]
        Accepted canonical long-form scenario P&L rows.
    source_hash : str
        Stable source-data hash for provenance.
    mapping_hash : str
        Stable mapping-spec hash for provenance.

    Returns
    -------
    NormalizedArrowTable
        Normalized canonical scenario P&L Arrow handoff.
    """

    if not accepted:
        raise ValueError("scenario P&L mapping produced no accepted rows")
    return normalize_arrow_table(
        pa.table({key: [row[key] for row in accepted] for key in accepted[0]}),
        column_specs=IMA_SCENARIO_PNL_VECTOR_ARROW_COLUMN_SPECS,
        metadata={"mapping_hash": mapping_hash},
        source_hash=source_hash,
        require_unique_row_ids=True,
    )


def build_scenario_pnl_batch_from_arrow(handoff: NormalizedArrowTable) -> ScenarioPnlVectorBatch:
    """Build accepted scenario P&L row batch from a normalized Arrow table.

    Parameters
    ----------
    handoff : NormalizedArrowTable
        Normalized canonical scenario P&L handoff table.

    Returns
    -------
    ScenarioPnlVectorBatch
        Accepted long-form scenario P&L rows with source lineage.
    """

    if not isinstance(handoff, NormalizedArrowTable):
        raise ValueError("handoff must be NormalizedArrowTable")
    table = handoff.accepted
    return ScenarioPnlVectorBatch(
        scenario_ids=np.asarray(_column_values(table, "scenario_id"), dtype=np.str_),
        scenario_dates=np.asarray(_column_values(table, "scenario_date"), dtype="datetime64[D]"),
        scenario_sets=np.asarray(_column_values(table, "scenario_set"), dtype=np.str_),
        position_ids=np.asarray(_column_values(table, "position_id"), dtype=np.str_),
        risk_factor_names=np.asarray(_column_values(table, "risk_factor_name"), dtype=np.str_),
        pnl=np.asarray(_column_values(table, "pnl"), dtype=np.float64),
        source_row_ids=np.asarray(_column_values(table, "source_row_id"), dtype=np.str_),
        source_hash=handoff.source_hash or "",
        handoff_hash=normalized_arrow_table_hash(handoff),
    )


def scenario_cube_from_batch(batch: ScenarioPnlVectorBatch, *, missing_cells: str) -> ScenarioCube:
    """Build a dense scenario cube from accepted canonical scenario P&L rows.

    Parameters
    ----------
    batch : ScenarioPnlVectorBatch
        Accepted canonical long-form scenario P&L rows.
    missing_cells : str
        Missing-cell policy: ``reject`` or ``zero``.

    Returns
    -------
    ScenarioCube
        Dense runtime scenario cube using positive-loss P&L convention.
    """

    scenarios = _scenario_axis(batch)
    position_ids = tuple(sorted({str(position_id) for position_id in batch.position_ids}))
    risk_factor_names = tuple(
        sorted({str(risk_factor_name) for risk_factor_name in batch.risk_factor_names})
    )
    expected_count = len(scenarios) * len(position_ids) * len(risk_factor_names)
    if missing_cells == "reject" and batch.observation_count != expected_count:
        raise ValueError(
            "scenario P&L mapping has missing scenario/position/risk-factor cells; "
            "set scenario_pnl_vectors.missing_cells to zero to permit sparse inputs"
        )
    return _build_cube(batch, scenarios, position_ids, risk_factor_names)


def _scenario_axis(batch: ScenarioPnlVectorBatch) -> list[tuple[str, date, ScenarioSetType]]:
    return sorted(
        {
            (str(scenario_id), _date_from_value(scenario_date), ScenarioSetType(str(scenario_set)))
            for scenario_id, scenario_date, scenario_set in zip(
                batch.scenario_ids, batch.scenario_dates, batch.scenario_sets, strict=True
            )
        },
        key=lambda item: (item[1], item[0]),
    )


def _build_cube(
    batch: ScenarioPnlVectorBatch,
    scenarios: Sequence[tuple[str, date, ScenarioSetType]],
    position_ids: tuple[str, ...],
    risk_factor_names: tuple[str, ...],
) -> ScenarioCube:
    scenario_index = {scenario_id: idx for idx, (scenario_id, _, _) in enumerate(scenarios)}
    position_index = {position_id: idx for idx, position_id in enumerate(position_ids)}
    risk_factor_index = {
        risk_factor_name: idx for idx, risk_factor_name in enumerate(risk_factor_names)
    }
    values = np.zeros((len(scenarios), len(position_ids), len(risk_factor_names)), dtype=float)
    for scenario_id, position_id, risk_factor_name, pnl in zip(
        batch.scenario_ids,
        batch.position_ids,
        batch.risk_factor_names,
        batch.pnl,
        strict=True,
    ):
        values[
            scenario_index[str(scenario_id)],
            position_index[str(position_id)],
            risk_factor_index[str(risk_factor_name)],
        ] = float(pnl)
    return ScenarioCube(
        values=values,
        scenario_metadata=tuple(
            ScenarioMetadata(
                scenario_id=scenario_id,
                scenario_date=scenario_date,
                scenario_set=scenario_set,
            )
            for scenario_id, scenario_date, scenario_set in scenarios
        ),
        position_ids=position_ids,
        risk_factor_names=risk_factor_names,
        name=IMA_SCENARIO_PNL_VECTOR_TARGET,
    )


def _date_from_value(value: object) -> date:
    return date.fromisoformat(str(np.datetime64(str(value), "D")))


def _column_values(table: pa.Table, column_name: str) -> list[object]:
    values: Sequence[object] = table.column(column_name).to_pylist()
    return list(values)
