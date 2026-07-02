"""Shared CVA validation errors, sign conventions, and scalar helpers."""

from __future__ import annotations

import math
from enum import StrEnum
from typing import Literal

from frtb_cva.data_models import CvaSourceLineage

AmountSignConvention = Literal["positive_loss", "signed_absolute"]
EADSignConvention = Literal["non_negative", "signed_absolute"]


class EadSignConvention(StrEnum):
    """Supported exposure-at-default sign conventions for netting-set inputs."""

    NON_NEGATIVE = "non_negative"
    SIGNED_ABSOLUTE = "signed_absolute"


class AmountSignConventionEnum(StrEnum):
    """Supported sensitivity amount sign conventions for SA-CVA inputs."""

    POSITIVE_LOSS = "positive_loss"
    SIGNED_ABSOLUTE = "signed_absolute"


VALID_EAD_SIGN_CONVENTIONS: frozenset[str] = frozenset(EadSignConvention)
VALID_AMOUNT_SIGN_CONVENTIONS: frozenset[str] = frozenset(AmountSignConventionEnum)
MAX_EFFECTIVE_MATURITY_YEARS = 5.0


class CvaInputError(ValueError):
    """Raised when canonical CVA inputs fail deterministic validation."""

    def __init__(self, message: str, *, field: str = "", record_id: str = "") -> None:
        self.field = field
        self.record_id = record_id
        prefix = f"record {record_id}: " if record_id else ""
        suffix = f" [{field}]" if field else ""
        super().__init__(f"{prefix}{message}{suffix}")


def _finite_float(value: object, *, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise CvaInputError("value must be numeric", field=field)
    number = float(value)
    if not math.isfinite(number):
        raise CvaInputError("value must be finite", field=field)
    return number


def _validate_effective_maturity(value: object, *, record_id: str = "") -> float:
    maturity = _finite_float(value, field="effective_maturity")
    if maturity < 0.0:
        raise CvaInputError(
            "effective maturity must be non-negative",
            field="effective_maturity",
            record_id=record_id,
        )
    if maturity > MAX_EFFECTIVE_MATURITY_YEARS:
        raise CvaInputError(
            "effective_maturity must not exceed 5 years (MAR50.15)",
            field="effective_maturity",
            record_id=record_id,
        )
    return maturity


def normalise_ead_amount(
    value: float,
    *,
    source_sign_convention: EADSignConvention = "non_negative",
) -> float:
    """Return a finite non-negative exposure-at-default amount.

    Parameters
    ----------
    value : float
        Raw EAD amount from a netting set or adapter row.
    source_sign_convention : EADSignConvention, optional
        ``non_negative`` rejects negative values; ``signed_absolute`` takes the absolute value.

    Returns
    -------
    float
        Finite, non-negative EAD stored on canonical netting-set records.

    Raises
    ------
    CvaInputError
        If the value is non-finite or negative under ``non_negative``.
    """

    if source_sign_convention not in {"non_negative", "signed_absolute"}:
        raise CvaInputError(
            "source_sign_convention must be 'non_negative' or 'signed_absolute'",
            field="source_sign_convention",
        )
    amount = _finite_float(value, field="ead")
    if amount < 0:
        if source_sign_convention == "signed_absolute":
            return abs(amount)
        raise CvaInputError("EAD must be non-negative", field="ead")
    return amount


def normalise_sensitivity_amount(
    value: float,
    *,
    source_sign_convention: AmountSignConvention = "positive_loss",
) -> float:
    """Return a finite sensitivity amount under the positive-loss convention.

    Parameters
    ----------
    value : float
        Raw sensitivity amount from a row or adapter.
    source_sign_convention : AmountSignConvention, optional
        ``positive_loss`` requires a finite numeric value; ``signed_absolute`` allows negatives.

    Returns
    -------
    float
        Finite sensitivity amount stored on canonical SA-CVA records.

    Raises
    ------
    CvaInputError
        If the value is non-finite or the sign convention token is unknown.
    """

    if source_sign_convention not in {"positive_loss", "signed_absolute"}:
        raise CvaInputError(
            "source_sign_convention must be 'positive_loss' or 'signed_absolute'",
            field="source_sign_convention",
        )
    return _finite_float(value, field="amount")


normalise_cva_amount = normalise_sensitivity_amount


def _require_text(value: object, field: str, record_id: str = "") -> str:
    if not isinstance(value, str) or not value.strip():
        raise CvaInputError("non-empty text is required", field=field, record_id=record_id)
    return value


def _validate_optional_text(value: object, field: str, record_id: str = "") -> None:
    if value == "":
        return
    _require_text(value, field, record_id)


def _require_mixed_sensitivity_scope_evidence(value: object) -> str:
    if not isinstance(value, str) or not value.strip():
        raise CvaInputError(
            "mixed carve-out requires SA-CVA sensitivity scope evidence for the non-carved slice",
            field="sa_cva_sensitivity_scope_evidence_id",
        )
    return value


def _validate_lineage(lineage: CvaSourceLineage | None, record_id: str) -> None:
    if lineage is None:
        return
    if not isinstance(lineage, CvaSourceLineage):
        raise CvaInputError("invalid source lineage", field="lineage", record_id=record_id)
    _require_text(lineage.source_system, "lineage.source_system", record_id)
    _require_text(lineage.source_file, "lineage.source_file", record_id)
    _require_text(lineage.source_row_id, "lineage.source_row_id", record_id)
    for mapping in lineage.source_column_map:
        if not isinstance(mapping, tuple) or len(mapping) != 2:
            raise CvaInputError(
                "source column map entries must be field pairs",
                field="lineage.source_column_map",
                record_id=record_id,
            )
        source_field, canonical_field = mapping
        _require_text(source_field, "lineage.source_column_map.source", record_id)
        _require_text(canonical_field, "lineage.source_column_map.canonical", record_id)


__all__ = [
    "MAX_EFFECTIVE_MATURITY_YEARS",
    "VALID_AMOUNT_SIGN_CONVENTIONS",
    "VALID_EAD_SIGN_CONVENTIONS",
    "AmountSignConvention",
    "AmountSignConventionEnum",
    "CvaInputError",
    "EADSignConvention",
    "EadSignConvention",
    "_finite_float",
    "_require_mixed_sensitivity_scope_evidence",
    "_require_text",
    "_validate_effective_maturity",
    "_validate_lineage",
    "_validate_optional_text",
    "normalise_cva_amount",
    "normalise_ead_amount",
    "normalise_sensitivity_amount",
]
