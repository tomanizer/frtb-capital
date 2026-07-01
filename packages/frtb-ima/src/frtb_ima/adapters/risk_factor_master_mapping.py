"""Risk-factor master mapping adapter for v1 IMA client ingestion."""

from __future__ import annotations

import csv
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import numpy as np
import pyarrow as pa  # type: ignore[import-untyped]
from frtb_common import NormalizedArrowTable, normalize_arrow_table, normalized_arrow_table_hash

from frtb_ima.adapters._mapping_hash import stable_mapping_hash
from frtb_ima.adapters._mapping_row_helpers import (
    mapped_date,
    mapped_str,
    mapped_value,
    plain_mapping,
    resolve_source_row_id,
)
from frtb_ima.adapters._risk_factor_master_mapping_types import (
    IMA_RISK_FACTOR_MASTER_ARROW_COLUMN_SPECS,
    IMA_RISK_FACTOR_MASTER_TARGET,
    RiskFactorMasterBatch,
    RiskFactorMasterTableMapping,
    RiskFactorMasterValidationReport,
    input_hash_for_risk_factor_master_batch,
)
from frtb_ima.adapters.mapping_spec import (
    FieldMapping,
    ImaMappingSpec,
    MappingFinding,
    MappingSpecError,
)
from frtb_ima.data_models import LiquidityHorizon, RiskClass

__all__ = [
    "IMA_RISK_FACTOR_MASTER_ARROW_COLUMN_SPECS",
    "IMA_RISK_FACTOR_MASTER_TARGET",
    "RiskFactorMasterBatch",
    "RiskFactorMasterMappingResult",
    "RiskFactorMasterTableMapping",
    "RiskFactorMasterValidationReport",
    "build_risk_factor_master_batch_from_arrow",
    "input_hash_for_risk_factor_master_batch",
    "materialize_risk_factor_master_from_mapping",
    "materialize_risk_factor_master_from_rows",
]


@dataclass(frozen=True)
class RiskFactorMasterMappingResult:
    """Materialized risk-factor master batch and validation report."""

    batch: RiskFactorMasterBatch
    report: RiskFactorMasterValidationReport


def materialize_risk_factor_master_from_mapping(
    mapping_spec: ImaMappingSpec,
    *,
    source_root: str | Path = ".",
) -> RiskFactorMasterMappingResult:
    """Read the configured CSV source and materialize a risk-factor master batch.

    Parameters
    ----------
    mapping_spec : ImaMappingSpec
        Parsed v1 IMA mapping spec with ``risk_factor_master`` table metadata.
    source_root : str | Path, optional
        Root directory used to resolve ``risk_factor_master.source``.

    Returns
    -------
    RiskFactorMasterMappingResult
        Materialized risk-factor master batch and validation report.
    """

    table = mapping_spec.risk_factor_master
    if table is None:
        raise MappingSpecError("tables.risk_factor_master is required for risk-factor mapping")
    source_path = (Path(source_root) / table.source).resolve()
    if source_path.suffix.lower() != ".csv":
        raise MappingSpecError("risk_factor_master.source currently supports CSV files only")
    source_text = source_path.read_text(encoding="utf-8")
    rows = tuple(csv.DictReader(source_text.splitlines()))
    return materialize_risk_factor_master_from_rows(
        rows,
        mapping_spec,
        source_file=table.source,
        source_hash=stable_mapping_hash({"source_text": source_text}),
    )


def materialize_risk_factor_master_from_rows(
    rows: Sequence[Mapping[str, object]],
    mapping_spec: ImaMappingSpec,
    *,
    source_file: str = "<rows>",
    source_hash: str | None = None,
) -> RiskFactorMasterMappingResult:
    """Materialize risk-factor master rows from already-loaded source rows.

    Parameters
    ----------
    rows : Sequence[Mapping[str, object]]
        Client-shaped risk-factor rows keyed by source column names.
    mapping_spec : ImaMappingSpec
        Parsed v1 IMA mapping spec with field mappings for risk-factor rows.
    source_file : str, optional
        Logical source identifier recorded in the validation report.
    source_hash : str | None, optional
        Precomputed source hash; derived from ``rows`` when omitted.

    Returns
    -------
    RiskFactorMasterMappingResult
        Materialized risk-factor master batch and generated validation report.
    """

    table = mapping_spec.risk_factor_master
    if table is None:
        raise MappingSpecError("tables.risk_factor_master is required for risk-factor mapping")
    row_hash = source_hash or stable_mapping_hash({"rows": [plain_mapping(row) for row in rows]})
    accepted, findings = _accepted_risk_factor_master_rows(rows, table.fields)
    arrow_table = _risk_factor_master_arrow_from_accepted(
        accepted,
        source_hash=row_hash,
        mapping_hash=mapping_spec.spec_hash,
    )
    batch = build_risk_factor_master_batch_from_arrow(arrow_table)
    if batch.row_count != len(accepted):
        raise ValueError(
            "Risk-factor master Arrow normalizer changed accepted row count: "
            f"accepted={len(accepted)}, batch={batch.row_count}"
        )
    report = RiskFactorMasterValidationReport(
        target_schema=mapping_spec.target_schema,
        source_system=mapping_spec.source_system,
        source_file=source_file,
        mapping_hash=mapping_spec.spec_hash,
        source_hash=row_hash,
        row_count_read=len(rows),
        row_count_mapped=batch.row_count,
        row_count_rejected=len(rows) - len(accepted),
        findings=tuple(findings),
    )
    return RiskFactorMasterMappingResult(batch=batch, report=report)


def build_risk_factor_master_batch_from_arrow(
    table: NormalizedArrowTable,
) -> RiskFactorMasterBatch:
    """Build a risk-factor master batch from a normalized Arrow table.

    Parameters
    ----------
    table : NormalizedArrowTable
        Normalized canonical risk-factor master table.

    Returns
    -------
    RiskFactorMasterBatch
        Accepted risk-factor master batch with source lineage.
    """

    if not isinstance(table, NormalizedArrowTable):
        raise ValueError("table must be NormalizedArrowTable")
    accepted = table.accepted
    return RiskFactorMasterBatch(
        risk_factor_names=np.asarray(_column_values(accepted, "risk_factor_name"), dtype=np.str_),
        risk_factor_ids=np.asarray(
            _column_values(accepted, "risk_factor_id", default=""),
            dtype=np.str_,
        ),
        risk_factor_mapping_versions=np.asarray(
            _column_values(accepted, "risk_factor_mapping_version", default=""),
            dtype=np.str_,
        ),
        risk_classes=np.asarray(_column_values(accepted, "risk_class"), dtype=np.str_),
        liquidity_horizons=np.asarray(
            _column_values(accepted, "liquidity_horizon"), dtype=np.int64
        ),
        buckets=np.asarray(_column_values(accepted, "bucket"), dtype=np.str_),
        effective_dates=np.asarray(
            _column_values(accepted, "effective_date"), dtype="datetime64[D]"
        ),
        source_row_ids=np.asarray(_column_values(accepted, "source_row_id"), dtype=np.str_),
        source_hash=table.source_hash or "",
        mapping_hash=str((table.metadata or {}).get("mapping_hash", "")),
        table_hash=normalized_arrow_table_hash(table),
    )


def _accepted_risk_factor_master_rows(
    rows: Sequence[Mapping[str, object]],
    fields: Mapping[str, FieldMapping],
) -> tuple[list[dict[str, object]], list[MappingFinding]]:
    accepted: list[dict[str, object]] = []
    findings: list[MappingFinding] = []
    seen_keys: set[tuple[str, date]] = set()
    for row_index, row in enumerate(rows, start=1):
        source_row_id = resolve_source_row_id(row, row_index, fields, findings=findings)
        try:
            mapped = _map_risk_factor_master_row(row, fields, source_row_id=source_row_id)
        except ValueError as exc:
            findings.append(_finding("RISK_FACTOR_MASTER_ROW_REJECTED", str(exc), source_row_id))
            continue
        key = (str(mapped["risk_factor_name"]), _require_date(mapped["effective_date"]))
        if key in seen_keys:
            findings.append(
                _finding(
                    "RISK_FACTOR_MASTER_DUPLICATE_KEY",
                    "risk_factor_master contains duplicate risk_factor_name/effective_date",
                    source_row_id,
                )
            )
            continue
        seen_keys.add(key)
        accepted.append(mapped)
    if not accepted:
        raise ValueError("risk-factor master mapping produced no accepted rows")
    return accepted, findings


def _map_risk_factor_master_row(
    row: Mapping[str, object],
    fields: Mapping[str, FieldMapping],
    *,
    source_row_id: str,
) -> dict[str, object]:
    risk_class = _risk_class(mapped_str(row, fields["risk_class"], "risk_class"))
    liquidity_horizon = _liquidity_horizon(
        mapped_value(row, fields["liquidity_horizon"], "liquidity_horizon")
    )
    return {
        "risk_factor_name": mapped_str(row, fields["risk_factor_name"], "risk_factor_name"),
        "risk_factor_id": _optional_str(row, fields.get("risk_factor_id"), "risk_factor_id"),
        "risk_factor_mapping_version": _optional_str(
            row,
            fields.get("risk_factor_mapping_version"),
            "risk_factor_mapping_version",
        ),
        "risk_class": risk_class.value,
        "liquidity_horizon": liquidity_horizon.value,
        "bucket": _optional_str(row, fields.get("bucket"), "bucket"),
        "effective_date": mapped_date(row, fields["effective_date"], "effective_date"),
        "source_row_id": source_row_id,
    }


def _risk_factor_master_arrow_from_accepted(
    accepted: Sequence[Mapping[str, object]],
    *,
    source_hash: str,
    mapping_hash: str,
) -> NormalizedArrowTable:
    return normalize_arrow_table(
        pa.table({key: [row[key] for row in accepted] for key in accepted[0]}),
        column_specs=IMA_RISK_FACTOR_MASTER_ARROW_COLUMN_SPECS,
        metadata={"mapping_hash": mapping_hash},
        source_hash=source_hash,
        require_unique_row_ids=True,
    )


def _risk_class(value: str) -> RiskClass:
    normalized = value.strip().upper()
    try:
        return RiskClass(normalized)
    except ValueError as exc:
        raise ValueError(
            f"risk_class must be one of {', '.join(item.value for item in RiskClass)}"
        ) from exc


def _liquidity_horizon(value: object) -> LiquidityHorizon:
    if value is None or str(value).strip() == "":
        raise ValueError("liquidity_horizon is required")
    text = str(value).strip().upper().removeprefix("LH").removesuffix("D")
    try:
        return LiquidityHorizon(int(text))
    except ValueError as exc:
        raise ValueError("liquidity_horizon must be one of 10, 20, 40, 60, 120") from exc


def _optional_str(row: Mapping[str, object], mapping: FieldMapping | None, field: str) -> str:
    if mapping is None:
        return ""
    try:
        value = mapped_value(row, mapping, field)
    except ValueError as exc:
        if mapping.constant is None and mapping.source is not None and mapping.source not in row:
            return ""
        raise exc
    if value is None:
        return ""
    return str(value).strip()


def _require_date(value: object) -> date:
    if not isinstance(value, date):
        raise TypeError("effective_date must be a date")
    return value


def _finding(code: str, message: str, source_row_id: str) -> MappingFinding:
    return MappingFinding(
        severity="ERROR",
        code=code,
        message=message,
        row_id=source_row_id,
    )


def _column_values(
    table: pa.Table, column_name: str, *, default: object | None = None
) -> list[object]:
    if column_name not in table.column_names:
        if default is None:
            raise KeyError(column_name)
        return [default] * table.num_rows
    values: Sequence[object] = table.column(column_name).to_pylist()
    return list(values)
