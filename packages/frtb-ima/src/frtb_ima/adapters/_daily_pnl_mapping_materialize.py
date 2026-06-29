"""Materialization for v1 daily P&L mapping specs."""

from __future__ import annotations

import csv
import hashlib
import json
from collections.abc import Mapping, Sequence
from datetime import date
from pathlib import Path

import numpy as np

from frtb_ima.adapters._daily_pnl_mapping_types import (
    DailyPnlMappingResult,
    DailyPnlValidationReport,
    DailyPnlVectorBatch,
    FieldMapping,
    ImaMappingSpec,
    MappingFinding,
    MappingSpecError,
)

_VAR_FIELDS = frozenset({"var_975", "var_99"})


def materialize_daily_pnl_vectors_from_mapping(
    mapping_spec: ImaMappingSpec,
    *,
    source_root: str | Path = ".",
) -> DailyPnlMappingResult:
    """Read the configured CSV source and materialize daily P&L vectors."""

    table = mapping_spec.daily_pnl_vectors
    source_path = (Path(source_root) / table.source).resolve()
    if source_path.suffix.lower() != ".csv":
        raise MappingSpecError("daily_pnl_vectors.source currently supports CSV files only")
    source_text = source_path.read_text(encoding="utf-8")
    rows = tuple(csv.DictReader(source_text.splitlines()))
    return materialize_daily_pnl_vectors_from_rows(
        rows,
        mapping_spec,
        source_file=table.source,
        source_hash=_stable_hash({"source_text": source_text}),
    )


def materialize_daily_pnl_vectors_from_rows(
    rows: Sequence[Mapping[str, object]],
    mapping_spec: ImaMappingSpec,
    *,
    source_file: str = "<rows>",
    source_hash: str | None = None,
) -> DailyPnlMappingResult:
    """Materialize daily P&L vectors from already-loaded source rows."""

    row_hash = source_hash or _stable_hash({"rows": [_plain_mapping(row) for row in rows]})
    accepted: list[dict[str, object]] = []
    findings: list[MappingFinding] = []
    seen_keys: set[tuple[str, date]] = set()
    sign_multiplier = -1.0 if mapping_spec.pnl_positive_means == "loss" else 1.0

    for row_index, row in enumerate(rows, start=1):
        source_row_id = _source_row_id(row, row_index, mapping_spec.daily_pnl_vectors.fields)
        try:
            mapped = _map_daily_pnl_row(
                row,
                mapping_spec.daily_pnl_vectors.fields,
                source_row_id=source_row_id,
                sign_multiplier=sign_multiplier,
            )
        except ValueError as exc:
            findings.append(_finding("DAILY_PNL_ROW_REJECTED", str(exc), source_row_id))
            continue
        business_date = mapped["business_date"]
        if not isinstance(business_date, date):
            raise TypeError("mapped business_date must be a datetime.date")
        key = (str(mapped["desk_id"]), business_date)
        if key in seen_keys:
            findings.append(
                _finding(
                    "DAILY_PNL_DUPLICATE_DESK_DATE",
                    "daily_pnl_vectors contains duplicate desk_id/business_date "
                    f"for {key[0]} on {key[1].isoformat()}",
                    source_row_id,
                )
            )
            continue
        seen_keys.add(key)
        accepted.append(mapped)

    accepted.sort(key=lambda item: (str(item["desk_id"]), item["business_date"], str(item["source_row_id"])))
    batch = _daily_pnl_batch_from_accepted(accepted, source_hash=row_hash, mapping_hash=mapping_spec.spec_hash)
    report = DailyPnlValidationReport(
        target_schema=mapping_spec.target_schema,
        source_system=mapping_spec.source_system,
        source_file=source_file,
        mapping_hash=mapping_spec.spec_hash,
        source_hash=row_hash,
        row_count_read=len(rows),
        row_count_mapped=batch.observation_count,
        row_count_rejected=len(rows) - batch.observation_count,
        findings=tuple(findings),
    )
    return DailyPnlMappingResult(batch=batch, report=report)


def _map_daily_pnl_row(
    row: Mapping[str, object],
    fields: Mapping[str, FieldMapping],
    *,
    source_row_id: str,
    sign_multiplier: float,
) -> dict[str, object]:
    mapped: dict[str, object] = {
        "desk_id": _mapped_str(row, fields["desk_id"], "desk_id"),
        "business_date": _mapped_date(row, fields["business_date"], "business_date"),
        "apl": _mapped_float(row, fields["apl"], "apl") * sign_multiplier,
        "hpl": _mapped_float(row, fields["hpl"], "hpl") * sign_multiplier,
        "rtpl": _mapped_float(row, fields["rtpl"], "rtpl") * sign_multiplier,
        "var_975": 0.0,
        "var_99": 0.0,
        "var_975_present": False,
        "var_99_present": False,
        "source_row_id": source_row_id,
    }
    for field_name in _VAR_FIELDS:
        if field_name not in fields:
            continue
        value = _mapped_optional_float(row, fields[field_name], field_name)
        if value is not None and value < 0.0:
            raise ValueError(f"{field_name} must use positive_magnitude convention")
        mapped[field_name] = 0.0 if value is None else value
        mapped[f"{field_name}_present"] = value is not None
    return mapped


def _daily_pnl_batch_from_accepted(
    accepted: Sequence[Mapping[str, object]],
    *,
    source_hash: str,
    mapping_hash: str,
) -> DailyPnlVectorBatch:
    if not accepted:
        raise ValueError("daily P&L mapping produced no accepted rows")
    return DailyPnlVectorBatch(
        desk_ids=np.asarray([item["desk_id"] for item in accepted], dtype=np.str_),
        business_dates=np.asarray([item["business_date"] for item in accepted], dtype="datetime64[D]"),
        apl=np.asarray([item["apl"] for item in accepted], dtype=np.float64),
        hpl=np.asarray([item["hpl"] for item in accepted], dtype=np.float64),
        rtpl=np.asarray([item["rtpl"] for item in accepted], dtype=np.float64),
        var_975=np.asarray([item["var_975"] for item in accepted], dtype=np.float64),
        var_99=np.asarray([item["var_99"] for item in accepted], dtype=np.float64),
        var_975_present=np.asarray([item["var_975_present"] for item in accepted], dtype=np.bool_),
        var_99_present=np.asarray([item["var_99_present"] for item in accepted], dtype=np.bool_),
        source_row_ids=np.asarray([item["source_row_id"] for item in accepted], dtype=np.str_),
        source_hash=source_hash,
        mapping_hash=mapping_hash,
    )


def _mapped_value(row: Mapping[str, object], mapping: FieldMapping, field_name: str) -> object:
    if mapping.constant is not None:
        value: object = mapping.constant
    else:
        assert mapping.source is not None
        if mapping.source not in row:
            raise ValueError(f"{field_name} source column {mapping.source!r} is missing")
        value = row[mapping.source]
    if value is None:
        return None
    text = str(value)
    return mapping.values.get(text, value)


def _mapped_str(row: Mapping[str, object], mapping: FieldMapping, field_name: str) -> str:
    value = _mapped_value(row, mapping, field_name)
    text = "" if value is None else str(value).strip()
    if not text:
        raise ValueError(f"{field_name} is required")
    return text


def _mapped_date(row: Mapping[str, object], mapping: FieldMapping, field_name: str) -> date:
    try:
        return date.fromisoformat(_mapped_str(row, mapping, field_name))
    except ValueError as exc:
        raise ValueError(f"{field_name} must be an ISO date") from exc


def _mapped_float(row: Mapping[str, object], mapping: FieldMapping, field_name: str) -> float:
    value = _mapped_optional_float(row, mapping, field_name)
    if value is None:
        raise ValueError(f"{field_name} is required")
    return value


def _mapped_optional_float(row: Mapping[str, object], mapping: FieldMapping, field_name: str) -> float | None:
    value = _mapped_value(row, mapping, field_name)
    if value is None or str(value).strip() == "":
        return None
    try:
        result = float(str(value).replace(",", ""))
    except ValueError as exc:
        raise ValueError(f"{field_name} must be numeric") from exc
    if not np.isfinite(result):
        raise ValueError(f"{field_name} must be finite")
    return result


def _source_row_id(row: Mapping[str, object], row_index: int, fields: Mapping[str, FieldMapping]) -> str:
    mapping = fields.get("source_row_id")
    if mapping is None:
        return f"row-{row_index}"
    try:
        return _mapped_str(row, mapping, "source_row_id")
    except ValueError:
        return f"row-{row_index}"


def _finding(code: str, message: str, row_id: str) -> MappingFinding:
    return MappingFinding(severity="ERROR", code=code, message=message, row_id=row_id)


def _plain_mapping(row: Mapping[str, object]) -> dict[str, str]:
    return {str(key): "" if value is None else str(value) for key, value in row.items()}


def _stable_hash(payload: Mapping[str, object]) -> str:
    data = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    return hashlib.sha256(data).hexdigest()
