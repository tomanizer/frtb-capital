"""Canonical DRC position construction for CRIF/vendor source rows."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from enum import StrEnum

from frtb_common import stable_json_hash

from frtb_drc._crif_models import DrcCrifDirectionStrategy
from frtb_drc._crif_row import _NormalizedRow, _RejectedRowError
from frtb_drc._crif_values import (
    _CREDIT_QUALITY_ALIASES,
    _FIELD_ALIASES,
    _INSTRUMENT_ALIASES,
    _SENIORITY_ALIASES,
    _citation_ids,
    _enum_value,
    _is_blank,
    _json_scalar,
    _normal_key,
    _optional_bool,
    _optional_bucket,
    _optional_float,
    _optional_text,
    _required_float,
    _required_text,
)
from frtb_drc.data_models import (
    CreditQuality,
    DefaultDirection,
    DrcInstrumentType,
    DrcPosition,
    DrcRiskClass,
    DrcSeniority,
    DrcSourceLineage,
)
from frtb_drc.validation import DrcInputError


def _accepted_position_from_row(
    row: _NormalizedRow,
    *,
    source_system: str,
    source_file: str,
    direction_strategy: DrcCrifDirectionStrategy,
    seen_position_ids: set[str],
) -> DrcPosition:
    position = _position_from_row(
        row,
        source_system=source_system,
        source_file=source_file,
        direction_strategy=direction_strategy,
    )
    if position.position_id in seen_position_ids:
        raise _RejectedRowError(
            "drc_crif.duplicate_position_id",
            f"duplicate position_id {position.position_id!r}",
            ("position_id",),
        )
    seen_position_ids.add(position.position_id)
    return position


def _source_hash(
    rows: Sequence[Mapping[str, object]],
    strategy: DrcCrifDirectionStrategy,
    *,
    source_system: str,
    source_file: str,
) -> str:
    return stable_json_hash(
        {
            "direction_strategy": strategy.value,
            "rows": [
                {key: _json_scalar(value) for key, value in sorted(row.items())} for row in rows
            ],
            "source_file": source_file,
            "source_system": source_system,
        }
    )


def _position_from_row(
    row: _NormalizedRow,
    *,
    source_system: str,
    source_file: str,
    direction_strategy: DrcCrifDirectionStrategy,
) -> DrcPosition:
    source_row_id = _required_text(row, "source_row_id")
    position_id = _required_text(row, "position_id")
    risk_class = _risk_class(row.value("risk_class"))
    default_direction, notional, market_value = _direction_and_amounts(row, direction_strategy)
    instrument_type = _enum_value(
        row,
        "instrument_type",
        DrcInstrumentType,
        _INSTRUMENT_ALIASES,
        required=True,
    )
    assert instrument_type is not None
    issuer_id = _optional_text(row, "issuer_id")
    tranche_id = _optional_text(row, "tranche_id")
    index_series_id = _optional_text(row, "index_series_id")
    bucket_key = _optional_bucket(row)
    citation_ids = _citation_ids(row.value("citation_ids"))
    seniority = _enum_value(row, "seniority", DrcSeniority, _SENIORITY_ALIASES, required=False)
    credit_quality = _enum_value(
        row,
        "credit_quality",
        CreditQuality,
        _CREDIT_QUALITY_ALIASES,
        required=False,
    )

    _require_class_identity(
        risk_class,
        issuer_id=issuer_id,
        tranche_id=tranche_id,
        index_series_id=index_series_id,
        bucket_key=bucket_key,
        seniority=seniority,
        credit_quality=credit_quality,
    )
    if not citation_ids:
        raise _RejectedRowError(
            "drc_crif.missing_citation_ids",
            "citation_ids are required for canonical DRC rows",
            ("citation_ids",),
        )

    try:
        return DrcPosition(
            position_id=position_id,
            source_row_id=source_row_id,
            desk_id=_required_text(row, "desk_id"),
            legal_entity=_required_text(row, "legal_entity"),
            risk_class=risk_class,
            instrument_type=instrument_type,
            default_direction=default_direction,
            issuer_id=issuer_id,
            tranche_id=tranche_id,
            index_series_id=index_series_id,
            bucket_key=bucket_key,
            seniority=seniority,
            credit_quality=credit_quality,
            notional=notional,
            market_value=market_value,
            cumulative_pnl=_optional_float(row, "cumulative_pnl"),
            maturity_years=_required_float(row, "maturity_years"),
            currency=_required_text(row, "currency").upper(),
            lgd_override=_optional_float(row, "lgd_override"),
            is_defaulted=_optional_bool(row, "is_defaulted"),
            is_gse=_optional_bool(row, "is_gse"),
            is_pse=_optional_bool(row, "is_pse"),
            is_covered_bond=_optional_bool(row, "is_covered_bond"),
            lineage=DrcSourceLineage(
                source_system=source_system,
                source_file=source_file,
                source_row_id=source_row_id,
                source_column_map=row.source_column_map(),
            ),
            citation_ids=citation_ids,
        )
    except ValueError as exc:
        raise _RejectedRowError(
            "drc_crif.invalid_canonical_value",
            str(exc),
            tuple(_FIELD_ALIASES),
        ) from exc


def _direction_and_amounts(
    row: _NormalizedRow,
    strategy: DrcCrifDirectionStrategy,
) -> tuple[DefaultDirection, float, float | None]:
    notional = _required_float(row, "notional")
    market_value = _optional_float(row, "market_value")
    market_value_magnitude = None if market_value is None else abs(market_value)
    if strategy == DrcCrifDirectionStrategy.EXPLICIT_FIELD:
        return _direction(row.value("default_direction")), abs(notional), market_value_magnitude
    if strategy == DrcCrifDirectionStrategy.SIGNED_NOTIONAL:
        return (
            _direction_from_signed_value(notional, "notional"),
            abs(notional),
            market_value_magnitude,
        )
    if strategy == DrcCrifDirectionStrategy.SIGNED_MARKET_VALUE:
        if market_value is None:
            raise _RejectedRowError(
                "drc_crif.missing_direction_amount",
                "market_value is required for SIGNED_MARKET_VALUE direction mapping",
                ("market_value",),
            )
        return (
            _direction_from_signed_value(market_value, "market_value"),
            abs(notional),
            market_value_magnitude,
        )
    raise AssertionError(f"unhandled direction strategy: {strategy}")


def _direction(value: object | None) -> DefaultDirection:
    text = _normal_key(value)
    if text in _LONG_VALUES:
        return DefaultDirection.LONG
    if text in _SHORT_VALUES:
        return DefaultDirection.SHORT
    raise _RejectedRowError(
        "drc_crif.ambiguous_direction",
        "default direction must map explicitly to LONG or SHORT",
        ("default_direction",),
    )


def _direction_from_signed_value(value: float, field_name: str) -> DefaultDirection:
    if value > 0:
        return DefaultDirection.LONG
    if value < 0:
        return DefaultDirection.SHORT
    raise _RejectedRowError(
        "drc_crif.ambiguous_direction",
        f"{field_name} sign is zero and cannot determine LONG or SHORT",
        (field_name,),
    )


def _risk_class(value: object | None) -> DrcRiskClass:
    key = _normal_key(value)
    try:
        return _RISK_CLASS_ALIASES[key]
    except KeyError as exc:
        raise _RejectedRowError(
            "drc_crif.unsupported_risk_class",
            f"unsupported DRC risk class {value!r}",
            ("risk_class",),
        ) from exc


def _require_class_identity(
    risk_class: DrcRiskClass,
    *,
    issuer_id: str | None,
    tranche_id: str | None,
    index_series_id: str | None,
    bucket_key: str | None,
    seniority: StrEnum | None,
    credit_quality: StrEnum | None,
) -> None:
    if _is_blank(bucket_key):
        raise _RejectedRowError(
            "drc_crif.missing_required_field",
            "bucket_key is required for DRC adapter rows",
            ("bucket_key",),
        )
    if risk_class == DrcRiskClass.NON_SECURITISATION:
        missing = [
            field_name
            for field_name, value in (
                ("issuer_id", issuer_id),
                ("seniority", seniority),
                ("credit_quality", credit_quality),
            )
            if value is None or _is_blank(value)
        ]
        if missing:
            raise _RejectedRowError(
                "drc_crif.missing_required_field",
                "non-securitisation rows require issuer_id, seniority, and credit_quality",
                tuple(missing),
            )
    elif risk_class == DrcRiskClass.SECURITISATION_NON_CTP:
        if _is_blank(tranche_id):
            raise _RejectedRowError(
                "drc_crif.missing_required_field",
                "securitisation non-CTP rows require tranche_id",
                ("tranche_id",),
            )
    elif risk_class == DrcRiskClass.CORRELATION_TRADING_PORTFOLIO and all(
        _is_blank(value) for value in (tranche_id, index_series_id, issuer_id)
    ):
        raise _RejectedRowError(
            "drc_crif.missing_required_field",
            "CTP rows require tranche_id, index_series_id, or issuer_id",
            ("tranche_id", "index_series_id", "issuer_id"),
        )


def _coerce_direction_strategy(
    value: DrcCrifDirectionStrategy | str,
) -> DrcCrifDirectionStrategy:
    if isinstance(value, DrcCrifDirectionStrategy):
        return value
    try:
        return DrcCrifDirectionStrategy(str(value).strip().upper())
    except ValueError as exc:
        allowed = ", ".join(item.value for item in DrcCrifDirectionStrategy)
        raise DrcInputError(f"direction_strategy must be one of: {allowed}") from exc


def _require_non_empty(value: str, field_name: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise DrcInputError(f"{field_name} must be a non-empty string")


_RISK_CLASS_ALIASES: Mapping[str, DrcRiskClass] = {
    "NON_SECURITISATION": DrcRiskClass.NON_SECURITISATION,
    "NON_SECURITIZATION": DrcRiskClass.NON_SECURITISATION,
    "NONSEC": DrcRiskClass.NON_SECURITISATION,
    "NON_SEC": DrcRiskClass.NON_SECURITISATION,
    "DRC_NONSEC": DrcRiskClass.NON_SECURITISATION,
    "DRC_NON_SEC": DrcRiskClass.NON_SECURITISATION,
    "SECURITISATION_NON_CTP": DrcRiskClass.SECURITISATION_NON_CTP,
    "SECURITIZATION_NON_CTP": DrcRiskClass.SECURITISATION_NON_CTP,
    "SEC_NON_CTP": DrcRiskClass.SECURITISATION_NON_CTP,
    "CTP": DrcRiskClass.CORRELATION_TRADING_PORTFOLIO,
    "CORRELATION_TRADING_PORTFOLIO": DrcRiskClass.CORRELATION_TRADING_PORTFOLIO,
}
_LONG_VALUES = {"LONG", "L", "BUY", "BOUGHT", "ASSET", "+"}
_SHORT_VALUES = {"SHORT", "S", "SELL", "SOLD", "LIABILITY", "-"}
