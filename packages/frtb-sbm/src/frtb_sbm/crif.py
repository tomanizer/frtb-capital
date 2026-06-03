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
    NormalizedArrowTable,
    TabularLogicalType,
    UnsupportedRegulatoryFeatureError,
    normalize_crif_arrow_table,
    normalize_crif_records,
)

from frtb_sbm.arrow_handoff import normalize_girr_delta_arrow_table
from frtb_sbm.csr_nonsec_reference_data import CSR_BOND_RISK_FACTOR, CSR_CDS_RISK_FACTOR
from frtb_sbm.csr_sec_nonctp_reference_data import (
    CSR_SEC_BOND_RISK_FACTOR,
    CSR_SEC_CDS_RISK_FACTOR,
)
from frtb_sbm.data_models import (
    SbmRiskClass,
    SbmRiskMeasure,
    SbmSensitivity,
    SbmSignConvention,
    SbmSourceLineage,
)
from frtb_sbm.equity_reference_data import EQUITY_REPO_RISK_FACTOR, EQUITY_SPOT_RISK_FACTOR
from frtb_sbm.validation import SbmInputError, validate_sbm_sensitivities

_CRIF_GIRR_DELTA = frozenset({"RISK_IRCURVE", "IR_CURVE", "GIRR_DELTA"})
_CRIF_GIRR_VEGA = frozenset({"RISK_IRVOL", "IR_VOL", "GIRR_VEGA"})
_CRIF_GIRR_CURVATURE = frozenset(
    {"RISK_IRCURVECURVATURE", "RISK_IRCURVE_CURVATURE", "IR_CURVATURE", "GIRR_CURVATURE"}
)
_CRIF_FX_DELTA = frozenset({"RISK_FX", "FX_DELTA"})
_CRIF_FX_VEGA = frozenset({"RISK_FXVOL", "RISK_FX_VOL", "FX_VOL", "FX_VEGA"})
_CRIF_FX_CURVATURE = frozenset({"RISK_FXCURVATURE", "RISK_FX_CURVATURE", "FX_CURVATURE"})
_CRIF_EQUITY_DELTA = frozenset({"RISK_EQ", "RISK_EQUITY", "EQ_DELTA", "EQUITY_DELTA"})
_CRIF_EQUITY_VEGA = frozenset(
    {
        "RISK_EQVOL",
        "RISK_EQ_VOL",
        "RISK_EQUITYVOL",
        "RISK_EQUITY_VOL",
        "EQ_VOL",
        "EQ_VEGA",
        "EQUITY_VEGA",
    }
)
_CRIF_EQUITY_CURVATURE = frozenset(
    {
        "RISK_EQCURVATURE",
        "RISK_EQ_CURVATURE",
        "RISK_EQUITYCURVATURE",
        "RISK_EQUITY_CURVATURE",
        "EQ_CURVATURE",
        "EQUITY_CURVATURE",
    }
)
_CRIF_COMMODITY_DELTA = frozenset({"RISK_CM", "RISK_COMMODITY", "CM_DELTA", "COMMODITY_DELTA"})
_CRIF_COMMODITY_VEGA = frozenset(
    {
        "RISK_CMVOL",
        "RISK_CM_VOL",
        "RISK_COMMODITYVOL",
        "RISK_COMMODITY_VOL",
        "CM_VOL",
        "CM_VEGA",
        "COMMODITY_VEGA",
    }
)
_CRIF_COMMODITY_CURVATURE = frozenset(
    {
        "RISK_CMCURVATURE",
        "RISK_CM_CURVATURE",
        "RISK_COMMODITYCURVATURE",
        "RISK_COMMODITY_CURVATURE",
        "CM_CURVATURE",
        "COMMODITY_CURVATURE",
    }
)
_CRIF_CSR_NONSEC_DELTA = frozenset({"RISK_CSRNONSEC", "RISK_CREDIT_NONSEC", "CSR_NONSEC_DELTA"})
_CRIF_CSR_NONSEC_VEGA = frozenset(
    {
        "RISK_CSRNONSECVOL",
        "RISK_CSRNONSEC_VOL",
        "RISK_CREDIT_NONSECVOL",
        "RISK_CREDIT_NONSEC_VOL",
        "CSR_NONSEC_VEGA",
    }
)
_CRIF_CSR_NONSEC_CURVATURE = frozenset(
    {
        "RISK_CSRNONSECCURVATURE",
        "RISK_CSRNONSEC_CURVATURE",
        "RISK_CREDIT_NONSECCURVATURE",
        "RISK_CREDIT_NONSEC_CURVATURE",
        "CSR_NONSEC_CURVATURE",
    }
)
_CRIF_CSR_SEC_NONCTP_DELTA = frozenset(
    {"RISK_CSRSECNONCTP", "RISK_CREDIT_SEC_NONCTP", "CSR_SEC_NONCTP_DELTA"}
)
_CRIF_CSR_SEC_NONCTP_VEGA = frozenset(
    {
        "RISK_CSRSECNONCTPVOL",
        "RISK_CSRSECNONCTP_VOL",
        "RISK_CREDIT_SEC_NONCTPVOL",
        "RISK_CREDIT_SEC_NONCTP_VOL",
        "CSR_SEC_NONCTP_VEGA",
    }
)
_CRIF_CSR_SEC_NONCTP_CURVATURE = frozenset(
    {
        "RISK_CSRSECNONCTPCURVATURE",
        "RISK_CSRSECNONCTP_CURVATURE",
        "RISK_CREDIT_SEC_NONCTPCURVATURE",
        "RISK_CREDIT_SEC_NONCTP_CURVATURE",
        "CSR_SEC_NONCTP_CURVATURE",
    }
)
_CRIF_CSR_SEC_CTP_DELTA = frozenset({"RISK_CSRSECCTP", "RISK_CREDIT_SEC_CTP", "CSR_SEC_CTP_DELTA"})
_CRIF_CSR_SEC_CTP_VEGA = frozenset(
    {
        "RISK_CSRSECCTPVOL",
        "RISK_CSRSECCTP_VOL",
        "RISK_CREDIT_SEC_CTPVOL",
        "RISK_CREDIT_SEC_CTP_VOL",
        "CSR_SEC_CTP_VEGA",
    }
)
_CRIF_CSR_SEC_CTP_CURVATURE = frozenset(
    {
        "RISK_CSRSECCTPCURVATURE",
        "RISK_CSRSECCTP_CURVATURE",
        "RISK_CREDIT_SEC_CTPCURVATURE",
        "RISK_CREDIT_SEC_CTP_CURVATURE",
        "CSR_SEC_CTP_CURVATURE",
    }
)

_SENSITIVITY_ID_FIELDS = ("SensitivityId", "Sensitivity ID", "sensitivity_id", "TradeId", "TradeID")
_SOURCE_ROW_ID_FIELDS = ("RowId", "RowID", "source_row_id")
_RISK_TYPE_FIELDS = ("RiskType", "risk_type", "RiskClass")
_QUALIFIER_FIELDS = ("Qualifier", "qualifier")
_BUCKET_FIELDS = ("Bucket", "bucket")
_LABEL1_FIELDS = ("Label1", "label1", "Tenor", "tenor")
_LABEL2_FIELDS = ("Label2", "label2")
_RISK_FACTOR_FIELDS = (
    "RiskFactor",
    "Risk Factor",
    "risk_factor",
    "Underlying",
    "UnderlyingName",
    "Name",
)
_LOCATION_FIELDS = ("Location", "location", "DeliveryLocation", "delivery_location")
_OPTION_TENOR_FIELDS = ("OptionTenor", "Option Tenor", "option_tenor", "OptionMaturity")
_UNDERLYING_TENOR_FIELDS = ("UnderlyingTenor", "Underlying Tenor", "underlying_tenor")
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

    if not isinstance(records, Sequence) or isinstance(records, str | bytes):
        raise SbmInputError("records must be a sequence of mapping rows", field="records")
    sensitivities: list[SbmSensitivity] = []
    warnings: list[SbmAdapterWarning] = []
    rejected: list[SbmRejectedRow] = []
    accepted_ids: set[str] = set()
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
            validated = _validate_adapter_row(sensitivity, accepted_ids=accepted_ids)
        except (SbmInputError, UnsupportedRegulatoryFeatureError) as exc:
            rejected.append(_rejected_row_from_exception(record, exc, fallback_row_id=str(index)))
            continue
        sensitivities.extend(validated)
        accepted_ids.update(item.sensitivity_id for item in validated)
        warnings.extend(row_warnings)
    return SbmAdapterResult(
        sensitivities=tuple(sensitivities),
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
) -> NormalizedArrowTable:
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
) -> NormalizedArrowTable:
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
    crif_handoff: NormalizedArrowTable,
    *,
    desk_id: str,
    legal_entity: str,
    sign_convention: SbmSignConvention,
) -> NormalizedArrowTable:
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
    return pa.repeat(pa.scalar(value, type=pa.string()), row_count)


_CSR_RISK_CLASSES = frozenset(
    {
        SbmRiskClass.CSR_NONSEC,
        SbmRiskClass.CSR_SEC_NONCTP,
        SbmRiskClass.CSR_SEC_CTP,
    }
)


def _validate_adapter_row(
    sensitivities: tuple[SbmSensitivity, ...],
    *,
    accepted_ids: set[str],
) -> tuple[SbmSensitivity, ...]:
    validated = validate_sbm_sensitivities(sensitivities)
    for sensitivity in validated:
        if sensitivity.sensitivity_id in accepted_ids:
            raise SbmInputError(
                "duplicate sensitivity id",
                field="sensitivity_id",
                sensitivity_id=sensitivity.sensitivity_id,
            )
    return validated


def _rejected_row_from_exception(
    record: Mapping[str, object],
    exc: Exception,
    *,
    fallback_row_id: str,
) -> SbmRejectedRow:
    return SbmRejectedRow(
        source_row_id=_first_text(record, _SOURCE_ROW_ID_FIELDS, fallback=fallback_row_id),
        reason=str(exc),
        field=getattr(exc, "field", "") or "RiskType",
        source_row=_source_row_snapshot(record),
    )


def _source_row_snapshot(record: Mapping[str, object]) -> tuple[tuple[str, str], ...]:
    return tuple(sorted((str(key), str(value)) for key, value in record.items()))


def _map_crif_row(
    record: Mapping[str, object],
    *,
    source_file: str,
    desk_id: str,
    legal_entity: str,
    sign_convention: SbmSignConvention,
    fallback_row_id: str,
) -> tuple[tuple[SbmSensitivity, ...], list[SbmAdapterWarning]]:
    source_row_id, source_row_source = _first_text_with_source(
        record,
        _SOURCE_ROW_ID_FIELDS,
        fallback=fallback_row_id,
    )
    sensitivity_id, sensitivity_id_source = _first_text_with_source(
        record,
        _SENSITIVITY_ID_FIELDS,
        fallback=source_row_id,
    )
    risk_type, risk_type_source = _first_text_with_source(record, _RISK_TYPE_FIELDS)
    risk_class, risk_measure = _map_risk_type(risk_type)
    bucket_hint, bucket_hint_source = _optional_text_with_source(record, _BUCKET_FIELDS)
    crif_qualifier, crif_qualifier_source = _optional_text_with_source(record, _QUALIFIER_FIELDS)
    label1, label1_source = _optional_text_with_source(record, _LABEL1_FIELDS)
    label2, label2_source = _optional_text_with_source(record, _LABEL2_FIELDS)
    risk_factor_hint, risk_factor_hint_source = _optional_text_with_source(
        record,
        _RISK_FACTOR_FIELDS,
    )
    location, location_source = _optional_text_with_source(record, _LOCATION_FIELDS)
    option_tenor_hint, option_tenor_hint_source = _optional_text_with_source(
        record,
        _OPTION_TENOR_FIELDS,
    )
    underlying_tenor_hint, underlying_tenor_hint_source = _optional_text_with_source(
        record,
        _UNDERLYING_TENOR_FIELDS,
    )
    amount_currency, amount_currency_source = _first_text_with_source(
        record,
        _AMOUNT_CCY_FIELDS,
        fallback="USD",
    )
    desk, desk_source = _first_text_with_source(record, _DESK_FIELDS, fallback=desk_id)
    entity, entity_source = _first_text_with_source(
        record,
        _LEGAL_ENTITY_FIELDS,
        fallback=legal_entity,
    )
    warnings: list[SbmAdapterWarning] = []
    column_map: list[tuple[str, str]] = []
    _append_column_map(column_map, source_row_source, "source_row_id")
    _append_column_map(column_map, sensitivity_id_source, "sensitivity_id")
    _append_column_map(column_map, risk_type_source, "risk_class")
    _append_column_map(column_map, risk_type_source, "risk_measure")
    _append_column_map(column_map, amount_currency_source, "amount_currency")
    _append_column_map(column_map, desk_source, "desk_id")
    _append_column_map(column_map, entity_source, "legal_entity")

    risk_factor, risk_factor_source = _canonical_risk_factor(
        risk_class,
        risk_measure,
        risk_factor_hint=risk_factor_hint,
        risk_factor_hint_source=risk_factor_hint_source,
        crif_qualifier=crif_qualifier,
        crif_qualifier_source=crif_qualifier_source,
        bucket_hint=bucket_hint,
        bucket_hint_source=bucket_hint_source,
        amount_currency=amount_currency,
        amount_currency_source=amount_currency_source,
        label2=label2,
        label2_source=label2_source,
    )
    bucket, bucket_source = _canonical_bucket(
        risk_class,
        bucket_hint=bucket_hint,
        bucket_hint_source=bucket_hint_source,
        risk_factor=risk_factor,
        risk_factor_source=risk_factor_source,
    )
    qualifier, qualifier_source = _canonical_qualifier(
        risk_class,
        risk_measure,
        risk_factor_hint=risk_factor_hint,
        crif_qualifier=crif_qualifier,
        crif_qualifier_source=crif_qualifier_source,
        location=location,
        location_source=location_source,
    )
    tenor, tenor_source = _canonical_tenor(
        risk_class,
        risk_measure,
        label1=label1,
        label1_source=label1_source,
        label2=label2,
        label2_source=label2_source,
        underlying_tenor_hint=underlying_tenor_hint,
        underlying_tenor_hint_source=underlying_tenor_hint_source,
    )
    option_tenor, option_tenor_source = _canonical_option_tenor(
        risk_measure,
        label1=label1,
        label1_source=label1_source,
        option_tenor_hint=option_tenor_hint,
        option_tenor_hint_source=option_tenor_hint_source,
    )
    _append_inference_warnings(
        warnings,
        source_row_id=source_row_id,
        risk_class=risk_class,
        bucket_hint=bucket_hint,
        risk_factor_hint=risk_factor_hint,
        risk_factor_source=risk_factor_source,
        label2_source=label2_source,
    )

    _append_column_map(column_map, bucket_source, "bucket")
    _append_column_map(column_map, risk_factor_source, "risk_factor")
    _append_column_map(column_map, qualifier_source, "qualifier")
    _append_column_map(column_map, tenor_source, "tenor")
    _append_column_map(column_map, option_tenor_source, "option_tenor")

    if risk_measure is SbmRiskMeasure.CURVATURE:
        amount = 0.0
        up_shock_amount, up_shock_source = _first_float_with_source(record, _UP_SHOCK_FIELDS)
        down_shock_amount, down_shock_source = _first_float_with_source(record, _DOWN_SHOCK_FIELDS)
        _append_column_map(column_map, up_shock_source, "up_shock_amount")
        _append_column_map(column_map, down_shock_source, "down_shock_amount")
    else:
        amount, amount_source = _first_float_with_source(record, _AMOUNT_FIELDS)
        up_shock_amount = None
        down_shock_amount = None
        _append_column_map(column_map, amount_source, "amount")

    sensitivity = SbmSensitivity(
        sensitivity_id=sensitivity_id,
        source_row_id=source_row_id,
        desk_id=desk,
        legal_entity=entity,
        risk_class=risk_class,
        risk_measure=risk_measure,
        bucket=bucket,
        risk_factor=risk_factor,
        amount=amount,
        amount_currency=amount_currency,
        sign_convention=sign_convention,
        lineage=SbmSourceLineage(
            source_system="crif",
            source_file=source_file,
            source_row_id=source_row_id,
            source_column_map=tuple(column_map),
        ),
        qualifier=qualifier,
        tenor=tenor,
        option_tenor=option_tenor,
        up_shock_amount=up_shock_amount,
        down_shock_amount=down_shock_amount,
    )
    return (sensitivity,), warnings


def _canonical_risk_factor(
    risk_class: SbmRiskClass,
    risk_measure: SbmRiskMeasure,
    *,
    risk_factor_hint: str | None,
    risk_factor_hint_source: str | None,
    crif_qualifier: str | None,
    crif_qualifier_source: str | None,
    bucket_hint: str | None,
    bucket_hint_source: str | None,
    amount_currency: str,
    amount_currency_source: str | None,
    label2: str | None,
    label2_source: str | None,
) -> tuple[str, str | None]:
    if risk_class is SbmRiskClass.GIRR:
        value = risk_factor_hint or crif_qualifier or amount_currency
        source = risk_factor_hint_source or crif_qualifier_source or amount_currency_source
        normalised = value.strip().upper()
        if risk_measure is SbmRiskMeasure.CURVATURE and normalised in {"INFL", "XCCY"}:
            raise SbmInputError(
                "GIRR curvature has no capital requirement for inflation or "
                "cross-currency basis risk factors (MAR21.8(5)(b))",
                field=source or "RiskFactor",
            )
        return normalised, source
    if risk_class is SbmRiskClass.FX:
        fx_value = risk_factor_hint or crif_qualifier or bucket_hint
        source = risk_factor_hint_source or crif_qualifier_source or bucket_hint_source
        if not fx_value:
            raise SbmInputError(
                "FX CRIF rows require currency in RiskFactor, Qualifier, or Bucket",
                field="RiskFactor",
            )
        return fx_value.strip().upper(), source
    if risk_class is SbmRiskClass.EQUITY:
        value = risk_factor_hint or EQUITY_SPOT_RISK_FACTOR
        source = risk_factor_hint_source or "RiskType"
        normalised = value.strip().upper()
        if normalised not in {EQUITY_SPOT_RISK_FACTOR, EQUITY_REPO_RISK_FACTOR}:
            raise SbmInputError(
                "equity CRIF RiskFactor must be SPOT or REPO",
                field=risk_factor_hint_source or "RiskFactor",
            )
        if risk_measure is not SbmRiskMeasure.DELTA and normalised == EQUITY_REPO_RISK_FACTOR:
            raise SbmInputError(
                "equity vega and curvature have no capital requirement for "
                "equity repo rates (MAR21.12(2)(b), MAR21.12(3))",
                field=risk_factor_hint_source or "RiskFactor",
            )
        return normalised, source
    if risk_class is SbmRiskClass.COMMODITY:
        commodity_value = risk_factor_hint or crif_qualifier
        source = risk_factor_hint_source or crif_qualifier_source
        if not commodity_value:
            raise SbmInputError(
                "commodity CRIF rows require RiskFactor or Qualifier",
                field="RiskFactor",
            )
        return commodity_value.strip(), source
    if risk_class in _CSR_RISK_CLASSES:
        csr_value = risk_factor_hint
        source = risk_factor_hint_source
        if csr_value is None and label2 is not None and _is_csr_basis(risk_class, label2):
            csr_value = label2
            source = label2_source
        if csr_value is None:
            raise SbmInputError(
                "CSR CRIF rows require RiskFactor or Label2 set to BOND or CDS",
                field="RiskFactor",
            )
        normalised = csr_value.strip().upper()
        if not _is_csr_basis(risk_class, normalised):
            raise SbmInputError(
                "CSR CRIF RiskFactor must be BOND or CDS",
                field=source or "RiskFactor",
            )
        return normalised, source
    raise SbmInputError(
        f"unsupported CRIF risk class {risk_class.value!r}",
        field="RiskType",
    )


def _canonical_bucket(
    risk_class: SbmRiskClass,
    *,
    bucket_hint: str | None,
    bucket_hint_source: str | None,
    risk_factor: str,
    risk_factor_source: str | None,
) -> tuple[str, str | None]:
    if bucket_hint:
        bucket = bucket_hint.strip()
        if risk_class is SbmRiskClass.FX:
            bucket = bucket.upper()
        return bucket, bucket_hint_source
    if risk_class is SbmRiskClass.GIRR:
        return "1", "RiskType"
    if risk_class is SbmRiskClass.FX:
        return risk_factor.strip().upper(), risk_factor_source
    raise SbmInputError(
        f"{risk_class.value} CRIF rows require Bucket",
        field="Bucket",
    )


def _canonical_qualifier(
    risk_class: SbmRiskClass,
    risk_measure: SbmRiskMeasure,
    *,
    risk_factor_hint: str | None,
    crif_qualifier: str | None,
    crif_qualifier_source: str | None,
    location: str | None,
    location_source: str | None,
) -> tuple[str | None, str | None]:
    if risk_class in {SbmRiskClass.GIRR, SbmRiskClass.FX}:
        return None, None
    if risk_class in {SbmRiskClass.EQUITY, *_CSR_RISK_CLASSES}:
        return crif_qualifier, crif_qualifier_source
    if risk_class is SbmRiskClass.COMMODITY:
        if location:
            return location, location_source
        if risk_measure is SbmRiskMeasure.VEGA and risk_factor_hint and crif_qualifier is None:
            return None, None
        return crif_qualifier, crif_qualifier_source
    return crif_qualifier, crif_qualifier_source


def _canonical_tenor(
    risk_class: SbmRiskClass,
    risk_measure: SbmRiskMeasure,
    *,
    label1: str | None,
    label1_source: str | None,
    label2: str | None,
    label2_source: str | None,
    underlying_tenor_hint: str | None,
    underlying_tenor_hint_source: str | None,
) -> tuple[str | None, str | None]:
    if underlying_tenor_hint:
        return underlying_tenor_hint, underlying_tenor_hint_source
    if risk_measure is SbmRiskMeasure.VEGA:
        if risk_class is SbmRiskClass.GIRR:
            return label2, label2_source
        return None, None
    if risk_measure is SbmRiskMeasure.DELTA and risk_class in {
        SbmRiskClass.GIRR,
        SbmRiskClass.COMMODITY,
        *_CSR_RISK_CLASSES,
    }:
        return label1, label1_source
    if risk_measure is SbmRiskMeasure.CURVATURE and risk_class is SbmRiskClass.GIRR:
        if label2:
            return label2, label2_source
        return label1, label1_source
    return None, None


def _canonical_option_tenor(
    risk_measure: SbmRiskMeasure,
    *,
    label1: str | None,
    label1_source: str | None,
    option_tenor_hint: str | None,
    option_tenor_hint_source: str | None,
) -> tuple[str | None, str | None]:
    if risk_measure is not SbmRiskMeasure.VEGA:
        return None, None
    if option_tenor_hint:
        return option_tenor_hint, option_tenor_hint_source
    return label1, label1_source


def _is_csr_basis(risk_class: SbmRiskClass, value: str) -> bool:
    normalised = value.strip().upper()
    if risk_class in {SbmRiskClass.CSR_NONSEC, SbmRiskClass.CSR_SEC_CTP}:
        return normalised in {CSR_BOND_RISK_FACTOR, CSR_CDS_RISK_FACTOR}
    if risk_class is SbmRiskClass.CSR_SEC_NONCTP:
        return normalised in {CSR_SEC_BOND_RISK_FACTOR, CSR_SEC_CDS_RISK_FACTOR}
    return False


def _append_inference_warnings(
    warnings: list[SbmAdapterWarning],
    *,
    source_row_id: str,
    risk_class: SbmRiskClass,
    bucket_hint: str | None,
    risk_factor_hint: str | None,
    risk_factor_source: str | None,
    label2_source: str | None,
) -> None:
    if risk_class is SbmRiskClass.FX and bucket_hint is None:
        warnings.append(
            SbmAdapterWarning(
                source_row_id=source_row_id,
                field="Bucket",
                message="FX bucket inferred from mapped currency",
            )
        )
    if risk_class is SbmRiskClass.EQUITY and risk_factor_hint is None:
        warnings.append(
            SbmAdapterWarning(
                source_row_id=source_row_id,
                field="RiskFactor",
                message="equity risk_factor defaulted to SPOT from CRIF risk type",
            )
        )
    if (
        risk_class in _CSR_RISK_CLASSES
        and risk_factor_hint is None
        and risk_factor_source == label2_source
    ):
        warnings.append(
            SbmAdapterWarning(
                source_row_id=source_row_id,
                field="RiskFactor",
                message="CSR basis risk_factor inferred from Label2",
            )
        )


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
    if normalised in _CRIF_FX_VEGA:
        return SbmRiskClass.FX, SbmRiskMeasure.VEGA
    if normalised in _CRIF_FX_CURVATURE:
        return SbmRiskClass.FX, SbmRiskMeasure.CURVATURE
    if normalised in _CRIF_EQUITY_DELTA:
        return SbmRiskClass.EQUITY, SbmRiskMeasure.DELTA
    if normalised in _CRIF_EQUITY_VEGA:
        return SbmRiskClass.EQUITY, SbmRiskMeasure.VEGA
    if normalised in _CRIF_EQUITY_CURVATURE:
        return SbmRiskClass.EQUITY, SbmRiskMeasure.CURVATURE
    if normalised in _CRIF_COMMODITY_DELTA:
        return SbmRiskClass.COMMODITY, SbmRiskMeasure.DELTA
    if normalised in _CRIF_COMMODITY_VEGA:
        return SbmRiskClass.COMMODITY, SbmRiskMeasure.VEGA
    if normalised in _CRIF_COMMODITY_CURVATURE:
        return SbmRiskClass.COMMODITY, SbmRiskMeasure.CURVATURE
    if normalised in _CRIF_CSR_NONSEC_DELTA:
        return SbmRiskClass.CSR_NONSEC, SbmRiskMeasure.DELTA
    if normalised in _CRIF_CSR_NONSEC_VEGA:
        return SbmRiskClass.CSR_NONSEC, SbmRiskMeasure.VEGA
    if normalised in _CRIF_CSR_NONSEC_CURVATURE:
        return SbmRiskClass.CSR_NONSEC, SbmRiskMeasure.CURVATURE
    if normalised in _CRIF_CSR_SEC_NONCTP_DELTA:
        return SbmRiskClass.CSR_SEC_NONCTP, SbmRiskMeasure.DELTA
    if normalised in _CRIF_CSR_SEC_NONCTP_VEGA:
        return SbmRiskClass.CSR_SEC_NONCTP, SbmRiskMeasure.VEGA
    if normalised in _CRIF_CSR_SEC_NONCTP_CURVATURE:
        return SbmRiskClass.CSR_SEC_NONCTP, SbmRiskMeasure.CURVATURE
    if normalised in _CRIF_CSR_SEC_CTP_DELTA:
        return SbmRiskClass.CSR_SEC_CTP, SbmRiskMeasure.DELTA
    if normalised in _CRIF_CSR_SEC_CTP_VEGA:
        return SbmRiskClass.CSR_SEC_CTP, SbmRiskMeasure.VEGA
    if normalised in _CRIF_CSR_SEC_CTP_CURVATURE:
        return SbmRiskClass.CSR_SEC_CTP, SbmRiskMeasure.CURVATURE
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
    value, _source = _first_text_with_source(record, fields, fallback=fallback)
    return value


def _first_text_with_source(
    record: Mapping[str, object],
    fields: tuple[str, ...],
    *,
    fallback: str = "",
) -> tuple[str, str | None]:
    for field in fields:
        if field in record and record[field] is not None:
            value = str(record[field]).strip()
            if value:
                return value, field
    if fallback:
        return fallback, None
    raise SbmInputError(f"missing required field; tried {fields}", field=fields[0])


def _optional_text_with_source(
    record: Mapping[str, object],
    fields: tuple[str, ...],
) -> tuple[str | None, str | None]:
    for field in fields:
        if field in record and record[field] is not None:
            value = str(record[field]).strip()
            if value:
                return value, field
    return None, None


def _first_float_with_source(
    record: Mapping[str, object],
    fields: tuple[str, ...],
) -> tuple[float, str]:
    for field in fields:
        if field not in record or record[field] is None:
            continue
        try:
            raw_value = record[field]
            if isinstance(raw_value, bool):
                raise ValueError("boolean values are not numeric CRIF amounts")
            value = float(cast(str | float | int, raw_value))
            if not math.isfinite(value):
                raise ValueError("value must be finite")
            return value, field
        except (TypeError, ValueError) as exc:
            raise SbmInputError(
                f"field {field} must be numeric and finite",
                field=field,
            ) from exc
    raise SbmInputError(f"missing required numeric field; tried {fields}", field=fields[0])


def _append_column_map(
    column_map: list[tuple[str, str]],
    source_field: str | None,
    canonical_field: str,
) -> None:
    if source_field is None:
        return
    pair = (source_field, canonical_field)
    if pair not in column_map:
        column_map.append(pair)


__all__ = [
    "SbmAdapterResult",
    "SbmAdapterWarning",
    "SbmRejectedRow",
    "adapt_crif_records",
    "normalize_girr_delta_crif_arrow_table",
    "normalize_girr_delta_crif_records",
]
