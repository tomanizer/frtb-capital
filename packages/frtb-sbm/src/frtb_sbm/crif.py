"""
Optional CRIF-to-canonical SBM adapter.

Regulatory traceability:
    ISDA CRIF field conventions; SBM-CRIF-001, SBM-FUNC-023.
    Row-dict compatibility emits canonical ``SbmSensitivity`` records. The
    GIRR delta handoff path emits Arrow-backed batches without dataframe
    runtime dependencies or accepted-row dataclass materialization.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import cast

import pyarrow as pa  # type: ignore[import-untyped]
import pyarrow.compute as pc  # type: ignore[import-untyped]
from frtb_common import (
    CRIF_SOURCE_ROW_ID_COLUMN,
    CrifColumnSpec,
    CrifRiskTypeMapping,
    NormalizedTabularHandoff,
    TabularLogicalType,
    normalize_crif_arrow_table,
    normalize_crif_records,
)

from frtb_sbm.arrow_handoff import normalize_girr_delta_arrow_table
from frtb_sbm.data_models import (
    SbmRiskClass,
    SbmRiskMeasure,
    SbmSensitivity,
    SbmSignConvention,
    SbmSourceLineage,
)
from frtb_sbm.validation import SbmInputError, validate_sbm_sensitivities

_CRIF_GIRR_DELTA = frozenset({"RISK_IRCURVE", "IR_CURVE", "GIRR_DELTA"})
_CRIF_GIRR_VEGA = frozenset({"RISK_IRVOL", "IR_VOL", "GIRR_VEGA"})
_CRIF_GIRR_CURVATURE = frozenset({"RISK_IRCURVE_CURVATURE", "IR_CURVATURE", "GIRR_CURVATURE"})
_CRIF_FX_DELTA = frozenset({"RISK_FX", "FX_DELTA"})
_CRIF_EQUITY_DELTA = frozenset({"RISK_EQ", "EQ_DELTA"})
_CRIF_COMMODITY_DELTA = frozenset({"RISK_CM", "CM_DELTA"})
_CRIF_CSR_NONSEC_DELTA = frozenset({"RISK_CREDIT_NONSEC", "CSR_NONSEC_DELTA"})
_CRIF_CSR_SEC_NONCTP_DELTA = frozenset({"RISK_CREDIT_SEC_NONCTP", "CSR_SEC_NONCTP_DELTA"})
_CRIF_CSR_SEC_CTP_DELTA = frozenset({"RISK_CREDIT_SEC_CTP", "CSR_SEC_CTP_DELTA"})

_SENSITIVITY_ID_FIELDS = ("SensitivityId", "Sensitivity ID", "sensitivity_id", "TradeId", "TradeID")
_SOURCE_ROW_ID_FIELDS = ("RowId", "RowID", "source_row_id")
_RISK_TYPE_FIELDS = ("RiskType", "risk_type", "RiskClass")
_QUALIFIER_FIELDS = ("Qualifier", "qualifier")
_BUCKET_FIELDS = ("Bucket", "bucket")
_LABEL1_FIELDS = ("Label1", "label1", "Tenor", "tenor")
_LABEL2_FIELDS = ("Label2", "label2", "OptionTenor", "option_tenor")
_AMOUNT_FIELDS = ("Amount", "amount", "AmountUSD", "AmountUsd")
_AMOUNT_CCY_FIELDS = ("AmountCurrency", "amount_currency", "Currency", "currency")
_UP_SHOCK_FIELDS = ("CvrUp", "UpShock", "up_shock_amount")
_DOWN_SHOCK_FIELDS = ("CvrDown", "DownShock", "down_shock_amount")
_DESK_FIELDS = ("DeskId", "DeskID", "desk_id", "Desk")
_LEGAL_ENTITY_FIELDS = ("LegalEntity", "LegalEntityID", "legal_entity", "Entity")

_GIRR_DELTA_CRIF_COLUMN_SPECS: tuple[CrifColumnSpec, ...] = (
    CrifColumnSpec("sensitivity_id", aliases=_SENSITIVITY_ID_FIELDS),
    CrifColumnSpec(CRIF_SOURCE_ROW_ID_COLUMN, aliases=_SOURCE_ROW_ID_FIELDS),
    CrifColumnSpec("risk_type", aliases=_RISK_TYPE_FIELDS, required=True),
    CrifColumnSpec("qualifier", aliases=_QUALIFIER_FIELDS),
    CrifColumnSpec("bucket", aliases=_BUCKET_FIELDS),
    CrifColumnSpec("label1", aliases=_LABEL1_FIELDS),
    CrifColumnSpec(
        "amount",
        aliases=_AMOUNT_FIELDS,
        logical_type=TabularLogicalType.FLOAT,
        required=True,
    ),
    CrifColumnSpec("amount_currency", aliases=_AMOUNT_CCY_FIELDS),
    CrifColumnSpec("desk_id", aliases=_DESK_FIELDS),
    CrifColumnSpec("legal_entity", aliases=_LEGAL_ENTITY_FIELDS),
)
_GIRR_DELTA_CRIF_RISK_TYPE_MAPPINGS: tuple[CrifRiskTypeMapping, ...] = (
    CrifRiskTypeMapping(
        tuple(sorted(_CRIF_GIRR_DELTA)),
        {
            "risk_class": SbmRiskClass.GIRR.value,
            "risk_measure": SbmRiskMeasure.DELTA.value,
        },
    ),
)


@dataclass(frozen=True)
class SbmAdapterWarning:
    """Auditable non-fatal CRIF mapping warning."""

    source_row_id: str
    field: str
    message: str


@dataclass(frozen=True)
class SbmRejectedRow:
    """Auditable rejected CRIF row."""

    source_row_id: str
    reason: str
    field: str
    source_row: tuple[tuple[str, str], ...]


@dataclass(frozen=True)
class SbmAdapterResult:
    """Adapter output: canonical sensitivities plus warnings and rejected rows."""

    sensitivities: tuple[SbmSensitivity, ...]
    warnings: tuple[SbmAdapterWarning, ...] = ()
    rejected_rows: tuple[SbmRejectedRow, ...] = ()


def adapt_crif_records(
    records: object,
    *,
    source_file: str = "crif.csv",
    desk_id: str = "UNKNOWN",
    legal_entity: str = "UNKNOWN",
    sign_convention: SbmSignConvention = SbmSignConvention.RECEIVE,
) -> SbmAdapterResult:
    """Map CRIF-like row dictionaries into canonical ``SbmSensitivity`` records."""

    if not isinstance(records, list):
        raise SbmInputError("records must be a list of mapping rows", field="records")
    sensitivities: list[SbmSensitivity] = []
    warnings: list[SbmAdapterWarning] = []
    rejected: list[SbmRejectedRow] = []
    for index, record in enumerate(records):
        if not isinstance(record, Mapping):
            rejected.append(
                SbmRejectedRow(
                    source_row_id=str(index),
                    reason="row must be a mapping",
                    field="records",
                    source_row=(),
                )
            )
            continue
        try:
            sensitivity, row_warnings = _map_crif_row(
                record,
                source_file=source_file,
                desk_id=desk_id,
                legal_entity=legal_entity,
                sign_convention=sign_convention,
                fallback_row_id=str(index),
            )
        except SbmInputError as exc:
            rejected.append(
                SbmRejectedRow(
                    source_row_id=_first_text(record, _SOURCE_ROW_ID_FIELDS, fallback=str(index)),
                    reason=str(exc),
                    field=exc.field,
                    source_row=tuple(sorted((str(k), str(v)) for k, v in record.items())),
                )
            )
            continue
        sensitivities.extend(sensitivity)
        warnings.extend(row_warnings)
    validated = validate_sbm_sensitivities(sensitivities) if sensitivities else ()
    return SbmAdapterResult(
        sensitivities=validated,
        warnings=tuple(warnings),
        rejected_rows=tuple(rejected),
    )


def normalize_girr_delta_crif_records(
    records: object,
    *,
    source_file: str = "crif.csv",
    desk_id: str = "UNKNOWN",
    legal_entity: str = "UNKNOWN",
    sign_convention: SbmSignConvention = SbmSignConvention.RECEIVE,
    source_hash: str | None = None,
) -> NormalizedTabularHandoff:
    """Normalize CRIF-like row dictionaries into the GIRR delta Arrow handoff."""

    if not isinstance(records, Sequence) or isinstance(records, str | bytes):
        raise SbmInputError("records must be a sequence of mapping rows", field="records")
    rows: list[Mapping[str, object]] = []
    for index, record in enumerate(records):
        if not isinstance(record, Mapping):
            raise SbmInputError(
                "records must be a sequence of mapping rows",
                field=f"records[{index}]",
            )
        rows.append(record)
    crif_handoff = normalize_crif_records(
        rows,
        column_specs=_GIRR_DELTA_CRIF_COLUMN_SPECS,
        risk_type_mappings=_GIRR_DELTA_CRIF_RISK_TYPE_MAPPINGS,
        source_file=source_file,
        source_hash=source_hash,
    )
    return _girr_delta_handoff_from_normalized_crif(
        crif_handoff,
        desk_id=desk_id,
        legal_entity=legal_entity,
        sign_convention=sign_convention,
    )


def normalize_girr_delta_crif_arrow_table(
    table: pa.Table,
    *,
    source_file: str = "crif.csv",
    desk_id: str = "UNKNOWN",
    legal_entity: str = "UNKNOWN",
    sign_convention: SbmSignConvention = SbmSignConvention.RECEIVE,
    source_hash: str | None = None,
) -> NormalizedTabularHandoff:
    """Normalize a CRIF-like Arrow table into the GIRR delta Arrow handoff."""

    crif_handoff = normalize_crif_arrow_table(
        table,
        column_specs=_GIRR_DELTA_CRIF_COLUMN_SPECS,
        risk_type_mappings=_GIRR_DELTA_CRIF_RISK_TYPE_MAPPINGS,
        source_file=source_file,
        source_hash=source_hash,
    )
    return _girr_delta_handoff_from_normalized_crif(
        crif_handoff,
        desk_id=desk_id,
        legal_entity=legal_entity,
        sign_convention=sign_convention,
    )


def _girr_delta_handoff_from_normalized_crif(
    crif_handoff: NormalizedTabularHandoff,
    *,
    desk_id: str,
    legal_entity: str,
    sign_convention: SbmSignConvention,
) -> NormalizedTabularHandoff:
    table = crif_handoff.accepted
    amount_currency = _text_column(table, "amount_currency", "USD")
    source_row_ids = _text_column(table, CRIF_SOURCE_ROW_ID_COLUMN, "")
    girr_table = pa.table(
        {
            "sensitivity_id": _coalesce_text_columns(
                _text_column(table, "sensitivity_id", ""),
                source_row_ids,
            ),
            "source_row_id": source_row_ids,
            "desk_id": _text_column(table, "desk_id", desk_id),
            "legal_entity": _text_column(table, "legal_entity", legal_entity),
            "risk_class": _text_column(table, "risk_class", SbmRiskClass.GIRR.value),
            "risk_measure": _text_column(table, "risk_measure", SbmRiskMeasure.DELTA.value),
            "bucket": _text_column(table, "bucket", "1"),
            "risk_factor": _coalesce_text_columns(
                _text_column(table, "qualifier", ""),
                amount_currency,
            ),
            "amount": _required_column(table, "amount"),
            "amount_currency": amount_currency,
            "sign_convention": _constant_text_column(sign_convention.value, table.num_rows),
            "tenor": _text_column(table, "label1", ""),
            "lineage_source_system": _constant_text_column(
                crif_handoff.metadata.get("source_system", "crif"),
                table.num_rows,
            ),
            "lineage_source_file": _constant_text_column(
                crif_handoff.metadata.get("source_file", "crif.csv"),
                table.num_rows,
            ),
        }
    )
    return normalize_girr_delta_arrow_table(
        girr_table,
        diagnostics=crif_handoff.diagnostics,
        metadata=crif_handoff.metadata,
        rejected=crif_handoff.rejected,
        source_hash=crif_handoff.source_hash,
    )


def _required_column(table: pa.Table, column_name: str) -> pa.ChunkedArray:
    if column_name not in table.column_names:
        raise SbmInputError(f"required column {column_name!r} is missing", field=column_name)
    return table.column(column_name)


def _text_column(table: pa.Table, column_name: str, default: str) -> pa.Array:
    if table.num_rows == 0:
        return pa.array([], type=pa.string())
    if column_name not in table.column_names:
        return _constant_text_column(default, table.num_rows)
    column = table.column(column_name).combine_chunks()
    if not pa.types.is_string(column.type):
        column = pc.cast(column, pa.string())
    trimmed = pc.utf8_trim_whitespace(column)
    filled = pc.fill_null(trimmed, "")
    has_text = pc.not_equal(filled, "")
    return pc.if_else(has_text, trimmed, _constant_text_column(default, table.num_rows))


def _coalesce_text_columns(primary: pa.Array, fallback: pa.Array) -> pa.Array:
    if len(primary) != len(fallback):
        raise SbmInputError("coalesced CRIF columns must have matching lengths", field="crif")
    if len(primary) == 0:
        return pa.array([], type=pa.string())
    trimmed = pc.utf8_trim_whitespace(primary)
    filled = pc.fill_null(trimmed, "")
    has_text = pc.not_equal(filled, "")
    return pc.if_else(has_text, trimmed, fallback)


def _constant_text_column(value: str, row_count: int) -> pa.Array:
    return pa.array([value] * row_count, type=pa.string())


def _map_crif_row(
    record: Mapping[str, object],
    *,
    source_file: str,
    desk_id: str,
    legal_entity: str,
    sign_convention: SbmSignConvention,
    fallback_row_id: str,
) -> tuple[tuple[SbmSensitivity, ...], list[SbmAdapterWarning]]:
    source_row_id = _first_text(record, _SOURCE_ROW_ID_FIELDS, fallback=fallback_row_id)
    sensitivity_id = _first_text(record, _SENSITIVITY_ID_FIELDS, fallback=source_row_id)
    risk_type = _first_text(record, _RISK_TYPE_FIELDS)
    risk_class, risk_measure = _map_risk_type(risk_type)
    bucket = _first_text(record, _BUCKET_FIELDS, fallback="1")
    qualifier = _optional_text(record, _QUALIFIER_FIELDS)
    label1 = _optional_text(record, _LABEL1_FIELDS)
    label2 = _optional_text(record, _LABEL2_FIELDS)
    amount_currency = _first_text(record, _AMOUNT_CCY_FIELDS, fallback="USD")
    desk = _first_text(record, _DESK_FIELDS, fallback=desk_id)
    entity = _first_text(record, _LEGAL_ENTITY_FIELDS, fallback=legal_entity)
    warnings: list[SbmAdapterWarning] = []
    column_map: list[tuple[str, str]] = [("RiskType", "risk_class")]
    optional: dict[str, object] = {}

    if risk_measure is SbmRiskMeasure.CURVATURE:
        amount = 0.0
        optional["up_shock_amount"] = _first_float(record, _UP_SHOCK_FIELDS)
        optional["down_shock_amount"] = _first_float(record, _DOWN_SHOCK_FIELDS)
        optional["amount"] = amount
        column_map.extend([("CvrUp", "up_shock_amount"), ("CvrDown", "down_shock_amount")])
        if label2:
            optional["tenor"] = label2
            column_map.append(("Label2", "tenor"))
    else:
        amount = _first_float(record, _AMOUNT_FIELDS)
        optional["amount"] = amount
        column_map.append(("Amount", "amount"))

    if risk_class is SbmRiskClass.GIRR and risk_measure is not SbmRiskMeasure.CURVATURE:
        if risk_measure is SbmRiskMeasure.VEGA:
            optional["option_tenor"] = label1 or ""
            optional["tenor"] = label2 or ""
            column_map.extend([("Label1", "option_tenor"), ("Label2", "tenor")])
        else:
            optional["tenor"] = label1 or ""
            column_map.append(("Label1", "tenor"))
    elif risk_class in {
        SbmRiskClass.CSR_NONSEC,
        SbmRiskClass.CSR_SEC_NONCTP,
        SbmRiskClass.CSR_SEC_CTP,
        SbmRiskClass.COMMODITY,
    }:
        optional["tenor"] = label1 or ""
        optional["qualifier"] = qualifier or ""
        column_map.extend([("Label1", "tenor"), ("Qualifier", "qualifier")])

    if not qualifier and risk_class in {
        SbmRiskClass.CSR_NONSEC,
        SbmRiskClass.CSR_SEC_NONCTP,
        SbmRiskClass.CSR_SEC_CTP,
        SbmRiskClass.EQUITY,
        SbmRiskClass.COMMODITY,
    }:
        warnings.append(
            SbmAdapterWarning(
                source_row_id=source_row_id,
                field="qualifier",
                message="qualifier inferred empty from CRIF row",
            )
        )

    sensitivity = SbmSensitivity(
        sensitivity_id=sensitivity_id,
        source_row_id=source_row_id,
        desk_id=desk,
        legal_entity=entity,
        risk_class=risk_class,
        risk_measure=risk_measure,
        bucket=bucket,
        risk_factor=qualifier or amount_currency,
        amount=amount,
        amount_currency=amount_currency,
        sign_convention=sign_convention,
        lineage=SbmSourceLineage(
            source_system="crif",
            source_file=source_file,
            source_row_id=source_row_id,
            source_column_map=tuple(column_map),
        ),
        qualifier=optional.get("qualifier"),  # type: ignore[arg-type]
        tenor=optional.get("tenor"),  # type: ignore[arg-type]
        option_tenor=optional.get("option_tenor"),  # type: ignore[arg-type]
        up_shock_amount=optional.get("up_shock_amount"),  # type: ignore[arg-type]
        down_shock_amount=optional.get("down_shock_amount"),  # type: ignore[arg-type]
    )
    return (sensitivity,), warnings


def _map_risk_type(risk_type: str) -> tuple[SbmRiskClass, SbmRiskMeasure]:
    normalised = risk_type.strip().upper()
    if normalised in _CRIF_GIRR_DELTA:
        return SbmRiskClass.GIRR, SbmRiskMeasure.DELTA
    if normalised in _CRIF_GIRR_VEGA:
        return SbmRiskClass.GIRR, SbmRiskMeasure.VEGA
    if normalised in _CRIF_GIRR_CURVATURE:
        return SbmRiskClass.GIRR, SbmRiskMeasure.CURVATURE
    if normalised in _CRIF_FX_DELTA:
        return SbmRiskClass.FX, SbmRiskMeasure.DELTA
    if normalised in _CRIF_EQUITY_DELTA:
        return SbmRiskClass.EQUITY, SbmRiskMeasure.DELTA
    if normalised in _CRIF_COMMODITY_DELTA:
        return SbmRiskClass.COMMODITY, SbmRiskMeasure.DELTA
    if normalised in _CRIF_CSR_NONSEC_DELTA:
        return SbmRiskClass.CSR_NONSEC, SbmRiskMeasure.DELTA
    if normalised in _CRIF_CSR_SEC_NONCTP_DELTA:
        return SbmRiskClass.CSR_SEC_NONCTP, SbmRiskMeasure.DELTA
    if normalised in _CRIF_CSR_SEC_CTP_DELTA:
        return SbmRiskClass.CSR_SEC_CTP, SbmRiskMeasure.DELTA
    raise SbmInputError(
        f"unsupported CRIF RiskType {normalised!r}",
        field="RiskType",
    )


def _first_text(
    record: Mapping[str, object],
    fields: tuple[str, ...],
    *,
    fallback: str = "",
) -> str:
    for field in fields:
        if field in record and record[field] is not None:
            value = str(record[field]).strip()
            if value:
                return value
    if fallback:
        return fallback
    raise SbmInputError(f"missing required field; tried {fields}", field=fields[0])


def _optional_text(record: Mapping[str, object], fields: tuple[str, ...]) -> str | None:
    for field in fields:
        if field in record and record[field] is not None:
            value = str(record[field]).strip()
            if value:
                return value
    return None


def _first_float(record: Mapping[str, object], fields: tuple[str, ...]) -> float:
    for field in fields:
        if field not in record or record[field] is None:
            continue
        try:
            value = float(cast(str | float | int, record[field]))
            if not math.isfinite(value):
                raise ValueError("value must be finite")
            return value
        except (TypeError, ValueError) as exc:
            raise SbmInputError(
                f"field {field} must be numeric and finite",
                field=field,
            ) from exc
        if not math.isfinite(value):
            raise SbmInputError(
                f"field {field} must be finite, got {value}",
                field=field,
            )
        return value
    raise SbmInputError(f"missing required numeric field; tried {fields}", field=fields[0])


__all__ = [
    "SbmAdapterResult",
    "SbmAdapterWarning",
    "SbmRejectedRow",
    "adapt_crif_records",
    "normalize_girr_delta_crif_arrow_table",
    "normalize_girr_delta_crif_records",
]
