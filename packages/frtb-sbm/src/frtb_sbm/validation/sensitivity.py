"""Canonical sensitivity-row validation for SBM adapters.

Regulatory traceability:
    Basel MAR21.1 input scope, Basel MAR21 risk-class field requirements, and
    SBM-NFR-004 unsupported-feature handling.
"""

from __future__ import annotations

from frtb_sbm._errors import SbmInputError
from frtb_sbm._text import require_text as _require_text
from frtb_sbm.data_models import (
    SbmRiskClass,
    SbmRiskMeasure,
    SbmSensitivity,
    SbmSignConvention,
    SbmSourceLineage,
)
from frtb_sbm.validation.coercion import (
    _coerce_enum,
    normalise_currency_code,
    normalise_sensitivity_amount,
)
from frtb_sbm.validation.risk_class_fields import validate_risk_class_fields


def validate_sbm_sensitivities(sensitivities: object) -> tuple[SbmSensitivity, ...]:
    """Validate canonical SBM sensitivities and return them in input order.
    Parameters
    ----------
    sensitivities : object
        See signature.

    Returns
    -------
    tuple[SbmSensitivity, ...]
    """

    if isinstance(sensitivities, SbmSensitivity):
        raise SbmInputError("sensitivities must be an iterable of SbmSensitivity objects")
    try:
        candidates: tuple[object, ...] = tuple(sensitivities)  # type: ignore[arg-type]
    except TypeError as exc:
        raise SbmInputError("sensitivities must be an iterable of SbmSensitivity objects") from exc

    seen_sensitivity_ids: set[str] = set()
    validated: list[SbmSensitivity] = []
    for candidate in candidates:
        if not isinstance(candidate, SbmSensitivity):
            raise SbmInputError("sensitivities must contain only SbmSensitivity objects")
        sensitivity = candidate
        _validate_sensitivity(sensitivity, seen_sensitivity_ids)
        seen_sensitivity_ids.add(sensitivity.sensitivity_id)
        validated.append(sensitivity)
    return tuple(validated)


def _validate_sensitivity(sensitivity: SbmSensitivity, seen_sensitivity_ids: set[str]) -> None:
    sensitivity_id = _require_text(sensitivity.sensitivity_id, "sensitivity_id")
    if sensitivity_id in seen_sensitivity_ids:
        raise SbmInputError(
            "duplicate sensitivity id",
            field="sensitivity_id",
            sensitivity_id=sensitivity_id,
        )

    _require_text(sensitivity.source_row_id, "source_row_id", sensitivity_id)
    _require_text(sensitivity.desk_id, "desk_id", sensitivity_id)
    _require_text(sensitivity.legal_entity, "legal_entity", sensitivity_id)
    _require_text(sensitivity.bucket, "bucket", sensitivity_id)
    _require_text(sensitivity.risk_factor, "risk_factor", sensitivity_id)
    normalise_currency_code(
        sensitivity.amount_currency,
        field="amount_currency",
        sensitivity_id=sensitivity_id,
    )
    normalise_sensitivity_amount(sensitivity.amount, sensitivity_id=sensitivity_id)

    risk_class = _coerce_enum(
        sensitivity.risk_class,
        SbmRiskClass,
        "risk_class",
        sensitivity_id,
    )
    risk_measure = _coerce_enum(
        sensitivity.risk_measure,
        SbmRiskMeasure,
        "risk_measure",
        sensitivity_id,
    )
    _coerce_enum(
        sensitivity.sign_convention,
        SbmSignConvention,
        "sign_convention",
        sensitivity_id,
    )

    if sensitivity.position_id is not None:
        _require_text(sensitivity.position_id, "position_id", sensitivity_id)

    _validate_lineage(sensitivity.lineage, sensitivity_id)
    if sensitivity.source_row_id != sensitivity.lineage.source_row_id:
        raise SbmInputError(
            "source_row_id must match lineage.source_row_id",
            field="source_row_id",
            sensitivity_id=sensitivity_id,
        )

    for citation_id in sensitivity.mapping_citation_ids:
        _require_text(citation_id, "mapping_citation_ids", sensitivity_id)

    validate_risk_class_fields(
        sensitivity,
        risk_class=risk_class,
        risk_measure=risk_measure,
    )


def _validate_lineage(lineage: SbmSourceLineage, sensitivity_id: str) -> None:
    if not isinstance(lineage, SbmSourceLineage):
        raise SbmInputError(
            "invalid source lineage",
            field="lineage",
            sensitivity_id=sensitivity_id,
        )

    _require_text(lineage.source_system, "lineage.source_system", sensitivity_id)
    _require_text(lineage.source_file, "lineage.source_file", sensitivity_id)
    _require_text(lineage.source_row_id, "lineage.source_row_id", sensitivity_id)
    for mapping in lineage.source_column_map:
        if not isinstance(mapping, tuple | list) or len(mapping) != 2:
            raise SbmInputError(
                "source column map entries must be field pairs",
                field="lineage.source_column_map",
                sensitivity_id=sensitivity_id,
            )
        source_field, canonical_field = mapping
        _require_text(source_field, "lineage.source_column_map.source", sensitivity_id)
        _require_text(canonical_field, "lineage.source_column_map.canonical", sensitivity_id)


__all__ = ["validate_sbm_sensitivities"]
