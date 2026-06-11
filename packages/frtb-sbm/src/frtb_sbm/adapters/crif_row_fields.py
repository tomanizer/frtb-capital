"""Raw CRIF row field extraction for SBM adapters."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from frtb_sbm.adapters.crif_constants import (
    _AMOUNT_CCY_FIELDS,
    _BUCKET_FIELDS,
    _DESK_FIELDS,
    _LABEL1_FIELDS,
    _LABEL2_FIELDS,
    _LEGAL_ENTITY_FIELDS,
    _LOCATION_FIELDS,
    _OPTION_TENOR_FIELDS,
    _QUALIFIER_FIELDS,
    _RISK_FACTOR_FIELDS,
    _RISK_TYPE_FIELDS,
    _SENSITIVITY_ID_FIELDS,
    _SOURCE_ROW_ID_FIELDS,
    _UNDERLYING_TENOR_FIELDS,
    _map_risk_type,
)
from frtb_sbm.adapters.crif_fields import (
    _append_column_map,
    _first_text_with_source,
    _optional_text_with_source,
)
from frtb_sbm.data_models import SbmRiskClass, SbmRiskMeasure


@dataclass(frozen=True)
class _RawCrifRowFields:
    source_row_id: str
    source_row_source: str | None
    sensitivity_id: str
    sensitivity_id_source: str | None
    risk_class: SbmRiskClass
    risk_measure: SbmRiskMeasure
    risk_type_source: str | None
    bucket_hint: str | None
    bucket_hint_source: str | None
    crif_qualifier: str | None
    crif_qualifier_source: str | None
    label1: str | None
    label1_source: str | None
    label2: str | None
    label2_source: str | None
    risk_factor_hint: str | None
    risk_factor_hint_source: str | None
    location: str | None
    location_source: str | None
    option_tenor_hint: str | None
    option_tenor_hint_source: str | None
    underlying_tenor_hint: str | None
    underlying_tenor_hint_source: str | None
    amount_currency: str
    amount_currency_source: str | None
    desk: str
    desk_source: str | None
    entity: str
    entity_source: str | None


@dataclass(frozen=True)
class _CanonicalCrifAxes:
    bucket: str
    bucket_source: str | None
    risk_factor: str
    risk_factor_source: str | None
    qualifier: str | None
    qualifier_source: str | None
    tenor: str | None
    tenor_source: str | None
    option_tenor: str | None
    option_tenor_source: str | None


@dataclass(frozen=True)
class _CrifAmounts:
    amount: float
    up_shock_amount: float | None
    down_shock_amount: float | None


def _extract_row_fields(
    record: Mapping[str, object],
    *,
    desk_id: str,
    legal_entity: str,
    fallback_row_id: str,
) -> _RawCrifRowFields:
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
    return _RawCrifRowFields(
        source_row_id=source_row_id,
        source_row_source=source_row_source,
        sensitivity_id=sensitivity_id,
        sensitivity_id_source=sensitivity_id_source,
        risk_class=risk_class,
        risk_measure=risk_measure,
        risk_type_source=risk_type_source,
        bucket_hint=bucket_hint,
        bucket_hint_source=bucket_hint_source,
        crif_qualifier=crif_qualifier,
        crif_qualifier_source=crif_qualifier_source,
        label1=label1,
        label1_source=label1_source,
        label2=label2,
        label2_source=label2_source,
        risk_factor_hint=risk_factor_hint,
        risk_factor_hint_source=risk_factor_hint_source,
        location=location,
        location_source=location_source,
        option_tenor_hint=option_tenor_hint,
        option_tenor_hint_source=option_tenor_hint_source,
        underlying_tenor_hint=underlying_tenor_hint,
        underlying_tenor_hint_source=underlying_tenor_hint_source,
        amount_currency=amount_currency,
        amount_currency_source=amount_currency_source,
        desk=desk,
        desk_source=desk_source,
        entity=entity,
        entity_source=entity_source,
    )


def _base_column_map(fields: _RawCrifRowFields) -> list[tuple[str, str]]:
    column_map: list[tuple[str, str]] = []
    _append_column_map(column_map, fields.source_row_source, "source_row_id")
    _append_column_map(column_map, fields.sensitivity_id_source, "sensitivity_id")
    _append_column_map(column_map, fields.risk_type_source, "risk_class")
    _append_column_map(column_map, fields.risk_type_source, "risk_measure")
    _append_column_map(column_map, fields.amount_currency_source, "amount_currency")
    _append_column_map(column_map, fields.desk_source, "desk_id")
    _append_column_map(column_map, fields.entity_source, "legal_entity")
    return column_map
