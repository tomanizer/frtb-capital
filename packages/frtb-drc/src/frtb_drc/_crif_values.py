"""Field aliases and scalar coercion helpers for DRC CRIF ingress."""

from __future__ import annotations

import math
import re
from collections.abc import Mapping
from enum import StrEnum
from typing import TYPE_CHECKING, TypeVar

from frtb_drc.data_models import (
    CreditQuality,
    DrcInstrumentType,
    DrcSeniority,
)

if TYPE_CHECKING:
    from frtb_drc._crif_row import _NormalizedRow

EnumT = TypeVar("EnumT", bound=StrEnum)


def _enum_value(
    row: _NormalizedRow,
    field_name: str,
    enum_type: type[EnumT],
    aliases: Mapping[str, EnumT],
    *,
    required: bool,
) -> EnumT | None:
    from frtb_drc._crif_row import _RejectedRowError

    value = row.value(field_name)
    if _is_blank(value):
        if required:
            raise _RejectedRowError(
                "drc_crif.missing_required_field",
                f"{field_name} is required",
                (field_name,),
            )
        return None
    key = _normal_key(value)
    if key in aliases:
        return aliases[key]
    try:
        return enum_type(str(value).strip())
    except ValueError as exc:
        raise _RejectedRowError(
            "drc_crif.invalid_enum",
            f"{field_name} value {value!r} is not supported",
            (field_name,),
        ) from exc


def _required_text(
    row: _NormalizedRow,
    field_name: str,
    *,
    fallback: str | None = None,
) -> str:
    from frtb_drc._crif_row import _RejectedRowError

    value = _text_or_none(row.value(field_name))
    if value is not None:
        return value
    if fallback is not None:
        return fallback
    raise _RejectedRowError(
        "drc_crif.missing_required_field",
        f"{field_name} is required",
        (field_name,),
    )


def _optional_text(row: _NormalizedRow, field_name: str) -> str | None:
    return _text_or_none(row.value(field_name))


def _optional_bucket(row: _NormalizedRow) -> str | None:
    value = _text_or_none(row.value("bucket_key"))
    if value is None:
        return None
    return _normal_key(value)


def _required_float(row: _NormalizedRow, field_name: str) -> float:
    from frtb_drc._crif_row import _RejectedRowError

    value = _optional_float(row, field_name)
    if value is None:
        raise _RejectedRowError(
            "drc_crif.missing_required_field",
            f"{field_name} is required",
            (field_name,),
        )
    return value


def _optional_float(row: _NormalizedRow, field_name: str) -> float | None:
    from frtb_drc._crif_row import _RejectedRowError

    value = row.value(field_name)
    if _is_blank(value):
        return None
    try:
        result = float(str(value).strip())
    except (TypeError, ValueError) as exc:
        raise _RejectedRowError(
            "drc_crif.invalid_numeric",
            f"{field_name} must be numeric",
            (field_name,),
        ) from exc
    if not math.isfinite(result):
        raise _RejectedRowError(
            "drc_crif.invalid_numeric",
            f"{field_name} must be finite",
            (field_name,),
        )
    return result


def _optional_bool(row: _NormalizedRow, field_name: str) -> bool:
    from frtb_drc._crif_row import _RejectedRowError

    value = row.value(field_name)
    if _is_blank(value):
        return False
    key = _normal_key(value)
    if key in {"1", "TRUE", "T", "YES", "Y"}:
        return True
    if key in {"0", "FALSE", "F", "NO", "N"}:
        return False
    raise _RejectedRowError(
        "drc_crif.invalid_boolean",
        f"{field_name} must be boolean",
        (field_name,),
    )


def _citation_ids(value: object | None) -> tuple[str, ...]:
    if _is_blank(value):
        return ()
    if isinstance(value, list | tuple):
        return tuple(str(item).strip() for item in value if str(item).strip())
    return tuple(item.strip() for item in re.split(r"[,;|]", str(value)) if item.strip())


def _text_or_none(value: object | None) -> str | None:
    if _is_blank(value):
        return None
    return str(value).strip()


def _is_blank(value: object | None) -> bool:
    return value is None or str(value).strip() == ""


def _normal_key(value: object | None) -> str:
    if value is None:
        return ""
    return re.sub(r"[^A-Z0-9]+", "_", str(value).strip().upper()).strip("_")


def _field_key(value: str) -> str:
    return "".join(character.lower() for character in value if character.isalnum())


def _json_scalar(value: object) -> object:
    if value is None or isinstance(value, str | int | float | bool):
        return value
    return str(value)


_FIELD_ALIASES: Mapping[str, tuple[str, ...]] = {
    "position_id": ("position_id", "PositionID", "PositionId", "TradeID", "TradeId"),
    "source_row_id": ("source_row_id", "SourceRowId", "RowID", "RowId"),
    "desk_id": ("desk_id", "DeskId", "DeskID", "Desk"),
    "legal_entity": ("legal_entity", "LegalEntity", "LegalEntityID", "Entity"),
    "risk_class": ("risk_class", "RiskClass", "DrcRiskClass", "RiskType"),
    "instrument_type": ("instrument_type", "InstrumentType", "ProductType", "Product"),
    "default_direction": ("default_direction", "DefaultDirection", "Direction", "LongShort"),
    "issuer_id": ("issuer_id", "IssuerId", "Issuer", "ObligorId", "Qualifier"),
    "tranche_id": ("tranche_id", "TrancheId", "Tranche"),
    "index_series_id": ("index_series_id", "IndexSeriesId", "IndexSeries"),
    "bucket_key": ("bucket_key", "BucketKey", "Bucket"),
    "seniority": ("seniority", "Seniority"),
    "credit_quality": ("credit_quality", "CreditQuality", "Rating", "CQS"),
    "notional": ("notional", "Notional", "Amount", "JtdNotional"),
    "market_value": ("market_value", "MarketValue", "MarketValueAmount", "MtM", "PV"),
    "cumulative_pnl": ("cumulative_pnl", "CumulativePnL", "CumulativePnl", "PnL"),
    "maturity_years": ("maturity_years", "MaturityYears", "Maturity", "EffectiveMaturity"),
    "currency": ("currency", "Currency", "AmountCurrency"),
    "lgd_override": ("lgd_override", "LgdOverride", "LGD"),
    "is_defaulted": ("is_defaulted", "IsDefaulted", "Defaulted"),
    "is_gse": ("is_gse", "IsGse", "GSE"),
    "is_pse": ("is_pse", "IsPse", "PSE"),
    "is_covered_bond": ("is_covered_bond", "IsCoveredBond", "CoveredBond"),
    "citation_ids": ("citation_ids", "CitationIds", "Citations", "RegulatoryCitations"),
}

_INSTRUMENT_ALIASES: Mapping[str, DrcInstrumentType] = {
    item.value: item for item in DrcInstrumentType
} | {
    "CDS": DrcInstrumentType.CREDIT_DERIVATIVE,
    "SECURITIZATION_TRANCHE": DrcInstrumentType.SECURITISATION_TRANCHE,
}
_SENIORITY_ALIASES: Mapping[str, DrcSeniority] = {item.value: item for item in DrcSeniority} | {
    "SENIOR": DrcSeniority.SENIOR_DEBT,
    "SUBORDINATED": DrcSeniority.NON_SENIOR_DEBT,
    "NON_SENIOR": DrcSeniority.NON_SENIOR_DEBT,
    "COVERED": DrcSeniority.COVERED_BOND,
}
_CREDIT_QUALITY_ALIASES: Mapping[str, CreditQuality] = {
    item.value: item for item in CreditQuality
} | {
    "IG": CreditQuality.INVESTMENT_GRADE,
    "SG": CreditQuality.SPECULATIVE_GRADE,
    "SUB_SG": CreditQuality.SUB_SPECULATIVE_GRADE,
    "CCC_AND_BELOW": CreditQuality.CCC,
}
