"""
Deterministic SBM audit serialization and reconciliation.

Regulatory traceability:
    Basel MAR21 component traceability by formula.
    SBM-AUDIT-001, SBM-FUNC-021, SBM-FUNC-022.
"""

from __future__ import annotations

import hashlib
import json
from datetime import date
from enum import Enum
from typing import Any

from frtb_sbm.data_models import (
    BucketCapital,
    RiskClassCapital,
    SbmCapitalResult,
    SbmReconciliationMetadata,
    SbmSensitivity,
    SbmSourceLineage,
    WeightedSensitivity,
)
from frtb_sbm.numeric import is_reconciled
from frtb_sbm.validation import SbmInputError, validate_sbm_sensitivities

_HASH_HEX_LENGTH = 64


def input_hash_for_sensitivities(sensitivities: object) -> str:
    """Return a deterministic hash of canonical SBM input sensitivities."""

    validated = validate_sbm_sensitivities(sensitivities)
    return _input_hash_for_validated_sensitivities(validated)


def _input_hash_for_validated_sensitivities(
    sensitivities: tuple[SbmSensitivity, ...],
) -> str:
    """Return an input hash for an already validated sensitivity tuple."""

    return _hash_payload(
        {"sensitivities": [_sensitivity_payload(sensitivity) for sensitivity in sensitivities]}
    )


def serialize_sbm_result(result: SbmCapitalResult) -> dict[str, object]:
    """Return a JSON-serialisable audit payload for an SBM result."""

    return {
        "total_capital": result.total_capital,
        "profile_id": result.profile_id,
        "profile_hash": result.profile_hash,
        "input_hash": result.input_hash,
        "warnings": list(result.warnings),
        "unsupported_flags": list(result.unsupported_flags),
        "risk_classes": [_risk_class_payload(risk_class) for risk_class in result.risk_classes],
        "reconciliation": _reconciliation_payload(result.reconciliation),
    }


def validate_sbm_result_reconciliation(result: SbmCapitalResult) -> None:
    """Raise when a public SBM result does not reconcile to its capital records."""

    _validate_hash("profile_hash", result.profile_hash)
    _validate_hash("input_hash", result.input_hash)

    expected_total = sum(risk_class.selected_capital for risk_class in result.risk_classes)
    if not is_reconciled(result.total_capital, expected_total):
        raise SbmInputError(
            "total capital does not reconcile to risk-class selected capital",
            field="total_capital",
        )

    for risk_class in result.risk_classes:
        _validate_risk_class_reconciliation(risk_class)


def _validate_risk_class_reconciliation(risk_class: RiskClassCapital) -> None:
    if risk_class.scenario_totals is None or risk_class.selected_scenario is None:
        raise SbmInputError(
            "risk-class capital must include scenario totals and selected scenario",
            field="risk_classes",
        )

    selected_total = float(risk_class.scenario_totals[risk_class.selected_scenario])
    if not is_reconciled(risk_class.selected_capital, selected_total):
        raise SbmInputError(
            "selected risk-class capital does not reconcile to selected scenario total",
            field="selected_capital",
        )

    expected_selected = max(risk_class.scenario_totals.values())
    if not is_reconciled(risk_class.selected_capital, expected_selected):
        raise SbmInputError(
            "selected risk-class capital does not reconcile to maximum scenario total",
            field="selected_capital",
        )


def _validate_hash(field: str, value: str) -> None:
    if not isinstance(value, str) or len(value) != _HASH_HEX_LENGTH:
        raise SbmInputError("hash must be a sha256 hex digest", field=field)
    try:
        int(value, 16)
    except ValueError as exc:
        raise SbmInputError("hash must be a sha256 hex digest", field=field) from exc


def _risk_class_payload(risk_class: RiskClassCapital) -> dict[str, object]:
    payload: dict[str, object] = {
        "risk_class": risk_class.risk_class.value,
        "selected_capital": risk_class.selected_capital,
        "citation_ids": list(risk_class.citation_ids),
        "buckets": [_bucket_payload(bucket) for bucket in risk_class.buckets],
    }
    if risk_class.risk_measure is not None:
        payload["risk_measure"] = risk_class.risk_measure.value
    if risk_class.scenario_totals is not None:
        payload["scenario_totals"] = {
            label.value: total for label, total in sorted(risk_class.scenario_totals.items())
        }
    if risk_class.selected_scenario is not None:
        payload["selected_scenario"] = risk_class.selected_scenario.value
    return payload


def _bucket_payload(bucket: BucketCapital) -> dict[str, object]:
    payload: dict[str, object] = {
        "bucket_id": bucket.bucket_id,
        "risk_class": bucket.risk_class.value,
        "risk_measure": bucket.risk_measure.value,
        "kb": bucket.kb,
        "citation_ids": list(bucket.citation_ids),
        "weighted_sensitivities": [
            _weighted_sensitivity_payload(item) for item in bucket.weighted_sensitivities
        ],
        "floor_applied": bucket.floor_applied,
    }
    if bucket.sb is not None:
        payload["sb"] = bucket.sb
    if bucket.scenario is not None:
        payload["scenario"] = bucket.scenario.value
    return payload


def _weighted_sensitivity_payload(item: WeightedSensitivity) -> dict[str, object]:
    payload: dict[str, object] = {
        "sensitivity_id": item.sensitivity_id,
        "risk_class": item.risk_class.value,
        "risk_measure": item.risk_measure.value,
        "bucket": item.bucket,
        "raw_amount": item.raw_amount,
        "risk_weight": item.risk_weight,
        "scaled_amount": item.scaled_amount,
        "citation_ids": list(item.citation_ids),
    }
    if item.qualifier is not None:
        payload["qualifier"] = item.qualifier
    return payload


def _reconciliation_payload(
    reconciliation: SbmReconciliationMetadata | None,
) -> dict[str, object] | None:
    if reconciliation is None:
        return None
    return {
        "input_count": reconciliation.input_count,
        "rejected_input_count": reconciliation.rejected_input_count,
        "requirement_ids": list(reconciliation.requirement_ids),
        "citation_ids": list(reconciliation.citation_ids),
    }


def _sensitivity_payload(sensitivity: SbmSensitivity) -> dict[str, object]:
    payload: dict[str, object] = {
        "sensitivity_id": sensitivity.sensitivity_id,
        "source_row_id": sensitivity.source_row_id,
        "desk_id": sensitivity.desk_id,
        "legal_entity": sensitivity.legal_entity,
        "risk_class": sensitivity.risk_class.value,
        "risk_measure": sensitivity.risk_measure.value,
        "bucket": sensitivity.bucket,
        "risk_factor": sensitivity.risk_factor,
        "amount": sensitivity.amount,
        "amount_currency": sensitivity.amount_currency,
        "sign_convention": sensitivity.sign_convention.value,
        "lineage": _lineage_payload(sensitivity.lineage),
        "mapping_citation_ids": list(sensitivity.mapping_citation_ids),
    }
    optional_fields = {
        "position_id": sensitivity.position_id,
        "qualifier": sensitivity.qualifier,
        "tenor": sensitivity.tenor,
        "option_tenor": sensitivity.option_tenor,
        "liquidity_horizon_days": sensitivity.liquidity_horizon_days,
        "maturity": sensitivity.maturity,
        "up_shock_amount": sensitivity.up_shock_amount,
        "down_shock_amount": sensitivity.down_shock_amount,
    }
    for field_name, value in optional_fields.items():
        if value is not None:
            payload[field_name] = value
    return payload


def _lineage_payload(lineage: SbmSourceLineage) -> dict[str, object]:
    return {
        "source_system": lineage.source_system,
        "source_file": lineage.source_file,
        "source_row_id": lineage.source_row_id,
        "source_column_map": [list(pair) for pair in lineage.source_column_map],
    }


def _hash_payload(payload: dict[str, object]) -> str:
    encoded = bytes(json.dumps(payload, sort_keys=True, separators=(",", ":")), "utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _normalise(value: object) -> Any:
    if isinstance(value, dict):
        return {str(key): _normalise(item) for key, item in sorted(value.items())}
    if isinstance(value, tuple | list):
        return [_normalise(item) for item in value]
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, date):
        return value.isoformat()
    return value


__all__ = [
    "input_hash_for_sensitivities",
    "serialize_sbm_result",
    "validate_sbm_result_reconciliation",
]
