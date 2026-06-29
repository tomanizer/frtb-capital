"""Mapping-spec adapter for RFET observation source rows."""

from __future__ import annotations

import csv
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

import pyarrow as pa  # type: ignore[import-untyped]

from frtb_ima.adapters._mapping_hash import stable_mapping_hash
from frtb_ima.adapters._mapping_row_helpers import (
    mapped_date,
    mapped_str,
    mapped_value,
    plain_mapping,
    resolve_source_row_id,
)
from frtb_ima.adapters._rfet_observation_mapping_types import RfetObservationValidationReport
from frtb_ima.adapters.arrow import (
    build_rfet_observation_batch_from_arrow,
    normalize_ima_rfet_observation_arrow_table,
)
from frtb_ima.adapters.mapping_spec import (
    FieldMapping,
    ImaMappingSpec,
    MappingFinding,
    MappingSpecError,
)
from frtb_ima.rfet_evidence import RFETObservationBatch

_OPTIONAL_STRING_FIELDS = (
    "source",
    "vendor_id",
    "venue",
    "feed",
    "date_normalization_evidence",
    "verifiability_reason",
    "data_pool_id",
    "vendor_audit_evidence_id",
    "source_row_id",
)
_OPTIONAL_FIELDS = (*_OPTIONAL_STRING_FIELDS, "observation_timestamp", "verifiable")


@dataclass(frozen=True)
class RfetObservationMappingResult:
    """Materialized RFET observation batch plus generated validation report."""

    batch: RFETObservationBatch
    report: RfetObservationValidationReport


def materialize_rfet_observations_from_mapping(
    mapping_spec: ImaMappingSpec,
    *,
    source_root: str | Path = ".",
) -> RfetObservationMappingResult:
    """Read the configured CSV source and materialize RFET observations.

    Parameters
    ----------
    mapping_spec : ImaMappingSpec
        Parsed v1 IMA mapping spec with ``rfet_observations`` table metadata.
    source_root : str | Path, optional
        Root directory used to resolve ``rfet_observations.source``.

    Returns
    -------
    RfetObservationMappingResult
        Materialized RFET observation batch plus generated validation report.
    """

    table = mapping_spec.rfet_observations
    if table is None:
        raise MappingSpecError("tables.rfet_observations is required for RFET observation mapping")
    source_path = (Path(source_root) / table.source).resolve()
    if source_path.suffix.lower() != ".csv":
        raise MappingSpecError("rfet_observations.source currently supports CSV files only")
    source_text = source_path.read_text(encoding="utf-8")
    rows = tuple(csv.DictReader(source_text.splitlines()))
    return materialize_rfet_observations_from_rows(
        rows,
        mapping_spec,
        source_file=table.source,
        source_hash=stable_mapping_hash({"source_text": source_text}),
    )


def materialize_rfet_observations_from_rows(
    rows: Sequence[Mapping[str, object]],
    mapping_spec: ImaMappingSpec,
    *,
    source_file: str = "<rows>",
    source_hash: str | None = None,
) -> RfetObservationMappingResult:
    """Materialize RFET observations from already-loaded source rows.

    Parameters
    ----------
    rows : Sequence[Mapping[str, object]]
        Client-shaped RFET observation rows keyed by source column names.
    mapping_spec : ImaMappingSpec
        Parsed v1 IMA mapping spec with field mappings for RFET observations.
    source_file : str, optional
        Logical source identifier recorded in the validation report.
    source_hash : str | None, optional
        Precomputed source hash; derived from ``rows`` when omitted.

    Returns
    -------
    RfetObservationMappingResult
        Materialized RFET observation batch plus generated validation report.
    """

    table = mapping_spec.rfet_observations
    if table is None:
        raise MappingSpecError("tables.rfet_observations is required for RFET observation mapping")
    row_hash = source_hash or stable_mapping_hash({"rows": [plain_mapping(row) for row in rows]})
    accepted: list[dict[str, object]] = []
    findings: list[MappingFinding] = []
    for row_index, row in enumerate(rows, start=1):
        source_row_id = resolve_source_row_id(row, row_index, table.fields, findings=findings)
        try:
            accepted.append(_map_rfet_row(row, table.fields, source_row_id=source_row_id))
        except ValueError as exc:
            findings.append(
                MappingFinding(
                    severity="ERROR",
                    code="RFET_OBSERVATION_ROW_REJECTED",
                    message=str(exc),
                    row_id=source_row_id,
                )
            )
    accepted.sort(
        key=lambda item: (
            str(item["risk_factor_name"]),
            item["observation_date"],
            str(item["source_row_id"]),
        )
    )
    if not accepted:
        raise ValueError("RFET observation mapping produced no accepted rows")
    handoff = normalize_ima_rfet_observation_arrow_table(
        pa.table({key: [row[key] for row in accepted] for key in accepted[0]}),
        source_hash=row_hash,
        metadata={"mapping_hash": mapping_spec.spec_hash},
    )
    batch = build_rfet_observation_batch_from_arrow(handoff)
    if batch.observation_count != len(accepted):
        raise ValueError(
            "RFET Arrow normalizer dropped mapped rows: "
            f"accepted={len(accepted)}, batch={batch.observation_count}"
        )
    report = RfetObservationValidationReport(
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
    return RfetObservationMappingResult(batch=batch, report=report)


def _map_rfet_row(
    row: Mapping[str, object],
    fields: Mapping[str, FieldMapping],
    *,
    source_row_id: str,
) -> dict[str, object]:
    mapped: dict[str, object] = {
        "risk_factor_name": mapped_str(row, fields["risk_factor_name"], "risk_factor_name"),
        "observation_date": mapped_date(row, fields["observation_date"], "observation_date"),
    }
    for field_name in _OPTIONAL_STRING_FIELDS:
        mapped[field_name] = (
            source_row_id
            if field_name == "source_row_id"
            else _optional_str(row, fields.get(field_name))
        )
    mapped["observation_timestamp"] = _optional_str(row, fields.get("observation_timestamp"))
    mapped["verifiable"] = _optional_bool(row, fields.get("verifiable"))
    return mapped


def _optional_str(row: Mapping[str, object], mapping: FieldMapping | None) -> str | None:
    if mapping is None:
        return None
    value = mapped_value(row, mapping, "optional field")
    text = "" if value is None else str(value).strip()
    return None if not text else text


def _optional_bool(row: Mapping[str, object], mapping: FieldMapping | None) -> bool | None:
    if mapping is None:
        return None
    value = _optional_str(row, mapping)
    if value is None:
        return None
    normalized = value.lower()
    if normalized in {"true", "t", "yes", "y", "1"}:
        return True
    if normalized in {"false", "f", "no", "n", "0"}:
        return False
    raise ValueError("verifiable must be boolean-like")


__all__ = [
    "RfetObservationMappingResult",
    "materialize_rfet_observations_from_mapping",
    "materialize_rfet_observations_from_rows",
]
