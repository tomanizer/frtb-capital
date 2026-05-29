"""
Optional CRIF/FNet-to-canonical RRAO adapter.

Regulatory traceability:
    See docs/REGULATORY_TRACEABILITY.md rows for crif.py, Basel MAR23,
    U.S. NPR 2.0 proposed section __.211, and public implementation-reference
    adapter boundaries.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from frtb_rrao.data_models import (
    RraoClassification,
    RraoEvidenceType,
    RraoExclusionReason,
    RraoPosition,
    RraoSourceLineage,
)
from frtb_rrao.validation import (
    NotionalSignConvention,
    RraoInputError,
    normalise_gross_effective_notional,
    validate_rrao_positions,
)

_CRIF_EXOTIC_RISK_TYPES = frozenset({"RRAO_1_PERCENT", "RRAO_1PCT", "RRAO_100BP"})
_CRIF_OTHER_RISK_TYPES = frozenset(
    {"RRAO_01_PERCENT", "RRAO_0_1_PERCENT", "RRAO_0.1_PERCENT", "RRAO_10BP"}
)
_CRIF_EXCLUSION_RISK_TYPES = frozenset({"RRAO_0_PERCENT", "RRAO_0PCT"})
_EXOTIC_BUCKETS = frozenset({"EXOTIC", "RRAO_1_PERCENT"})
_OTHER_BUCKETS = frozenset({"NON-EXOTIC", "NON_EXOTIC", "OTHER", "RRAO_01_PERCENT"})
_EXCLUDED_BUCKETS = frozenset({"EXCLUDED", "RRAO_0_PERCENT"})
_GROSS_NOTIONAL_CONVENTIONS = frozenset({"GROSS", "GROSS_EFFECTIVE", "GROSS_EFFECTIVE_NOTIONAL"})

_POSITION_ID_FIELDS = ("PositionID", "PositionId", "position_id", "TradeId", "TradeID")
_SOURCE_ROW_ID_FIELDS = ("RowID", "RowId", "source_row_id", "SourceRowID")
_DESK_FIELDS = ("DeskID", "Desk", "desk_id")
_LEGAL_ENTITY_FIELDS = ("LegalEntity", "LegalEntityID", "Entity", "legal_entity")
_CURRENCY_FIELDS = ("Currency", "currency", "Ccy")
_NOTIONAL_FIELDS = (
    "GrossEffectiveNotional",
    "gross_effective_notional",
    "AmountUSD",
    "Amount",
    "Notional",
    "WeightedNotional",
)
_RISK_TYPE_FIELDS = ("RiskType", "risk_type", "RiskClass")
_BUCKET_FIELDS = ("Bucket", "bucket")
_EVIDENCE_TYPE_FIELDS = ("EvidenceType", "Evidence", "ResidualRiskEvidence")
_EVIDENCE_LABEL_FIELDS = ("EvidenceLabel", "Description", "ProductType")
_EXCLUSION_REASON_FIELDS = ("ExclusionReason", "exclusion_reason")
_EXCLUSION_EVIDENCE_FIELDS = ("ExclusionEvidenceID", "ExclusionEvidenceId")
_NOTIONAL_CONVENTION_FIELDS = ("NotionalConvention", "notional_convention")

_EVIDENCE_ALIASES = {
    "GAP": RraoEvidenceType.GAP_RISK,
    "GAP_RISK": RraoEvidenceType.GAP_RISK,
    "CORRELATION": RraoEvidenceType.CORRELATION_RISK,
    "CORRELATION_RISK": RraoEvidenceType.CORRELATION_RISK,
    "BEHAVIOURAL": RraoEvidenceType.BEHAVIOURAL_RISK,
    "BEHAVIORAL": RraoEvidenceType.BEHAVIOURAL_RISK,
    "BEHAVIOURAL_RISK": RraoEvidenceType.BEHAVIOURAL_RISK,
    "BEHAVIORAL_RISK": RraoEvidenceType.BEHAVIOURAL_RISK,
    "CTP_THREE_OR_MORE_UNDERLYINGS": RraoEvidenceType.CTP_THREE_OR_MORE_UNDERLYINGS,
    "NON_REPLICABLE_OPTIONALITY": RraoEvidenceType.NON_REPLICABLE_OPTIONALITY,
    "NO_MATURITY_OPTIONALITY": RraoEvidenceType.NO_MATURITY_OPTIONALITY,
    "NO_STRIKE_OR_BARRIER_OPTIONALITY": RraoEvidenceType.NO_STRIKE_OR_BARRIER_OPTIONALITY,
    "MULTIPLE_STRIKE_OR_BARRIER_OPTIONALITY": (
        RraoEvidenceType.MULTIPLE_STRIKE_OR_BARRIER_OPTIONALITY
    ),
}


@dataclass(frozen=True)
class RraoAdapterWarning:
    """Auditable non-fatal adapter mapping warning."""

    source_row_id: str
    field: str
    message: str


@dataclass(frozen=True)
class RraoRejectedRow:
    """Auditable rejected adapter row."""

    source_row_id: str
    reason: str
    field: str
    source_row: tuple[tuple[str, str], ...]


@dataclass(frozen=True)
class RraoAdapterResult:
    """Adapter output: canonical positions plus warnings and rejected rows."""

    positions: tuple[RraoPosition, ...]
    warnings: tuple[RraoAdapterWarning, ...] = ()
    rejected_rows: tuple[RraoRejectedRow, ...] = ()


def adapt_rrao_records(
    records: object,
    *,
    source_system: str = "rrao-adapter",
    source_file: str = "records",
    source_sign_convention: NotionalSignConvention = "gross",
) -> RraoAdapterResult:
    """Convert CRIF/FNet-shaped mappings into canonical RRAO positions."""

    if isinstance(records, Mapping):
        raise RraoInputError("records must be an iterable of mapping rows", field="records")
    try:
        materialised_records: tuple[object, ...] = tuple(records)  # type: ignore[arg-type]
    except TypeError as exc:
        raise RraoInputError(
            "records must be an iterable of mapping rows",
            field="records",
        ) from exc

    positions: list[RraoPosition] = []
    warnings: list[RraoAdapterWarning] = []
    rejected_rows: list[RraoRejectedRow] = []
    seen_position_ids: set[str] = set()

    for row_number, raw_record in enumerate(materialised_records, start=1):
        if not isinstance(raw_record, Mapping):
            rejected_rows.append(
                RraoRejectedRow(
                    source_row_id=_fallback_source_row_id(row_number),
                    reason="record must be a mapping",
                    field="record",
                    source_row=(),
                )
            )
            continue

        record = _normalised_record(raw_record)
        source_row_id = _source_row_id(record, row_number, warnings)
        try:
            position = _position_from_record(
                record,
                source_row_id=source_row_id,
                source_system=source_system,
                source_file=source_file,
                source_sign_convention=source_sign_convention,
                warnings=warnings,
            )
            if position.position_id in seen_position_ids:
                raise RraoInputError(
                    "duplicate position id in adapter records",
                    field="position_id",
                    position_id=position.position_id,
                )
            validate_rrao_positions((position,))
        except RraoInputError as exc:
            rejected_rows.append(
                RraoRejectedRow(
                    source_row_id=source_row_id,
                    reason=str(exc),
                    field=exc.field,
                    source_row=_source_row_snapshot(record),
                )
            )
            continue

        seen_position_ids.add(position.position_id)
        positions.append(position)

    return RraoAdapterResult(
        positions=tuple(positions),
        warnings=tuple(warnings),
        rejected_rows=tuple(rejected_rows),
    )


def adapt_crif_records(
    records: object,
    *,
    source_file: str = "crif",
    source_sign_convention: NotionalSignConvention = "gross",
) -> RraoAdapterResult:
    """Convert CRIF-style RRAO rows into canonical positions."""

    return adapt_rrao_records(
        records,
        source_system="crif",
        source_file=source_file,
        source_sign_convention=source_sign_convention,
    )


def adapt_fnet_records(
    records: object,
    *,
    source_file: str = "fnet",
    source_sign_convention: NotionalSignConvention = "gross",
) -> RraoAdapterResult:
    """Convert FNet-shaped RRAO rows into canonical positions."""

    return adapt_rrao_records(
        records,
        source_system="fnet",
        source_file=source_file,
        source_sign_convention=source_sign_convention,
    )


def _position_from_record(
    record: Mapping[str, tuple[str, object]],
    *,
    source_row_id: str,
    source_system: str,
    source_file: str,
    source_sign_convention: NotionalSignConvention,
    warnings: list[RraoAdapterWarning],
) -> RraoPosition:
    column_map: list[tuple[str, str]] = []
    position_id = _required_text(record, _POSITION_ID_FIELDS, "position_id", column_map)
    desk_id = _required_text(record, _DESK_FIELDS, "desk_id", column_map)
    legal_entity = _required_text(record, _LEGAL_ENTITY_FIELDS, "legal_entity", column_map)
    currency = _required_text(record, _CURRENCY_FIELDS, "currency", column_map)
    notional = _gross_effective_notional(
        record,
        source_sign_convention=source_sign_convention,
        source_row_id=source_row_id,
        column_map=column_map,
        warnings=warnings,
    )
    classification, evidence_type, evidence_label = _classification_from_record(
        record,
        source_row_id=source_row_id,
        column_map=column_map,
    )
    exclusion_reason = _optional_exclusion_reason(record, column_map)
    exclusion_evidence_id = _optional_text(
        record,
        _EXCLUSION_EVIDENCE_FIELDS,
        "exclusion_evidence_id",
        column_map,
    )

    return RraoPosition(
        position_id=position_id,
        source_row_id=source_row_id,
        desk_id=desk_id,
        legal_entity=legal_entity,
        gross_effective_notional=notional,
        currency=currency,
        evidence_type=evidence_type,
        evidence_label=evidence_label,
        lineage=RraoSourceLineage(
            source_system=source_system,
            source_file=source_file,
            source_row_id=source_row_id,
            source_column_map=tuple(column_map),
        ),
        classification_hint=classification,
        exclusion_reason=exclusion_reason,
        exclusion_evidence_id=exclusion_evidence_id,
        notional_source="adapter",
    )


def _classification_from_record(
    record: Mapping[str, tuple[str, object]],
    *,
    source_row_id: str,
    column_map: list[tuple[str, str]],
) -> tuple[RraoClassification, RraoEvidenceType, str]:
    risk_type = _optional_upper_text(
        record,
        _RISK_TYPE_FIELDS,
        "classification_hint",
        column_map,
    )
    bucket = _optional_upper_text(
        record,
        _BUCKET_FIELDS,
        "classification_hint",
        column_map,
    )
    source_label = risk_type or bucket
    if source_label is None:
        raise RraoInputError(
            "row must include CRIF RiskType or FNet Bucket",
            field="RiskType/Bucket",
            position_id=source_row_id,
        )

    evidence_label = _evidence_label(record, source_label, column_map)
    if source_label in _CRIF_EXOTIC_RISK_TYPES or source_label in _EXOTIC_BUCKETS:
        return RraoClassification.EXOTIC, RraoEvidenceType.EXOTIC_UNDERLYING, evidence_label
    if source_label in _CRIF_OTHER_RISK_TYPES or source_label in _OTHER_BUCKETS:
        return (
            RraoClassification.OTHER_RESIDUAL_RISK,
            _specific_other_residual_evidence(record, source_row_id, column_map),
            evidence_label,
        )
    if source_label in _CRIF_EXCLUSION_RISK_TYPES or source_label in _EXCLUDED_BUCKETS:
        return RraoClassification.EXCLUDED, RraoEvidenceType.EXPLICIT_EXCLUSION, evidence_label

    raise RraoInputError(
        f"unsupported RRAO adapter classification label: {source_label}",
        field="RiskType/Bucket",
        position_id=source_row_id,
    )


def _specific_other_residual_evidence(
    record: Mapping[str, tuple[str, object]],
    source_row_id: str,
    column_map: list[tuple[str, str]],
) -> RraoEvidenceType:
    evidence_value = _optional_upper_text(
        record,
        _EVIDENCE_TYPE_FIELDS,
        "evidence_type",
        column_map,
    )
    if evidence_value is None:
        raise RraoInputError(
            "generic non-exotic RRAO rows require specific evidence type",
            field="EvidenceType",
            position_id=source_row_id,
        )
    if evidence_value in _EVIDENCE_ALIASES:
        return _EVIDENCE_ALIASES[evidence_value]
    try:
        evidence_type = RraoEvidenceType(evidence_value)
    except ValueError as exc:
        raise RraoInputError(
            f"unsupported adapter evidence type: {evidence_value}",
            field="EvidenceType",
            position_id=source_row_id,
        ) from exc
    if evidence_type is RraoEvidenceType.INVESTMENT_FUND_EXPOSURE:
        raise RraoInputError(
            "investment fund adapter mapping is unsupported until issue #90",
            field="EvidenceType",
            position_id=source_row_id,
        )
    return evidence_type


def _gross_effective_notional(
    record: Mapping[str, tuple[str, object]],
    *,
    source_sign_convention: NotionalSignConvention,
    source_row_id: str,
    column_map: list[tuple[str, str]],
    warnings: list[RraoAdapterWarning],
) -> float:
    field_name, raw_value = _field(record, _NOTIONAL_FIELDS)
    if field_name is None:
        raise RraoInputError(
            "gross effective notional field is required",
            field="gross_effective_notional",
            position_id=source_row_id,
        )
    if raw_value is None:
        raise RraoInputError(
            "gross effective notional must be numeric",
            field=field_name,
            position_id=source_row_id,
        )
    if isinstance(raw_value, bool) or not isinstance(raw_value, int | float | str):
        raise RraoInputError(
            "gross effective notional must be numeric",
            field=field_name,
            position_id=source_row_id,
        )
    column_map.append((field_name, "gross_effective_notional"))
    if field_name.lower() == "weightednotional":
        convention = _optional_upper_text(
            record,
            _NOTIONAL_CONVENTION_FIELDS,
            "gross_effective_notional",
            column_map,
        )
        if convention not in _GROSS_NOTIONAL_CONVENTIONS:
            raise RraoInputError(
                "WeightedNotional requires explicit gross notional convention",
                field=field_name,
                position_id=source_row_id,
            )
        warnings.append(
            RraoAdapterWarning(
                source_row_id=source_row_id,
                field=field_name,
                message=(
                    "mapped WeightedNotional as gross effective notional by explicit convention"
                ),
            )
        )
    try:
        return normalise_gross_effective_notional(
            float(raw_value),
            source_sign_convention=source_sign_convention,
        )
    except (TypeError, ValueError) as exc:
        raise RraoInputError(
            "gross effective notional must be numeric",
            field=field_name,
            position_id=source_row_id,
        ) from exc


def _source_row_id(
    record: Mapping[str, tuple[str, object]],
    row_number: int,
    warnings: list[RraoAdapterWarning],
) -> str:
    field_name, raw_value = _field(record, _SOURCE_ROW_ID_FIELDS)
    if field_name is not None and str(raw_value).strip():
        return str(raw_value).strip()
    fallback = _fallback_source_row_id(row_number)
    warnings.append(
        RraoAdapterWarning(
            source_row_id=fallback,
            field="source_row_id",
            message="source row id missing; generated deterministic row id",
        )
    )
    return fallback


def _evidence_label(
    record: Mapping[str, tuple[str, object]],
    fallback: str,
    column_map: list[tuple[str, str]],
) -> str:
    label = _optional_text(record, _EVIDENCE_LABEL_FIELDS, "evidence_label", column_map)
    if label is None:
        return fallback
    return label


def _optional_exclusion_reason(
    record: Mapping[str, tuple[str, object]],
    column_map: list[tuple[str, str]],
) -> RraoExclusionReason | None:
    reason = _optional_upper_text(
        record,
        _EXCLUSION_REASON_FIELDS,
        "exclusion_reason",
        column_map,
    )
    if reason is None:
        return None
    try:
        return RraoExclusionReason(reason)
    except ValueError as exc:
        raise RraoInputError(
            f"unsupported adapter exclusion reason: {reason}",
            field="ExclusionReason",
        ) from exc


def _required_text(
    record: Mapping[str, tuple[str, object]],
    candidates: tuple[str, ...],
    canonical_field: str,
    column_map: list[tuple[str, str]],
) -> str:
    value = _optional_text(record, candidates, canonical_field, column_map)
    if value is None:
        raise RraoInputError(
            f"{canonical_field} field is required",
            field=canonical_field,
        )
    return value


def _optional_text(
    record: Mapping[str, tuple[str, object]],
    candidates: tuple[str, ...],
    canonical_field: str,
    column_map: list[tuple[str, str]],
) -> str | None:
    field_name, raw_value = _field(record, candidates)
    if field_name is None:
        return None
    column_map.append((field_name, canonical_field))
    value = str(raw_value).strip()
    if not value:
        return None
    return value


def _optional_upper_text(
    record: Mapping[str, tuple[str, object]],
    candidates: tuple[str, ...],
    canonical_field: str,
    column_map: list[tuple[str, str]],
) -> str | None:
    value = _optional_text(record, candidates, canonical_field, column_map)
    if value is None:
        return None
    return value.upper()


def _field(
    record: Mapping[str, tuple[str, object]],
    candidates: tuple[str, ...],
) -> tuple[str | None, object | None]:
    for candidate in candidates:
        key = candidate.lower()
        if key in record:
            return record[key]
    return None, None


def _normalised_record(record: Mapping[object, object]) -> Mapping[str, tuple[str, object]]:
    return {str(key).lower(): (str(key), value) for key, value in record.items()}


def _source_row_snapshot(
    record: Mapping[str, tuple[str, object]],
) -> tuple[tuple[str, str], ...]:
    return tuple(
        (field_name, repr(value))
        for field_name, value in sorted(
            (field_name, value) for field_name, value in record.values()
        )
    )


def _fallback_source_row_id(row_number: int) -> str:
    return f"row-{row_number:06d}"


__all__ = [
    "RraoAdapterResult",
    "RraoAdapterWarning",
    "RraoRejectedRow",
    "adapt_crif_records",
    "adapt_fnet_records",
    "adapt_rrao_records",
]
