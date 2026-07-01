"""Risk-factor metadata row serialization helpers for result-store tables."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date, datetime

from frtb_result_store._row_codecs import (
    int_value as _int_value,
)
from frtb_result_store._row_codecs import (
    json_mapping as _json_mapping,
)
from frtb_result_store._row_codecs import (
    metadata_json as _metadata_json,
)
from frtb_result_store._row_codecs import (
    optional_text as _optional_text,
)
from frtb_result_store._row_codecs import (
    stored_value as _stored_value,
)
from frtb_result_store.model import (
    RiskFactorEvidenceState,
    RiskFactorMetadataRecord,
    RiskFactorMetadataSnapshot,
    RiskFactorRecordStatus,
    RiskFactorSourceMapping,
)

__all__ = [
    "_risk_factor_metadata_from_row",
    "_risk_factor_metadata_row",
    "_risk_factor_snapshot_from_row",
    "_risk_factor_snapshot_row",
    "_risk_factor_source_mapping_from_row",
    "_risk_factor_source_mapping_row",
]


def _risk_factor_snapshot_row(snapshot: RiskFactorMetadataSnapshot) -> dict[str, object]:
    return {
        "run_id": snapshot.run_id,
        "snapshot_id": snapshot.snapshot_id,
        "mapping_version": snapshot.mapping_version.value,
        "effective_date": snapshot.effective_date.isoformat(),
        "source_system": snapshot.source_system,
        "created_at": snapshot.created_at.isoformat(),
        "metadata_json": _metadata_json(snapshot.metadata),
    }


def _risk_factor_metadata_row(record: RiskFactorMetadataRecord) -> dict[str, object]:
    return {
        "run_id": record.run_id,
        "snapshot_id": record.snapshot_id,
        "risk_factor_id": record.risk_factor_id.value,
        "display_name": record.display_name,
        "risk_class": record.risk_class.value,
        "risk_factor_type": record.risk_factor_type.value,
        "mapping_version": record.mapping_version.value,
        "bucket_id": None if record.bucket_id is None else record.bucket_id.value,
        "bucket_label": record.bucket_label,
        "sensitivity_type": None
        if record.sensitivity_type is None
        else record.sensitivity_type.value,
        "currency": None if record.currency is None else record.currency.value,
        "curve_id": record.curve_id,
        "tenor": None if record.tenor is None else record.tenor.value,
        "issuer_id": record.issuer_id,
        "obligor_id": record.obligor_id,
        "counterparty_id": record.counterparty_id,
        "commodity_id": record.commodity_id,
        "equity_id": record.equity_id,
        "status": _stored_value(record.status),
        "rfet_evidence_state": _stored_value(record.rfet_evidence_state),
        "rfet_evidence_id": None
        if record.rfet_evidence_id is None
        else record.rfet_evidence_id.value,
        "modellability_state": _stored_value(record.modellability_state),
        "liquidity_horizon_days": record.liquidity_horizon_days,
        "nmrf_state": _stored_value(record.nmrf_state),
        "stress_period_id": record.stress_period_id,
        "source_system": record.source_system,
        "source_row_id": record.source_row_id,
        "metadata_json": _metadata_json(record.metadata),
    }


def _risk_factor_source_mapping_row(mapping: RiskFactorSourceMapping) -> dict[str, object]:
    return {
        "run_id": mapping.run_id,
        "snapshot_id": mapping.snapshot_id,
        "risk_factor_id": mapping.risk_factor_id.value,
        "source_system": mapping.source_system,
        "source_row_id": mapping.source_row_id,
        "mapping_version": mapping.mapping_version.value,
        "relationship": mapping.relationship,
        "source_hash": mapping.source_hash,
        "metadata_json": _metadata_json(mapping.metadata),
    }


def _risk_factor_snapshot_from_row(row: Sequence[object]) -> RiskFactorMetadataSnapshot:
    return RiskFactorMetadataSnapshot(
        run_id=str(row[0]),
        snapshot_id=str(row[1]),
        mapping_version=str(row[2]),
        effective_date=date.fromisoformat(str(row[3])),
        source_system=str(row[4]),
        created_at=datetime.fromisoformat(str(row[5])),
        metadata=_json_mapping(row[6]),
    )


def _risk_factor_metadata_from_row(row: Sequence[object]) -> RiskFactorMetadataRecord:
    liquidity_horizon = None if row[22] is None else _int_value(row[22])
    return RiskFactorMetadataRecord(
        run_id=str(row[0]),
        snapshot_id=str(row[1]),
        risk_factor_id=str(row[2]),
        display_name=str(row[3]),
        risk_class=str(row[4]),
        risk_factor_type=str(row[5]),
        mapping_version=str(row[6]),
        bucket_id=_optional_text(row[7]),
        bucket_label=_optional_text(row[8]),
        sensitivity_type=_optional_text(row[9]),
        currency=_optional_text(row[10]),
        curve_id=_optional_text(row[11]),
        tenor=_optional_text(row[12]),
        issuer_id=_optional_text(row[13]),
        obligor_id=_optional_text(row[14]),
        counterparty_id=_optional_text(row[15]),
        commodity_id=_optional_text(row[16]),
        equity_id=_optional_text(row[17]),
        status=RiskFactorRecordStatus(str(row[18])),
        rfet_evidence_state=RiskFactorEvidenceState(str(row[19])),
        rfet_evidence_id=_optional_text(row[20]),
        modellability_state=RiskFactorEvidenceState(str(row[21])),
        liquidity_horizon_days=liquidity_horizon,
        nmrf_state=RiskFactorEvidenceState(str(row[23])),
        stress_period_id=_optional_text(row[24]),
        source_system=_optional_text(row[25]),
        source_row_id=_optional_text(row[26]),
        metadata=_json_mapping(row[27]),
    )


def _risk_factor_source_mapping_from_row(row: Sequence[object]) -> RiskFactorSourceMapping:
    return RiskFactorSourceMapping(
        run_id=str(row[0]),
        snapshot_id=str(row[1]),
        risk_factor_id=str(row[2]),
        source_system=str(row[3]),
        source_row_id=str(row[4]),
        mapping_version=str(row[5]),
        relationship=str(row[6]),
        source_hash=_optional_text(row[7]),
        metadata=_json_mapping(row[8]),
    )
