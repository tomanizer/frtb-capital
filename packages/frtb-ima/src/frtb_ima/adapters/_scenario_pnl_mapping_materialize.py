"""Materialization for v1 scenario P&L mapping specs."""

from __future__ import annotations

import csv
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import numpy as np

from frtb_ima.adapters._mapping_hash import stable_mapping_hash
from frtb_ima.adapters._mapping_row_helpers import (
    mapped_date,
    mapped_str,
    mapped_value,
    plain_mapping,
    resolve_source_row_id,
)
from frtb_ima.adapters._scenario_pnl_mapping_cube import (
    build_scenario_pnl_batch_from_arrow,
    scenario_cube_from_batch,
    scenario_pnl_handoff_from_accepted,
)
from frtb_ima.adapters._scenario_pnl_mapping_types import ScenarioPnlValidationReport
from frtb_ima.adapters.mapping_spec import (
    FieldMapping,
    ImaMappingSpec,
    MappingFinding,
    MappingSpecError,
)
from frtb_ima.data_contracts import ScenarioCube
from frtb_ima.scenario import ScenarioSetType


@dataclass(frozen=True)
class ScenarioPnlMappingResult:
    """Materialized scenario P&L rows, cube, and validation report."""

    batch: object
    cube: ScenarioCube
    report: ScenarioPnlValidationReport


def materialize_scenario_pnl_vectors_from_mapping(
    mapping_spec: ImaMappingSpec,
    *,
    source_root: str | Path = ".",
) -> ScenarioPnlMappingResult:
    """Read the configured CSV source and materialize a scenario P&L cube.

    Parameters
    ----------
    mapping_spec : ImaMappingSpec
        Parsed v1 IMA mapping spec with ``scenario_pnl_vectors`` table metadata.
    source_root : str | Path, optional
        Root directory used to resolve ``scenario_pnl_vectors.source``.

    Returns
    -------
    ScenarioPnlMappingResult
        Materialized scenario rows, cube, and generated validation report.
    """

    table = mapping_spec.scenario_pnl_vectors
    if table is None:
        raise MappingSpecError(
            "tables.scenario_pnl_vectors is required for scenario P&L mapping"
        )
    source_path = (Path(source_root) / table.source).resolve()
    if source_path.suffix.lower() != ".csv":
        raise MappingSpecError("scenario_pnl_vectors.source currently supports CSV files only")
    source_text = source_path.read_text(encoding="utf-8")
    rows = tuple(csv.DictReader(source_text.splitlines()))
    return materialize_scenario_pnl_vectors_from_rows(
        rows,
        mapping_spec,
        source_file=table.source,
        source_hash=stable_mapping_hash({"source_text": source_text}),
    )


def materialize_scenario_pnl_vectors_from_rows(
    rows: Sequence[Mapping[str, object]],
    mapping_spec: ImaMappingSpec,
    *,
    source_file: str = "<rows>",
    source_hash: str | None = None,
) -> ScenarioPnlMappingResult:
    """Materialize scenario P&L vectors from already-loaded source rows.

    Parameters
    ----------
    rows : Sequence[Mapping[str, object]]
        Client-shaped long-form scenario P&L rows keyed by source column names.
    mapping_spec : ImaMappingSpec
        Parsed v1 IMA mapping spec with field mappings for scenario P&L rows.
    source_file : str, optional
        Logical source identifier recorded in the validation report.
    source_hash : str | None, optional
        Precomputed source hash; derived from ``rows`` when omitted.

    Returns
    -------
    ScenarioPnlMappingResult
        Materialized scenario rows, cube, and generated validation report.
    """

    table = mapping_spec.scenario_pnl_vectors
    if table is None:
        raise MappingSpecError(
            "tables.scenario_pnl_vectors is required for scenario P&L mapping"
        )
    row_hash = source_hash or stable_mapping_hash({"rows": [plain_mapping(row) for row in rows]})
    accepted, findings = _accepted_scenario_pnl_rows(rows, table.fields, mapping_spec)
    handoff = scenario_pnl_handoff_from_accepted(
        accepted,
        source_hash=row_hash,
        mapping_hash=mapping_spec.spec_hash,
    )
    batch = build_scenario_pnl_batch_from_arrow(handoff)
    if batch.observation_count != len(accepted):
        raise ValueError(
            "Scenario P&L Arrow normalizer changed the accepted row count: "
            f"accepted={len(accepted)}, batch={batch.observation_count}"
        )
    cube = scenario_cube_from_batch(batch, missing_cells=table.missing_cells)
    report = ScenarioPnlValidationReport(
        target_schema=mapping_spec.target_schema,
        source_system=mapping_spec.source_system,
        source_file=source_file,
        mapping_hash=mapping_spec.spec_hash,
        source_hash=row_hash,
        row_count_read=len(rows),
        row_count_mapped=batch.observation_count,
        row_count_rejected=len(rows) - len(accepted),
        findings=tuple(findings),
    )
    return ScenarioPnlMappingResult(batch=batch, cube=cube, report=report)


def _accepted_scenario_pnl_rows(
    rows: Sequence[Mapping[str, object]],
    fields: Mapping[str, FieldMapping],
    mapping_spec: ImaMappingSpec,
) -> tuple[list[dict[str, object]], list[MappingFinding]]:
    accepted: list[dict[str, object]] = []
    findings: list[MappingFinding] = []
    seen_keys: set[tuple[str, str, str]] = set()
    scenario_metadata_by_id: dict[str, tuple[date, ScenarioSetType]] = {}
    sign_multiplier = 1.0 if mapping_spec.pnl_positive_means == "loss" else -1.0
    for row_index, row in enumerate(rows, start=1):
        source_row_id = resolve_source_row_id(row, row_index, fields, findings=findings)
        _accept_scenario_pnl_row(
            row,
            fields,
            source_row_id=source_row_id,
            sign_multiplier=sign_multiplier,
            accepted=accepted,
            findings=findings,
            seen_keys=seen_keys,
            scenario_metadata_by_id=scenario_metadata_by_id,
        )
    return accepted, findings


def _accept_scenario_pnl_row(
    row: Mapping[str, object],
    fields: Mapping[str, FieldMapping],
    *,
    source_row_id: str,
    sign_multiplier: float,
    accepted: list[dict[str, object]],
    findings: list[MappingFinding],
    seen_keys: set[tuple[str, str, str]],
    scenario_metadata_by_id: dict[str, tuple[date, ScenarioSetType]],
) -> None:
    try:
        mapped = _map_scenario_pnl_row(
            row,
            fields,
            source_row_id=source_row_id,
            sign_multiplier=sign_multiplier,
        )
    except ValueError as exc:
        findings.append(_finding("SCENARIO_PNL_ROW_REJECTED", str(exc), source_row_id))
        return
    if _has_metadata_conflict(mapped, scenario_metadata_by_id):
        findings.append(
            _finding(
                "SCENARIO_PNL_SCENARIO_METADATA_CONFLICT",
                "scenario_id maps to conflicting scenario_date or scenario_set",
                source_row_id,
            )
        )
        return
    key = (str(mapped["scenario_id"]), str(mapped["position_id"]), str(mapped["risk_factor_name"]))
    if key in seen_keys:
        findings.append(
            _finding(
                "SCENARIO_PNL_DUPLICATE_KEY",
                "scenario_pnl_vectors contains duplicate scenario_id/position_id/risk_factor_name",
                source_row_id,
            )
        )
        return
    seen_keys.add(key)
    accepted.append(mapped)


def _map_scenario_pnl_row(
    row: Mapping[str, object],
    fields: Mapping[str, FieldMapping],
    *,
    source_row_id: str,
    sign_multiplier: float,
) -> dict[str, object]:
    scenario_set = _optional_scenario_set(row, fields.get("scenario_set"))
    return {
        "scenario_id": mapped_str(row, fields["scenario_id"], "scenario_id"),
        "scenario_date": mapped_date(row, fields["scenario_date"], "scenario_date"),
        "scenario_set": scenario_set.value,
        "position_id": mapped_str(row, fields["position_id"], "position_id"),
        "risk_factor_name": mapped_str(row, fields["risk_factor_name"], "risk_factor_name"),
        "pnl": _mapped_float(row, fields["pnl"], "pnl") * sign_multiplier,
        "source_row_id": source_row_id,
    }


def _has_metadata_conflict(
    mapped: Mapping[str, object],
    scenario_metadata_by_id: dict[str, tuple[date, ScenarioSetType]],
) -> bool:
    scenario_id = str(mapped["scenario_id"])
    metadata_key = (_require_date(mapped["scenario_date"]), _scenario_set(mapped["scenario_set"]))
    if scenario_metadata_by_id.get(scenario_id, metadata_key) != metadata_key:
        return True
    scenario_metadata_by_id[scenario_id] = metadata_key
    return False


def _mapped_float(row: Mapping[str, object], mapping: FieldMapping, field_name: str) -> float:
    value = mapped_value(row, mapping, field_name)
    if value is None or str(value).strip() == "":
        raise ValueError(f"{field_name} is required")
    try:
        result = float(str(value).replace(",", ""))
    except ValueError as exc:
        raise ValueError(f"{field_name} must be numeric") from exc
    if not np.isfinite(result):
        raise ValueError(f"{field_name} must be finite")
    return result


def _optional_scenario_set(
    row: Mapping[str, object], mapping: FieldMapping | None
) -> ScenarioSetType:
    if mapping is None:
        return ScenarioSetType.CURRENT
    text = str(mapped_value(row, mapping, "scenario_set") or "").strip().upper()
    if not text:
        return ScenarioSetType.CURRENT
    try:
        return ScenarioSetType(text)
    except ValueError as exc:
        raise ValueError("scenario_set must be CURRENT, STRESS, BACKTEST, or PLA") from exc


def _require_date(value: object) -> date:
    if not isinstance(value, date):
        raise TypeError("scenario_date must be a datetime.date")
    return value


def _scenario_set(value: object) -> ScenarioSetType:
    return ScenarioSetType(str(value))


def _finding(code: str, message: str, row_id: str) -> MappingFinding:
    return MappingFinding(severity="ERROR", code=code, message=message, row_id=row_id)
