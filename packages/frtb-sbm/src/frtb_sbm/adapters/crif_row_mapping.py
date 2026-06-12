"""Row-level CRIF mapping into canonical SBM sensitivities."""

from __future__ import annotations

from collections.abc import Mapping

from frtb_sbm.adapters.crif_canonical import (
    _append_inference_warnings,
    _canonical_bucket,
    _canonical_option_tenor,
    _canonical_qualifier,
    _canonical_risk_factor,
    _canonical_tenor,
)
from frtb_sbm.adapters.crif_constants import _AMOUNT_FIELDS, _DOWN_SHOCK_FIELDS, _UP_SHOCK_FIELDS
from frtb_sbm.adapters.crif_fields import _append_column_map, _first_float_with_source
from frtb_sbm.adapters.crif_models import SbmAdapterWarning
from frtb_sbm.adapters.crif_row_fields import (
    _base_column_map,
    _CanonicalCrifAxes,
    _CrifAmounts,
    _extract_row_fields,
    _RawCrifRowFields,
)
from frtb_sbm.data_models import SbmRiskMeasure, SbmSensitivity, SbmSignConvention, SbmSourceLineage


def _map_crif_row(
    record: Mapping[str, object],
    *,
    source_file: str,
    desk_id: str,
    legal_entity: str,
    sign_convention: SbmSignConvention,
    fallback_row_id: str,
) -> tuple[tuple[SbmSensitivity, ...], list[SbmAdapterWarning]]:
    fields = _extract_row_fields(
        record,
        desk_id=desk_id,
        legal_entity=legal_entity,
        fallback_row_id=fallback_row_id,
    )
    column_map = _base_column_map(fields)
    axes = _canonical_axes(fields)
    warnings = _inference_warnings(fields, axes)
    _append_axis_columns(column_map, axes)
    amounts = _amounts(record, fields.risk_measure, column_map)
    sensitivity = _build_sensitivity(
        fields,
        axes,
        amounts,
        source_file=source_file,
        sign_convention=sign_convention,
        column_map=column_map,
    )
    return (sensitivity,), warnings


def _canonical_axes(fields: _RawCrifRowFields) -> _CanonicalCrifAxes:
    risk_factor, risk_factor_source = _canonical_risk_factor(
        fields.risk_class,
        fields.risk_measure,
        risk_factor_hint=fields.risk_factor_hint,
        risk_factor_hint_source=fields.risk_factor_hint_source,
        crif_qualifier=fields.crif_qualifier,
        crif_qualifier_source=fields.crif_qualifier_source,
        bucket_hint=fields.bucket_hint,
        bucket_hint_source=fields.bucket_hint_source,
        amount_currency=fields.amount_currency,
        amount_currency_source=fields.amount_currency_source,
        label2=fields.label2,
        label2_source=fields.label2_source,
    )
    bucket, bucket_source = _canonical_bucket(
        fields.risk_class,
        bucket_hint=fields.bucket_hint,
        bucket_hint_source=fields.bucket_hint_source,
        risk_factor=risk_factor,
        risk_factor_source=risk_factor_source,
    )
    qualifier, qualifier_source = _canonical_qualifier(
        fields.risk_class,
        fields.risk_measure,
        risk_factor_hint=fields.risk_factor_hint,
        crif_qualifier=fields.crif_qualifier,
        crif_qualifier_source=fields.crif_qualifier_source,
        location=fields.location,
        location_source=fields.location_source,
    )
    tenor, tenor_source = _canonical_tenor(
        fields.risk_class,
        fields.risk_measure,
        label1=fields.label1,
        label1_source=fields.label1_source,
        label2=fields.label2,
        label2_source=fields.label2_source,
        underlying_tenor_hint=fields.underlying_tenor_hint,
        underlying_tenor_hint_source=fields.underlying_tenor_hint_source,
    )
    option_tenor, option_tenor_source = _canonical_option_tenor(
        fields.risk_measure,
        label1=fields.label1,
        label1_source=fields.label1_source,
        option_tenor_hint=fields.option_tenor_hint,
        option_tenor_hint_source=fields.option_tenor_hint_source,
    )
    return _CanonicalCrifAxes(
        bucket=bucket,
        bucket_source=bucket_source,
        risk_factor=risk_factor,
        risk_factor_source=risk_factor_source,
        qualifier=qualifier,
        qualifier_source=qualifier_source,
        tenor=tenor,
        tenor_source=tenor_source,
        option_tenor=option_tenor,
        option_tenor_source=option_tenor_source,
    )


def _inference_warnings(
    fields: _RawCrifRowFields,
    axes: _CanonicalCrifAxes,
) -> list[SbmAdapterWarning]:
    warnings: list[SbmAdapterWarning] = []
    _append_inference_warnings(
        warnings,
        source_row_id=fields.source_row_id,
        risk_class=fields.risk_class,
        bucket_hint=fields.bucket_hint,
        risk_factor_hint=fields.risk_factor_hint,
        risk_factor_source=axes.risk_factor_source,
        label2_source=fields.label2_source,
    )
    return warnings


def _append_axis_columns(
    column_map: list[tuple[str, str]],
    axes: _CanonicalCrifAxes,
) -> None:
    _append_column_map(column_map, axes.bucket_source, "bucket")
    _append_column_map(column_map, axes.risk_factor_source, "risk_factor")
    _append_column_map(column_map, axes.qualifier_source, "qualifier")
    _append_column_map(column_map, axes.tenor_source, "tenor")
    _append_column_map(column_map, axes.option_tenor_source, "option_tenor")


def _amounts(
    record: Mapping[str, object],
    risk_measure: SbmRiskMeasure,
    column_map: list[tuple[str, str]],
) -> _CrifAmounts:
    if risk_measure is SbmRiskMeasure.CURVATURE:
        up_shock_amount, up_shock_source = _first_float_with_source(record, _UP_SHOCK_FIELDS)
        down_shock_amount, down_shock_source = _first_float_with_source(record, _DOWN_SHOCK_FIELDS)
        _append_column_map(column_map, up_shock_source, "up_shock_amount")
        _append_column_map(column_map, down_shock_source, "down_shock_amount")
        return _CrifAmounts(0.0, up_shock_amount, down_shock_amount)
    amount, amount_source = _first_float_with_source(record, _AMOUNT_FIELDS)
    _append_column_map(column_map, amount_source, "amount")
    return _CrifAmounts(amount, None, None)


def _build_sensitivity(
    fields: _RawCrifRowFields,
    axes: _CanonicalCrifAxes,
    amounts: _CrifAmounts,
    *,
    source_file: str,
    sign_convention: SbmSignConvention,
    column_map: list[tuple[str, str]],
) -> SbmSensitivity:
    return SbmSensitivity(
        sensitivity_id=fields.sensitivity_id,
        source_row_id=fields.source_row_id,
        desk_id=fields.desk,
        legal_entity=fields.entity,
        risk_class=fields.risk_class,
        risk_measure=fields.risk_measure,
        bucket=axes.bucket,
        risk_factor=axes.risk_factor,
        amount=amounts.amount,
        amount_currency=fields.amount_currency,
        sign_convention=sign_convention,
        lineage=SbmSourceLineage(
            source_system="crif",
            source_file=source_file,
            source_row_id=fields.source_row_id,
            source_column_map=tuple(column_map),
        ),
        qualifier=axes.qualifier,
        tenor=axes.tenor,
        option_tenor=axes.option_tenor,
        up_shock_amount=amounts.up_shock_amount,
        down_shock_amount=amounts.down_shock_amount,
    )
