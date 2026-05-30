"""
Optional CRIF-to-canonical SBM adapter.

Regulatory traceability:
    ISDA CRIF field conventions; SBM-CRIF-001, SBM-FUNC-023.
    Adapters emit canonical ``SbmSensitivity`` records without dataframe runtime deps.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

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
        amount=float(optional.get("amount", amount)),  # type: ignore[arg-type]
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
    record: Mapping[str, object], fields: tuple[str, ...], *, fallback: str = ""
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
            return float(record[field])  # type: ignore[arg-type]
        except (TypeError, ValueError) as exc:
            raise SbmInputError(
                f"field {field} must be numeric",
                field=field,
            ) from exc
    raise SbmInputError(f"missing required numeric field; tried {fields}", field=fields[0])


__all__ = [
    "SbmAdapterResult",
    "SbmAdapterWarning",
    "SbmRejectedRow",
    "adapt_crif_records",
]
