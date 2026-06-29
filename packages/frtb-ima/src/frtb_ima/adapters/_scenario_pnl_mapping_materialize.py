"""Materialization for v1 scenario P&L mapping specs."""

from __future__ import annotations

import csv
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from types import MappingProxyType

import numpy as np

from frtb_ima.adapters._mapping_hash import stable_mapping_hash
from frtb_ima.adapters._mapping_row_helpers import (
    mapped_date,
    mapped_str,
    mapped_value,
    plain_mapping,
    resolve_source_row_id,
)
from frtb_ima.adapters._risk_factor_master_mapping_types import RiskFactorMasterBatch
from frtb_ima.adapters._scenario_pnl_mapping_cube import (
    _scenario_pnl_arrow_from_accepted,
    build_scenario_pnl_batch_from_arrow,
    scenario_cube_from_batch,
)
from frtb_ima.adapters._scenario_pnl_mapping_types import (
    ScenarioPnlValidationReport,
    ScenarioPnlVectorBatch,
)
from frtb_ima.adapters.mapping_spec import (
    FieldMapping,
    ImaMappingSpec,
    MappingFinding,
    MappingSpecError,
)
from frtb_ima.data_contracts import ScenarioCube
from frtb_ima.data_models import LiquidityHorizon
from frtb_ima.scenario import ScenarioSetType


@dataclass(frozen=True)
class ScenarioPnlMappingResult:
    """Materialized scenario P&L rows, cube, and validation report."""

    batch: ScenarioPnlVectorBatch
    cube: ScenarioCube
    report: ScenarioPnlValidationReport
    liquidity_horizons_by_risk_factor: Mapping[str, LiquidityHorizon] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "liquidity_horizons_by_risk_factor",
            MappingProxyType(dict(self.liquidity_horizons_by_risk_factor)),
        )


def materialize_scenario_pnl_vectors_from_mapping(
    mapping_spec: ImaMappingSpec,
    *,
    source_root: str | Path = ".",
    risk_factor_master: RiskFactorMasterBatch | None = None,
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
        raise MappingSpecError("tables.scenario_pnl_vectors is required for scenario P&L mapping")
    source_path = (Path(source_root) / table.source).resolve()
    if source_path.suffix.lower() != ".csv":
        raise MappingSpecError("scenario_pnl_vectors.source currently supports CSV files only")
    source_text = source_path.read_text(encoding="utf-8")
    rows = tuple(csv.DictReader(source_text.splitlines()))
    if risk_factor_master is None and mapping_spec.risk_factor_master is not None:
        from frtb_ima.adapters.risk_factor_master_mapping import (
            materialize_risk_factor_master_from_mapping,
        )

        risk_factor_master = materialize_risk_factor_master_from_mapping(
            mapping_spec, source_root=source_root
        ).batch
    return materialize_scenario_pnl_vectors_from_rows(
        rows,
        mapping_spec,
        source_file=table.source,
        source_hash=stable_mapping_hash({"source_text": source_text}),
        risk_factor_master=risk_factor_master,
    )


def materialize_scenario_pnl_vectors_from_rows(
    rows: Sequence[Mapping[str, object]],
    mapping_spec: ImaMappingSpec,
    *,
    source_file: str = "<rows>",
    source_hash: str | None = None,
    risk_factor_master: RiskFactorMasterBatch | None = None,
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
        raise MappingSpecError("tables.scenario_pnl_vectors is required for scenario P&L mapping")
    row_hash = source_hash or stable_mapping_hash({"rows": [plain_mapping(row) for row in rows]})
    accepted, findings = _accepted_scenario_pnl_rows(rows, table.fields, mapping_spec)
    handoff = _scenario_pnl_arrow_from_accepted(
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
    liquidity_horizons_by_risk_factor, liquidity_horizon_findings = _reconcile_liquidity_horizons(
        batch, risk_factor_master
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
        findings=tuple([*findings, *liquidity_horizon_findings]),
    )
    return ScenarioPnlMappingResult(
        batch=batch,
        cube=cube,
        report=report,
        liquidity_horizons_by_risk_factor=liquidity_horizons_by_risk_factor,
    )


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


def _reconcile_liquidity_horizons(
    batch: ScenarioPnlVectorBatch,
    risk_factor_master: RiskFactorMasterBatch | None,
) -> tuple[dict[str, LiquidityHorizon], list[MappingFinding]]:
    if risk_factor_master is None:
        return {}, []
    master_values = _master_liquidity_horizons(risk_factor_master)
    first_source_row_by_risk_factor = _first_source_row_by_risk_factor(batch)
    result: dict[str, LiquidityHorizon] = {}
    findings: list[MappingFinding] = []
    for risk_factor_name in sorted(first_source_row_by_risk_factor):
        horizons = master_values.get(risk_factor_name, frozenset())
        row_id = first_source_row_by_risk_factor[risk_factor_name]
        if not horizons:
            findings.append(
                _finding(
                    "SCENARIO_PNL_RISK_FACTOR_NOT_IN_MASTER",
                    "scenario_pnl_vectors risk_factor_name is missing from risk_factor_master",
                    row_id,
                )
            )
            continue
        if len(horizons) > 1:
            findings.append(
                _finding(
                    "SCENARIO_PNL_RISK_FACTOR_LH_CONFLICT",
                    "risk_factor_master maps risk_factor_name to multiple liquidity horizons",
                    row_id,
                )
            )
            continue
        result[risk_factor_name] = next(iter(horizons))
    return result, findings


def _master_liquidity_horizons(
    risk_factor_master: RiskFactorMasterBatch,
) -> dict[str, frozenset[LiquidityHorizon]]:
    values: dict[str, set[LiquidityHorizon]] = {}
    for risk_factor_name, liquidity_horizon in zip(
        risk_factor_master.risk_factor_names,
        risk_factor_master.liquidity_horizons,
        strict=True,
    ):
        values.setdefault(str(risk_factor_name), set()).add(
            LiquidityHorizon(int(liquidity_horizon))
        )
    return {key: frozenset(value) for key, value in values.items()}


def _first_source_row_by_risk_factor(batch: ScenarioPnlVectorBatch) -> dict[str, str]:
    result: dict[str, str] = {}
    for risk_factor_name, source_row_id in zip(
        batch.risk_factor_names,
        batch.source_row_ids,
        strict=True,
    ):
        result.setdefault(str(risk_factor_name), str(source_row_id))
    return result
